import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'Financial App',
  description: 'Track stocks, manage portfolios, and view market data',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <div className="min-h-screen bg-gray-50">
          <nav className="bg-white shadow-sm border-b">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
              <div className="flex justify-between items-center h-16">
                <div className="flex items-center">
                  <h1 className="text-2xl font-bold text-primary-600">
                    Financial App
                  </h1>
                </div>
                <div className="flex space-x-8">
                  <a href="/" className="text-gray-900 hover:text-primary-600 px-3 py-2 text-sm font-medium">
                    Dashboard
                  </a>
                  <a href="/stocks" className="text-gray-900 hover:text-primary-600 px-3 py-2 text-sm font-medium">
                    Stocks
                  </a>
                  <a href="/portfolio" className="text-gray-900 hover:text-primary-600 px-3 py-2 text-sm font-medium">
                    Portfolio
                  </a>
                  <a href="/watchlist" className="text-gray-900 hover:text-primary-600 px-3 py-2 text-sm font-medium">
                    Watchlist
                  </a>
                </div>
              </div>
            </div>
          </nav>
          <main>{children}</main>
        </div>
      </body>
    </html>
  );
} 