package repository

import (
	"financial-app-backend/internal/models"

	"gorm.io/gorm"
)

type StockRepository struct {
	db *gorm.DB
}

func NewStockRepository(db *gorm.DB) *StockRepository {
	return &StockRepository{
		db: db,
	}
}

func (r *StockRepository) GetAll(limit int) ([]models.Stock, error) {
	var stocks []models.Stock
	err := r.db.Limit(limit).Find(&stocks).Error
	return stocks, err
}

func (r *StockRepository) GetBySymbol(symbol string) (*models.Stock, error) {
	var stock models.Stock
	err := r.db.Where("symbol = ?", symbol).First(&stock).Error
	if err != nil {
		return nil, err
	}
	return &stock, nil
}

func (r *StockRepository) GetByID(id uint) (*models.Stock, error) {
	var stock models.Stock
	err := r.db.First(&stock, id).Error
	if err != nil {
		return nil, err
	}
	return &stock, nil
}

func (r *StockRepository) Create(stock *models.Stock) error {
	return r.db.Create(stock).Error
}

func (r *StockRepository) Update(stock *models.Stock) error {
	return r.db.Save(stock).Error
}

func (r *StockRepository) Delete(id uint) error {
	return r.db.Delete(&models.Stock{}, id).Error
}

func (r *StockRepository) GetStockPrices(stockID uint, limit int) ([]models.StockPrice, error) {
	var prices []models.StockPrice
	err := r.db.Where("stock_id = ?", stockID).
		Order("date DESC").
		Limit(limit).
		Find(&prices).Error
	return prices, err
}

func (r *StockRepository) CreateStockPrice(price *models.StockPrice) error {
	return r.db.Create(price).Error
} 