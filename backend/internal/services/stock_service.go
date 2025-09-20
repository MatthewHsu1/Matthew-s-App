package services

import (
	"financial-app-backend/internal/models"
	"financial-app-backend/internal/repository"
)

type StockService struct {
	stockRepo *repository.StockRepository
}

func NewStockService(stockRepo *repository.StockRepository) *StockService {
	return &StockService{
		stockRepo: stockRepo,
	}
}

func (s *StockService) GetStocks(limit int) ([]models.Stock, error) {
	return s.stockRepo.GetAll(limit)
}

func (s *StockService) GetStockBySymbol(symbol string) (*models.Stock, error) {
	return s.stockRepo.GetBySymbol(symbol)
}

func (s *StockService) GetStockQuote(symbol string) (*models.StockQuote, error) {
	// TODO: Implement real-time quote fetching from external API
	// For now, return mock data
	quote := &models.StockQuote{
		Symbol:        symbol,
		Price:         150.25,
		Change:        2.50,
		ChangePercent: 1.69,
		Volume:        1000000,
		MarketCap:     2500000000,
		PreviousClose: 147.75,
	}
	return quote, nil
}

func (s *StockService) GetStockHistory(symbol string, period string) ([]models.StockPrice, error) {
	// TODO: Implement historical data fetching
	// For now, return empty slice
	return []models.StockPrice{}, nil
}

func (s *StockService) CreateStock(stock *models.Stock) error {
	return s.stockRepo.Create(stock)
}

func (s *StockService) UpdateStock(stock *models.Stock) error {
	return s.stockRepo.Update(stock)
}

func (s *StockService) DeleteStock(id uint) error {
	return s.stockRepo.Delete(id)
} 