import logging
from typing import Dict, List, Optional, Set
from vk_api_client import VkApiClient

logger = logging.getLogger(__name__)


class UserManager:
    #Менеджер для управления поиском и хранением результатов.

    def __init__(self, vk_client: VkApiClient):

        self.vk_client = vk_client
        self.search_results: Dict[int, List[Dict]] = {}      # user_id -> список найденных
        self.current_index: Dict[int, int] = {}               # user_id -> текущий индекс
        self.viewed_users: Dict[int, Set[int]] = {}           # user_id -> просмотренные ID
        self.search_params: Dict[int, Dict] = {}              # user_id -> параметры поиска
        self.favorite_users: Dict[int, Set[int]] = {}         # user_id -> избранные ID

    def start_search(self, user_id: int, params: Optional[Dict] = None) -> bool:

        try:
            # Сохраняем параметры поиска
            self.search_params[user_id] = params or {}

            # Инициализируем структуры данных
            self.search_results[user_id] = []
            self.current_index[user_id] = -1
            self.viewed_users[user_id] = set()
            self.favorite_users[user_id] = set()

            # Выполняем первый поиск
            return self._load_more_results(user_id)

        except Exception as e:
            logger.error(f"Ошибка начала поиска: {e}")
            return False

    def _load_more_results(self, user_id: int) -> bool:

        try:
            params = self.search_params.get(user_id, {}).copy()

            # Добавляем параметры пагинации
            params['offset'] = len(self.search_results.get(user_id, []))

            # Выполняем поиск
            results = self.vk_client.search_users(params)

            if results:
                # Фильтруем уже просмотренных
                viewed = self.viewed_users.get(user_id, set())
                favorites = self.favorite_users.get(user_id, set())

                # Исключаем просмотренных и уже добавленных в избранное
                filtered_results = [
                    r for r in results
                    if r['id'] not in viewed and r['id'] not in favorites
                ]

                if user_id not in self.search_results:
                    self.search_results[user_id] = []

                self.search_results[user_id].extend(filtered_results)
                logger.info(f"Загружено {len(filtered_results)} новых результатов для {user_id}")
                return len(filtered_results) > 0

            return False

        except Exception as e:
            logger.error(f"Ошибка загрузки результатов: {e}")
            return False

    def get_next_user(self, user_id: int) -> Optional[Dict]:

        try:
            # Проверяем, есть ли результаты
            if user_id not in self.search_results:
                if not self.start_search(user_id):
                    return None

            results = self.search_results[user_id]
            current_idx = self.current_index.get(user_id, -1)

            # Если дошли до конца, загружаем еще
            if current_idx >= len(results) - 1:
                if not self._load_more_results(user_id):
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

        try:
            if user_id in self.search_results:
                idx = self.current_index.get(user_id, -1)
                if 0 <= idx < len(self.search_results[user_id]):
                    return self.search_results[user_id][idx]
            return None
        except Exception as e:
            logger.error(f"Ошибка получения текущего пользователя: {e}")
            return None

    def mark_as_favorite(self, user_id: int, vk_user_id: int) -> None:

        if user_id not in self.favorite_users:
            self.favorite_users[user_id] = set()
        self.favorite_users[user_id].add(vk_user_id)

    def is_favorite(self, user_id: int, vk_user_id: int) -> bool:

        return vk_user_id in self.favorite_users.get(user_id, set())

    def reset_search(self, user_id: int) -> None:

        # Сброс поиска для пользователя.
        keys_to_delete = [
            'search_results', 'current_index', 'viewed_users',
            'search_params', 'favorite_users'
        ]

        for key in keys_to_delete:
            attr = getattr(self, key)
            if user_id in attr:
                del attr[user_id]

        logger.info(f"Поиск для пользователя {user_id} сброшен")