import consolidate as C
import os
import pandas as pd
from drive_utils import _get_service, download_file_to_memory, list_files_in_folder

def test_detect():
    print("Начинаю тест автодетекции...")
    svc = _get_service()
    inn_id = '1h9OOA1EfKAoSNsJG4aW6SEtRokWcBFbT'
    files = list_files_in_folder(svc, inn_id)
    print(f"Файлов в папке: {len(files)}")
    sg = next((f for f in files if 'supplier-goods' in f['name'].lower()), None)
    
    if sg:
        print(f"Найден файл: {sg['name']}")
        buf = download_file_to_memory(svc, sg['id'])
        with open('test_sg.xlsx', 'wb') as f:
            f.write(buf.read())
        
        C.WB_QTY_FILE = 'test_sg.xlsx'
        d_from, d_to, label = C.auto_detect_period()
        print(f"РЕЗУЛЬТАТ: {d_from} to {d_to} (Label: {label})")
        if os.path.exists('test_sg.xlsx'):
            os.remove('test_sg.xlsx')
    else:
        print("Файл supplier-goods не найден!")

if __name__ == '__main__':
    test_detect()
