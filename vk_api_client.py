import vk_api
from vk_api.exceptions import ApiError
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class VkApiError(Exception):
    # Специальное исключение для ошибок VK API.
    pass


class VkApiClient:
    # Клиент для работы с VK API.

    def __init__(self, vk_token: str, user_token: str, api_version: str = '5.131'):

        self.api_version = api_version

        # Для отправки сообщений используем токен сообщества
        try:
            self.vk_session = vk_api.VkApi(token=vk_token)
            self.vk = self.vk_session.get_api()
        except Exception as e:
            logger.error(f"Ошибка инициализации с токеном сообщества: {e}")
            raise VkApiError("Не удалось инициализировать клиент с токеном сообщества")

        # Для поиска используем ключ пользователя
        if user_token:
            try:
                self.user_vk = vk_api.VkApi(token=user_token)
                self.user_api = self.user_vk.get_api()
            except Exception as e:
                logger.error(f"Ошибка инициализации с токеном пользователя: {e}")
                self.user_api = None
        else:
            logger.error("USER_TOKEN не указан! Поиск пользователей работать не будет.")
            self.user_api = None

    def _handle_api_error(self, error: ApiError, method: str) -> None:

        error_code = getattr(error, 'code', None)
        error_msg = str(error)

        if error_code == 5:
            logger.error(f"Ошибка авторизации в методе {method}: {error_msg}")
            raise VkApiError("Ошибка авторизации. Проверьте токены доступа.")
        elif error_code == 6:
            logger.warning(f"Слишком много запросов в методе {method}")
            raise VkApiError("Слишком много запросов к API. Попробуйте позже.")
        elif error_code == 18:
            logger.warning(f"Пользователь удален или заблокирован")
            raise VkApiError("Пользователь удален или заблокирован.")
        elif error_code == 30:
            logger.warning(f"Профиль приватный")
            raise VkApiError("Профиль пользователя закрыт.")
        elif error_code == 113:
            logger.warning(f"Неверный идентификатор пользователя")
            raise VkApiError("Неверный идентификатор пользователя.")
        else:
            logger.error(f"Ошибка VK API в методе {method}: код {error_code}, {error_msg}")
            raise VkApiError(f"Ошибка VK API: {error_msg}")

    def get_user_info(self, user_id: int) -> Optional[Dict]:

        try:
            users = self.vk.users.get(
                user_ids=user_id,
                fields='sex,bdate,city,country,photo_max_orig,relation'
            )
            return users[0] if users else None
        except ApiError as e:
            self._handle_api_error(e, "users.get")
            return None

    def search_users(self, params: Dict) -> List[Dict]:

        if not self.user_api:
            logger.error("Не удается выполнить поиск: отсутствует USER_TOKEN")
            return []

        try:
            # Базовые параметры поиска
            search_params = {
                'count': 20,
                'fields': 'photo_id,verified,sex,city,country,relation,photo_max_orig',
                'has_photo': 1,
                'status': 6,  # активный поиск
                'sort': 0,    # сортировка по популярности
            }

            # Добавляем переданные параметры
            search_params.update(params)

            logger.info(f"Параметры поиска: {search_params}")

            # Выполняем поиск с ключом пользователя
            result = self.user_api.users.search(**search_params)

            if result and 'items' in result:
                logger.info(f"Найдено пользователей: {len(result['items'])}")
                return result['items']
            return []

        except ApiError as e:
            self._handle_api_error(e, "users.search")
            return []

    def get_user_photos(self, user_id: int, count: int = 10) -> List[Dict]:

        if not self.user_api:
            logger.error("Не удается получить фото: отсутствует USER_TOKEN")
            return []

        try:
            photos = self.user_api.photos.get(
                owner_id=user_id,
                album_id='profile',
                extended=1,  # получаем дополнительную информацию (лайки)
                count=count
            )

            if photos and 'items' in photos:
                return photos['items']
            return []

        except ApiError as e:
            self._handle_api_error(e, "photos.get")
            return []

    def get_best_photos(self, user_id: int, count: int = 3) -> List[Dict]:

        # Получаем фотографии (запрашиваем больше, чтобы было из чего выбрать)
        photos = self.get_user_photos(user_id, count * 2)

        if not photos:
            return []

        # Сортируем по количеству лайков (от большего к меньшему)
        sorted_photos = sorted(
            photos,
            key=lambda x: x.get('likes', {}).get('count', 0),
            reverse=True
        )

        # Возвращаем только топ-N фотографий
        return sorted_photos[:count]

    def has_photos(self, user_id: int) -> bool:

        photos = self.get_user_photos(user_id, 1)
        return len(photos) > 0

    def get_photo_attachment(self, photo: Dict) -> str:

        owner_id = photo['owner_id']
        photo_id = photo['id']
        return f"photo{owner_id}_{photo_id}"

    def get_user_age(self, bdate: Optional[str]) -> Optional[int]:

        if not bdate:
            return None

        try:
            parts = bdate.split('.')
            if len(parts) == 3:  # Полная дата с годом
                day, month, year = map(int, parts)
                birth_date = datetime(year, month, day)
                today = datetime.now()
                age = today.year - birth_date.year

                # Проверяем, был ли уже день рождения в этом году
                if (today.month, today.day) < (birth_date.month, birth_date.day):
                    age -= 1

                return age
            # Если год не указан, возвращаем None
            return None

        except (ValueError, IndexError):
            logger.warning(f"Не удалось распарсить дату рождения: {bdate}")
            return None

    def format_user_info(self, user: Dict, photos: List[Dict]) -> Tuple[str, List[str]]:

        first_name = user.get('first_name', '')
        last_name = user.get('last_name', '')
        user_id = user.get('id')

        message_parts = [f"👤 {first_name} {last_name}"]

        # Добавляем возраст
        bdate = user.get('bdate')
        age = self.get_user_age(bdate)
        if age:
            message_parts.append(f"📅 Возраст: {age} лет")

        # Добавляем город
        city = user.get('city', {})
        if city:
            message_parts.append(f"🏙 Город: {city.get('title', '')}")

        # Добавляем ссылку на профиль
        message_parts.append(f"🔗 Ссылка: vk.com/id{user_id}")

        # Добавляем информацию о фотографиях
        if photos:
            likes_count = photos[0].get('likes', {}).get('count', 0)
            message_parts.append(f"\n📸 Лучшие фото (лайков: {likes_count})")
        else:
            message_parts.append("\n❌ У пользователя нет фотографий")

        message = "\n".join(message_parts)
        attachments = [self.get_photo_attachment(photo) for photo in photos]

        return message, attachments

    def parse_user_params(self, user_info: Dict) -> Dict:

        params = {}

        # Пол
        sex = user_info.get('sex')
        if sex:
            # Для поиска ищем противоположный пол
            params['sex'] = 2 if sex == 1 else 1

        # Возраст
        bdate = user_info.get('bdate')
        age = self.get_user_age(bdate)
        if age:
            # Ищем людей в диапазоне возраст ± 5 лет
            params['age_from'] = max(18, age - 5)
            params['age_to'] = age + 5

        # Город
        city = user_info.get('city')
        if city:
            params['city'] = city.get('id')

        return params