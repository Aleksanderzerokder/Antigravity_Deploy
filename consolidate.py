"""
consolidate.py — Модуль консолидации данных.
Содержит логику обработки отчетов Wildberries и Ozon, 
расчета прибыли и юнит-экономики.
"""

import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Подавление предупреждений openpyxl о стилях
import warnings
warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

# Глобальные пути к файлам (устанавливаются извне через main.py)
WB_QTY_FILE: str = ''
WB_REV_FILES: List[str] = []
OZON_FILE: str = ''
WB_COST_FILE: str = ''
OZON_COST_FILE: str = ''

# Рекламные расходы (устанавливаются через main.py после вызова ads_parser)
# Словарь: {seller_article -> ad_spend_rub}
WB_ADS_PER_SKU: Dict[str, float] = {}
OZON_ADS_PER_SKU: Dict[str, float] = {}
# Нераспределённые маркетинговые расходы (без SKU-привязки)
WB_ADS_UNALLOCATED: float = 0.0
OZON_ADS_UNALLOCATED: float = 0.0

# Константы фильтрации столбцов
_WB_REV_KEEP_KEYWORDS: List[str] = [
    'артикул продавца', 'артикул поставщика', 'дата продажи', 'тип документа',
    'обоснование', 'розничная цена', 'кол-во', 'количество', 'к перечислению',
    'услуги по доставке', 'хранение', 'удержания', 'штраф', 'название',
    'предмет', 'вайлдберриз реализовал', 'код номенклатуры'
]
_WB_QTY_KEEP_KEYWORDS: List[str] = [
    'артикул продавца', 'артикул поставщика', 'выкупили', 'возврат',
    'наименование', 'предмет', 'название'
]
_OZON_KEEP_KEYWORDS: List[str] = [
    'артикул', 'sku', 'сумма', 'группа услуг', 'тип начисления',
    'количество', 'название', 'наименование'
]

_FILE_SIZE_WARN_MB: int = 20


def auto_detect_period() -> Tuple[Optional[str], Optional[str], str]:
    """
    Пытается определить период из заголовков файлов (WB или Ozon).

    Returns:
        Tuple[Optional[str], Optional[str], str]: (дата_от, дата_до, метка_периода).
    """
    found_from, found_to = None, None

    # 1. Пробуем WB (из первой строки supplier-goods)
    if WB_QTY_FILE and os.path.exists(WB_QTY_FILE):
        try:
            df = pd.read_excel(WB_QTY_FILE, nrows=1, header=None)
            text = str(df.iloc[0, 0])
            dates = re.findall(r'(\d{2,4}-\d{2}-\d{2,4})|(\d{2}\.\d{2}\.\d{2,4})', text)
            if len(dates) >= 2:
                found_from = dates[0][0] if dates[0][0] else dates[0][1]
                found_to = dates[1][0] if dates[1][0] else dates[1][1]
        except Exception as e:
            logger.debug(f"Не удалось извлечь дату из WB: {e}")

    # 2. Пробуем Ozon (если WB не дал результата)
    if not found_from and OZON_FILE and os.path.exists(OZON_FILE):
        try:
            df = pd.read_excel(OZON_FILE, nrows=1, header=None)
            text = str(df.iloc[0, 0])
            dates = re.findall(r'(\d{2}\.\d{2}\.\d{4})', text)
            if len(dates) >= 2:
                found_from, found_to = dates[0], dates[1]
        except Exception as e:
            logger.debug(f"Не удалось извлечь дату из Ozon: {e}")
            
    if found_from and found_to:
        label = f"{found_from} – {found_to}"
        return found_from, found_to, label
    
    return None, None, "не указан"


def clean_sku(sku: Any) -> str:
    """
    Нормализует артикул: обрезка пробелов, удаление .0, перевод в верхний регистр.

    Args:
        sku: Исходное значение артикула.

    Returns:
        str: Очищенный строковый артикул.
    """
    if pd.isna(sku):
        return ''
    sku_str = str(sku).strip()
    if sku_str.endswith('.0'):
        sku_str = sku_str[:-2]
    if 'e+' in sku_str.lower():
        try:
            sku_str = str(int(float(sku_str)))
        except (ValueError, TypeError):
            pass
    return sku_str.upper()


def _filter_usecols(header_cols: List[Any], keep_keywords: List[str]) -> Optional[List[int]]:
    """
    Фильтрует индексы столбцов по ключевым словам.

    Args:
        header_cols: Список названий столбцов.
        keep_keywords: Список ключевых слов.

    Returns:
        Optional[List[int]]: Индексы подходящих столбцов или None.
    """
    keep_indices = []
    for i, col in enumerate(header_cols):
        col_lower = str(col).lower()
        if any(kw in col_lower for kw in keep_keywords):
            keep_indices.append(i)
    return keep_indices if keep_indices else None


def read_excel_with_header(file_path: str, keywords: Optional[List[str]] = None, 
                          keep_keywords: Optional[List[str]] = None) -> Tuple[pd.DataFrame, List[str]]:
    """
    Читает Excel-файл с автоматическим поиском строки заголовка.

    Args:
        file_path: Путь к файлу.
        keywords: Ключевые слова для поиска заголовка.
        keep_keywords: Ключевые слова для фильтрации столбцов.

    Returns:
        Tuple[pd.DataFrame, List[str]]: Загруженный DataFrame и список его столбцов.
    """
    if keywords is None:
        keywords = ['артикул']

    try:
        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if size_mb > _FILE_SIZE_WARN_MB:
            logger.info(f"   Большой файл: {os.path.basename(file_path)} ({size_mb:.1f} MB) — оптимизирую чтение")
    except Exception:
        pass

    try:
        for header_idx in range(5):
            df_head = pd.read_excel(file_path, header=header_idx, nrows=0)
            header_cols = df_head.columns.tolist()
            cols_lower = [str(c).lower() for c in header_cols]

            if any(any(kw in c for kw in keywords) for c in cols_lower):
                usecols = None
                if keep_keywords:
                    usecols = _filter_usecols(header_cols, keep_keywords)

                df = pd.read_excel(file_path, header=header_idx, usecols=usecols)
                return df, df.columns.tolist()

        # Fallback
        df = pd.read_excel(file_path)
        return df, df.columns.tolist()
    except Exception as e:
        logger.error(f"Ошибка при чтении Excel {file_path}: {e}")
        return pd.DataFrame(), []


def process_wb(date_from: Optional[str] = None, date_to: Optional[str] = None) -> pd.DataFrame:
    """
    Обрабатывает отчеты Wildberries: агрегирует продажи, расходы и считает прибыль.

    Args:
        date_from: Начало периода фильтрации.
        date_to: Конец периода фильтрации.

    Returns:
        pd.DataFrame: Таблица с результатами по артикулам WB.
    """
    logger.info(f"Обработка данных Wildberries..." + (f" ({date_from} – {date_to})" if date_from else ""))
    
    try:
        df_qty, qty_cols = read_excel_with_header(WB_QTY_FILE, ['артикул', 'выкупили'], keep_keywords=_WB_QTY_KEEP_KEYWORDS)
        if df_qty.empty:
            return pd.DataFrame()
            
        sku_col_qty = next((c for c in qty_cols if 'артикул продавца' in str(c).lower() or 'артикул поставщика' in str(c).lower()), None)
        bought_col = next((c for c in qty_cols if 'выкупили' in str(c).lower() and 'шт' in str(c).lower()), None)
        if not bought_col:
            bought_col = next((c for c in qty_cols if 'выкуп' in str(c).lower()), None)
        
        if not sku_col_qty or not bought_col:
            logger.error(f"Не найдены обязательные столбцы в WB QTY. Столбцы: {qty_cols}")
            return pd.DataFrame()
            
        df_qty['Seller_Art'] = df_qty[sku_col_qty].apply(clean_sku)
        df_qty['Количество'] = pd.to_numeric(df_qty[bought_col], errors='coerce').fillna(0)
        
        # Учет возвратов
        ret_col = next((c for c in qty_cols if 'возврат' in str(c).lower() and 'шт' in str(c).lower()), None)
        if ret_col:
            df_qty['Количество'] -= pd.to_numeric(df_qty[ret_col], errors='coerce').fillna(0)
            
        name_col_qty = next((c for c in qty_cols if 'наименование' in str(c).lower() or 'предмет' in str(c).lower() or 'название' in str(c).lower()), None)
        if name_col_qty:
            df_qty['Название'] = df_qty[name_col_qty].astype(str)
            df_qty_agg = df_qty.groupby('Seller_Art', as_index=False).agg({'Количество': 'sum', 'Название': 'first'})
        else:
            df_qty_agg = df_qty.groupby('Seller_Art', as_index=False)['Количество'].sum()
            df_qty_agg['Название'] = ''
        
        # Чтение детализации
        df_rev_list = []
        for f in WB_REV_FILES:
            df_temp, _ = read_excel_with_header(f, ['артикул', 'розничная цена'], keep_keywords=_WB_REV_KEEP_KEYWORDS)
            if not df_temp.empty:
                df_rev_list.append(df_temp)
            
        if not df_rev_list:
            logger.warning("Не найдены файлы детализации WB!")
            return pd.DataFrame()
        
        df_rev = pd.concat(df_rev_list, ignore_index=True)
        rev_cols = df_rev.columns.tolist()
        
        sku_col_rev = next((c for c in rev_cols if 'артикул продавца' in str(c).lower() or 'артикул поставщика' in str(c).lower()), None)
        date_col = next((c for c in rev_cols if 'дата продажи' in str(c).lower()), None)
        type_col_rev = next((c for c in rev_cols if 'тип документа' in str(c).lower() or 'обоснование' in str(c).lower()), None)
        realized_col = next((c for c in rev_cols if 'вайлдберриз реализовал товар' in str(c).lower()), None)
        price_col = next((c for c in rev_cols if 'розничная цена с учетом согласованной скидки' in str(c).lower() or 'цена розничная с учетом согласованной скидки' in str(c).lower()), None)
        qty_col_rev = next((c for c in rev_cols if 'кол-во' in str(c).lower() or 'количество' in str(c).lower()), None)
        to_transfer_col = next((c for c in rev_cols if 'к перечислению' in str(c).lower()), None)
        delivery_col = next((c for c in rev_cols if 'услуги по доставке' in str(c).lower()), None)
        storage_col = next((c for c in rev_cols if 'хранение' in str(c).lower()), None)
        deduction_col = next((c for c in rev_cols if 'удержания' in str(c).lower()), None)
        penalty_col = next((c for c in rev_cols if 'штраф' in str(c).lower()), None)

        if not sku_col_rev:
            logger.error(f"Не найден артикул в WB детализации. Столбцы: {rev_cols}")
            return pd.DataFrame()

        df_rev['Seller_Art'] = df_rev[sku_col_rev].apply(clean_sku)

        # Выручка в периоде
        df_income = df_rev.copy()
        if date_col and (date_from or date_to):
            df_income[date_col] = pd.to_datetime(df_income[date_col], errors='coerce')
            if date_from:
                df_income = df_income[df_income[date_col] >= pd.Timestamp(date_from)]
            if date_to:
                df_income = df_income[df_income[date_col] <= pd.Timestamp(date_to)]
            logger.info(f"   Строк продаж в периоде: {len(df_income)}")

        def _get_num(col_name, source_df):
            if col_name and col_name in source_df.columns:
                return pd.to_numeric(source_df[col_name].astype(str).str.replace(' ', '').str.replace(',', '.'), errors='coerce').fillna(0)
            return pd.Series(0, index=source_df.index)

        if price_col and qty_col_rev and type_col_rev:
            p_num = _get_num(price_col, df_income)
            q_num = _get_num(qty_col_rev, df_income)
            is_sale = df_income[type_col_rev].astype(str).str.contains('Продажа', case=False, na=False)
            is_return = df_income[type_col_rev].astype(str).str.contains('Возврат', case=False, na=False)
            df_income['Выручка_Сырая'] = 0.0
            df_income.loc[is_sale, 'Выручка_Сырая'] = p_num[is_sale] * q_num[is_sale]
            df_income.loc[is_return, 'Выручка_Сырая'] = -1 * p_num[is_return] * q_num[is_return]
        elif realized_col:
            df_income['Выручка_Сырая'] = _get_num(realized_col, df_income)
        else:
            df_income['Выручка_Сырая'] = 0

        # Количество из детализации
        if qty_col_rev and type_col_rev:
            q_raw = _get_num(qty_col_rev, df_income)
            df_income['Количество_Рев'] = np.where(
                df_income[type_col_rev].astype(str).str.contains('Продажа', case=False, na=False), q_raw,
                np.where(df_income[type_col_rev].astype(str).str.contains('Возврат', case=False, na=False), -1 * q_raw, 0)
            )
        else:
            df_income['Количество_Рев'] = 0

        # Расходы (на весь отчет)
        df_rev['К_перечислению'] = _get_num(to_transfer_col, df_rev)
        df_rev['Логистика'] = _get_num(delivery_col, df_rev)
        df_rev['Хранение'] = _get_num(storage_col, df_rev)
        df_rev['Прочие_удержания'] = _get_num(deduction_col, df_rev) + _get_num(penalty_col, df_rev)

        name_col_rev = next((c for c in rev_cols if 'название' in str(c).lower() or 'предмет' in str(c).lower()), None)
        mp_sku_col_rev = next((c for c in rev_cols if 'код номенклатуры' in str(c).lower()), None)
        df_rev['Название'] = df_rev[name_col_rev].astype(str) if name_col_rev else ''
        df_rev['SKU_МП'] = df_rev[mp_sku_col_rev].apply(clean_sku) if mp_sku_col_rev else ''

        df_income['К_перечислению'] = _get_num(to_transfer_col, df_income)
        df_income_agg = df_income.groupby('Seller_Art', as_index=False).agg({
            'Выручка_Сырая': 'sum',
            'Количество_Рев': 'sum',
            'К_перечислению': 'sum',
            'Название': 'first',
            'SKU_МП': 'first'
        })

        # Сверка количества
        qty_check = pd.merge(
            df_qty_agg[['Seller_Art', 'Количество']].rename(columns={'Количество': 'Qty_SG'}),
            df_income_agg[['Seller_Art', 'Количество_Рев']].rename(columns={'Количество_Рев': 'Qty_Rev'}),
            on='Seller_Art', how='inner'
        )
        qty_check = qty_check[abs(qty_check['Qty_SG'] - qty_check['Qty_Rev']) > 0]
        if not qty_check.empty:
            logger.warning(f"   Расхождение кол-ва (SG vs Rev) по {len(qty_check)} артикулам. Использую SG.")

        df_expense_agg = df_rev.groupby('Seller_Art', as_index=False).agg({
            'Логистика': 'sum', 'Хранение': 'sum', 'Прочие_удержания': 'sum'
        })

        df_rev_agg = pd.merge(df_income_agg, df_expense_agg, on='Seller_Art', how='outer').fillna(0)
        df_rev_agg['Комиссия'] = df_rev_agg['Выручка_Сырая'] - df_rev_agg['К_перечислению']
        
        wb_final = pd.merge(df_qty_agg, df_rev_agg, on='Seller_Art', how='outer').fillna(0)
        
        # Обработка себестоимости
        cost_dict = {}
        if WB_COST_FILE and os.path.exists(WB_COST_FILE):
            try:
                df_c, c_cols = read_excel_with_header(WB_COST_FILE, ['артикул'])
                sku_c = next((c for c in c_cols if 'артикул' in str(c).lower()), None)
                p_c = next((c for c in c_cols if 'себестоимость' in str(c).lower() or 'закуп' in str(c).lower()), None)
                if sku_c and p_c:
                    df_c['Seller_Art'] = df_c[sku_c].apply(clean_sku)
                    df_c['Price'] = pd.to_numeric(df_c[p_c], errors='coerce').fillna(0)
                    cost_dict = df_c.set_index('Seller_Art')['Price'].to_dict()
            except Exception as e:
                logger.error(f"Ошибка чтения себестоимости WB: {e}")

        wb_final['Себестоимость_шт'] = wb_final['Seller_Art'].map(cost_dict).fillna(0)
        wb_final['Себестоимость_Общая'] = wb_final['Количество'] * wb_final['Себестоимость_шт']

        # === Рекламные расходы WB ===
        # 1. Прямые расходы: привязаны к конкретному артикулу
        wb_final['Реклама_Прямая'] = wb_final['Seller_Art'].map(WB_ADS_PER_SKU).fillna(0)
        # 2. Нераспределённые: распределяем пропорционально выручке
        wb_final.rename(columns={'Выручка_Сырая': 'Выручка'}, inplace=True)
        total_wb_revenue = wb_final['Выручка'].sum()
        if WB_ADS_UNALLOCATED > 0 and total_wb_revenue > 0:
            wb_final['Реклама_Нераспред'] = (wb_final['Выручка'] / total_wb_revenue) * WB_ADS_UNALLOCATED
            logger.info(f"   WB: распределено нераспред. маркетинга {WB_ADS_UNALLOCATED:.2f} руб. пропорционально выручке")
        else:
            wb_final['Реклама_Нераспред'] = 0.0
        wb_final['Реклама_Итого'] = wb_final['Реклама_Прямая'] + wb_final['Реклама_Нераспред']

        wb_final['Чистая_Прибыль'] = (wb_final['К_перечислению'] - wb_final['Логистика']
                                       - wb_final['Хранение'] - wb_final['Прочие_удержания']
                                       - wb_final['Себестоимость_Общая'] - wb_final['Реклама_Итого'])

        wb_final['Маркетплейс'] = 'WB'
        wb_final['Рентабельность_%'] = np.where(wb_final['Выручка'] > 0, (wb_final['Чистая_Прибыль'] / wb_final['Выручка']) * 100, 0)
        wb_final['ROI_%'] = np.where(wb_final['Себестоимость_Общая'] > 0, (wb_final['Чистая_Прибыль'] / wb_final['Себестоимость_Общая']) * 100, 0)

        return wb_final
    except Exception as e:
        logger.error(f"Критическая ошибка process_wb: {e}")
        return pd.DataFrame()


def process_ozon() -> pd.DataFrame:
    """
    Обрабатывает отчеты Ozon (начисления).

    Returns:
        pd.DataFrame: Таблица с результатами по артикулам Ozon.
    """
    logger.info("Обработка данных Ozon...")
    try:
        df, cols = read_excel_with_header(OZON_FILE, ['артикул', 'сумма', 'группа услуг'], keep_keywords=_OZON_KEEP_KEYWORDS)
        if df.empty:
            return pd.DataFrame()
            
        sku_col = next((c for c in cols if 'артикул' in str(c).lower() and 'sku' not in str(c).lower()), None)
        mp_sku_col = next((c for c in cols if 'sku' in str(c).lower()), None)
        sum_col = next((c for c in cols if 'сумма итого' in str(c).lower() or 'итого' in str(c).lower() and 'руб' in str(c).lower()), None)
        group_col = next((c for c in cols if 'группа услуг' in str(c).lower()), None)
        type_col = next((c for c in cols if 'тип начисления' in str(c).lower()), None)
        qty_col = next((c for c in cols if 'количество' in str(c).lower()), None)
        name_col = next((c for c in cols if 'название' in str(c).lower() or 'наименование' in str(c).lower()), None)
        
        if not all([sku_col, group_col, type_col]):
            logger.error(f"Недостаточно столбцов в Ozon отчете. Столбцы: {cols}")
            return pd.DataFrame()
            
        df['Seller_Art'] = df[sku_col].apply(clean_sku)
        df['SKU_МП'] = df[mp_sku_col].apply(clean_sku) if mp_sku_col else ''
        df['Сумма'] = pd.to_numeric(df[sum_col].astype(str).str.replace(' ', '').str.replace(',', '.'), errors='coerce').fillna(0) if sum_col else 0
        df['Название'] = df[name_col].astype(str) if name_col else ''
        
        df['Выручка'] = np.where(df[group_col].astype(str).str.contains('Продажи|Возвраты', case=False, na=False, regex=True), df['Сумма'], 0)
        df['Количество'] = np.where(df[type_col].astype(str).str.contains('Выручка', case=False, na=False), pd.to_numeric(df[qty_col], errors='coerce').fillna(0), 0)
        df['Комиссия_Сырая'] = np.where(df[group_col].astype(str).str.contains('Вознаграждение', case=False, na=False), df['Сумма'], 0)
        df['Логистика_Сырая'] = np.where(df[group_col].astype(str).str.contains('доставки', case=False, na=False), df['Сумма'], 0)
        
        other_mask = ~df[group_col].astype(str).str.contains('Продажи|Возвраты|Вознаграждение|доставки', case=False, na=False, regex=True)
        df['Прочие_расходы'] = np.where(other_mask, df['Сумма'], 0)
        
        ozon_agg = df.groupby('Seller_Art', as_index=False).agg({
            'Выручка': 'sum', 'Количество': 'sum', 'Комиссия_Сырая': 'sum',
            'Логистика_Сырая': 'sum', 'Прочие_расходы': 'sum', 'Название': 'first', 'SKU_МП': 'first'
        })
        
        ozon_agg['Комиссия'] = -ozon_agg['Комиссия_Сырая']
        ozon_agg['Логистика'] = -ozon_agg['Логистика_Сырая']
        ozon_agg['Прочие_расходы'] = -ozon_agg['Прочие_расходы']
        
        # Себестоимость Ozon
        cost_dict = {}
        if OZON_COST_FILE and os.path.exists(OZON_COST_FILE):
            try:
                df_c, c_cols = read_excel_with_header(OZON_COST_FILE, ['артикул'])
                sku_c = next((c for c in c_cols if 'артикул' in str(c).lower()), None)
                p_c = next((c for c in c_cols if 'себестоимость' in str(c).lower() or 'закуп' in str(c).lower()), None)
                if sku_c and p_c:
                    df_c['Seller_Art'] = df_c[sku_c].apply(clean_sku)
                    df_c['Price'] = pd.to_numeric(df_c[p_c], errors='coerce').fillna(0)
                    cost_dict = df_c.set_index('Seller_Art')['Price'].to_dict()
            except Exception as e:
                logger.error(f"Ошибка чтения себестоимости Ozon: {e}")

        ozon_agg['Себестоимость_шт'] = ozon_agg['Seller_Art'].map(cost_dict).fillna(0)
        ozon_agg['Себестоимость_Общая'] = ozon_agg['Количество'] * ozon_agg['Себестоимость_шт']

        # === Рекламные расходы Ozon ===
        ozon_agg['Реклама_Прямая'] = ozon_agg['Seller_Art'].map(OZON_ADS_PER_SKU).fillna(0)
        total_ozon_revenue = ozon_agg['Выручка'].sum()
        if OZON_ADS_UNALLOCATED > 0 and total_ozon_revenue > 0:
            ozon_agg['Реклама_Нераспред'] = (ozon_agg['Выручка'] / total_ozon_revenue) * OZON_ADS_UNALLOCATED
            logger.info(f"   Ozon: распределено нераспред. маркетинга {OZON_ADS_UNALLOCATED:.2f} руб. пропорционально выручке")
        else:
            ozon_agg['Реклама_Нераспред'] = 0.0
        ozon_agg['Реклама_Итого'] = ozon_agg['Реклама_Прямая'] + ozon_agg['Реклама_Нераспред']

        ozon_agg['Чистая_Прибыль'] = (ozon_agg['Выручка'] - ozon_agg['Комиссия']
                                       - ozon_agg['Логистика'] - ozon_agg['Прочие_расходы']
                                       - ozon_agg['Себестоимость_Общая'] - ozon_agg['Реклама_Итого'])

        ozon_agg['Маркетплейс'] = 'Ozon'
        ozon_agg['Рентабельность_%'] = np.where(ozon_agg['Выручка'] > 0, (ozon_agg['Чистая_Прибыль'] / ozon_agg['Выручка']) * 100, 0)
        ozon_agg['ROI_%'] = np.where(ozon_agg['Себестоимость_Общая'] > 0, (ozon_agg['Чистая_Прибыль'] / ozon_agg['Себестоимость_Общая']) * 100, 0)

        return ozon_agg
    except Exception as e:
        logger.error(f"Критическая ошибка process_ozon: {e}")
        return pd.DataFrame()
