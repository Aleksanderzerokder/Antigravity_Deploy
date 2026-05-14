from drive_utils import _get_service, list_files_in_folder

def debug_name():
    svc = _get_service()
    dict_id = '1DFwlEWue7m_gBTZaiAyGweB01klNtML-' # Irvida Dict
    files = list_files_in_folder(svc, dict_id)
    
    code_word = 'себестоимость'
    print(f"Кодовое слово: {code_word}")
    print(f"Hex кодового слова: {[hex(ord(c)) for c in code_word]}")
    
    for f in files:
        name = f['name']
        name_lower = name.lower()
        print(f"\nФайл: {name}")
        print(f"Hex имени (lower): {[hex(ord(c)) for c in name_lower]}")
        print(f"Поиск 'себестоимость' в имени: {'себестоимость' in name_lower}")
        print(f"Поиск 'cost' в имени: {'cost' in name_lower}")

if __name__ == '__main__':
    debug_name()
