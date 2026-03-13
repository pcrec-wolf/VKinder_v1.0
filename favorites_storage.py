import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class FavoritesStorage:

    def __init__(self, data_file: str = 'favorites.json'):

        self.data_file = data_file
        self.data = self._load_data()

    def _load_data(self) -> Dict[str, List[Dict]]:

        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError) as e:
                logger.error(f"Ошибка загрузки данных: {e}")
                return {}
        return {}

    def _save_data(self) -> None:
        # Сохранение данных в JSON файл с красивым форматированием.
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2, sort_keys=True)
        except Exception as e:
            logger.error(f"Ошибка сохранения данных: {e}")

    def _get_user_favorites(self, user_id: str) -> List[Dict]:

        if user_id not in self.data:
            self.data[user_id] = []
            self._save_data()

        return self.data[user_id]

    def add_favorite(
        self,
        user_id: str,
        vk_user_id: int,
        first_name: str,
        last_name: str,
        profile_url: str,
        photos: List[Dict],
        city: Optional[str] = None,
        age: Optional[int] = None
    ) -> bool:

        try:
            favorites = self._get_user_favorites(user_id)

            # Проверяем, нет ли уже такого пользователя
            if self.is_favorite(user_id, vk_user_id):
                logger.info(f"Пользователь {vk_user_id} уже в избранном")
                return False

            # Формируем запись для избранного
            favorite_entry = {
                'vk_user_id': vk_user_id,
                'first_name': first_name,
                'last_name': last_name,
                'profile_url': profile_url,
                'added_at': datetime.now().isoformat(),
                'city': city,
                'age': age,
                'photos': self._format_photos_for_storage(photos)
            }

            favorites.append(favorite_entry)
            self._save_data()

            logger.info(f"Пользователь {vk_user_id} добавлен в избранное для {user_id}")
            return True

        except Exception as e:
            logger.error(f"Ошибка добавления в избранное: {e}")
            return False

    def remove_favorite(self, user_id: str, vk_user_id: int) -> bool:

        try:
            favorites = self._get_user_favorites(user_id)
            initial_length = len(favorites)

            # Удаляем запись
            self.data[user_id] = [
                fav for fav in favorites
                if fav.get('vk_user_id') != vk_user_id
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

        try:
            favorites = self._get_user_favorites(user_id)
            # Сортируем по дате добавления (сначала новые)
            return sorted(
                favorites,
                key=lambda x: x.get('added_at', ''),
                reverse=True
            )
        except Exception as e:
            logger.error(f"Ошибка получения избранных: {e}")
            return []

    def is_favorite(self, user_id: str, vk_user_id: int) -> bool:

        favorites = self._get_user_favorites(user_id)
        return any(fav.get('vk_user_id') == vk_user_id for fav in favorites)

    def _format_photos_for_storage(self, photos: List[Dict]) -> List[Dict]:

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

        sizes = photo.get('sizes', [])
        if not sizes:
            return None

        # Ищем самый большой размер
        best_size = max(
            sizes,
            key=lambda x: x.get('height', 0) * x.get('width', 0)
        )
        return best_size.get('url')

    def get_favorite_by_index(self, user_id: str, index: int) -> Optional[Dict]:

        favorites = self.get_favorites(user_id)
        if 1 <= index <= len(favorites):
            return favorites[index - 1]
        return None

    def get_favorite_photos_attachments(self, user_id: str, index: int) -> List[str]:

        favorite = self.get_favorite_by_index(user_id, index)
        if not favorite:
            return []

        photos = favorite.get('photos', [])
        return [
            f"photo{photo['owner_id']}_{photo['id']}"
            for photo in photos
        ]

    def clear_favorites(self, user_id: str) -> bool:

        try:
            self.data[user_id] = []
            self._save_data()
            logger.info(f"Избранное пользователя {user_id} очищено")
            return True
        except Exception as e:
            logger.error(f"Ошибка очистки избранного: {e}")
            return False

