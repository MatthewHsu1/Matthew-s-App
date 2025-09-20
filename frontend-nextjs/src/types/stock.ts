export interface Stock {
  symbol: string;
  price: number;
  change: number;
  change_percent: number;
  volume?: number;
  market_cap?: number;
  previous_close?: number;
  last_updated?: string;
}

export interface StockQuote {
  symbol: string;
  price: number;
  change: number;
  change_percent: number;
  volume: number;
  timestamp: string;
}

export interface StockHistory {
  symbol: string;
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface ApiResponse<T> {
  data: T;
  message?: string;
  status: string;
} 