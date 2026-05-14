'use client';

import React, { useState, useEffect } from 'react';
import { 
  TrendingUp, 
  DollarSign, 
  Package, 
  BarChart3, 
  BrainCircuit, 
  RefreshCcw, 
  ChevronRight,
  ExternalLink,
  ShoppingBag
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

export default function Dashboard() {
  const [activeSeller, setActiveSeller] = useState('Запакуй');
  const [isSyncing, setIsSyncing] = useState(false);
  const [data, setData] = useState([]);
  const [insights, setInsights] = useState("");
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
      console.error("Fetch error:", error);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchData();
  }, [activeSeller]);

  // Расчет метрик на лету на основе данных из таблицы
  const calculateMetrics = () => {
    if (!data.length) return { rev: '0 ₽', profit: '0 ₽', margin: '0%', roi: '0%' };
    
    // Берем данные последнего периода
    const latestPeriod = data[data.length - 1]?.Период;
    const currentData = data.filter(d => d.Период === latestPeriod);

    const totalRev = currentData.reduce((sum, d) => sum + parseFloat(d.Выручка || 0), 0);
    const totalProfit = currentData.reduce((sum, d) => sum + parseFloat(d.Чистая_Прибыль || 0), 0);
    const totalCost = currentData.reduce((sum, d) => sum + parseFloat(d.Себестоимость_Общая || 0), 0);

    return {
      rev: new Intl.NumberFormat('ru-RU').format(Math.round(totalRev)) + ' ₽',
      profit: new Intl.NumberFormat('ru-RU').format(Math.round(totalProfit)) + ' ₽',
      margin: totalRev > 0 ? ((totalProfit / totalRev) * 100).toFixed(1) + '%' : '0%',
      roi: totalCost > 0 ? ((totalProfit / totalCost) * 100).toFixed(0) + '%' : '0%'
    };
  };

  const m = calculateMetrics();
  const metrics = [
    { label: 'Выручка', value: m.rev, trend: 'тек. период', icon: <TrendingUp className="text-emerald-400" /> },
    { label: 'Чистая прибыль', value: m.profit, trend: 'тек. период', icon: <DollarSign className="text-blue-400" /> },
    { label: 'Маржинальность', value: m.margin, trend: 'средняя', icon: <BarChart3 className="text-purple-400" /> },
    { label: 'ROI', value: m.roi, trend: 'на вложения', icon: <Package className="text-amber-400" /> },
  ];

  // Подготовка данных для графика (группировка по периодам)
  const getChartData = () => {
    const periods = [...new Set(data.map(d => d.Период))].slice(-6); // последние 6 периодов
    const revData = periods.map(p => data.filter(d => d.Период === p).reduce((sum, d) => sum + parseFloat(d.Выручка || 0), 0));
    const profitData = periods.map(p => data.filter(d => d.Период === p).reduce((sum, d) => sum + parseFloat(d.Чистая_Прибыль || 0), 0));

    return {
      labels: periods.map(p => p.split(' – ')[0]), // берем только дату начала для краткости
      datasets: [
        {
          label: 'Выручка',
          data: revData,
          borderColor: '#005bff',
          backgroundColor: 'rgba(0, 91, 255, 0.1)',
          fill: true,
          tension: 0.4,
        },
        {
          label: 'Прибыль',
          data: profitData,
          borderColor: '#00e676',
          backgroundColor: 'rgba(0, 230, 118, 0.1)',
          fill: true,
          tension: 0.4,
        }
      ],
    };
  };

  return (
    <div className={`p-6 lg:p-10 max-w-[1600px] mx-auto space-y-8 transition-opacity duration-500 ${loading ? 'opacity-50' : 'opacity-100'}`}>
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <h1 className="text-3xl font-bold gradient-text">Antigravity Analytics</h1>
          <p className="text-secondary mt-1">Интеллектуальный мониторинг маркетплейсов</p>
        </div>

        <div className="flex items-center gap-4">
          <div className="glass px-4 py-2 flex items-center gap-3">
            <ShoppingBag size={18} className="text-blue-400" />
            <select 
              className="bg-transparent border-none text-white focus:outline-none cursor-pointer font-medium"
              value={activeSeller}
              onChange={(e) => setActiveSeller(e.target.value)}
            >
              <option value="Запакуй">Селлер: Запакуй</option>
              <option value="Ирвида">Селлер: Ирвида</option>
            </select>
          </div>

          <button 
            onClick={() => { setIsSyncing(true); fetchData(); setTimeout(() => setIsSyncing(false), 1000); }}
            className={`glass px-6 py-2 flex items-center gap-2 font-semibold transition-all active:scale-95 ${isSyncing ? 'opacity-50' : 'hover:bg-white/10'}`}
          >
            <RefreshCcw size={18} className={isSyncing ? 'animate-spin' : ''} />
            {isSyncing ? 'Загрузка...' : 'Обновить'}
          </button>
        </div>
      </header>

      {/* Metrics Grid */}
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 glass p-8 min-h-[450px] flex flex-col">
          <h2 className="text-xl font-bold flex items-center gap-2 mb-8">
            <BarChart3 className="text-blue-400" size={20} />
            Динамика прибыли
          </h2>
          <div className="flex-1 relative">
            {!loading && data.length > 0 && <Line data={getChartData()} options={{ responsive: true, maintainAspectRatio: false }} />}
          </div>
        </div>

        <div className="glass p-8 space-y-6 flex flex-col">
          <div className="flex items-center gap-2 mb-2">
            <BrainCircuit className="text-purple-400" size={24} />
            <h2 className="text-xl font-bold">ИИ Аналитика</h2>
          </div>
          <div className="flex-1 overflow-y-auto pr-2">
             <div className="p-4 rounded-xl bg-purple-500/10 border border-purple-500/20">
              <p className="text-sm leading-relaxed text-secondary italic">
                {insights || "Данные анализируются... Пожалуйста, обновите страницу через минуту."}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Таблица последних артикулов */}
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
                <th className="px-8 py-4">Прибыль</th>
                <th className="px-8 py-4">Рентабельность</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {data.slice(-10).map((p, i) => (
                <tr key={i} className="hover:bg-white/[0.02] transition-colors group">
                  <td className="px-8 py-5 font-medium truncate max-w-[300px]">{p.Название}</td>
                  <td className="px-8 py-5 text-secondary font-mono text-sm">{p.Артикул}</td>
                  <td className="px-8 py-5 font-semibold text-blue-400">{Math.round(p.Выручка || 0).toLocaleString()} ₽</td>
                  <td className="px-8 py-5 font-semibold text-emerald-400">{Math.round(p.Чистая_Прибыль || 0).toLocaleString()} ₽</td>
                  <td className="px-8 py-5">
                    <span className="px-2 py-1 rounded bg-amber-500/10 text-amber-500 text-xs font-bold">{p['Рентабельность_%']}%</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
