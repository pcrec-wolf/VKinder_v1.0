import vk_api
from vk_api.exceptions import ApiError
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from config import VK_TOKEN, USER_TOKEN, API_VERSION

logger = logging.getLogger(__name__)


class VkApiClient:
    """Клиент для работы с VK API"""

    def __init__(self):
        """Инициализация клиента VK API"""
        # Для отправки сообщений используем токен сообщества
        self.vk_session = vk_api.VkApi(token=VK_TOKEN)
        self.vk = self.vk_session.get_api()

        # Для поиска используем ключ пользователя
        if USER_TOKEN:
            self.user_vk = vk_api.VkApi(token=USER_TOKEN)
            self.user_api = self.user_vk.get_api()
        else:
            logger.error("USER_TOKEN не указан! Поиск пользователей работать не будет.")
            self.user_api = None

    def get_user_info(self, user_id: int) -> Optional[Dict]:
        """
        Получение информации о пользователе

        Args:
            user_id: ID пользователя ВК

        Returns:
            Dict: информация о пользователе
        """
        try:
            users = self.vk.users.get(
                user_ids=user_id,
                fields='sex,bdate,city,country,photo_max_orig,relation'
            )
            return users[0] if users else None
        except ApiError as e:
            logger.error(f"Ошибка получения информации о пользователе: {e}")
            return None

    def search_users(self, params: Dict) -> List[Dict]:
        """
        Поиск пользователей по параметрам

        Args:
            params: параметры поиска

        Returns:
            List[Dict]: список найденных пользователей
        """
        if not self.user_api:
            logger.error("Не удается выполнить поиск: отсутствует USER_TOKEN")
            return []

        try:
            # Базовые параметры поиска
            search_params = {
                'count': 20,
                'fields': 'photo_id,verified,sex,city,country,relation,photo_max_orig',
                'has_photo': 1,
                'status': 6,
                'sort': 0,
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
            logger.error(f"Ошибка поиска пользователей: {e}")
            return []

    def get_user_photos(self, user_id: int, count: int = 10) -> List[Dict]:
        """
        Получение фотографий пользователя

        Args:
            user_id: ID пользователя
            count: количество фотографий

        Returns:
            List[Dict]: список фотографий
        """
        if not self.user_api:
            logger.error("Не удается получить фото: отсутствует USER_TOKEN")
            return []

        try:
            photos = self.user_api.photos.get(
                owner_id=user_id,
                album_id='profile',
                extended=1,
                count=count
            )

            if photos and 'items' in photos:
                return photos['items']
            return []

        except ApiError as e:
            logger.error(f"Ошибка получения фотографий пользователя {user_id}: {e}")
            return []

    # ✅ ДОБАВЛЯЕМ НЕДОСТАЮЩИЙ МЕТОД
    def get_best_photos(self, user_id: int, count: int = 3) -> List[Dict]:
        """
        Получение лучших фотографий пользователя (с наибольшим количеством лайков)

        Args:
            user_id: ID пользователя
            count: количество фотографий для возврата

        Returns:
            List[Dict]: список лучших фотографий, отсортированных по лайкам
        """
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

    def get_photo_attachment(self, photo: Dict) -> str:
        """
        Формирование attachment для фотографии

        Args:
            photo: данные фотографии

        Returns:
            str: строка attachment
        """
        owner_id = photo['owner_id']
        photo_id = photo['id']
        return f"photo{owner_id}_{photo_id}"

    def get_user_age(self, bdate: Optional[str]) -> Optional[int]:
        """
        Вычисление возраста пользователя по дате рождения

        Args:
            bdate: дата рождения в формате DD.MM.YYYY

        Returns:
            Optional[int]: возраст или None
        """
        if not bdate:
            return None

        try:
            parts = bdate.split('.')
            if len(parts) == 3:
                day, month, year = map(int, parts)
                birth_date = datetime(year, month, day)
                today = datetime.now()
                age = today.year - birth_date.year

                if (today.month, today.day) < (birth_date.month, birth_date.day):
                    age -= 1

                return age
            return None
        except (ValueError, IndexError):
            return None

    def format_user_info(self, user: Dict, photos: List[Dict]) -> Tuple[str, List[str]]:
        """
        Форматирование информации о пользователе для отправки

        Args:
            user: данные пользователя
            photos: список фотографий

        Returns:
            Tuple[str, List[str]]: текст сообщения и список attachment
        """
        first_name = user.get('first_name', '')
        last_name = user.get('last_name', '')
        user_id = user.get('id')

        message = f"👤 {first_name} {last_name}\n"

        bdate = user.get('bdate')
        age = self.get_user_age(bdate)
        if age:
            message += f"📅 Возраст: {age} лет\n"

        city = user.get('city', {})
        if city:
            message += f"🏙 Город: {city.get('title', '')}\n"

        message += f"🔗 Ссылка: vk.com/id{user_id}\n"

        if photos:
            likes_count = photos[0].get('likes', {}).get('count', 0)
            message += f"\n📸 Лучшие фото (лайков: {likes_count})"

        attachments = [self.get_photo_attachment(photo) for photo in photos]

        return message, attachments

    def parse_user_params(self, user_info: Dict) -> Dict:
        """
        Парсинг параметров пользователя для поиска

        Args:
            user_info: информация о пользователе

        Returns:
            Dict: параметры для поиска
        """
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