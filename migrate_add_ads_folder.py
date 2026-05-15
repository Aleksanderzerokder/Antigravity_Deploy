"""
migrate_add_ads_folder.py — Миграция: создание папки 1. ADS у существующих селлеров.

Запускается один раз. Читает sellers_config.json, для каждого селлера
проверяет наличие папки 1. ADS и создаёт её если она отсутствует.
"""

import json
import os
from dotenv import load_dotenv
load_dotenv()

from drive_utils import get_service, FOLDER_ADS, _find_subfolder
from schema_loader import get_folder_name

SELLERS_CONFIG = 'sellers_config.json'


def create_folder_if_missing(service, parent_id: str, folder_name: str, seller_name: str) -> str:
    """Создаёт папку в parent_id, если её нет. Возвращает ID."""
    existing_id = _find_subfolder(service, parent_id, folder_name)
    if existing_id:
        print(f"  [OK] [{seller_name}] Folder '{folder_name}' already exists (ID: {existing_id})")
        return existing_id

    meta = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id]
    }
    folder = service.files().create(body=meta, fields='id, name').execute()
    new_id = folder['id']
    print(f"  [CREATED] [{seller_name}] Folder '{folder_name}' (ID: {new_id})")
    return new_id


def main():
    if not os.path.exists(SELLERS_CONFIG):
        print(f"Файл {SELLERS_CONFIG} не найден. Нет зарегистрированных селлеров.")
        return

    with open(SELLERS_CONFIG, 'r', encoding='utf-8') as f:
        config = json.load(f)

    if not config:
        print("Нет зарегистрированных селлеров в sellers_config.json")
        return

    service = get_service()
    ads_folder_name = FOLDER_ADS  # '1. ADS' из схемы

    print(f"\n>>> Migration: adding folder '{ads_folder_name}' for {len(config)} sellers\n")

    for seller_folder_id, info in config.items():
        seller_name = info.get('name', seller_folder_id)
        print(f"Обрабатываю: {seller_name} (папка: {seller_folder_id})")
        try:
            create_folder_if_missing(service, seller_folder_id, ads_folder_name, seller_name)
        except Exception as e:
            print(f"  [ERROR] {seller_name}: {e}")

    print("\n[DONE] Migration complete!")
    print(f"Folder '{ads_folder_name}' now exists for all sellers.")
    print("Upload advertising reports there - type will be detected automatically by column contents.")


if __name__ == "__main__":
    main()
