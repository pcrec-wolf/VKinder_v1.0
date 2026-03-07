import os
from dotenv import load_dotenv

load_dotenv()

VK_TOKEN = os.getenv("VK_TOKEN")
USER_TOKEN = os.getenv("USER_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")
SERVICE_KEY = os.getenv("SERVICE_KEY")
API_VERSION = '5.131'

DEFAULT_SEARCH_PARAMS = {
    'count': 20,  # Количество результатов за раз
    'fields': 'photo_id,verified,sex,city,country,relation,photo_max_orig',
    'has_photo': 1,  # Только с фото
    'status': 6,  # 6 - активный поиск
}

# Настройки фотографий
MAX_PHOTOS_TO_SHOW = 3  # Количество фото для показа
PHOTO_SIZES = ['x', 'y', 'z', 'w']  # Приоритетные размеры фото