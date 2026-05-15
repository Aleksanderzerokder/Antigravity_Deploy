"""
schema_loader.py — Единый источник правды о структуре папок и типах файлов.

Читает seller_schema.json и предоставляет удобные методы для:
  - Получения стандартных имён папок
  - Определения типа файла по его содержимому (колонкам)
  - Создания полной структуры папок нового селлера

Используется:
  - drive_utils.py (создание папок, загрузка файлов)
  - ads_parser.py (обнаружение рекламных колонок)
  - main.py (оркестрация)
  - dashboard API (загрузка файлов через UI)
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Путь к схеме — всегда рядом с этим файлом
_SCHEMA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'seller_schema.json')

# Кэш схемы (читаем один раз)
_schema_cache: Optional[Dict[str, Any]] = None


def load_schema() -> Dict[str, Any]:
    """
    Загружает схему из seller_schema.json (с кэшированием).

    Returns:
        Dict: Полная структура схемы.
    """
    global _schema_cache
    if _schema_cache is not None:
        return _schema_cache

    try:
        with open(_SCHEMA_FILE, 'r', encoding='utf-8') as f:
            _schema_cache = json.load(f)
        logger.debug(f"Схема v{_schema_cache.get('version', '?')} загружена из {_SCHEMA_FILE}")
        return _schema_cache
    except FileNotFoundError:
        logger.error(f"Файл схемы не найден: {_SCHEMA_FILE}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга seller_schema.json: {e}")
        raise


def get_folder_name(folder_key: str) -> str:
    """
    Возвращает имя папки по её ключу из схемы.

    Args:
        folder_key: Ключ папки (например, 'financial', 'advertising').

    Returns:
        str: Имя папки на Google Drive (например, '1. IN').
    """
    schema = load_schema()
    folder = schema['folders'].get(folder_key)
    if not folder:
        raise KeyError(f"Папка с ключом '{folder_key}' не найдена в схеме")
    return folder['name']


def get_all_folder_names() -> List[str]:
    """
    Возвращает список всех стандартных имён папок для создания у нового селлера.

    Returns:
        List[str]: Список имён папок в порядке схемы.
    """
    schema = load_schema()
    return [f['name'] for f in schema['folders'].values()]


def get_archived_folder_names() -> List[str]:
    """
    Возвращает список папок, содержимое которых нужно архивировать после обработки.

    Returns:
        List[str]: Имена папок с archived=true.
    """
    schema = load_schema()
    return [f['name'] for f in schema['folders'].values() if f.get('archived', False)]


def get_column_aliases(file_type_key: str, column_role: str) -> List[str]:
    """
    Возвращает список псевдонимов для конкретной роли колонки в файле.

    Args:
        file_type_key: Ключ типа файла (например, 'wb_ads', 'ozon_charges').
        column_role: Роль колонки (например, 'sku', 'cost', 'date').

    Returns:
        List[str]: Список возможных названий этой колонки (в нижнем регистре).
    """
    schema = load_schema()
    file_type = schema['file_types'].get(file_type_key, {})
    cols = file_type.get('detect_columns', {})
    return [alias.lower() for alias in cols.get(column_role, [])]


def find_column(df_columns: List[str], file_type_key: str, column_role: str) -> Optional[str]:
    """
    Ищет в списке колонок DataFrame ту, которая соответствует нужной роли.

    Args:
        df_columns: Список колонок из реального файла.
        file_type_key: Ключ типа файла.
        column_role: Роль искомой колонки.

    Returns:
        Optional[str]: Имя найденной колонки или None.
    """
    aliases = get_column_aliases(file_type_key, column_role)
    for col in df_columns:
        if str(col).lower().strip() in aliases:
            return col
    # Частичное совпадение как fallback
    for alias in aliases:
        for col in df_columns:
            if alias in str(col).lower():
                return col
    return None


def detect_file_type_from_columns(df_columns: List[str], folder_key: str) -> Optional[str]:
    """
    Определяет тип файла по его колонкам. Используется для файлов в папках
    без строгой привязки к имени (например, все файлы в '1. ADS').

    Args:
        df_columns: Список колонок из реального файла.
        folder_key: Ключ папки, в которой находится файл.

    Returns:
        Optional[str]: Ключ типа файла или None, если не определено.
    """
    schema = load_schema()
    folder_name = schema['folders'].get(folder_key, {}).get('name', '')
    cols_lower = [str(c).lower().strip() for c in df_columns]

    for type_key, type_def in schema['file_types'].items():
        # Только типы, принадлежащие этой папке
        if type_def.get('folder') != folder_key:
            continue

        required_any = type_def.get('detect_columns', {}).get('required_any', [])
        if any(req.lower() in ' '.join(cols_lower) for req in required_any):
            logger.debug(f"Файл определён как '{type_key}' по колонкам")
            return type_key

    return None


def get_schema_for_dashboard() -> Dict[str, Any]:
    """
    Возвращает упрощённую версию схемы для Next.js дашборда.
    Содержит только то, что нужно UI: папки, типы файлов, описания.

    Returns:
        Dict: Схема для сериализации в JSON API-ответе.
    """
    schema = load_schema()
    return {
        'version': schema.get('version'),
        'folders': {
            key: {
                'name': f['name'],
                'purpose': f['purpose']
            }
            for key, f in schema['folders'].items()
        },
        'file_types': {
            key: {
                'marketplace': t['marketplace'],
                'folder': t['folder'],
                'description': t['description']
            }
            for key, t in schema['file_types'].items()
        }
    }
