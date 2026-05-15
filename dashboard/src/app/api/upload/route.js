import { google } from 'googleapis';
import { NextResponse } from 'next/server';

import fs from 'fs';
import path from 'path';

// Имена папок для каждого типа файла (из схемы)
const FOLDER_NAMES = {
  financial:    '1. IN',
  advertising:  '1. ADS',
  dictionaries: '2. DICTIONARIES',
};

/**
 * POST /api/upload
 * Принимает файл и загружает его в правильную папку на Google Drive.
 *
 * Body (multipart/form-data):
 *   - file: File
 *   - seller: string ('Запакуй' | 'Ирвида')
 *   - folder_key: string ('financial' | 'advertising' | 'dictionaries')
 *   - file_type: string (для логирования)
 */
export async function POST(request) {
  try {
    const formData = await request.formData();
    const file = formData.get('file');
    const sellerName = formData.get('seller');
    const folderKey = formData.get('folder_key');
    const fileType = formData.get('file_type') || 'unknown';

    // Валидация входных данных
    if (!file || !sellerName || !folderKey) {
      return NextResponse.json(
        { error: 'Обязательные поля: file, seller, folder_key' },
        { status: 400 }
      );
    }

    // Загрузка конфига селлеров
    let sellersConfig = {};
    try {
      const configPath = path.join(process.cwd(), '..', 'sellers_config.json');
      const fileContents = fs.readFileSync(configPath, 'utf8');
      sellersConfig = JSON.parse(fileContents);
    } catch (e) {
      console.warn("Could not read sellers_config.json from parent dir", e.message);
    }

    // Ищем ID папки селлера (учитываем, что в конфиге может быть "Seller_1 (Тест)" а в UI "Запакуй")
    let sellerFolderId = null;
    for (const [folderId, info] of Object.entries(sellersConfig)) {
      const configName = info.name.toLowerCase();
      const searchName = sellerName.toLowerCase();
      // Для Запакуй исторически используется Seller_1
      if (searchName === 'запакуй' && configName.includes('seller_1')) {
        sellerFolderId = folderId;
        break;
      }
      if (configName.includes(searchName)) {
        sellerFolderId = folderId;
        break;
      }
    }

    if (!sellerFolderId) {
      return NextResponse.json(
        { error: `Селлер '${sellerName}' не найден в конфигурации` },
        { status: 404 }
      );
    }

    const targetFolderName = FOLDER_NAMES[folderKey];
    if (!targetFolderName) {
      return NextResponse.json(
        { error: `Неизвестный ключ папки: '${folderKey}'` },
        { status: 400 }
      );
    }

    // Аутентификация Google Drive
    const auth = new google.auth.GoogleAuth({
      credentials: JSON.parse(process.env.GOOGLE_CREDENTIALS_JSON),
      scopes: ['https://www.googleapis.com/auth/drive'],
    });
    const drive = google.drive({ version: 'v3', auth });

    // Поиск целевой подпапки в Drive
    const folderQuery = await drive.files.list({
      q: `'${sellerFolderId}' in parents and name = '${targetFolderName}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false`,
      fields: 'files(id, name)',
    });

    let targetFolderId;
    if (folderQuery.data.files && folderQuery.data.files.length > 0) {
      targetFolderId = folderQuery.data.files[0].id;
    } else {
      // Если папка не найдена — создаём её
      const newFolder = await drive.files.create({
        resource: {
          name: targetFolderName,
          mimeType: 'application/vnd.google-apps.folder',
          parents: [sellerFolderId],
        },
        fields: 'id',
      });
      targetFolderId = newFolder.data.id;
      console.log(`[Upload] Создана папка '${targetFolderName}' для ${sellerName}`);
    }

    // Конвертация File → Buffer
    const arrayBuffer = await file.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);
    const { Readable } = await import('stream');
    const stream = Readable.from(buffer);

    // Загрузка файла на Drive
    const uploadedFile = await drive.files.create({
      resource: {
        name: file.name,
        parents: [targetFolderId],
      },
      media: {
        mimeType: file.type || 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        body: stream,
      },
      fields: 'id, name, size, createdTime',
    });

    console.log(`[Upload] OK: ${file.name} → ${sellerName}/${targetFolderName} (type: ${fileType})`);

    return NextResponse.json({
      success: true,
      file: {
        id: uploadedFile.data.id,
        name: uploadedFile.data.name,
        size: uploadedFile.data.size,
        folder: targetFolderName,
        seller: sellerName,
      },
      message: `Файл '${file.name}' загружен в ${targetFolderName}`,
    });

  } catch (error) {
    console.error('[Upload] Error:', error);
    return NextResponse.json(
      { error: 'Ошибка загрузки файла', details: error.message },
      { status: 500 }
    );
  }
}
