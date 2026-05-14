import { google } from 'googleapis';
import { NextResponse } from 'next/server';

export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const seller = searchParams.get('seller') || 'Запакуй';

  // Сопоставление имен селлеров с ID таблиц из ваших переменных окружения
  const sheetIds = {
    'Запакуй': process.env.SELLER_1_SHEET_ID,
    'Ирвида': process.env.SELLER_2_SHEET_ID,
  };

  const spreadsheetId = sheetIds[seller];
  
  if (!spreadsheetId) {
    return NextResponse.json({ error: 'Seller not found' }, { status: 404 });
  }

  try {
    const auth = new google.auth.GoogleAuth({
      credentials: JSON.parse(process.env.GOOGLE_CREDENTIALS_JSON),
      scopes: ['https://www.googleapis.com/auth/spreadsheets.readonly'],
    });

    const sheets = google.sheets({ version: 'v4', auth });

    // 1. Читаем данные из листа "Data" (Master Table)
    const response = await sheets.spreadsheets.values.get({
      spreadsheetId,
      range: 'Data!A:Z', // Читаем всю таблицу
    });

    const rows = response.data.values;
    if (!rows || rows.length === 0) {
      return NextResponse.json({ error: 'No data found' }, { status: 404 });
    }

    // Преобразуем массив строк в массив объектов (ключ-значение)
    const headers = rows[0];
    const data = rows.slice(1).map(row => {
      let obj = {};
      headers.forEach((header, index) => {
        obj[header] = row[index];
      });
      return obj;
    });

    // 2. Читаем ИИ-инсайты из листа "AI_Dashboard"
    let insights = "";
    try {
      const aiResponse = await sheets.spreadsheets.values.get({
        spreadsheetId,
        range: 'AI_Dashboard!B2:B2', // Там лежит текст последнего инсайта
      });
      insights = aiResponse.data.values?.[0]?.[0] || "";
    } catch (e) {
      console.error("AI Insights not found");
    }

    return NextResponse.json({ data, insights });
  } catch (error) {
    console.error('API Error:', error);
    return NextResponse.json({ error: 'Internal Server Error', details: error.message }, { status: 500 });
  }
}
