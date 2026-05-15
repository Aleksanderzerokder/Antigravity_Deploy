'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  TrendingUp,
  DollarSign,
  Package,
  BarChart3,
  BrainCircuit,
  RefreshCcw,
  ShoppingBag,
  Upload,
  CheckCircle,
  AlertCircle,
  FileSpreadsheet,
  Megaphone,
  BookOpen,
  ChevronDown,
  X,
  Loader2,
} from 'lucide-react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { Line } from 'react-chartjs-2';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Title, Tooltip, Legend, Filler);

// ─────────────────────────────────────────────
// Конфигурация типов файлов (синхронизирована с seller_schema.json)
// ─────────────────────────────────────────────
const FILE_GROUPS = [
  {
    key: 'financial',
    label: 'Финансовые отчёты',
    folder: '1. IN',
    icon: <FileSpreadsheet size={18} />,
    color: 'blue',
    types: [
      { key: 'wb_weekly',        label: 'Еженедельный отчёт WB',  marketplace: 'WB',   hint: 'Файл «Еженедельный детализированный отчёт №...»' },
      { key: 'wb_supplier_goods',label: 'Отчёт по товарам WB',    marketplace: 'WB',   hint: 'Файл «supplier-goods-...»' },
      { key: 'ozon_charges',     label: 'Начисления Ozon',         marketplace: 'Ozon', hint: 'Файл «Отчёт по начислениям...»' },
    ],
  },
  {
    key: 'advertising',
    label: 'Рекламные отчёты',
    folder: '1. ADS',
    icon: <Megaphone size={18} />,
    color: 'purple',
    types: [
      { key: 'wb_ads',   label: 'Реклама WB (Статистика)',    marketplace: 'WB',   hint: 'Файл «Статистика...» из рекламного кабинета WB' },
      { key: 'ozon_ads', label: 'Реклама Ozon (Продвижение)', marketplace: 'Ozon', hint: 'Файл «Аналитика продвижения...»' },
    ],
  },
  {
    key: 'dictionaries',
    label: 'Себестоимость',
    folder: '2. DICTIONARIES',
    icon: <BookOpen size={18} />,
    color: 'amber',
    types: [
      { key: 'cost_file', label: 'Справочник себестоимости', marketplace: 'ALL', hint: 'Excel: Артикул | Название | Себестоимость' },
    ],
  },
];

const SELLERS = ['Запакуй', 'Ирвида'];

const COLOR_MAP = {
  blue:   { bg: 'bg-blue-500/10',   border: 'border-blue-500/30',   text: 'text-blue-400',   badge: 'bg-blue-500/20 text-blue-300' },
  purple: { bg: 'bg-purple-500/10', border: 'border-purple-500/30', text: 'text-purple-400', badge: 'bg-purple-500/20 text-purple-300' },
  amber:  { bg: 'bg-amber-500/10',  border: 'border-amber-500/30',  text: 'text-amber-400',  badge: 'bg-amber-500/20 text-amber-300' },
  teal:   { bg: 'bg-teal-500/10',   border: 'border-teal-500/30',   text: 'text-teal-400',   badge: 'bg-teal-500/20 text-teal-300' },
};

// ─────────────────────────────────────────────
// Компонент: карточка загрузки одного типа файла
// ─────────────────────────────────────────────
function UploadCard({ fileType, groupKey, folderName, color, seller }) {
  const [status, setStatus] = useState('idle'); // idle | dragging | uploading | success | error
  const [message, setMessage] = useState('');
  const [fileName, setFileName] = useState('');
  const c = COLOR_MAP[color] || COLOR_MAP.blue;

  const uploadFile = async (file) => {
    if (!file) return;
    setFileName(file.name);
    setStatus('uploading');
    setMessage('');

    const formData = new FormData();
    formData.append('file', file);
    formData.append('seller', seller);
    formData.append('folder_key', groupKey);
    formData.append('file_type', fileType.key);

    try {
      const res = await fetch('/api/upload', { method: 'POST', body: formData });
      const result = await res.json();

      if (res.ok && result.success) {
        setStatus('success');
        setMessage(result.message || 'Файл загружен успешно');
        setTimeout(() => { setStatus('idle'); setFileName(''); setMessage(''); }, 5000);
      } else {
        setStatus('error');
        setMessage(result.error || 'Ошибка загрузки');
      }
    } catch (err) {
      setStatus('error');
      setMessage('Сетевая ошибка: ' + err.message);
    }
  };

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setStatus('idle');
    const file = e.dataTransfer.files[0];
    if (file) uploadFile(file);
  }, [seller, groupKey]);

  const handleDragOver = (e) => { e.preventDefault(); setStatus('dragging'); };
  const handleDragLeave = () => { if (status === 'dragging') setStatus('idle'); };
  const handleFileInput = (e) => { const file = e.target.files[0]; if (file) uploadFile(file); };

  const isUploading = status === 'uploading';
  const isSuccess = status === 'success';
  const isError = status === 'error';
  const isDragging = status === 'dragging';

  return (
    <div
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      className={`
        relative rounded-xl border-2 border-dashed p-5 transition-all duration-200 cursor-pointer
        ${isDragging ? `${c.border} ${c.bg} scale-[1.02]` : 'border-white/10 hover:border-white/20'}
        ${isSuccess ? 'border-emerald-500/40 bg-emerald-500/5' : ''}
        ${isError ? 'border-red-500/40 bg-red-500/5' : ''}
      `}
    >
      <label className="cursor-pointer block">
        <input
          type="file"
          accept=".xlsx,.xls"
          className="hidden"
          onChange={handleFileInput}
          disabled={isUploading}
        />

        {/* Заголовок карточки */}
        <div className="flex items-start justify-between mb-3">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${c.badge}`}>
                {fileType.marketplace}
              </span>
            </div>
            <p className="font-semibold text-sm text-white">{fileType.label}</p>
            <p className="text-xs text-white/40 mt-0.5">{fileType.hint}</p>
          </div>

          {/* Статус иконка */}
          <div className="shrink-0 ml-3">
            {isUploading && <Loader2 size={20} className="text-blue-400 animate-spin" />}
            {isSuccess && <CheckCircle size={20} className="text-emerald-400" />}
            {isError && <AlertCircle size={20} className="text-red-400" />}
            {!isUploading && !isSuccess && !isError && (
              <Upload size={20} className={`${c.text} opacity-60`} />
            )}
          </div>
        </div>

        {/* Контент зоны */}
        {isUploading && (
          <div className="text-center py-2">
            <p className="text-xs text-white/60 truncate">{fileName}</p>
            <div className="mt-2 h-1 bg-white/10 rounded-full overflow-hidden">
              <div className="h-full bg-blue-500 rounded-full animate-pulse w-3/4" />
            </div>
          </div>
        )}
        {isSuccess && (
          <p className="text-xs text-emerald-400 font-medium text-center py-1">{message}</p>
        )}
        {isError && (
          <p className="text-xs text-red-400 text-center py-1">{message}</p>
        )}
        {!isUploading && !isSuccess && !isError && (
          <div className={`text-center py-2 rounded-lg ${c.bg} border ${c.border}`}>
            <p className="text-xs text-white/50">
              {isDragging ? 'Отпустите файл' : 'Нажмите или перетащите .xlsx'}
            </p>
          </div>
        )}
      </label>
    </div>
  );
}

// ─────────────────────────────────────────────
// Компонент: секция загрузки файлов
// ─────────────────────────────────────────────
function UploadSection({ seller }) {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 pb-2 border-b border-white/5">
        <Upload size={20} className="text-blue-400" />
        <div>
          <h2 className="text-lg font-bold">Загрузка отчётов</h2>
          <p className="text-xs text-white/40 mt-0.5">
            Селлер: <span className="text-white/70 font-medium">{seller}</span> · Файлы сохраняются в Google Drive автоматически
          </p>
        </div>
      </div>

      {/* Инфо-баннер */}
      <div className="rounded-xl bg-blue-500/5 border border-blue-500/15 px-4 py-3 flex gap-3 items-start">
        <AlertCircle size={16} className="text-blue-400 mt-0.5 shrink-0" />
        <p className="text-xs text-white/55 leading-relaxed">
          Загружайте финансовый и рекламный отчёты за <strong className="text-white/80">один и тот же период</strong>.
          После расчёта система автоматически переместит файлы в архив.
          Имя файла не важно — тип определяется по содержимому.
        </p>
      </div>

      {/* Группы файлов */}
      {FILE_GROUPS.map((group) => {
        const c = COLOR_MAP[group.color] || COLOR_MAP.blue;
        return (
          <div key={group.key} className="glass rounded-2xl p-6 space-y-4">
            {/* Заголовок группы */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className={c.text}>{group.icon}</span>
                <span className="font-semibold text-sm">{group.label}</span>
              </div>
              <span className={`text-xs px-2 py-1 rounded-full font-mono ${c.badge}`}>
                → {group.folder}
              </span>
            </div>

            {/* Карточки типов файлов */}
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
              {group.types.map((fileType) => (
                <UploadCard
                  key={fileType.key}
                  fileType={fileType}
                  groupKey={group.key}
                  folderName={group.folder}
                  color={group.color}
                  seller={seller}
                />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─────────────────────────────────────────────
// Главная страница
// ─────────────────────────────────────────────
export default function Dashboard() {
  const [activeSeller, setActiveSeller] = useState('Запакуй');
  const [activeTab, setActiveTab] = useState('analytics'); // 'analytics' | 'upload'
  const [isSyncing, setIsSyncing] = useState(false);
  const [data, setData] = useState([]);
  const [insights, setInsights] = useState('');
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/data?seller=${encodeURIComponent(activeSeller)}`);
      const result = await res.json();
      if (result.data) {
        setData(result.data);
        setInsights(result.insights);
      }
    } catch (error) {
      console.error('Fetch error:', error);
    }
    setLoading(false);
  };

  useEffect(() => { fetchData(); }, [activeSeller]);

  const calculateMetrics = () => {
    if (!data.length) return { rev: '0 ₽', profit: '0 ₽', margin: '0%', roi: '0%', ads: '0 ₽' };
    const latestPeriod = data[data.length - 1]?.Период;
    const currentData = data.filter(d => d.Период === latestPeriod);
    const totalRev = currentData.reduce((sum, d) => sum + parseFloat(d.Выручка || 0), 0);
    const totalProfit = currentData.reduce((sum, d) => sum + parseFloat(d['Чистая_Прибыль'] || 0), 0);
    const totalCost = currentData.reduce((sum, d) => sum + parseFloat(d.Себестоимость_Общая || 0), 0);
    const totalAds = currentData.reduce((sum, d) => sum + parseFloat(d['Реклама (итого)'] || 0), 0);
    const fmt = (n) => new Intl.NumberFormat('ru-RU').format(Math.round(n)) + ' ₽';
    return {
      rev: fmt(totalRev),
      profit: fmt(totalProfit),
      margin: totalRev > 0 ? ((totalProfit / totalRev) * 100).toFixed(1) + '%' : '0%',
      roi: totalCost > 0 ? ((totalProfit / totalCost) * 100).toFixed(0) + '%' : '0%',
      ads: fmt(totalAds),
    };
  };

  const m = calculateMetrics();
  const metrics = [
    { label: 'Выручка', value: m.rev, trend: 'тек. период', icon: <TrendingUp className="text-emerald-400" /> },
    { label: 'Чистая прибыль', value: m.profit, trend: 'тек. период', icon: <DollarSign className="text-blue-400" /> },
    { label: 'Маржинальность', value: m.margin, trend: 'средняя', icon: <BarChart3 className="text-purple-400" /> },
    { label: 'Реклама', value: m.ads, trend: 'тек. период', icon: <Megaphone className="text-pink-400" /> },
  ];

  const getChartData = () => {
    const periods = [...new Set(data.map(d => d.Период))].slice(-6);
    const sum = (p, col) => data.filter(d => d.Период === p).reduce((s, d) => s + parseFloat(d[col] || 0), 0);
    return {
      labels: periods.map(p => p.split(' – ')[0]),
      datasets: [
        { label: 'Выручка',  data: periods.map(p => sum(p, 'Выручка')),        borderColor: '#3b82f6', backgroundColor: 'rgba(59,130,246,0.1)', fill: true, tension: 0.4 },
        { label: 'Прибыль',  data: periods.map(p => sum(p, 'Чистая_Прибыль')),  borderColor: '#10b981', backgroundColor: 'rgba(16,185,129,0.1)', fill: true, tension: 0.4 },
        { label: 'Реклама',  data: periods.map(p => sum(p, 'Реклама (итого)')), borderColor: '#ec4899', backgroundColor: 'rgba(236,72,153,0.05)', fill: true, tension: 0.4, borderDash: [4, 4] },
      ],
    };
  };

  const TABS = [
    { key: 'analytics', label: 'Аналитика', icon: <BarChart3 size={16} /> },
    { key: 'upload',    label: 'Загрузка файлов', icon: <Upload size={16} /> },
  ];

  return (
    <div className={`p-6 lg:p-10 max-w-[1600px] mx-auto space-y-8 transition-opacity duration-500 ${loading && activeTab === 'analytics' ? 'opacity-60' : 'opacity-100'}`}>

      {/* ── Header ── */}
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <h1 className="text-3xl font-bold gradient-text">Antigravity Analytics</h1>
          <p className="text-secondary mt-1">Интеллектуальный мониторинг маркетплейсов</p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {/* Селлер */}
          <div className="glass px-4 py-2 flex items-center gap-3">
            <ShoppingBag size={18} className="text-blue-400" />
            <select
              className="bg-transparent border-none text-white focus:outline-none cursor-pointer font-medium"
              value={activeSeller}
              onChange={(e) => setActiveSeller(e.target.value)}
            >
              {SELLERS.map(s => <option key={s} value={s}>Селлер: {s}</option>)}
            </select>
          </div>

          {/* Обновить (только на вкладке аналитики) */}
          {activeTab === 'analytics' && (
            <button
              onClick={() => { setIsSyncing(true); fetchData(); setTimeout(() => setIsSyncing(false), 1000); }}
              className={`glass px-5 py-2 flex items-center gap-2 font-semibold transition-all active:scale-95 ${isSyncing ? 'opacity-50' : 'hover:bg-white/10'}`}
            >
              <RefreshCcw size={16} className={isSyncing ? 'animate-spin' : ''} />
              {isSyncing ? 'Загрузка...' : 'Обновить'}
            </button>
          )}
        </div>
      </header>

      {/* ── Tabs ── */}
      <div className="flex gap-1 p-1 bg-white/5 rounded-xl w-fit">
        {TABS.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`
              flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold transition-all duration-200
              ${activeTab === tab.key
                ? 'bg-white/10 text-white shadow-lg'
                : 'text-white/40 hover:text-white/70'}
            `}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── Вкладка: Аналитика ── */}
      {activeTab === 'analytics' && (
        <>
          {/* Метрики */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {metrics.map((metric, i) => (
              <div key={i} className="glass p-6 card-hover space-y-4">
                <div className="flex items-center justify-between">
                  <div className="p-3 bg-white/5 rounded-xl">{metric.icon}</div>
                  <span className="text-xs font-medium text-secondary uppercase tracking-wider">{metric.trend}</span>
                </div>
                <div>
                  <p className="text-secondary text-sm font-medium">{metric.label}</p>
                  <p className="text-2xl font-bold mt-1 tracking-tight">{metric.value}</p>
                </div>
              </div>
            ))}
          </div>

          {/* График + ИИ */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-2 glass p-8 min-h-[400px] flex flex-col">
              <h2 className="text-xl font-bold flex items-center gap-2 mb-6">
                <BarChart3 className="text-blue-400" size={20} />
                Динамика: выручка, прибыль, реклама
              </h2>
              <div className="flex-1 relative">
                {!loading && data.length > 0 && (
                  <Line
                    data={getChartData()}
                    options={{
                      responsive: true,
                      maintainAspectRatio: false,
                      plugins: { legend: { labels: { color: 'rgba(255,255,255,0.5)', boxWidth: 12 } } },
                      scales: {
                        x: { ticks: { color: 'rgba(255,255,255,0.4)' }, grid: { color: 'rgba(255,255,255,0.03)' } },
                        y: { ticks: { color: 'rgba(255,255,255,0.4)' }, grid: { color: 'rgba(255,255,255,0.03)' } },
                      }
                    }}
                  />
                )}
                {!loading && data.length === 0 && (
                  <div className="flex items-center justify-center h-full text-white/30 text-sm">Нет данных</div>
                )}
              </div>
            </div>

            <div className="glass p-8 flex flex-col space-y-4">
              <div className="flex items-center gap-2">
                <BrainCircuit className="text-purple-400" size={22} />
                <h2 className="text-xl font-bold">ИИ Аналитика</h2>
              </div>
              <div className="flex-1 overflow-y-auto">
                <div className="p-4 rounded-xl bg-purple-500/10 border border-purple-500/20">
                  <p className="text-sm leading-relaxed text-secondary italic">
                    {insights || 'Данные анализируются... Обновите страницу через минуту.'}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Таблица артикулов */}
          <div className="glass overflow-hidden">
            <div className="p-8 border-b border-white/5">
              <h2 className="text-xl font-bold flex items-center gap-2">
                <Package className="text-emerald-400" size={20} />
                Детализация по артикулам (последний период)
              </h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="text-secondary text-sm font-medium bg-white/[0.02]">
                    <th className="px-8 py-4">Товар</th>
                    <th className="px-8 py-4">Артикул</th>
                    <th className="px-8 py-4">Выручка</th>
                    <th className="px-8 py-4">Реклама</th>
                    <th className="px-8 py-4">Прибыль</th>
                    <th className="px-8 py-4">Рентабельность</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {(() => {
                    const latestPeriod = data[data.length - 1]?.Период;
                    return data.filter(d => d.Период === latestPeriod).map((p, i) => {
                      const ads = parseFloat(p['Реклама (итого)'] || 0);
                      const margin = parseFloat(p['Рентабельность_%'] || 0);
                      return (
                        <tr key={i} className="hover:bg-white/[0.02] transition-colors">
                          <td className="px-8 py-5 font-medium truncate max-w-[280px]">{p.Название}</td>
                          <td className="px-8 py-5 text-secondary font-mono text-sm">{p.Артикул}</td>
                          <td className="px-8 py-5 font-semibold text-blue-400">{Math.round(p.Выручка || 0).toLocaleString()} ₽</td>
                          <td className="px-8 py-5 font-semibold text-pink-400">{ads > 0 ? `-${Math.round(ads).toLocaleString()} ₽` : '—'}</td>
                          <td className="px-8 py-5 font-semibold text-emerald-400">{Math.round(p['Чистая_Прибыль'] || 0).toLocaleString()} ₽</td>
                          <td className="px-8 py-5">
                            <span className={`px-2 py-1 rounded text-xs font-bold ${margin >= 0 ? 'bg-amber-500/10 text-amber-400' : 'bg-red-500/10 text-red-400'}`}>
                              {margin.toFixed(1)}%
                            </span>
                          </td>
                        </tr>
                      );
                    });
                  })()}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* ── Вкладка: Загрузка файлов ── */}
      {activeTab === 'upload' && (
        <UploadSection seller={activeSeller} />
      )}
    </div>
  );
}
