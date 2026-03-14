import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import logging
from typing import Optional
import sys
import os
from dotenv import load_dotenv

load_dotenv()

from config import VK_TOKEN, GROUP_ID, USER_TOKEN, API_VERSION
from vk_api_client import VkApiClient, VkApiError
from user_manager import UserManager
from favorites_storage import FavoritesStorage
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class VkDatingBot:

    def __init__(self, token: str, group_id: str, user_token: str):
        logger.info("Инициализация бота...")

        self.token = token
        self.group_id = group_id

        try:
            # Инициализация VK сессии
            self.vk_session = vk_api.VkApi(token=token)
            self.vk = self.vk_session.get_api()

            # Проверка соединения - исправлено!
            try:
                # Пытаемся получить информацию о группе
                if group_id:
                    # Если group_id передан, используем его
                    group_info = self.vk.groups.getById(group_ids=group_id)
                    logger.info(f"Подключено к группе: {group_info}")
                else:
                    # Если group_id не передан, пробуем получить группы пользователя
                    groups = self.vk.groups.get()
                    logger.info(f"Пользователь состоит в {len(groups.get('items', []))} группах")
            except Exception as e:
                logger.warning(f"Не удалось получить информацию о группе: {e}")

            self.longpoll = VkLongPoll(self.vk_session)
            logger.info("LongPoll инициализирован")

            # Инициализация компонентов
            self.vk_client = VkApiClient(token, user_token, API_VERSION)
            self.user_manager = UserManager(self.vk_client)
            self.favorites_storage = FavoritesStorage()

            # Состояния пользователей
            self.user_states = {}

            logger.info("Бот успешно инициализирован")

        except Exception as e:
            logger.error(f"Ошибка инициализации бота: {e}")
            raise

    def send_message(
            self,
            user_id: int,
            message: str,
            keyboard: Optional[dict] = None,
            attachment: Optional[str] = None
    ) -> None:
        try:
            params = {
                'user_id': user_id,
                'random_id': get_random_id(),
                'message': message
            }

            if keyboard:
                params['keyboard'] = keyboard
            if attachment:
                params['attachment'] = attachment

            self.vk.messages.send(**params)
            logger.info(f"Сообщение отправлено пользователю {user_id}: {message[:50]}...")

        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}")

    def get_main_keyboard(self) -> dict:
        keyboard = VkKeyboard(one_time=False)
        keyboard.add_button('🔍 Начать поиск', color=VkKeyboardColor.POSITIVE)
        keyboard.add_button('⭐ Избранное', color=VkKeyboardColor.PRIMARY)
        keyboard.add_line()
        keyboard.add_button('➡️ Следующий', color=VkKeyboardColor.SECONDARY)
        keyboard.add_button('❤️ В избранное', color=VkKeyboardColor.NEGATIVE)
        keyboard.add_line()
        keyboard.add_button('❓ Помощь', color=VkKeyboardColor.PRIMARY)
        return keyboard.get_keyboard()

    def handle_start(self, user_id: int) -> None:
        welcome_message = (
            "👋 Привет! Я бот для знакомств ВКонтакте!\n\n"
            "🔍 Я помогу тебе найти интересных людей для знакомства.\n"
            "📸 Покажу лучшие фото профиля.\n"
            "⭐ Сохраняй понравившихся в избранное.\n\n"
            "Давай начнем поиск! Нажми '🔍 Начать поиск'"
        )
        self.send_message(user_id, welcome_message, keyboard=self.get_main_keyboard())

    def handle_search(self, user_id: int) -> None:
        try:
            user_info = self.vk_client.get_user_info(user_id)

            if not user_info:
                self.send_message(
                    user_id,
                    "❌ Не удалось получить информацию о вашем профиле.",
                    keyboard=self.get_main_keyboard()
                )
                return

            favorites = self.favorites_storage.get_favorites(str(user_id))
            favorite_ids = [fav['vk_user_id'] for fav in favorites]

            search_params = self.vk_client.parse_user_params(user_info)

            if self.user_manager.start_search(user_id, search_params, favorite_ids):
                self.send_message(
                    user_id,
                    "✅ Поиск начат! Нажми '➡️ Следующий' для просмотра анкет.",
                    keyboard=self.get_main_keyboard()
                )
            else:
                self.send_message(
                    user_id,
                    "❌ Не удалось начать поиск. Попробуйте позже.",
                    keyboard=self.get_main_keyboard()
                )

        except Exception as e:
            logger.error(f"Ошибка в handle_search: {e}")
            self.send_message(
                user_id,
                "❌ Произошла ошибка. Попробуйте позже.",
                keyboard=self.get_main_keyboard()
            )

    def handle_next(self, user_id: int) -> None:
        try:
            next_user = self.user_manager.get_next_user(user_id)

            if not next_user:
                self.send_message(
                    user_id,
                    "😕 Больше нет подходящих анкет. Попробуйте позже.",
                    keyboard=self.get_main_keyboard()
                )
                return

            if not self.vk_client.has_photos(next_user['id']):
                logger.info(f"У пользователя {next_user['id']} нет фото, пропускаем")
                self.handle_next(user_id)
                return

            photos = self.vk_client.get_best_photos(next_user['id'], 3)
            message, attachments = self.vk_client.format_user_info(next_user, photos)

            if self.user_manager.is_favorite(user_id, next_user['id']):
                message += "\n\n❤️ Этот пользователь уже в вашем избранном!"

            attachment_str = ','.join(attachments) if attachments else None
            self.send_message(
                user_id,
                message,
                keyboard=self.get_main_keyboard(),
                attachment=attachment_str
            )

        except Exception as e:
            logger.error(f"Ошибка в handle_next: {e}")
            self.send_message(
                user_id,
                "❌ Произошла ошибка при загрузке анкеты.",
                keyboard=self.get_main_keyboard()
            )

    def handle_add_to_favorites(self, user_id: int) -> None:
        try:
            current_user = self.user_manager.get_current_user(user_id)

            if not current_user:
                self.send_message(
                    user_id,
                    "❌ Сначала начните поиск и выберите пользователя.",
                    keyboard=self.get_main_keyboard()
                )
                return

            if self.user_manager.is_favorite(user_id, current_user['id']):
                self.send_message(
                    user_id,
                    "❌ Этот пользователь уже в избранном.",
                    keyboard=self.get_main_keyboard()
                )
                return

            photos = self.vk_client.get_best_photos(current_user['id'], 3)
            bdate = current_user.get('bdate')
            age = self.vk_client.get_user_age(bdate)
            city = current_user.get('city', {})
            city_title = city.get('title') if city else None

            success = self.favorites_storage.add_favorite(
                user_id=str(user_id),
                vk_user_id=current_user['id'],
                first_name=current_user.get('first_name', ''),
                last_name=current_user.get('last_name', ''),
                profile_url=f"https://vk.com/id{current_user['id']}",
                photos=photos,
                city=city_title,
                age=age
            )

            if success:
                self.user_manager.mark_as_favorite(user_id, current_user['id'])
                self.send_message(
                    user_id,
                    f"✅ {current_user['first_name']} {current_user['last_name']} добавлен(а) в избранное!",
                    keyboard=self.get_main_keyboard()
                )
            else:
                self.send_message(
                    user_id,
                    "❌ Не удалось добавить в избранное.",
                    keyboard=self.get_main_keyboard()
                )

        except Exception as e:
            logger.error(f"Ошибка в handle_add_to_favorites: {e}")
            self.send_message(
                user_id,
                "❌ Ошибка при добавлении в избранное.",
                keyboard=self.get_main_keyboard()
            )

    def handle_show_favorites(self, user_id: int) -> None:
        try:
            favorites = self.favorites_storage.get_favorites(str(user_id))

            if not favorites:
                self.send_message(
                    user_id,
                    "📭 У вас пока нет избранных пользователей",
                    keyboard=self.get_main_keyboard()
                )
                return

            message_parts = ["🌟 Ваши избранные пользователи:\n"]

            for i, fav in enumerate(favorites, 1):
                added_at = datetime.fromisoformat(fav['added_at'])
                added_str = added_at.strftime("%d.%m.%Y %H:%M")

                message_parts.append(f"{i}. {fav['first_name']} {fav['last_name']}")
                message_parts.append(f"   🔗 {fav['profile_url']}")

                if fav.get('age'):
                    message_parts.append(f"   📅 Возраст: {fav['age']}")
                if fav.get('city'):
                    message_parts.append(f"   🏙 Город: {fav['city']}")
                message_parts.append(f"   📸 Фото: {len(fav.get('photos', []))}")
                message_parts.append(f"   ⏰ Добавлен: {added_str}\n")

            message_parts.append("\nДля просмотра фото используйте: просмотр [номер]")
            self.send_message(user_id, "\n".join(message_parts), keyboard=self.get_main_keyboard())

        except Exception as e:
            logger.error(f"Ошибка в handle_show_favorites: {e}")
            self.send_message(
                user_id,
                "❌ Ошибка при загрузке избранного.",
                keyboard=self.get_main_keyboard()
            )

    def handle_view_favorite_photos(self, user_id: int, index: int) -> None:
        try:
            favorite = self.favorites_storage.get_favorite_by_index(str(user_id), index)

            if not favorite:
                self.send_message(
                    user_id,
                    f"❌ Пользователь с номером {index} не найден.",
                    keyboard=self.get_main_keyboard()
                )
                return

            attachments = self.favorites_storage.get_favorite_photos_attachments(str(user_id), index)
            message = f"📸 Фото {favorite['first_name']} {favorite['last_name']}\n🔗 {favorite['profile_url']}"
            attachment_str = ','.join(attachments) if attachments else None
            self.send_message(user_id, message, attachment=attachment_str)

        except Exception as e:
            logger.error(f"Ошибка в handle_view_favorite_photos: {e}")
            self.send_message(
                user_id,
                "❌ Ошибка при загрузке фото.",
                keyboard=self.get_main_keyboard()
            )

    def handle_help(self, user_id: int) -> None:
        help_message = (
            "❓ Справка по командам:\n\n"
            "🔍 Начать поиск - запуск поиска анкет\n"
            "➡️ Следующий - показать следующую анкету\n"
            "❤️ В избранное - добавить текущую анкету в избранное\n"
            "⭐ Избранное - показать список избранных\n"
            "📸 просмотр [номер] - показать фото избранного\n\n"
            "Бот автоматически подбирает анкеты на основе:\n"
            "• Вашего возраста\n"
            "• Вашего пола\n"
            "• Вашего города\n\n"
            "Удачных знакомств! 🌟"
        )
        self.send_message(user_id, help_message, keyboard=self.get_main_keyboard())

    def run(self) -> None:
        logger.info("Бот для знакомств запущен и ожидает сообщения...")

        for event in self.longpoll.listen():
            if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                logger.info(f"Получено сообщение от {event.user_id}: {event.text}")
                self.handle_event(event)


    def handle_event(self, event) -> None:
        user_id = event.user_id
        message = event.text.lower().strip()

        if message in ['/start', 'начать', 'start']:
            self.handle_start(user_id)
        elif message in ['🔍 начать поиск', 'начать поиск', 'поиск']:
            self.handle_search(user_id)
        elif message in ['➡️ следующий', 'следующий', 'дальше']:
            self.handle_next(user_id)
        elif message in ['❤️ в избранное', 'в избранное', 'избранное', 'добавить']:
            self.handle_add_to_favorites(user_id)
        elif message in ['⭐ избранное', 'мои избранные', 'список']:
            self.handle_show_favorites(user_id)
        elif message.startswith('просмотр ') or message.startswith('фото '):
            try:
                parts = message.split()
                if len(parts) == 2 and parts[1].isdigit():
                    index = int(parts[1])
                    self.handle_view_favorite_photos(user_id, index)
                else:
                    self.send_message(
                        user_id,
                        "❌ Неверный формат. Используйте: просмотр [номер]",
                        keyboard=self.get_main_keyboard()
                    )
            except Exception as e:
                logger.error(f"Ошибка парсинга команды просмотра: {e}")
        elif message in ['❓ помощь', 'помощь', 'help', 'команды']:
            self.handle_help(user_id)
        else:
            self.send_message(
                user_id,
                "🤔 Я не понимаю эту команду. Нажми '❓ Помощь' для списка команд.",
                keyboard=self.get_main_keyboard()
            )


if __name__ == "__main__":
    # Проверка переменных окружения
    logger.info(f"VK_TOKEN: {'установлен' if VK_TOKEN else 'не установлен'}")
    logger.info(f"USER_TOKEN: {'установлен' if USER_TOKEN else 'не установлен'}")
    logger.info(f"GROUP_ID: {GROUP_ID}")

    if not VK_TOKEN:
        logger.error("VK_TOKEN не указан в .env файле")
        print("Создайте файл .env с VK_TOKEN=ваш_токен_сообщества")
        exit(1)

    if not GROUP_ID:
        logger.warning("GROUP_ID не указан в .env файле")

    if not USER_TOKEN:
        logger.warning("USER_TOKEN не указан в .env файле, поиск будет работать ограниченно")

    bot = VkDatingBot(VK_TOKEN, GROUP_ID, USER_TOKEN)
    bot.run()