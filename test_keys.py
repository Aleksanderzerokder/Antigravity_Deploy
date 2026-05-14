import os
from dotenv import load_dotenv, set_key

load_dotenv()
creds = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
if creds and not os.path.exists(creds) and os.path.exists('antigravity-market-analytics-695242fe8429.json'):
    set_key('.env', 'GOOGLE_APPLICATION_CREDENTIALS', 'antigravity-market-analytics-695242fe8429.json')
    load_dotenv(override=True)
    creds = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')

# Test GigaChat
try:
    from gigachat import GigaChat
    auth = os.environ.get('GIGACHAT_AUTH_KEY')
    scope = os.environ.get('GIGACHAT_SCOPE')
    with GigaChat(credentials=auth, scope=scope, verify_ssl_certs=False) as giga:
        response = giga.chat('Привет! Ты работаешь? Ответь одним словом.')
        print('GigaChat OK:', response.choices[0].message.content)
except Exception as e:
    print('GigaChat Error:', str(e))

# Test Google Drive
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    
    creds_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    folder_id = os.environ.get('GOOGLE_DRIVE_ROOT_FOLDER_ID')
    
    creds = service_account.Credentials.from_service_account_file(
        creds_path, scopes=['https://www.googleapis.com/auth/drive']
    )
    service = build('drive', 'v3', credentials=creds)
    results = service.files().list(q=f"'{folder_id}' in parents", fields="files(id, name)").execute()
    print('Google Drive OK. Found files/folders:', len(results.get('files', [])))
except Exception as e:
    print('Google Drive Error:', str(e))
