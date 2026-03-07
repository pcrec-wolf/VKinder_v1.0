import random
from typing import Dict, List, Optional, Set
from datetime import datetime
import logging
from vk_api_client import VkApiClient
from config import DEFAULT_SEARCH_PARAMS

logger = logging.getLogger(__name__)


class UserManager:
    """Менеджер для управления поиском и хранением результатов"""

    def __init__(self, vk_client: VkApiClient):
        """
        Инициализация менеджера пользователей

        Args:
            vk_client: клиент VK API
        """
        self.vk_client = vk_client
        self.search_results = {}  # user_id -> список найденных пользователей
        self.current_index = {}  # user_id -> текущий индекс в результатах
        self.viewed_users = {}  # user_id -> множество просмотренных ID
        self.search_params = {}  # user_id -> параметры поиска

    def start_search(self, user_id: int, params: Optional[Dict] = None) -> bool:
        """
        Начало поиска для пользователя

        Args:
            user_id: ID пользователя
            params: параметры поиска

        Returns:
            bool: успешность начала поиска
        """
        try:
            # Сохраняем параметры поиска
            self.search_params[user_id] = params or {}

            # Инициализируем структуры данных
            self.search_results[user_id] = []
            self.current_index[user_id] = -1
            self.viewed_users[user_id] = set()

            # Выполняем первый поиск
            return self.load_more_results(user_id)

        except Exception as e:
            logger.error(f"Ошибка начала поиска: {e}")
            return False

    def load_more_results(self, user_id: int) -> bool:
        """
        Загрузка дополнительных результатов поиска

        Args:
            user_id: ID пользователя

        Returns:
            bool: успешность загрузки
        """
        try:
            params = self.search_params.get(user_id, {}).copy()

            # Добавляем параметры пагинации
            params['offset'] = len(self.search_results.get(user_id, []))

            # Выполняем поиск
            results = self.vk_client.search_users(params)

            if results:
                # Фильтруем уже просмотренных
                viewed = self.viewed_users.get(user_id, set())
                new_results = [r for r in results if r['id'] not in viewed]

                if user_id not in self.search_results:
                    self.search_results[user_id] = []

                self.search_results[user_id].extend(new_results)
                return len(new_results) > 0

            return False

        except Exception as e:
            logger.error(f"Ошибка загрузки результатов: {e}")
            return False

    def get_next_user(self, user_id: int) -> Optional[Dict]:
        """
        Получение следующего пользователя для показа

        Args:
            user_id: ID пользователя

        Returns:
            Optional[Dict]: данные следующего пользователя или None
        """
        try:
            # Проверяем, есть ли результаты
            if user_id not in self.search_results:
                if not self.start_search(user_id):
                    return None

            results = self.search_results[user_id]
            current_idx = self.current_index.get(user_id, -1)

            # Если дошли до конца, загружаем еще
            if current_idx >= len(results) - 1:
                if not self.load_more_results(user_id):
                    return None
                results = self.search_results[user_id]

            # Переходим к следующему
            next_idx = current_idx + 1
            if next_idx < len(results):
                self.current_index[user_id] = next_idx
                user_data = results[next_idx]

                # Добавляем в просмотренные
                if user_id not in self.viewed_users:
                    self.viewed_users[user_id] = set()
                self.viewed_users[user_id].add(user_data['id'])

                return user_data

            return None

        except Exception as e:
            logger.error(f"Ошибка получения следующего пользователя: {e}")
            return None

    def get_current_user(self, user_id: int) -> Optional[Dict]:
        """
        Получение текущего пользователя

        Args:
            user_id: ID пользователя

        Returns:
            Optional[Dict]: данные текущего пользователя
        """
        try:
            if user_id in self.search_results:
                idx = self.current_index.get(user_id, -1)
                if idx >= 0 and idx < len(self.search_results[user_id]):
                    return self.search_results[user_id][idx]
            return None
        except Exception as e:
            logger.error(f"Ошибка получения текущего пользователя: {e}")
            return None

    def reset_search(self, user_id: int):
        """
        Сброс поиска для пользователя

        Args:
            user_id: ID пользователя
        """
        if user_id in self.search_results:
            del self.search_results[user_id]
        if user_id in self.current_index:
            del self.current_index[user_id]
        if user_id in self.viewed_users:
            del self.viewed_users[user_id]
        if user_id in self.search_params:
            del self.search_params[user_id]