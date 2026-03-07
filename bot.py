import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import logging
from typing import Optional

from config import VK_TOKEN, GROUP_ID, API_VERSION
from vk_api_client import VkApiClient
from user_manager import UserManager
from favorites_manager import FavoritesManager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class VkDatingBot:
    """Бот для знакомств ВКонтакте"""

    def __init__(self, token: str, group_id: str):
        """
        Инициализация бота

        Args:
            token: токен доступа к сообществу
            group_id: ID группы
        """
        self.token = token
        self.group_id = group_id
        self.vk_session = vk_api.VkApi(token=token)
        self.vk = self.vk_session.get_api()
        self.longpoll = VkLongPoll(self.vk_session)

        # Инициализация компонентов
        self.vk_client = VkApiClient()
        self.user_manager = UserManager(self.vk_client)
        self.favorites_manager = FavoritesManager()

        # Состояния пользователей
        self.user_states = {}

    def send_message(self, user_id: int, message: str, keyboard: Optional[dict] = None,
                     attachment: Optional[str] = None):
        """
        Отправка сообщения пользователю

        Args:
            user_id: ID получателя
            message: текст сообщения
            keyboard: клавиатура (опционально)
            attachment: вложения (опционально)
        """
        try:
            self.vk.messages.send(
                user_id=user_id,
                random_id=get_random_id(),
                message=message,
                keyboard=keyboard,
                attachment=attachment
            )
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}")

    def get_main_keyboard(self) -> dict:
        """Создание основной клавиатуры"""
        keyboard = VkKeyboard(one_time=False)
        keyboard.add_button('🔍 Начать поиск', color=VkKeyboardColor.POSITIVE)
        keyboard.add_button('⭐ Избранное', color=VkKeyboardColor.PRIMARY)
        keyboard.add_line()
        keyboard.add_button('➡️ Следующий', color=VkKeyboardColor.SECONDARY)
        keyboard.add_button('❤️ В избранное', color=VkKeyboardColor.NEGATIVE)
        keyboard.add_line()
        keyboard.add_button('❓ Помощь', color=VkKeyboardColor.PRIMARY)

        return keyboard.get_keyboard()

    def handle_start(self, user_id: int):
        """Обработка начала работы с ботом"""
        welcome_message = (
            "👋 Привет! Я бот для знакомств ВКонтакте!\n\n"
            "🔍 Я помогу тебе найти интересных людей для знакомства.\n"
            "📸 Покажу лучшие фото профиля.\n"
            "⭐ Сохраняй понравившихся в избранное.\n\n"
            "Давай начнем поиск! Нажми '🔍 Начать поиск'"
        )

        self.send_message(
            user_id,
            welcome_message,
            keyboard=self.get_main_keyboard()
        )

    def handle_search(self, user_id: int):
        """Начало поиска пользователей"""
        try:
            # Получаем информацию о пользователе
            user_info = self.vk_client.get_user_info(user_id)

            if not user_info:
                self.send_message(
                    user_id,
                    "❌ Не удалось получить информацию о вашем профиле.",
                    keyboard=self.get_main_keyboard()
                )
                return

            # Парсим параметры для поиска
            search_params = self.vk_client.parse_user_params(user_info)

            # Запускаем поиск
            if self.user_manager.start_search(user_id, search_params):
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

    def handle_next(self, user_id: int):
        """Показ следующего пользователя"""
        try:
            # Получаем следующего пользователя
            next_user = self.user_manager.get_next_user(user_id)

            if not next_user:
                self.send_message(
                    user_id,
                    "😕 Больше нет подходящих анкет. Попробуйте позже или измените параметры поиска.",
                    keyboard=self.get_main_keyboard()
                )
                return

            # ✅ Получаем лучшие фото - здесь вызывается метод, который мы добавили
            photos = self.vk_client.get_best_photos(next_user['id'], 3)

            # Форматируем информацию
            message, attachments = self.vk_client.format_user_info(next_user, photos)

            # Проверяем, в избранном ли этот пользователь
            if self.favorites_manager.is_favorite(str(user_id), str(next_user['id'])):
                message += "\n\n❤️ Этот пользователь уже в вашем избранном!"

            # Отправляем сообщение с фото
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

    def handle_add_to_favorites(self, user_id: int):
        """Добавление текущего пользователя в избранное"""
        try:
            current_user = self.user_manager.get_current_user(user_id)

            if not current_user:
                self.send_message(
                    user_id,
                    "❌ Сначала начните поиск и выберите пользователя.",
                    keyboard=self.get_main_keyboard()
                )
                return

            # Получаем фото текущего пользователя
            photos = self.vk_client.get_best_photos(current_user['id'], 3)

            # Добавляем в избранное
            if self.favorites_manager.add_favorite(str(user_id), current_user, photos):
                self.send_message(
                    user_id,
                    f"✅ {current_user['first_name']} {current_user['last_name']} добавлен(а) в избранное!",
                    keyboard=self.get_main_keyboard()
                )
            else:
                self.send_message(
                    user_id,
                    "❌ Этот пользователь уже в избранном.",
                    keyboard=self.get_main_keyboard()
                )

        except Exception as e:
            logger.error(f"Ошибка в handle_add_to_favorites: {e}")
            self.send_message(
                user_id,
                "❌ Ошибка при добавлении в избранное.",
                keyboard=self.get_main_keyboard()
            )

    def handle_show_favorites(self, user_id: int):
        """Показ списка избранных"""
        try:
            # Получаем форматированный список
            favorites_text = self.favorites_manager.format_favorites_list(str(user_id))

            # Если есть избранные, добавляем инструкцию
            if "📭" not in favorites_text:
                favorites_text += "\nДля просмотра фото используйте команду 'просмотр [номер]'"

            self.send_message(
                user_id,
                favorites_text,
                keyboard=self.get_main_keyboard()
            )

        except Exception as e:
            logger.error(f"Ошибка в handle_show_favorites: {e}")
            self.send_message(
                user_id,
                "❌ Ошибка при загрузке избранного.",
                keyboard=self.get_main_keyboard()
            )

    def handle_view_favorite_photos(self, user_id: int, index: int):
        """Просмотр фото избранного пользователя"""
        try:
            favorites = self.favorites_manager.get_favorites(str(user_id))

            if 0 < index <= len(favorites):
                fav = favorites[index - 1]
                attachments = self.favorites_manager.get_favorites_attachments(str(user_id), index - 1)

                message = f"📸 Фото {fav['first_name']} {fav['last_name']}\n"
                message += f"🔗 {fav['profile_url']}"

                attachment_str = ','.join(attachments) if attachments else None
                self.send_message(
                    user_id,
                    message,
                    attachment=attachment_str
                )
            else:
                self.send_message(
                    user_id,
                    f"❌ Пользователь с номером {index} не найден.",
                    keyboard=self.get_main_keyboard()
                )

        except Exception as e:
            logger.error(f"Ошибка в handle_view_favorite_photos: {e}")
            self.send_message(
                user_id,
                "❌ Ошибка при загрузке фото.",
                keyboard=self.get_main_keyboard()
            )

    def handle_help(self, user_id: int):
        """Отображение справки"""
        help_message = (
            "❓ Справка по командам:\n\n"
            "🔍 Начать поиск - запуск поиска анкет\n"
            "➡️ Следующий - показать следующую анкету\n"
            "❤️ В избранное - добавить текущую анкету в избранное\n"
            "⭐ Избранное - показать список избранных\n"
            "📸 просмотр [номер] - показать фото избранного (например: 'просмотр 1')\n\n"
            "Бот автоматически подбирает анкеты на основе:\n"
            "• Вашего возраста\n"
            "• Вашего пола\n"
            "• Вашего города\n\n"
            "Удачных знакомств! 🌟"
        )

        self.send_message(
            user_id,
            help_message,
            keyboard=self.get_main_keyboard()
        )

    def run(self):
        """Запуск бота"""
        logger.info("Бот для знакомств запущен и ожидает сообщения...")

        for event in self.longpoll.listen():
            if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                self.handle_event(event)

    def handle_event(self, event):
        """Обработка входящего сообщения"""
        user_id = event.user_id
        message = event.text.lower().strip()

        # Обработка команд
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
                # Извлекаем номер из команды
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
            # Неизвестная команда
            self.send_message(
                user_id,
                "🤔 Я не понимаю эту команду. Нажми '❓ Помощь' для списка команд.",
                keyboard=self.get_main_keyboard()
            )


if __name__ == "__main__":
    if not VK_TOKEN or not GROUP_ID:
        logger.error("Не указан VK_TOKEN или GROUP_ID в файле .env")
        exit(1)

    bot = VkDatingBot(VK_TOKEN, GROUP_ID)
    bot.run()