"""
sheets_utils.py — Модуль для работы с Google Sheets.
Обновляет листы Data и AI_Dashboard в существующей Мастер-таблице.
Таблица создаётся пользователем один раз вручную или находится автоматически.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import gspread
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build, Resource

logger = logging.getLogger(__name__)

# Области доступа для Google API
SCOPES: List[str] = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
]
CREDS_FILE: str = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', 'credentials.json')

# Константы листов
SHEET_DATA: str = 'Data'
SHEET_AI: str = 'AI_Dashboard'

# Файл-реестр таблиц по селлерам: {seller_folder_id: spreadsheet_id}
SELLERS_CONFIG_FILE: str = 'sellers_config.json'

# Цветовые стили заголовков (RGB 0.0 - 1.0)
HEADER_COLOR: Dict[str, float] = {'red': 0.122, 'green': 0.471, 'blue': 0.706}  # синий
AI_HEADER_COLOR: Dict[str, float] = {'red': 0.18, 'green': 0.545, 'blue': 0.341}  # зелёный


def _get_clients() -> Tuple[gspread.Client, Resource]:
    """
    Возвращает аутентифицированные клиенты gspread и Drive API.

    Returns:
        Tuple[gspread.Client, Resource]: Кортеж из клиентов gspread и Drive API.
    """
    try:
        if not os.path.exists(CREDS_FILE):
            logger.error(f"Файл учетных данных не найден: {CREDS_FILE}")
            raise FileNotFoundError(f"Missing {CREDS_FILE}")
            
        creds = service_account.Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
        gc = gspread.authorize(creds)
        drive_service = build('drive', 'v3', credentials=creds)
        return gc, drive_service
    except Exception as e:
        logger.error(f"Ошибка аутентификации Google Sheets/Drive: {e}")
        raise


def load_sellers_config() -> Dict[str, Any]:
    """
    Загружает конфиг реестра таблиц из JSON файла.

    Returns:
        Dict[str, Any]: Словарь соответствия папок селлеров и таблиц.
    """
    if os.path.exists(SELLERS_CONFIG_FILE):
        try:
            with open(SELLERS_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка при чтении {SELLERS_CONFIG_FILE}: {e}")
    return {}


def save_sellers_config(config: Dict[str, Any]) -> None:
    """
    Сохраняет конфиг реестра таблиц в JSON файл.

    Args:
        config: Словарь конфигурации для сохранения.
    """
    try:
        with open(SELLERS_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка при сохранении {SELLERS_CONFIG_FILE}: {e}")


def register_seller_table(seller_folder_id: str, seller_name: str, spreadsheet_id: str) -> None:
    """
    Регистрирует ID таблицы для конкретного селлера в реестре.

    Args:
        seller_folder_id: ID папки селлера на Drive.
        seller_name: Имя селлера.
        spreadsheet_id: ID Google таблицы.
    """
    config = load_sellers_config()
    config[seller_folder_id] = {
        'name': seller_name,
        'spreadsheet_id': spreadsheet_id
    }
    save_sellers_config(config)
    logger.info(f"✅ Зарегистрирована таблица для {seller_name}: {spreadsheet_id}")


def _find_master_table(drive_service: Resource, seller_folder_id: str) -> Optional[Dict[str, str]]:
    """
    Ищет существующую Мастер-таблицу в папке селлера на Drive.

    Args:
        drive_service: Клиент Google Drive API.
        seller_folder_id: ID папки селлера.

    Returns:
        Optional[Dict[str, str]]: Метаданные найденной таблицы или None.
    """
    try:
        query = (
            f"'{seller_folder_id}' in parents "
            f"and mimeType = 'application/vnd.google-apps.spreadsheet' "
            f"and trashed = false"
        )
        results = drive_service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])
        return files[0] if files else None
    except Exception as e:
        logger.error(f"Ошибка поиска таблицы в папке {seller_folder_id}: {e}")
        return None


def _ensure_sheets(spreadsheet: gspread.Spreadsheet) -> None:
    """
    Создаёт листы Data и AI_Dashboard, если они отсутствуют в таблице.

    Args:
        spreadsheet: Объект Google таблицы.
    """
    try:
        existing = [ws.title for ws in spreadsheet.worksheets()]
        if SHEET_DATA not in existing:
            spreadsheet.add_worksheet(title=SHEET_DATA, rows=2000, cols=30)
            logger.info(f"   📄 Создан лист: {SHEET_DATA}")
        if SHEET_AI not in existing:
            spreadsheet.add_worksheet(title=SHEET_AI, rows=100, cols=5)
            logger.info(f"   📄 Создан лист: {SHEET_AI}")
    except Exception as e:
        logger.error(f"Ошибка при проверке/создании листов в таблице: {e}")


def get_or_find_master_table(seller_folder_id: str, seller_name: str) -> Optional[gspread.Spreadsheet]:
    """
    Возвращает объект Spreadsheet для данного селлера, используя разные уровни поиска.

    Args:
        seller_folder_id: ID папки селлера.
        seller_name: Имя селлера.

    Returns:
        Optional[gspread.Spreadsheet]: Объект таблицы или None, если не найдена.
    """
    try:
        gc, drive_service = _get_clients()

        # 1. Проверяем переменные окружения SELLER_N_SHEET_ID
        for i in range(1, 11):
            env_key = f'SELLER_{i}_SHEET_ID'
            sheet_id = os.environ.get(env_key, '').strip()
            if sheet_id:
                config = load_sellers_config()
                if seller_folder_id in config and config[seller_folder_id]['spreadsheet_id'] == sheet_id:
                    logger.info(f"  📗 Таблица из .env ({env_key}): {seller_name}")
                    spreadsheet = gc.open_by_key(sheet_id)
                    _ensure_sheets(spreadsheet)
                    return spreadsheet
                
                # Если папка новая, но ID в .env есть — регистрируем связь
                if seller_folder_id not in config:
                    # Важно: тут мы не знаем наверняка, какому селлеру принадлежит этот ID из .env,
                    # поэтому регистрируем по факту использования в цикле main.py
                    register_seller_table(seller_folder_id, seller_name, sheet_id)
                    logger.info(f"  📗 Таблица из .env ({env_key}) зарегистрирована: {seller_name}")
                    spreadsheet = gc.open_by_key(sheet_id)
                    _ensure_sheets(spreadsheet)
                    return spreadsheet

        # 2. Проверяем локальный конфиг
        config = load_sellers_config()
        if seller_folder_id in config:
            sheet_id = config[seller_folder_id]['spreadsheet_id']
            logger.info(f"  📗 Таблица из конфига: {config[seller_folder_id]['name']}")
            spreadsheet = gc.open_by_key(sheet_id)
            _ensure_sheets(spreadsheet)
            return spreadsheet

        # 3. Ищем таблицу напрямую в папке селлера на Drive
        existing = _find_master_table(drive_service, seller_folder_id)
        if existing:
            logger.info(f"  📗 Найдена таблица на Drive: {existing['name']} (ID: {existing['id']})")
            register_seller_table(seller_folder_id, seller_name, existing['id'])
            spreadsheet = gc.open_by_key(existing['id'])
            _ensure_sheets(spreadsheet)
            return spreadsheet

        logger.warning(f"Мастер-таблица для '{seller_name}' не найдена!")
        return None
    except Exception as e:
        logger.error(f"Критическая ошибка при поиске/открытии таблицы для {seller_name}: {e}")
        return None


def _format_header(spreadsheet: gspread.Spreadsheet, sheet_name: str, num_cols: int, color: Dict[str, float]) -> None:
    """
    Применяет стилизацию к первой строке листа (заголовку).

    Args:
        spreadsheet: Объект таблицы.
        sheet_name: Имя листа.
        num_cols: Количество столбцов для форматирования.
        color: Словарь с цветом заливки.
    """
    try:
        ws = spreadsheet.worksheet(sheet_name)
        requests = [{
            'repeatCell': {
                'range': {
                    'sheetId': ws.id,
                    'startRowIndex': 0,
                    'endRowIndex': 1,
                    'startColumnIndex': 0,
                    'endColumnIndex': num_cols
                },
                'cell': {
                    'userEnteredFormat': {
                        'backgroundColor': color,
                        'textFormat': {
                            'bold': True,
                            'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}
                        },
                        'horizontalAlignment': 'CENTER'
                    }
                },
                'fields': 'userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)'
            }
        }, {
            'updateSheetProperties': {
                'properties': {
                    'sheetId': ws.id,
                    'gridProperties': {'frozenRowCount': 1}
                },
                'fields': 'gridProperties.frozenRowCount'
            }
        }]
        spreadsheet.batch_update({'requests': requests})
    except Exception as e:
        logger.error(f"Ошибка форматирования заголовка в {sheet_name}: {e}")


def write_data_sheet(spreadsheet: gspread.Spreadsheet, df: pd.DataFrame, period_label: str) -> pd.DataFrame:
    """
    Записывает данные P&L на лист Data, сохраняя историю и удаляя дубли за текущий период.

    Args:
        spreadsheet: Объект таблицы.
        df: DataFrame с новыми данными.
        period_label: Метка периода для фильтрации дублей.

    Returns:
        pd.DataFrame: Полная история данных (существующие + новые).
    """
    try:
        ws = spreadsheet.worksheet(SHEET_DATA)
        
        # Загружаем текущую историю
        existing_records = []
        try:
            existing_records = ws.get_all_records()
        except Exception:
            logger.info(f"Лист {SHEET_DATA} пуст или имеет некорректный формат.")
            
        df_existing = pd.DataFrame(existing_records)
        
        # Удаляем старые данные за этот же период (защита от дублей при перезапуске)
        if not df_existing.empty and 'Период' in df_existing.columns:
            df_existing = df_existing[df_existing['Период'] != period_label]
            
        # Подготовка новых данных
        df_out = df.copy()
        float_cols = df_out.select_dtypes(include=['float64', 'float32']).columns
        for col in float_cols:
            df_out[col] = df_out[col].round(2)
        df_out = df_out.fillna('')
        
        # Склеиваем историю с новыми данными
        if not df_existing.empty:
            final_df = pd.concat([df_existing, df_out], ignore_index=True)
        else:
            final_df = df_out
            
        final_df = final_df.fillna('')
        
        # Перезаписываем лист целиком
        ws.clear()
        rows_data = [final_df.columns.tolist()] + final_df.values.tolist()
        ws.update(range_name='A1', values=rows_data, value_input_option='USER_ENTERED')
        
        _format_header(spreadsheet, SHEET_DATA, len(final_df.columns), HEADER_COLOR)
        logger.info(f"✅ Лист 'Data' обновлен: {len(final_df)} строк (с учетом истории).")
        
        return final_df
    except Exception as e:
        logger.error(f"Ошибка при записи на лист Data: {e}")
        return df


def write_ai_dashboard(spreadsheet: gspread.Spreadsheet, seller_name: str, period: str, ai_text: str) -> None:
    """
    Обновляет лист AI_Dashboard результатами анализа нейросети.

    Args:
        spreadsheet: Объект таблицы.
        seller_name: Имя селлера.
        period: Период анализа.
        ai_text: Текст отчета от ИИ.
    """
    try:
        ws = spreadsheet.worksheet(SHEET_AI)
        ws.clear()

        header = [['🤖 AI-Анализ P&L', '', '', '', '']]
        meta = [
            ['Селлер:', seller_name, '', 'Период:', period],
            ['', '', '', '', ''],
        ]
        text_rows = [[line, '', '', '', ''] for line in ai_text.split('\n')]

        data = header + meta + text_rows
        ws.update(range_name='A1', values=data)
        _format_header(spreadsheet, SHEET_AI, 5, AI_HEADER_COLOR)

        logger.info(f"✅ Лист '{SHEET_AI}' обновлен.")
    except Exception as e:
        logger.error(f"Ошибка при записи на лист AI_Dashboard: {e}")
