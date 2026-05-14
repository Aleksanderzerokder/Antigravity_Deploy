from drive_utils import _get_service
import os

def check():
    svc = _get_service()
    seller_id = '1s8bsLcFhnlqJwaNkTOp43Nf6POlhoeSj' # Seller_2 (Ирвида)
    
    query = f"'{seller_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    results = svc.files().list(q=query, fields='files(id, name)').execute()
    folders = results.get('files', [])
    
    print(f"Папки в Seller 2 ({len(folders)}):")
    for f in folders:
        print(f" - {f['name']} (ID: {f['id']})")
        
    # Также проверим Seller 1 для сравнения
    seller1_id = '198GYfAvSROb-FJl-jc7EVpnmX9Yyjbpq'
    query1 = f"'{seller1_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    res1 = svc.files().list(q=query1, fields='files(id, name)').execute()
    folders1 = res1.get('files', [])
    print(f"\nПапки в Seller 1 ({len(folders1)}):")
    for f in folders1:
        print(f" - {f['name']} (ID: {f['id']})")

if __name__ == '__main__':
    check()
