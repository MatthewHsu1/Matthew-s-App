'use client';

import { useEffect, useState } from 'react';
import { Stock } from '@/types/stock';
import { getStocks, checkHealth } from '@/lib/api';
import StockCard from '@/components/StockCard';
import { Activity, TrendingUp, DollarSign, BarChart } from 'lucide-react';

export default function Dashboard() {
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [loading, setLoading] = useState(true);
  const [backendStatus, setBackendStatus] = useState<string>('checking');

  useEffect(() => {
    const loadData = async () => {
      try {
        // Check backend health
        const health = await checkHealth();
        setBackendStatus(health.status === 'ok' ? 'connected' : 'error');
      } catch (error) {
        setBackendStatus('disconnected');
      }

      try {
        // Load stocks
        const stockData = await getStocks();
        setStocks(stockData.slice(0, 4)); // Show top 4 stocks
      } catch (error) {
        console.error('Error loading stocks:', error);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, []);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'connected': return 'text-success';
      case 'disconnected': return 'text-danger';
      default: return 'text-yellow-500';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'connected': return 'Backend Connected';
      case 'disconnected': return 'Backend Disconnected';
      default: return 'Checking Backend...';
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Dashboard</h1>
        <div className="flex items-center">
          <div className={`flex items-center ${getStatusColor(backendStatus)}`}>
            <Activity size={16} className="mr-2" />
            <span className="text-sm font-medium">{getStatusText(backendStatus)}</span>
          </div>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <div className="bg-white rounded-lg shadow-md p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-500">Total Portfolio</p>
              <p className="text-2xl font-bold text-gray-900">$12,450.00</p>
            </div>
            <DollarSign className="h-8 w-8 text-primary-500" />
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-md p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-500">Day Change</p>
              <p className="text-2xl font-bold text-success">+$245.60</p>
            </div>
            <TrendingUp className="h-8 w-8 text-success" />
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-md p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-500">Total Stocks</p>
              <p className="text-2xl font-bold text-gray-900">{stocks.length}</p>
            </div>
            <BarChart className="h-8 w-8 text-primary-500" />
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-md p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-500">Watchlist</p>
              <p className="text-2xl font-bold text-gray-900">8</p>
            </div>
            <Activity className="h-8 w-8 text-primary-500" />
          </div>
        </div>
      </div>

      {/* Top Stocks */}
      <div className="mb-8">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-2xl font-bold text-gray-900">Top Stocks</h2>
          <a 
            href="/stocks" 
            className="text-primary-600 hover:text-primary-700 font-medium"
          >
            View All →
          </a>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="bg-white rounded-lg shadow-md p-6 animate-pulse">
                <div className="h-4 bg-gray-200 rounded mb-4"></div>
                <div className="h-8 bg-gray-200 rounded mb-2"></div>
                <div className="h-4 bg-gray-200 rounded"></div>
              </div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {stocks.map((stock) => (
              <StockCard 
                key={stock.symbol} 
                stock={stock}
                onClick={() => window.location.href = `/stocks/${stock.symbol}`}
              />
            ))}
          </div>
        )}
      </div>

      {/* Quick Actions */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Quick Actions</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <button className="bg-primary-600 text-white px-4 py-2 rounded-md hover:bg-primary-700 transition-colors">
            Add to Portfolio
          </button>
          <button className="bg-gray-200 text-gray-800 px-4 py-2 rounded-md hover:bg-gray-300 transition-colors">
            View Market News
          </button>
          <button className="bg-gray-200 text-gray-800 px-4 py-2 rounded-md hover:bg-gray-300 transition-colors">
            Analyze Trends
          </button>
        </div>
      </div>
    </div>
  );
} 