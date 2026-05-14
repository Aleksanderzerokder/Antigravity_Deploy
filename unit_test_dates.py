import pandas as pd
import os
import re

def auto_detect_period_mock(text):
    dates = re.findall(r'(\d{2,4}-\d{2}-\d{2,4})|(\d{2}\.\d{2}\.\d{2,4})', text)
    if len(dates) >= 2:
        found_from = dates[0][0] if dates[0][0] else dates[0][1]
        found_to = dates[1][0] if dates[1][0] else dates[1][1]
        return found_from, found_to
    return None, None

test_texts = [
    "Отчёт по данным поставщика ... с 01.04.2026 по 30.04.2026 сформирован ...",
    "Период: 01.04.2026-30.04.2026",
    "supplier-goods-123-2026-05-01-2026-05-31-abc.xlsx"
]

for t in test_texts:
    f, t_out = auto_detect_period_mock(t)
    print(f"Text: {t[:50]}... -> Detected: {f} to {t_out}")
