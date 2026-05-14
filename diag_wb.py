from drive_utils import _get_service, _find_subfolder, list_files_in_folder, download_file_to_memory
import pandas as pd
import io

def diag():
    svc = _get_service()
    seller_id = '1s8bsLcFhnlqJwaNkTOp43Nf6POlhoeSj'
    inn_id = '1h9OOA1EfKAoSNsJG4aW6SEtRokWcBFbT'
    dict_id = '1DFwlEWue7m_gBTZaiAyGweB01klNtML-'
    
    # 1. WB Supplier Goods
    files = list_files_in_folder(svc, inn_id)
    sg = next((f for f in files if 'supplier-goods' in f['name'].lower()), None)
    if sg:
        buf = download_file_to_memory(svc, sg['id'])
        df = pd.read_excel(buf)
        print(f"WB Supplier Goods ({sg['name']})")
        print(f"  Колонки: {df.columns.tolist()}")
        print(f"  Примеры артикулов: {df.iloc[:, 0].head(3).tolist() if not df.empty else 'пусто'}")
        
    # 2. Cost Dictionary
    files_dict = list_files_in_folder(svc, dict_id)
    cd = next((f for f in files_dict if 'себестоимост' in f['name'].lower()), None)
    if cd:
        buf = download_file_to_memory(svc, cd['id'])
        df = pd.read_excel(buf)
        print(f"\nCost Dictionary ({cd['name']})")
        print(f"  Колонки: {df.columns.tolist()}")
        print(f"  Примеры данных:\n{df.head(3)}")

if __name__ == '__main__':
    diag()
