"""
drive_utils.py — Модуль для работы с Google Drive.
Обходит папки селлеров, скачивает новые файлы в память,
перемещает обработанные в архив.
"""

import io
import logging
import os
from typing import Any, Dict, List, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build, Resource
from googleapiclient.http import MediaIoBaseDownload

logger = logging.getLogger(__name__)

# Настройки Google API
SCOPES: List[str] = ['https://www.googleapis.com/auth/drive']
CREDS_FILE: str = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', 'credentials.json')
ROOT_FOLDER_ID: Optional[str] = os.environ.get('GOOGLE_DRIVE_ROOT_FOLDER_ID')

# Имена подпапок внутри каждого селлера (стандарт)
FOLDER_IN: str = '1. IN'
FOLDER_DICT: str = '2. DICTIONARIES'
FOLDER_ARCHIVE: str = '3. ARCHIVE'


def get_service() -> Resource:
    """
    Создает аутентифицированный клиент Google Drive API.

    Returns:
        Resource: Объект сервиса Google Drive.
    """
    try:
        if not os.path.exists(CREDS_FILE):
            logger.error(f"Файл учетных данных не найден: {CREDS_FILE}")
            raise FileNotFoundError(f"Missing {CREDS_FILE}")
            
        creds = service_account.Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        logger.error(f"Ошибка инициализации Google Drive Service: {e}")
        raise


def list_seller_folders(service: Optional[Resource] = None) -> List[Dict[str, str]]:
    """
    Возвращает список папок селлеров в корневой директории.

    Args:
        service: Объект сервиса Drive. Если None, создается новый.

    Returns:
        List[Dict[str, str]]: Список словарей {'id': ..., 'name': ...}.
    """
    try:
        if service is None:
            service = get_service()
        
        if not ROOT_FOLDER_ID:
            logger.warning("GOOGLE_DRIVE_ROOT_FOLDER_ID не задан в .env")
            return []

        query = f"'{ROOT_FOLDER_ID}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        return results.get('files', [])
    except Exception as e:
        logger.error(f"Ошибка при получении списка папок селлеров: {e}")
        return []


def _find_subfolder(service: Resource, parent_id: str, folder_name: str) -> Optional[str]:
    """
    Находит ID подпапки по имени внутри parent_id.

    Args:
        service: Объект сервиса Drive.
        parent_id: ID родительской папки.
        folder_name: Имя искомой папки.

    Returns:
        Optional[str]: ID папки или None, если не найдена.
    """
    try:
        query = (
            f"'{parent_id}' in parents "
            f"and mimeType = 'application/vnd.google-apps.folder' "
            f"and name = '{folder_name}' "
            f"and trashed = false"
        )
        results = service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])
        return files[0]['id'] if files else None
    except Exception as e:
        logger.error(f"Ошибка при поиске подпапки '{folder_name}': {e}")
        return None


def list_files_in_folder(service: Resource, folder_id: str, extension: str = '.xlsx') -> List[Dict[str, Any]]:
    """
    Возвращает список файлов с определенным расширением в папке.

    Args:
        service: Объект сервиса Drive.
        folder_id: ID папки.
        extension: Расширение файлов (по умолчанию .xlsx).

    Returns:
        List[Dict[str, Any]]: Список словарей метаданных файлов.
    """
    try:
        query = f"'{folder_id}' in parents and trashed = false"
        results = service.files().list(q=query, fields="files(id, name, modifiedTime)").execute()
        files = results.get('files', [])
        return [f for f in files if f['name'].lower().endswith(extension.lower())]
    except Exception as e:
        logger.error(f"Ошибка при листинге файлов в папке {folder_id}: {e}")
        return []


def download_file_to_memory(service: Resource, file_id: str) -> io.BytesIO:
    """
    Скачивает файл с Google Drive в оперативную память.

    Args:
        service: Объект сервиса Drive.
        file_id: ID файла.

    Returns:
        io.BytesIO: Буфер с содержимым файла.
    """
    try:
        request = service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        buffer.seek(0)
        return buffer
    except Exception as e:
        logger.error(f"Ошибка при скачивании файла {file_id}: {e}")
        raise


def get_or_create_subfolder(service: Resource, parent_id: str, folder_name: str) -> Optional[str]:
    """
    Находит ID подпапки или создает её, если она не существует.

    Args:
        service: Объект сервиса Drive.
        parent_id: ID родительской папки.
        folder_name: Имя папки.

    Returns:
        Optional[str]: ID существующей или созданной папки.
    """
    try:
        folder_id = _find_subfolder(service, parent_id, folder_name)
        if folder_id:
            return folder_id
            
        meta = {
            'name': folder_name, 
            'mimeType': 'application/vnd.google-apps.folder', 
            'parents': [parent_id]
        }
        folder = service.files().create(body=meta, fields='id').execute()
        return folder['id']
    except Exception as e:
        logger.error(f"Ошибка при создании/поиске папки '{folder_name}': {e}")
        return None


def move_to_archive(service: Resource, file_id: str, seller_folder_id: str, period_str: Optional[str] = None) -> bool:
    """
    Перемещает обработанный файл в папку ARCHIVE с учетом иерархии Год/Месяц.

    Args:
        service: Объект сервиса Drive.
        file_id: ID файла для перемещения.
        seller_folder_id: ID корневой папки селлера.
        period_str: Строка периода (например '2026-04-01 – 2026-04-30') для определения YYYY/MM.

    Returns:
        bool: True если успешно, иначе False.
    """
    try:
        archive_id = _find_subfolder(service, seller_folder_id, FOLDER_ARCHIVE)
        if not archive_id:
            logger.warning(f"Папка ARCHIVE не найдена для селлера {seller_folder_id}")
            return False
            
        target_folder_id = archive_id
        if period_str and '-' in period_str:
            # Пытаемся извлечь год и месяц из строки типа '2026-04-01'
            parts = period_str.split('-')
            if len(parts) >= 2:
                year, month = parts[0].strip(), parts[1].strip()
                year_id = get_or_create_subfolder(service, archive_id, year)
                if year_id:
                    target_folder_id = get_or_create_subfolder(service, year_id, month) or year_id

        # Получаем текущих родителей файла
        file_meta = service.files().get(fileId=file_id, fields='parents').execute()
        current_parents = ','.join(file_meta.get('parents', []))
        
        service.files().update(
            fileId=file_id,
            addParents=target_folder_id,
            removeParents=current_parents,
            fields='id, parents'
        ).execute()
        return True
    except Exception as e:
        logger.error(f"Ошибка при архивации файла {file_id}: {e}")
        return False


def get_seller_files(seller_folder_id: str, service: Optional[Resource] = None) -> Dict[str, Any]:
    """
    Собирает все необходимые файлы для обработки P&L конкретного селлера.

    Args:
        seller_folder_id: ID папки селлера.
        service: Объект сервиса Drive.

    Returns:
        Dict[str, Any]: Словарь с BytesIO объектами отчетов и справочников.
    """
    if service is None:
        service = get_service()

    result = {
        'wb_reports': [],
        'wb_supplier_goods': None,
        'wb_cost': None,
        'ozon_report': None,
        'ozon_cost': None,
        'wb_ads': [],           # Рекламные отчёты WB (Статистика)
        'ozon_ads': [],         # Рекламные отчёты Ozon (Продвижение)
        'new_file_ids': []
    }

    in_folder_id = _find_subfolder(service, seller_folder_id, FOLDER_IN)
    if not in_folder_id:
        in_folder_id = _find_subfolder(service, seller_folder_id, "1. INN") # Fallback для опечаток
        
    dict_folder_id = _find_subfolder(service, seller_folder_id, FOLDER_DICT)

    if not in_folder_id:
        logger.warning(f"Папка IN не найдена в {seller_folder_id}")
        return result

    # Обработка входящих отчетов
    in_files = list_files_in_folder(service, in_folder_id)
    logger.info(f"Найдено {len(in_files)} файлов в папке IN")

    for f in in_files:
        name_lower = f['name'].lower()
        try:
            buf = download_file_to_memory(service, f['id'])
            result['new_file_ids'].append(f['id'])

            if 'supplier-goods' in name_lower or 'supplier_goods' in name_lower:
                result['wb_supplier_goods'] = buf
                logger.info(f"✅ Загружен WB supplier-goods: {f['name']}")
            elif 'статистика' in name_lower and 'продвиж' not in name_lower:
                # WB реклама: файлы типа "Статистика (1).xlsx"
                result['wb_ads'].append(buf)
                logger.info(f"✅ Загружен WB рекламный отчёт: {f['name']}")
            elif 'аналитика продвиж' in name_lower or 'продвижение' in name_lower:
                # Ozon реклама: "Аналитика продвижения"
                result['ozon_ads'].append(buf)
                logger.info(f"✅ Загружен Ozon рекламный отчёт: {f['name']}")
            elif 'еженедельный' in name_lower or 'детализированный' in name_lower:
                result['wb_reports'].append(buf)
                logger.info(f"✅ Загружен WB еженедельный отчет: {f['name']}")
            elif 'начислени' in name_lower or 'ozon' in name_lower:
                result['ozon_report'] = buf
                logger.info(f"✅ Загружен Ozon отчет: {f['name']}")
        except Exception as e:
            logger.error(f"Не удалось загрузить файл {f['name']}: {e}")

    # Обработка справочников себестоимости
    if dict_folder_id:
        dict_files = list_files_in_folder(service, dict_folder_id)
        for f in dict_files:
            name_lower = f['name'].lower()
            if 'себестоимост' in name_lower or 'cost' in name_lower:
                try:
                    logger.debug(f"Обработка справочника: {f['name']}")
                    buf = download_file_to_memory(service, f['id'])
                    if 'вб' in name_lower or 'wb' in name_lower:
                        result['wb_cost'] = buf
                        logger.info(f"✅ Себестоимость WB: {f['name']}")
                    elif 'озон' in name_lower or 'ozon' in name_lower:
                        result['ozon_cost'] = buf
                        logger.info(f"✅ Себестоимость Ozon: {f['name']}")
                    else:
                        # Fallback логика
                        if not result['wb_cost']:
                            result['wb_cost'] = buf
                            logger.info(f"✅ Себестоимость WB (fallback): {f['name']}")
                        if result['ozon_report'] and not result['ozon_cost']:
                            result['ozon_cost'] = buf
                            logger.info(f"✅ Себестоимость Ozon (fallback): {f['name']}")
                except Exception as e:
                    logger.error(f"Ошибка при загрузке справочника {f['name']}: {e}")

    return result


def create_seller_folder_structure(seller_name: str, service: Optional[Resource] = None) -> Optional[str]:
    """
    Создает стандартную структуру папок для нового селлера.

    Args:
        seller_name: Имя селлера.
        service: Объект сервиса Drive.

    Returns:
        Optional[str]: ID созданной корневой папки селлера.
    """
    try:
        if service is None:
            service = get_service()

        def _create_folder(name: str, parent_id: str) -> str:
            meta = {'name': name, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [parent_id]}
            folder = service.files().create(body=meta, fields='id, name').execute()
            return folder['id']

        if not ROOT_FOLDER_ID:
            raise ValueError("ROOT_FOLDER_ID is not configured")

        seller_id = _create_folder(seller_name, ROOT_FOLDER_ID)
        logger.info(f"Создана папка селлера: {seller_name} (ID: {seller_id})")
        
        for sub in [FOLDER_IN, FOLDER_DICT, FOLDER_ARCHIVE]:
            sub_id = _create_folder(sub, seller_id)
            logger.info(f"   Подпапка: {sub} (ID: {sub_id})")

        return seller_id
    except Exception as e:
        logger.error(f"Ошибка при создании структуры папок для {seller_name}: {e}")
        return None
