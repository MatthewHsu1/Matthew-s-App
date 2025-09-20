# Financial App Frontend (Next.js + TypeScript)

A modern web frontend for the Financial App built with Next.js, TypeScript, and Tailwind CSS.

## Features

- 📊 **Dashboard**: Overview of market data and portfolio performance
- 📈 **Stock List**: Browse and search available stocks with filtering
- 🔍 **Real-time Data**: Connect to Go backend API for live stock data
- 📱 **Responsive Design**: Works on desktop, tablet, and mobile
- ⚡ **Fast Performance**: Server-side rendering with Next.js
- 🎨 **Modern UI**: Clean design with Tailwind CSS
- 🔒 **Type Safety**: Full TypeScript integration

## Tech Stack

- **Framework**: Next.js 14 with App Router
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Icons**: Lucide React
- **HTTP Client**: Axios
- **Charts**: Recharts (planned)

## Getting Started

### Prerequisites

- Node.js 18+ 
- npm or yarn
- Go backend running on `http://localhost:8080`

### Installation

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Run the development server:**
   ```bash
   npm run dev
   ```

3. **Open your browser:**
   - Navigate to `http://localhost:3000`
   - The app will connect to your Go backend automatically

### Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run start` - Start production server
- `npm run lint` - Run ESLint
- `npm run type-check` - Run TypeScript checks

## Project Structure

```
src/
├── app/                    # Next.js App Router pages
│   ├── layout.tsx         # Root layout with navigation
│   ├── page.tsx           # Dashboard page
│   ├── stocks/            # Stock-related pages
│   ├── portfolio/         # Portfolio page
│   └── watchlist/         # Watchlist page
├── components/            # Reusable UI components
│   └── StockCard.tsx     # Stock display component
├── lib/                  # Utility functions
│   └── api.ts            # API client for Go backend
└── types/                # TypeScript type definitions
    └── stock.ts          # Stock data interfaces
```

## API Integration

The frontend connects to your Go backend at `http://localhost:8080/api/v1/`:

- `GET /health` - Backend health check
- `GET /stocks` - List all stocks
- `GET /stocks/:symbol` - Get specific stock
- `GET /stocks/:symbol/quote` - Get real-time quote
- `GET /stocks/:symbol/history` - Get historical data

## Features Overview

### Dashboard
- Backend connection status indicator
- Portfolio overview with key metrics
- Top performing stocks
- Quick action buttons

### Stock List
- Search stocks by symbol
- Sort by symbol, price, or change
- Responsive grid layout
- Click to view stock details

### Mock Data
If the backend is unavailable, the app shows mock data for development:
- AAPL, GOOGL, MSFT, TSLA sample stocks
- Realistic price and change data

## Development

### Backend Connection
The app expects your Go backend to be running on `http://localhost:8080`. Make sure to:

1. Start your Go backend first:
   ```bash
   cd ../backend
   docker-compose up -d
   ```

2. Verify backend is running:
   ```bash
   curl http://localhost:8080/health
   ```

3. Then start the frontend:
   ```bash
   npm run dev
   ```

### Adding New Features

1. **New Pages**: Add to `src/app/` directory
2. **Components**: Add to `src/components/`
3. **API Calls**: Add to `src/lib/api.ts`
4. **Types**: Add to `src/types/`

## Deployment

### Production Build
```bash
npm run build
npm run start
```

### Docker (Optional)
```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
```

## Customization

### Styling
- Modify `tailwind.config.js` for theme customization
- Update `src/app/globals.css` for global styles
- Colors are defined in the Tailwind config

### API Endpoint
- Update `API_BASE_URL` in `src/lib/api.ts` if backend URL changes

## Contributing

1. Follow TypeScript best practices
2. Use Tailwind for styling
3. Add proper error handling
4. Include loading states
5. Make components responsive

## License

MIT License - see the main project README for details. 