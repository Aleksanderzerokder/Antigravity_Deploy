from drive_utils import _get_service, _find_subfolder, list_files_in_folder, download_file_to_memory
import pandas as pd
import io

def diag_head_ozon():
    svc = _get_service()
    seller_id = '1s8bsLcFhnlqJwaNkTOp43Nf6POlhoeSj'
    inn_id = '1h9OOA1EfKAoSNsJG4aW6SEtRokWcBFbT'
    
    files = list_files_in_folder(svc, inn_id)
    oz = next((f for f in files if 'начислени' in f['name'].lower() or 'ozon' in f['name'].lower()), None)
    if oz:
        buf = download_file_to_memory(svc, oz['id'])
        df = pd.read_excel(buf, header=None)
        print(f"Первые 10 строк Ozon Report (без хедера):")
        print(df.head(10).to_string())

if __name__ == '__main__':
    diag_head_ozon()
