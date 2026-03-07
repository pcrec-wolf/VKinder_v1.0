import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class FavoritesManager:
    """
    Менеджер для работы с избранными пользователями
    Данные хранятся в favorites.json в корне проекта
    """

    def __init__(self, data_file: str = 'favorites.json'):
        """
        Инициализация менеджера избранного

        Args:
            data_file: путь к файлу с избранными пользователями
        """
        self.data_file = data_file
        self.data = self._load_data()

    def _load_data(self) -> Dict:
        """
        Загрузка данных из JSON файла

        Returns:
            Dict: загруженные данные
        """
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError) as e:
                logger.error(f"Ошибка загрузки данных: {e}")
                return {}
        return {}

    def _save_data(self):
        """Сохранение данных в JSON файл с красивым форматированием"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2, sort_keys=True)
        except Exception as e:
            logger.error(f"Ошибка сохранения данных: {e}")

    def _get_user_favorites(self, user_id: str) -> List[Dict]:
        """
        Получение списка избранных для конкретного пользователя бота

        Args:
            user_id: ID пользователя бота

        Returns:
            List[Dict]: список избранных
        """
        if user_id not in self.data:
            self.data[user_id] = []
            self._save_data()

        return self.data[user_id]

    def add_favorite(self, user_id: str, profile_data: Dict, photos: List[Dict]) -> bool:
        """
        Добавление пользователя в избранное

        Args:
            user_id: ID пользователя бота, который добавляет
            profile_data: данные профиля ВК для добавления
            photos: список фотографий профиля

        Returns:
            bool: успешность добавления
        """
        try:
            favorites = self._get_user_favorites(user_id)

            # Проверяем, нет ли уже такого пользователя
            vk_user_id = str(profile_data.get('id'))
            for fav in favorites:
                if str(fav.get('vk_user_id')) == vk_user_id:
                    return False  # Уже в избранном

            # Формируем запись для избранного
            favorite_entry = {
                'vk_user_id': profile_data.get('id'),
                'first_name': profile_data.get('first_name', ''),
                'last_name': profile_data.get('last_name', ''),
                'profile_url': f"https://vk.com/id{profile_data.get('id')}",
                'added_at': datetime.now().isoformat(),
                'city': profile_data.get('city', {}).get('title') if profile_data.get('city') else None,
                'age': self._calculate_age(profile_data.get('bdate')),
                'photos': self._format_photos_for_storage(photos)
            }

            favorites.append(favorite_entry)
            self._save_data()

            logger.info(f"Пользователь {vk_user_id} добавлен в избранное для {user_id}")
            return True

        except Exception as e:
            logger.error(f"Ошибка добавления в избранное: {e}")
            return False

    def remove_favorite(self, user_id: str, vk_user_id: str) -> bool:
        """
        Удаление пользователя из избранного

        Args:
            user_id: ID пользователя бота
            vk_user_id: ID пользователя ВК для удаления

        Returns:
            bool: успешность удаления
        """
        try:
            favorites = self._get_user_favorites(user_id)
            initial_length = len(favorites)

            # Удаляем запись
            self.data[user_id] = [
                fav for fav in favorites
                if str(fav.get('vk_user_id')) != str(vk_user_id)
            ]

            if len(self.data[user_id]) < initial_length:
                self._save_data()
                logger.info(f"Пользователь {vk_user_id} удален из избранного для {user_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Ошибка удаления из избранного: {e}")
            return False

    def get_favorites(self, user_id: str) -> List[Dict]:
        """
        Получение списка избранных пользователей

        Args:
            user_id: ID пользователя бота

        Returns:
            List[Dict]: список избранных
        """
        try:
            favorites = self._get_user_favorites(user_id)
            # Сортируем по дате добавления (сначала новые)
            return sorted(favorites, key=lambda x: x.get('added_at', ''), reverse=True)
        except Exception as e:
            logger.error(f"Ошибка получения избранных: {e}")
            return []

    def is_favorite(self, user_id: str, vk_user_id: str) -> bool:
        """
        Проверка, находится ли пользователь в избранном

        Args:
            user_id: ID пользователя бота
            vk_user_id: ID пользователя ВК для проверки

        Returns:
            bool: True если в избранном
        """
        favorites = self._get_user_favorites(user_id)
        return any(str(fav.get('vk_user_id')) == str(vk_user_id) for fav in favorites)

    def _calculate_age(self, bdate: Optional[str]) -> Optional[int]:
        """
        Вычисление возраста по дате рождения

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
                birth = datetime(year, month, day)
                today = datetime.now()
                age = today.year - birth.year
                if (today.month, today.day) < (birth.month, birth.day):
                    age -= 1
                return age
            return None
        except (ValueError, IndexError):
            return None

    def _format_photos_for_storage(self, photos: List[Dict]) -> List[Dict]:
        """
        Форматирование фотографий для хранения в JSON

        Args:
            photos: список фотографий от VK API

        Returns:
            List[Dict]: отформатированный список для хранения
        """
        formatted_photos = []
        for photo in photos[:3]:  # Храним только топ-3 фото
            formatted_photos.append({
                'id': photo.get('id'),
                'owner_id': photo.get('owner_id'),
                'likes': photo.get('likes', {}).get('count', 0),
                'url': self._get_best_photo_url(photo)
            })
        return formatted_photos

    def _get_best_photo_url(self, photo: Dict) -> Optional[str]:
        """
        Получение URL лучшего размера фотографии

        Args:
            photo: данные фотографии

        Returns:
            Optional[str]: URL фотографии
        """
        sizes = photo.get('sizes', [])
        if not sizes:
            return None

        # Ищем самый большой размер
        best_size = max(sizes, key=lambda x: x.get('height', 0) * x.get('width', 0))
        return best_size.get('url')

    def format_favorites_list(self, user_id: str) -> str:
        """
        Форматирование списка избранных для отправки

        Args:
            user_id: ID пользователя бота

        Returns:
            str: отформатированный список
        """
        favorites = self.get_favorites(user_id)

        if not favorites:
            return "📭 У вас пока нет избранных пользователей"

        message = "🌟 Ваши избранные пользователи:\n\n"

        for i, fav in enumerate(favorites, 1):
            added_at = datetime.fromisoformat(fav['added_at'])
            added_str = added_at.strftime("%d.%m.%Y %H:%M")

            message += f"{i}. {fav['first_name']} {fav['last_name']}\n"
            message += f"   🔗 {fav['profile_url']}\n"
            if fav.get('age'):
                message += f"   📅 Возраст: {fav['age']}\n"
            if fav.get('city'):
                message += f"   🏙 Город: {fav['city']}\n"
            message += f"   📸 Фото: {len(fav.get('photos', []))}\n"
            message += f"   ⏰ Добавлен: {added_str}\n\n"

        return message

    def get_favorites_attachments(self, user_id: str, index: int) -> List[str]:
        """
        Получение attachments для фотографий из избранного

        Args:
            user_id: ID пользователя бота
            index: индекс в списке избранных

        Returns:
            List[str]: список attachment строк
        """
        favorites = self.get_favorites(user_id)

        if 0 <= index < len(favorites):
            fav = favorites[index]
            photos = fav.get('photos', [])
            return [f"photo{photo['owner_id']}_{photo['id']}" for photo in photos]

        return []