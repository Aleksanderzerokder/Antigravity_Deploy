"""
register_seller.py — Утилита для первоначальной регистрации селлера.
Запускается один раз при добавлении нового селлера в систему.
"""
from sheets_utils import register_seller_table
from drive_utils import list_seller_folders, _get_service

print("=== Регистрация Мастер-таблицы селлера ===\n")

svc = _get_service()
sellers = list_seller_folders(svc)

if not sellers:
    print("❌ Папок селлеров не найдено в корневой папке Google Drive.")
    print("   Сначала создайте папку селлера (или запустите drive_utils.py)")
    exit(1)

print("Доступные папки селлеров:")
for i, s in enumerate(sellers, 1):
    print(f"  {i}. {s['name']} (ID: {s['id']})")

idx = int(input("\nВыберите номер селлера: ")) - 1
seller = sellers[idx]

print(f"\nВыбран: {seller['name']}")
print("\nОткройте Мастер-таблицу на Google Drive и скопируйте её ID из адресной строки.")
print("URL выглядит так: https://docs.google.com/spreadsheets/d/ВОТ_ЭТОТ_ID/edit")
sheet_id = input("\nВставьте ID таблицы: ").strip()

register_seller_table(seller['id'], seller['name'], sheet_id)
print(f"\n🎉 Готово! Теперь скрипт будет обновлять таблицу автоматически.")
