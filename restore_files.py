from drive_utils import _get_service, _find_subfolder, list_files_in_folder
import os

def restore():
    svc = _get_service()
    seller_id = '1s8bsLcFhnlqJwaNkTOp43Nf6POlhoeSj'
    archive_id = '1-QcBCmt4_0DJ0vkZTmdGXvLdfsUsC-gk'
    inn_id = '1h9OOA1EfKAoSNsJG4aW6SEtRokWcBFbT'
    
    # Ищем файлы в 2026/04
    year_id = _find_subfolder(svc, archive_id, "2026")
    if not year_id: return
    month_id = _find_subfolder(svc, year_id, "04")
    if not month_id: return
    
    files = list_files_in_folder(svc, month_id)
    print(f"Восстановление {len(files)} файлов...")
    
    for f in files:
        file_id = f['id']
        file_meta = svc.files().get(fileId=file_id, fields='parents').execute()
        current_parents = ','.join(file_meta.get('parents', []))
        
        svc.files().update(
            fileId=file_id,
            addParents=inn_id,
            removeParents=current_parents,
            fields='id, parents'
        ).execute()
        print(f" - {f['name']} восстановлен в INN")

if __name__ == '__main__':
    restore()
