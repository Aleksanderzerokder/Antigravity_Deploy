import { google } from 'googleapis';
import { NextResponse } from 'next/server';

/**
 * GET /api/schema
 * Возвращает структуру папок и типов файлов из seller_schema.json
 * для использования в UI загрузки файлов.
 */
export async function GET() {
  try {
    const schema = {
      folders: {
        financial: { name: '1. IN', purpose: 'Финансовые отчёты маркетплейсов' },
        advertising: { name: '1. ADS', purpose: 'Рекламные отчёты' },
        dictionaries: { name: '2. DICTIONARIES', purpose: 'Справочник себестоимости' },
      },
      file_types: [
        {
          key: 'wb_weekly',
          folder: 'financial',
          marketplace: 'WB',
          label: 'Еженедельный отчёт WB',
          hint: 'Файл «Еженедельный детализированный отчёт №...»',
          accept: '.xlsx,.xls',
          color: 'blue',
        },
        {
          key: 'wb_supplier_goods',
          folder: 'financial',
          marketplace: 'WB',
          label: 'Отчёт по товарам WB',
          hint: 'Файл «supplier-goods-...»',
          accept: '.xlsx,.xls',
          color: 'blue',
        },
        {
          key: 'ozon_charges',
          folder: 'financial',
          marketplace: 'Ozon',
          label: 'Начисления Ozon',
          hint: 'Файл «Отчёт по начислениям...»',
          accept: '.xlsx,.xls',
          color: 'teal',
        },
        {
          key: 'wb_ads',
          folder: 'advertising',
          marketplace: 'WB',
          label: 'Реклама WB (Статистика)',
          hint: 'Файл «Статистика...» из кабинета WB',
          accept: '.xlsx,.xls',
          color: 'purple',
        },
        {
          key: 'ozon_ads',
          folder: 'advertising',
          marketplace: 'Ozon',
          label: 'Реклама Ozon (Продвижение)',
          hint: 'Файл «Аналитика продвижения...»',
          accept: '.xlsx,.xls',
          color: 'purple',
        },
        {
          key: 'cost_file',
          folder: 'dictionaries',
          marketplace: 'ALL',
          label: 'Себестоимость товаров',
          hint: 'Excel-файл: Артикул | Себестоимость',
          accept: '.xlsx,.xls',
          color: 'amber',
        },
      ],
    };

    return NextResponse.json(schema);
  } catch (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
