import json
import os
from typing import Dict, List, Optional
from datetime import datetime


class DataManager:
    """Класс для управления данными пользователей в JSON файле"""

    def __init__(self, data_file: str = 'data/users_data.json'):
        """
        Инициализация менеджера данных

        Args:
            data_file: путь к файлу с данными
        """
        self.data_file = data_file
        self._ensure_data_directory()
        self.data = self._load_data()

    def _ensure_data_directory(self):
        """Создание директории для данных, если она не существует"""
        directory = os.path.dirname(self.data_file)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

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
            except (json.JSONDecodeError, FileNotFoundError):
                return {}
        return {}

    def _save_data(self):
        """Сохранение данных в JSON файл"""
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def get_user_data(self, user_id: str) -> Dict:
        """
        Получение данных пользователя

        Args:
            user_id: ID пользователя ВКонтакте

        Returns:
            Dict: данные пользователя
        """
        if user_id not in self.data:
            self.data[user_id] = {
                'tasks': [],
                'created_at': datetime.now().isoformat(),
                'last_active': datetime.now().isoformat()
            }
            self._save_data()

        return self.data[user_id]

    def add_task(self, user_id: str, task_text: str) -> Dict:
        """
        Добавление задачи для пользователя

        Args:
            user_id: ID пользователя
            task_text: текст задачи

        Returns:
            Dict: созданная задача
        """
        user_data = self.get_user_data(user_id)

        task = {
            'id': len(user_data['tasks']) + 1,
            'text': task_text,
            'created_at': datetime.now().isoformat(),
            'completed': False
        }

        user_data['tasks'].append(task)
        user_data['last_active'] = datetime.now().isoformat()
        self._save_data()

        return task

    def get_tasks(self, user_id: str) -> List[Dict]:
        """
        Получение списка задач пользователя

        Args:
            user_id: ID пользователя

        Returns:
            List[Dict]: список задач
        """
        user_data = self.get_user_data(user_id)
        return user_data['tasks']

    def delete_task(self, user_id: str, task_id: int) -> bool:
        """
        Удаление задачи пользователя

        Args:
            user_id: ID пользователя
            task_id: ID задачи

        Returns:
            bool: успешность удаления
        """
        user_data = self.get_user_data(user_id)
        initial_length = len(user_data['tasks'])

        user_data['tasks'] = [t for t in user_data['tasks'] if t['id'] != task_id]

        # Перенумеровываем задачи
        for i, task in enumerate(user_data['tasks'], 1):
            task['id'] = i

        user_data['last_active'] = datetime.now().isoformat()
        self._save_data()

        return len(user_data['tasks']) < initial_length

    def complete_task(self, user_id: str, task_id: int) -> bool:
        """
        Отметка задачи как выполненной

        Args:
            user_id: ID пользователя
            task_id: ID задачи

        Returns:
            bool: успешность операции
        """
        user_data = self.get_user_data(user_id)

        for task in user_data['tasks']:
            if task['id'] == task_id:
                task['completed'] = True
                user_data['last_active'] = datetime.now().isoformat()
                self._save_data()
                return True

        return False

    def clear_all_tasks(self, user_id: str) -> bool:
        """
        Очистка всех задач пользователя

        Args:
            user_id: ID пользователя

        Returns:
            bool: успешность операции
        """
        if user_id in self.data:
            self.data[user_id]['tasks'] = []
            self.data[user_id]['last_active'] = datetime.now().isoformat()
            self._save_data()
            return True
        return False