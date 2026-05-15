"""
ads_parser.py — Модуль парсинга рекламных отчетов.

Поддерживает:
  - Wildberries: отчёты «Статистика» (детализация по товарам)
  - Ozon: «Аналитика продвижения» (детализация по SKU)

Возвращает:
  - per_sku_costs: Dict[str, float] — прямые рекламные расходы по каждому артикулу поставщика
  - unallocated_total: float — «Нераспределённые маркетинговые расходы» (без SKU-привязки)
  - report_meta: List[Dict] — метаданные для отображения в дашборде
"""

import io
import logging
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from consolidate import clean_sku

logger = logging.getLogger(__name__)


def _safe_num(series: pd.Series) -> pd.Series:
    """Приводит серию к числовому типу, заменяя ошибки на 0."""
    return pd.to_numeric(
        series.astype(str).str.replace(' ', '').str.replace(',', '.').str.replace('₽', ''),
        errors='coerce'
    ).fillna(0)


def parse_wb_ads(
    file_buf: io.BytesIO,
    sku_map: Optional[Dict[str, str]] = None
) -> Tuple[Dict[str, float], float]:
    """
    Парсит рекламный отчёт Wildberries «Статистика по товарам».

    Колонки: Название, Номенклатура (WB ID), Затраты, RUB, ...

    Args:
        file_buf: BytesIO буфер Excel-файла.
        sku_map: Словарь {wb_nomenclature_id -> seller_article} для маппинга WB ID -> артикул.
                 Если не передан — расходы идут в «нераспределённые».

    Returns:
        Tuple[Dict[str, float], float]:
            - per_sku_costs: {seller_article: total_ad_spend}
            - unallocated: сумма расходов, которые не удалось привязать к артикулу
    """
    try:
        df = pd.read_excel(file_buf)
        cols = df.columns.tolist()

        # Поиск ключевых колонок
        nomenclature_col = next(
            (c for c in cols if 'номенклатура' in str(c).lower()),
            None
        )
        cost_col = next(
            (c for c in cols if 'затраты' in str(c).lower()),
            None
        )

        if not cost_col:
            logger.warning(f"WB ads: не найдена колонка 'Затраты'. Доступные: {cols}")
            return {}, 0.0

        df['_cost'] = _safe_num(df[cost_col])
        total_cost = df['_cost'].sum()

        if not nomenclature_col or not sku_map:
            # Нет возможности привязать к артикулу — всё в нераспределённые
            logger.info(f"WB ads: привязка к SKU невозможна. Нераспределённые: {total_cost:.2f} руб.")
            return {}, round(total_cost, 2)

        # Маппинг WB Номенклатура -> Артикул поставщика
        df['_wb_id'] = df[nomenclature_col].apply(clean_sku)
        df['_seller_art'] = df['_wb_id'].map(sku_map)

        matched = df[df['_seller_art'].notna()]
        unmatched = df[df['_seller_art'].isna()]

        per_sku = matched.groupby('_seller_art')['_cost'].sum().to_dict()
        unallocated = unmatched['_cost'].sum()

        if unallocated > 0:
            logger.info(
                f"WB ads: привязано {len(per_sku)} артикулов. "
                f"Нераспределённые: {unallocated:.2f} руб."
            )

        return {str(k): round(float(v), 2) for k, v in per_sku.items()}, round(float(unallocated), 2)

    except Exception as e:
        logger.error(f"Ошибка парсинга WB рекламы: {e}")
        return {}, 0.0


def parse_ozon_ads(
    file_buf: io.BytesIO
) -> Tuple[Dict[str, float], float]:
    """
    Парсит рекламный отчёт Ozon «Аналитика продвижения».

    Структура: первая строка — метаданные, вторая строка — заголовки.
    Колонки: SKU, Название товара, Инструмент, Расход ₽, ...

    Args:
        file_buf: BytesIO буфер Excel-файла.

    Returns:
        Tuple[Dict[str, float], float]:
            - per_sku_costs: {seller_article: total_ad_spend}
            - unallocated: сумма расходов без SKU-привязки
    """
    try:
        # Файл Ozon имеет метаданные в первой строке, заголовки — во второй
        df = pd.read_excel(file_buf, header=1)
        cols = df.columns.tolist()

        sku_col = next(
            (c for c in cols if str(c).strip().upper() == 'SKU' or 'sku' in str(c).lower()),
            None
        )
        cost_col = next(
            (c for c in cols if 'расход' in str(c).lower()),
            None
        )

        if not cost_col:
            logger.warning(f"Ozon ads: не найдена колонка 'Расход'. Доступные: {cols}")
            return {}, 0.0

        df['_cost'] = _safe_num(df[cost_col])

        if not sku_col:
            unallocated = df['_cost'].sum()
            logger.info(f"Ozon ads: нет колонки SKU. Нераспределённые: {unallocated:.2f} руб.")
            return {}, round(float(unallocated), 2)

        df['_sku'] = df[sku_col].apply(clean_sku)
        matched = df[df['_sku'] != '']
        unmatched = df[df['_sku'] == '']

        per_sku = matched.groupby('_sku')['_cost'].sum().to_dict()
        unallocated = unmatched['_cost'].sum()

        logger.info(
            f"Ozon ads: привязано {len(per_sku)} SKU. "
            f"Нераспределённые: {unallocated:.2f} руб."
        )

        return {str(k): round(float(v), 2) for k, v in per_sku.items()}, round(float(unallocated), 2)

    except Exception as e:
        logger.error(f"Ошибка парсинга Ozon рекламы: {e}")
        return {}, 0.0


def aggregate_ad_costs(
    wb_ads_bufs: List[io.BytesIO],
    ozon_ads_bufs: List[io.BytesIO],
    wb_sku_map: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Агрегирует все рекламные файлы в единый словарь расходов.

    Args:
        wb_ads_bufs: Список BytesIO буферов WB рекламных отчётов.
        ozon_ads_bufs: Список BytesIO буферов Ozon рекламных отчётов.
        wb_sku_map: Словарь {wb_nomenclature_id -> seller_article}.

    Returns:
        Dict с ключами:
          - 'per_sku': Dict[str, float] — прямые расходы по артикулам
          - 'unallocated': float — нераспределённые расходы
          - 'total': float — итого все рекламные расходы
    """
    combined_per_sku: Dict[str, float] = {}
    total_unallocated = 0.0

    # Обработка WB
    for i, buf in enumerate(wb_ads_bufs):
        per_sku, unallocated = parse_wb_ads(buf, wb_sku_map)
        logger.info(f"WB Ads [{i+1}/{len(wb_ads_bufs)}]: прямые={sum(per_sku.values()):.2f}, нераспред.={unallocated:.2f}")
        for art, cost in per_sku.items():
            combined_per_sku[art] = combined_per_sku.get(art, 0.0) + cost
        total_unallocated += unallocated

    # Обработка Ozon
    for i, buf in enumerate(ozon_ads_bufs):
        per_sku, unallocated = parse_ozon_ads(buf)
        logger.info(f"Ozon Ads [{i+1}/{len(ozon_ads_bufs)}]: прямые={sum(per_sku.values()):.2f}, нераспред.={unallocated:.2f}")
        for art, cost in per_sku.items():
            combined_per_sku[art] = combined_per_sku.get(art, 0.0) + cost
        total_unallocated += unallocated

    total_direct = sum(combined_per_sku.values())
    total_all = total_direct + total_unallocated

    logger.info(
        f"📊 Итого реклама: прямые={total_direct:.2f}, "
        f"нераспределённые={total_unallocated:.2f}, "
        f"всего={total_all:.2f} руб."
    )

    return {
        'per_sku': combined_per_sku,
        'unallocated': round(total_unallocated, 2),
        'total': round(total_all, 2),
    }
