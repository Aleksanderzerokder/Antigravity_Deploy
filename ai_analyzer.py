"""
ai_analyzer.py - Модуль для генерации бизнес-инсайтов с помощью GigaChat.
Поддерживает несколько селлеров: каждый получает свой аналитический блок.
"""

import logging
import os
from typing import Optional

import pandas as pd
from gigachat import GigaChat

logger = logging.getLogger(__name__)


def generate_insights(df_full: pd.DataFrame, period_label: str, seller_name: str = '') -> str:
    """
    Генерирует текстовые инсайты для конкретного селлера за указанный период 
    с использованием нейросети GigaChat.

    Args:
        df_full: Полный исторический DataFrame (все периоды селлера).
        period_label: Строка текущего периода (напр. '2026-04-01 – 2026-04-30').
        seller_name: Название селлера для контекста нейросети.

    Returns:
        str: Текст отчета с инсайтами или сообщение об ошибке.
    """
    auth_key = os.environ.get('GIGACHAT_AUTH_KEY')
    scope = os.environ.get('GIGACHAT_SCOPE')

    if not auth_key:
        logger.warning("GIGACHAT_AUTH_KEY не найден в переменных окружения.")
        return "Не настроен ключ GigaChat для анализа."

    if df_full is None or df_full.empty:
        logger.warning("Пустой DataFrame передан в ai_analyzer.")
        return "Нет данных для анализа."

    try:
        # --- Подготовка данных ---
        df_current = df_full[df_full['Период'] == period_label] if 'Период' in df_full.columns else df_full
        if df_current.empty:
            return f"Нет данных за период {period_label}."

        total_rev = df_current['Выручка'].sum()
        total_profit = df_current['Чистая_Прибыль'].sum()
        margin = (total_profit / total_rev * 100) if total_rev > 0 else 0

        # Разбивка по маркетплейсам
        mp_breakdown = 'нет данных'
        if 'Маркетплейс' in df_current.columns:
            mp_stats = df_current.groupby('Маркетплейс').agg(
                Выручка=('Выручка', 'sum'),
                Прибыль=('Чистая_Прибыль', 'sum')
            ).reset_index()
            mp_stats['Маржа_%'] = mp_stats.apply(
                lambda r: round(r['Прибыль'] / r['Выручка'] * 100, 1) if r['Выручка'] > 0 else 0, axis=1
            )
            mp_breakdown = mp_stats.to_string(index=False)

        # Сравнение с прошлым периодом (наивная логика поиска по строке)
        prev_info = "нет данных"
        if 'Период' in df_full.columns and '-' in period_label:
            try:
                # Пытаемся определить YYYY-MM
                parts = period_label.split('-')
                if len(parts) >= 2:
                    y, m = int(parts[0]), int(parts[1])
                    prev_y, prev_m = (y - 1, 12) if m == 1 else (y, m - 1)
                    prev_label = f"{prev_y}-{prev_m:02d}"
                    df_prev = df_full[df_full['Период'].str.contains(prev_label, na=False)]
                    if not df_prev.empty:
                        prev_rev = df_prev['Выручка'].sum()
                        prev_marg = (df_prev['Чистая_Прибыль'].sum() / prev_rev * 100) if prev_rev > 0 else 0
                        prev_info = f"Выручка: {prev_rev:,.2f} руб., Маржинальность: {prev_marg:.1f}%"
            except (ValueError, IndexError):
                pass

        # Топ товаров
        top_profit = df_current.nlargest(5, 'Чистая_Прибыль')[['Артикул', 'Название', 'Чистая_Прибыль']]
        top_loss = df_current.nsmallest(5, 'Чистая_Прибыль')[['Артикул', 'Название', 'Чистая_Прибыль']]
        top_loss = top_loss[top_loss['Чистая_Прибыль'] < 0]

        # Товары без себестоимости
        no_cost_count = len(df_current[(df_current['Количество'] > 0) & (df_current['Себестоимость_Общая'] == 0)])

        # --- Формируем промпт ---
        seller_ctx = f"Клиент: {seller_name}." if seller_name else ""
        prompt = f"""
Ты опытный финансовый аналитик селлеров на маркетплейсах.
Напиши краткую сводку (инсайт) для дашборда. Используй форматирование и списки.
Пиши по делу, без "воды" и приветствий. {seller_ctx}

=== ПЕРИОД: {period_label} ===

Итоговые показатели:
- Выручка: {total_rev:,.2f} руб.
- Чистая прибыль: {total_profit:,.2f} руб.
- Маржинальность: {margin:.1f}%

Разбивка по маркетплейсам:
{mp_breakdown}

Сравнение с прошлым месяцем:
{prev_info}

Топ-5 прибыльных SKU:
{top_profit.to_string(index=False)}

Убыточные SKU:
{top_loss.to_string(index=False) if not top_loss.empty else "Нет убыточных"}

Проблемы:
- Товаров без себестоимости: {no_cost_count} (их реальная прибыльность неизвестна).

Выводы: 2-3 ключевых факта и 1-2 конкретных действия на следующий месяц.
"""
        logger.info(f"Отправка запроса в GigaChat для {seller_name}...")
        with GigaChat(credentials=auth_key, scope=scope, verify_ssl_certs=False) as giga:
            response = giga.chat(prompt)
            return response.choices[0].message.content

    except Exception as e:
        logger.error(f"Ошибка при работе с GigaChat: {e}")
        return f"Ошибка генерации инсайтов: {str(e)}"
