import axios from 'axios';
import { Stock, StockQuote, StockHistory, ApiResponse } from '@/types/stock';

const API_BASE_URL = 'http://localhost:8080/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Health check
export const checkHealth = async (): Promise<{ status: string; message: string }> => {
  const response = await api.get('/health');
  return response.data;
};

// Stock API functions
export const getStocks = async (): Promise<Stock[]> => {
  try {
    const response = await api.get('/stocks');
    return response.data.data || [];
  } catch (error) {
    console.error('Error fetching stocks:', error);
    // Return mock data if backend is not available
    return getMockStocks();
  }
};

export const getStock = async (symbol: string): Promise<Stock> => {
  try {
    const response = await api.get(`/stocks/${symbol}`);
    return response.data.data;
  } catch (error) {
    console.error(`Error fetching stock ${symbol}:`, error);
    throw error;
  }
};

export const getStockQuote = async (symbol: string): Promise<StockQuote> => {
  try {
    const response = await api.get(`/stocks/${symbol}/quote`);
    return response.data.data;
  } catch (error) {
    console.error(`Error fetching quote for ${symbol}:`, error);
    throw error;
  }
};

export const getStockHistory = async (symbol: string): Promise<StockHistory[]> => {
  try {
    const response = await api.get(`/stocks/${symbol}/history`);
    return response.data.data;
  } catch (error) {
    console.error(`Error fetching history for ${symbol}:`, error);
    throw error;
  }
};

// Mock data for development
const getMockStocks = (): Stock[] => [
  {
    symbol: 'AAPL',
    price: 150.25,
    change: 2.50,
    change_percent: 1.69,
    volume: 1000000,
    market_cap: 2500000000,
    previous_close: 147.75,
    last_updated: new Date().toISOString(),
  },
  {
    symbol: 'GOOGL',
    price: 2750.80,
    change: -15.20,
    change_percent: -0.55,
    volume: 800000,
    market_cap: 1800000000,
    previous_close: 2766.00,
    last_updated: new Date().toISOString(),
  },
  {
    symbol: 'MSFT',
    price: 305.15,
    change: 3.75,
    change_percent: 1.24,
    volume: 1200000,
    market_cap: 2300000000,
    previous_close: 301.40,
    last_updated: new Date().toISOString(),
  },
  {
    symbol: 'TSLA',
    price: 245.60,
    change: -8.90,
    change_percent: -3.50,
    volume: 2500000,
    market_cap: 780000000,
    previous_close: 254.50,
    last_updated: new Date().toISOString(),
  },
]; 