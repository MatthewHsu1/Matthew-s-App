# Financial App

A modern financial application with a Go backend and Next.js frontend for tracking stocks, managing portfolios, and viewing market data.

## 🏗️ Architecture

- **Backend**: Go REST API with PostgreSQL database
- **Frontend**: Next.js web application with TypeScript
- **Communication**: RESTful API with JSON
- **Deployment**: Docker containers with docker-compose

## 🚀 Features

### Backend (Go)
- RESTful API for stock data
- Real-time stock quotes
- Historical price data
- PostgreSQL database with GORM
- Clean architecture (handlers, services, repositories)
- Docker support
- Environment-based configuration

### Frontend (Next.js + TypeScript)
- Modern web application with server-side rendering
- TypeScript for type safety
- Tailwind CSS for styling
- Responsive design for all devices
- Real-time market data
- Dashboard with portfolio overview

## 📁 Project Structure

```
Financial App/
├── backend/                    # Go REST API
│   ├── cmd/server/            # Application entry point
│   ├── internal/              # Private application code
│   │   ├── api/handlers/      # HTTP handlers
│   │   ├── services/          # Business logic
│   │   ├── repository/        # Data access layer
│   │   ├── models/            # Data models
│   │   └── config/            # Configuration
│   ├── pkg/                   # Public packages
│   └── Dockerfile
│
├── frontend-nextjs/           # Next.js + TypeScript web app
│   ├── src/app/              # Next.js App Router pages
│   ├── src/components/       # Reusable UI components
│   ├── src/lib/              # API client and utilities
│   └── src/types/            # TypeScript type definitions
│
├── shared/                    # Shared resources
│   └── api-contracts/         # API schemas
│
├── docker-compose.yml         # Production setup
├── docker-compose.dev.yml     # Local development setup
└── README.md
```

## 🛠️ Tech Stack

### Backend
- **Language**: Go 1.21
- **Web Framework**: Gin
- **Database**: PostgreSQL with GORM ORM
- **Caching**: Redis (planned)
- **Authentication**: JWT (planned)
- **Testing**: Go testing package
- **Containerization**: Docker

### Frontend
- **Framework**: Next.js 14 with App Router
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Icons**: Lucide React
- **HTTP**: Axios with error handling
- **Testing**: Jest (planned)

## 🚀 Getting Started

### Prerequisites

- **Go**: 1.21 or later
- **Node.js**: 18 or later
- **PostgreSQL**: 13 or later
- **Docker**: (optional, for containerized development)

### Quick Start with Docker

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd Financial\ App
   ```

2. Start all services:
   ```bash
   docker-compose up -d
   ```

3. The application will be available at:
   - Frontend: `http://localhost:3000`
   - Backend API: `http://localhost:8080`

### Manual Setup

#### Backend Setup

1. Navigate to backend directory:
   ```bash
   cd backend
   ```

2. Copy environment file:
   ```bash
   cp .env.example .env
   ```

3. Update `.env` with your database configuration

4. Install dependencies:
   ```bash
   go mod download
   ```

5. Run the application:
   ```bash
   go run cmd/server/main.go
   ```

#### Frontend Setup

1. **Install Node.js 18+** from [nodejs.org](https://nodejs.org/)

2. Navigate to Next.js frontend directory:
   ```bash
   cd frontend-nextjs
   ```

3. Install dependencies:
   ```bash
   npm install
   ```

4. Run the development server:
   ```bash
   npm run dev
   ```

5. Open your browser to `http://localhost:3000`

## �� API Documentation

### Endpoints

- `GET /health` - Health check
- `GET /api/v1/stocks` - List stocks
- `GET /api/v1/stocks/:symbol` - Get stock details
- `GET /api/v1/stocks/:symbol/quote` - Get real-time quote
- `GET /api/v1/stocks/:symbol/history` - Get historical data

### Example Response

```json
{
  "data": {
    "symbol": "AAPL",
    "price": 150.25,
    "change": 2.50,
    "change_percent": 1.69,
    "volume": 1000000,
    "market_cap": 2500000000,
    "previous_close": 147.75,
    "last_updated": "2024-01-01T12:00:00Z"
  }
}
```

## 🧪 Testing

### Backend Tests
```bash
cd backend
go test ./...
```

### Frontend Tests
```bash
cd frontend-nextjs
npm test
```

## 🚀 Deployment

### Docker Deployment
```bash
# Development
docker-compose -f docker-compose.dev.yml up -d

# Production
docker-compose up -d
```

### Manual Deployment

#### Backend
```bash
cd backend
docker build -t financial-app-backend .
docker run -p 8080:8080 financial-app-backend
```

#### Frontend
```bash
cd frontend-nextjs
npm run build
npm start
```

## 🔧 Development

### Adding New Features

1. **Backend**: Add handlers → services → repositories
2. **Frontend**: Add components → pages → API calls
3. Update API contracts in `shared/api-contracts/`

### Code Style

- **Go**: Follow standard Go conventions, use `gofmt`
- **TypeScript**: Follow standard conventions, use ESLint/Prettier

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔮 Roadmap

- [ ] Real-time stock data integration (Alpha Vantage, Yahoo Finance)
- [ ] User authentication and authorization
- [ ] Portfolio management
- [ ] Watchlist functionality
- [ ] Advanced charting with technical indicators
- [ ] Push notifications for price alerts
- [ ] Dark/Light theme support
- [ ] Offline data caching
- [ ] Export functionality (PDF, CSV)
- [ ] Multi-language support

## 📞 Support

If you have questions or need help, please:

1. Check the documentation
2. Search existing issues
3. Create a new issue with detailed information

## 🙏 Acknowledgments

- [Gin Web Framework](https://gin-gonic.com/)
- [GORM](https://gorm.io/)
- [Next.js](https://nextjs.org/)
- [Lucide React](https://lucide-react.com/)
- [Tailwind CSS](https://tailwindcss.com/) 