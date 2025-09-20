# Financial App Backend

A Go-based REST API backend for the Financial App, providing stock data and market information.

## Features

- RESTful API for stock data
- Real-time stock quotes
- Historical price data
- PostgreSQL database integration
- Docker support
- Clean architecture with separation of concerns

## Tech Stack

- **Language**: Go 1.23
- **Web Framework**: Gin
- **Database**: PostgreSQL with GORM
- **Authentication**: JWT (planned)
- **Containerization**: Docker

## Project Structure

```
backend/
├── cmd/server/          # Application entry point
├── internal/            # Private application code
│   ├── api/            # HTTP handlers and routes
│   ├── config/         # Configuration management
│   ├── models/         # Data models
│   ├── services/       # Business logic
│   └── repository/     # Data access layer
├── pkg/                # Public packages
│   └── database/       # Database connection
├── migrations/         # Database migrations
└── docs/              # API documentation
```

## Getting Started

### Prerequisites

- Go 1.21 or later
- PostgreSQL 13 or later
- Docker (optional)

### Installation

1. Clone the repository
2. Copy environment variables:
   ```bash
   cp .env.example .env
   ```
3. Update the `.env` file with your configuration
4. Install dependencies:
   ```bash
   go mod download
   ```
5. Run the application:
   ```bash
   go run cmd/server/main.go
   ```

### Using Docker

1. Build the image:
   ```bash
   docker build -t financial-app-backend .
   ```
2. Run the container:
   ```bash
   docker run -p 8080:8080 financial-app-backend
   ```

## API Endpoints

- `GET /health` - Health check
- `GET /api/v1/stocks` - List stocks
- `GET /api/v1/stocks/:symbol` - Get stock details
- `GET /api/v1/stocks/:symbol/quote` - Get real-time quote
- `GET /api/v1/stocks/:symbol/history` - Get historical data

## Development

### Running Tests

```bash
go test ./...
```

### Code Formatting

```bash
go fmt ./...
```

### Linting

```bash
golangci-lint run
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License. 