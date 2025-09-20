package models

import (
	"time"
)

// Stock represents a stock symbol and its basic information
type Stock struct {
	ID          uint      `json:"id" gorm:"primaryKey"`
	Symbol      string    `json:"symbol" gorm:"uniqueIndex;not null"`
	Name        string    `json:"name" gorm:"not null"`
	Exchange    string    `json:"exchange"`
	Sector      string    `json:"sector"`
	Industry    string    `json:"industry"`
	MarketCap   float64   `json:"market_cap"`
	CreatedAt   time.Time `json:"created_at"`
	UpdatedAt   time.Time `json:"updated_at"`
}

// StockPrice represents historical stock price data
type StockPrice struct {
	ID        uint      `json:"id" gorm:"primaryKey"`
	StockID   uint      `json:"stock_id" gorm:"not null"`
	Stock     Stock     `json:"stock" gorm:"foreignKey:StockID"`
	Date      time.Time `json:"date" gorm:"not null"`
	Open      float64   `json:"open"`
	High      float64   `json:"high"`
	Low       float64   `json:"low"`
	Close     float64   `json:"close"`
	Volume    int64     `json:"volume"`
	CreatedAt time.Time `json:"created_at"`
}

// StockQuote represents real-time stock quote
type StockQuote struct {
	Symbol           string    `json:"symbol"`
	Price            float64   `json:"price"`
	Change           float64   `json:"change"`
	ChangePercent    float64   `json:"change_percent"`
	Volume           int64     `json:"volume"`
	MarketCap        float64   `json:"market_cap"`
	PreviousClose    float64   `json:"previous_close"`
	LastUpdated      time.Time `json:"last_updated"`
} 