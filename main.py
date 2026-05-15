"""
main.py — Точка входа в систему Antigravity Analytics.
Оркестрирует полный пайплайн обработки данных:
1. Инициализация окружения и логирования.
2. Сбор файлов из Google Drive.
3. Расчет P&L и консолидация.
4. Выгрузка в Google Sheets и архивация.
"""

import logging
import os
import shutil
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from dotenv import load_dotenv

# Инициализация окружения (должна быть до импорта локальных модулей)
load_dotenv()

# Локальные модули
import consolidate as C
from ads_parser import aggregate_ad_costs
from ai_analyzer import generate_insights
from drive_utils import get_service, get_seller_files, list_seller_folders, move_to_archive
from sheets_utils import get_or_find_master_table, write_ai_dashboard, write_data_sheet

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Папки системы
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARQUET_CACHE_DIR = os.path.join(BASE_DIR, 'cache')
SCRATCH_DIR = os.path.join(BASE_DIR, 'scratch')


def initialize_environment() -> None:
    """
    Проверяет переменные окружения и создает необходимые директории.
    """
    load_dotenv()
    
    required_vars = [
        'GOOGLE_APPLICATION_CREDENTIALS',
        'GOOGLE_DRIVE_ROOT_FOLDER_ID',
        'GIGACHAT_AUTH_KEY'
    ]
    
    missing = [v for v in required_vars if not os.environ.get(v)]
    if missing:
        logger.error(f"Отсутствуют необходимые переменные в .env: {', '.join(missing)}")
        sys.exit(1)
        
    for directory in [PARQUET_CACHE_DIR, SCRATCH_DIR]:
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            logger.info(f"Создана директория: {directory}")


def get_run_dates() -> Tuple[Optional[str], Optional[str]]:
    """
    Определяет период анализа через аргументы CLI или интерактивный ввод.

    Returns:
        Tuple[Optional[str], Optional[str]]: (date_from, date_to).
    """
    logger.info("Настройка периода анализа...")
    d_from = sys.argv[1] if len(sys.argv) > 1 else None
    d_to = sys.argv[2] if len(sys.argv) > 2 else None

    if not d_from:
        # В CI/автоматическом режиме пропускаем ввод
        if os.environ.get('CI') == 'true' or not sys.stdin.isatty():
            logger.info("   Автоматический режим: ручной ввод дат пропущен.")
            return None, None

        print("\n--- Выбор периода ---")
        print("Введите даты в формате ГГГГ-ММ-ДД (например, 2026-04-01).")
        print("Или нажмите ENTER для АВТООПРЕДЕЛЕНИЯ по содержимому файлов.")
        
        raw_from = input("  Дата начала: ").strip()
        d_from = "".join(c for c in raw_from if c.isalnum() or c == '-') or None
        
        if d_from:
            raw_to = input("  Дата конца: ").strip()
            d_to = "".join(c for c in raw_to if c.isalnum() or c == '-') or None
    
    return d_from, d_to


def save_period_parquet(df: pd.DataFrame, period_label: str, seller_name: str) -> None:
    """
    Сохраняет обработанный P&L в локальный кэш Parquet.

    Args:
        df: DataFrame для сохранения.
        period_label: Метка периода.
        seller_name: Имя селлера.
    """
    try:
        df_copy = df.copy()
        # Приведение типов для стабильности pyarrow
        for col in ['Артикул', 'Название']:
            if col in df_copy.columns:
                df_copy[col] = df_copy[col].astype(str)
        
        safe_name = "".join(c if c.isalnum() or c in '-_' else '_' for c in f"{seller_name}_{period_label}")
        path = os.path.join(PARQUET_CACHE_DIR, f"{safe_name}.parquet")
        df_copy.to_parquet(path, index=False, engine='pyarrow')
        logger.info(f"💾 Кэш сохранен: cache/{os.path.basename(path)}")
    except Exception as e:
        logger.error(f"Не удалось сохранить parquet-кэш: {e}")


def run_for_seller(seller_folder_id: str, seller_name: str, service: Any, 
                   global_from: Optional[str], global_to: Optional[str], 
                   global_label: str) -> Optional[pd.DataFrame]:
    """
    Выполняет полный цикл обработки для одного селлера.

    Args:
        seller_folder_id: ID папки селлера на Drive.
        seller_name: Имя селлера.
        service: Google Drive API Resource.
        global_from: Дата начала (если задана вручную).
        global_to: Дата конца (если задана вручную).
        global_label: Метка периода по умолчанию.

    Returns:
        Optional[pd.DataFrame]: Консолидированный DataFrame или None.
    """
    logger.info(f"Начало обработки селлера: {seller_name}")

    # 1. Загрузка файлов
    files = get_seller_files(seller_folder_id, service=service)
    has_wb = bool(files['wb_reports'] or files['wb_supplier_goods'])
    has_ozon = bool(files['ozon_report'])

    if not has_wb and not has_ozon:
        logger.warning(f"Нет данных для {seller_name} в папке IN. Пропуск.")
        return None

    # 2. Подготовка временного хранилища
    tmp_dir = tempfile.mkdtemp(prefix='antigravity_')
    try:
        def save_buf(buf: Any, name: str) -> str:
            path = os.path.join(tmp_dir, name)
            with open(path, 'wb') as f:
                f.write(buf.read())
            buf.seek(0)
            return path

        # Сохранение буферов во временные файлы для pandas
        wb_qty_path = save_buf(files['wb_supplier_goods'], 'sg.xlsx') if files['wb_supplier_goods'] else ''
        wb_rev_paths = [save_buf(b, f'rev_{i}.xlsx') for i, b in enumerate(files['wb_reports'])]
        ozon_path = save_buf(files['ozon_report'], 'ozon.xlsx') if files['ozon_report'] else ''
        wb_cost_path = save_buf(files['wb_cost'], 'wb_cost.xlsx') if files['wb_cost'] else ''
        ozon_cost_path = save_buf(files['ozon_cost'], 'ozon_cost.xlsx') if files['ozon_cost'] else ''

        # Инъекция путей в модуль консолидации
        C.WB_QTY_FILE = wb_qty_path
        C.WB_REV_FILES = wb_rev_paths
        C.OZON_FILE = ozon_path
        C.WB_COST_FILE = wb_cost_path
        C.OZON_COST_FILE = ozon_cost_path

        # Обработка рекламных расходов
        has_wb_ads = bool(files.get('wb_ads'))
        has_ozon_ads = bool(files.get('ozon_ads'))
        if has_wb_ads or has_ozon_ads:
            logger.info("📊 Обработка рекламных отчётов...")
            # Для WB-маппинга номенклатуры → артикул поставщика используем WB-отчёты
            wb_sku_map: Dict[str, str] = {}
            if wb_rev_paths:
                import pandas as _pd
                try:
                    from consolidate import read_excel_with_header, clean_sku, _WB_REV_KEEP_KEYWORDS
                    for rev_path in wb_rev_paths:
                        _df, _ = read_excel_with_header(rev_path, ['артикул'], keep_keywords=_WB_REV_KEEP_KEYWORDS)
                        if not _df.empty:
                            nom_col = next((c for c in _df.columns if 'код номенклатуры' in str(c).lower()), None)
                            art_col = next((c for c in _df.columns if 'артикул поставщика' in str(c).lower() or 'артикул продавца' in str(c).lower()), None)
                            if nom_col and art_col:
                                for _, row in _df[[nom_col, art_col]].drop_duplicates().iterrows():
                                    wb_sku_map[clean_sku(row[nom_col])] = clean_sku(row[art_col])
                except Exception as _e:
                    logger.warning(f"Не удалось построить WB маппинг номенклатур: {_e}")

            ads_result = aggregate_ad_costs(
                wb_ads_bufs=files.get('wb_ads', []),
                ozon_ads_bufs=files.get('ozon_ads', []),
                wb_sku_map=wb_sku_map or None
            )
            # Разделяем WB и Ozon-расходы (в данном MVP все прямые идут в WB)
            C.WB_ADS_PER_SKU = ads_result['per_sku']
            C.WB_ADS_UNALLOCATED = ads_result['unallocated']
            C.OZON_ADS_PER_SKU = {}
            C.OZON_ADS_UNALLOCATED = 0.0
        else:
            logger.info("ℹ️  Рекламные отчёты не найдены — расходы на рекламу не учитываются.")
            C.WB_ADS_PER_SKU = {}
            C.WB_ADS_UNALLOCATED = 0.0
            C.OZON_ADS_PER_SKU = {}
            C.OZON_ADS_UNALLOCATED = 0.0

        # Определение периода
        current_from = global_from
        current_to = global_to
        current_label = global_label
        
        if not current_from:
            logger.info("🔍 Запуск автоопределения периода...")
            current_from, current_to, current_label = C.auto_detect_period()
            logger.info(f"📅 Обнаружен период: {current_label}")

        # 3. Расчет
        wb_df = C.process_wb(date_from=current_from, date_to=current_to) if has_wb and wb_qty_path else pd.DataFrame()
        ozon_df = C.process_ozon() if has_ozon else pd.DataFrame()

        # 4. Консолидация
        cols = ['Период', 'Маркетплейс', 'Название', 'Seller_Art', 'SKU_МП',
                'Количество', 'Выручка', 'Комиссия', 'Логистика', 'Хранение',
                'Прочие_расходы', 'Себестоимость_Общая',
                'Реклама_Прямая', 'Реклама_Нераспред', 'Реклама_Итого',
                'Чистая_Прибыль', 'Рентабельность_%', 'ROI_%']

        frames = []
        for df, mp_name in [(wb_df, 'WB'), (ozon_df, 'Ozon')]:
            if not df.empty:
                df['Период'] = current_label
                df['Маркетплейс'] = mp_name
                if 'Прочие_удержания' in df.columns:
                    df['Прочие_расходы'] = df['Прочие_удержания']
                for c in cols:
                    if c not in df.columns:
                        df[c] = 0
                frames.append(df[cols])

        if not frames:
            logger.warning(f"После обработки {seller_name} данных не обнаружено.")
            return None

        final_df = pd.concat(frames, ignore_index=True)
        # Фильтр пустых строк
        final_df = final_df[(final_df['Количество'] != 0) | (final_df['Выручка'] != 0)]
        final_df.rename(columns={
            'Seller_Art': 'Артикул', 'SKU_МП': 'SKU',
            'Реклама_Прямая': 'Реклама (прямая)', 'Реклама_Нераспред': 'Нераспред. маркетинг',
            'Реклама_Итого': 'Реклама (итого)'
        }, inplace=True)

        # 5. Выгрузка
        spreadsheet = get_or_find_master_table(seller_folder_id, seller_name)
        if spreadsheet:
            full_history_df = write_data_sheet(spreadsheet, final_df, current_label)
            
            # Аналитика
            logger.info("🧠 Генерация ИИ-инсайтов...")
            insights = generate_insights(full_history_df, current_label, seller_name=seller_name)
            write_ai_dashboard(spreadsheet, seller_name, current_label, insights)
            
            # 6. Архивация
            logger.info("📦 Архивация файлов...")
            for fid in files.get('new_file_ids', []):
                move_to_archive(service, fid, seller_folder_id, current_label)
            
            # 7. Кэш
            save_period_parquet(final_df, current_label, seller_name)
            logger.info(f"✅ Успешное завершение для {seller_name}")
            return final_df
            
        return None

    except Exception as e:
        logger.exception(f"Ошибка при обработке селлера {seller_name}: {e}")
        return None
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def main() -> None:
    """
    Основная функция запуска пайплайна.
    """
    initialize_environment()
    
    date_from, date_to = get_run_dates()
    period_label = f"{date_from} – {date_to}" if date_from else "Автоопределение"
    
    logger.info("🚀 Antigravity Analytics — Запуск")
    service = get_service()
    sellers = list_seller_folders(service)

    if not sellers:
        logger.error("Папки селлеров не найдены. Проверьте структуру на Google Drive.")
        return

    logger.info(f"Найдено селлеров для обработки: {len(sellers)}")
    
    for seller in sellers:
        run_for_seller(
            seller_folder_id=seller['id'],
            seller_name=seller['name'],
            service=service,
            global_from=date_from,
            global_to=date_to,
            global_label=period_label
        )

    logger.info("🏁 Все задачи завершены успешно!")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Прервано пользователем.")
    except Exception as e:
        logger.critical(f"Необработанное исключение: {e}", exc_info=True)
