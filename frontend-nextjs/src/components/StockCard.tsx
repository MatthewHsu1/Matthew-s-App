'use client';

import { Stock } from '@/types/stock';
import { TrendingUp, TrendingDown } from 'lucide-react';

interface StockCardProps {
  stock: Stock;
  onClick?: () => void;
}

export default function StockCard({ stock, onClick }: StockCardProps) {
  const isPositive = stock.change >= 0;
  const changeColor = isPositive ? 'text-success' : 'text-danger';
  const IconComponent = isPositive ? TrendingUp : TrendingDown;

  return (
    <div 
      className="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow cursor-pointer border border-gray-200"
      onClick={onClick}
    >
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="text-xl font-bold text-gray-900">{stock.symbol}</h3>
          <p className="text-2xl font-semibold text-gray-800">${stock.price.toFixed(2)}</p>
        </div>
        <div className={`flex items-center ${changeColor}`}>
          <IconComponent size={20} className="mr-1" />
          <span className="font-semibold">
            {isPositive ? '+' : ''}{stock.change.toFixed(2)}
          </span>
        </div>
      </div>
      
      <div className="flex justify-between items-end">
        <div className={`${changeColor}`}>
          <span className="text-sm font-medium">
            {isPositive ? '+' : ''}{stock.change_percent.toFixed(2)}%
          </span>
        </div>
        {stock.volume && (
          <div className="text-right">
            <p className="text-xs text-gray-500">Volume</p>
            <p className="text-sm font-medium text-gray-700">
              {stock.volume.toLocaleString()}
            </p>
          </div>
        )}
      </div>
    </div>
  );
} 