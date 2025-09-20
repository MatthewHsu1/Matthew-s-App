package handlers

import (
	"net/http"
	"strconv"

	"financial-app-backend/internal/models"
	"financial-app-backend/internal/services"

	"github.com/gin-gonic/gin"
)

type StockHandler struct {
	stockService *services.StockService
}

func NewStockHandler(stockService *services.StockService) *StockHandler {
	return &StockHandler{
		stockService: stockService,
	}
}

// GetStocks returns a list of stocks
func (h *StockHandler) GetStocks(c *gin.Context) {
	// Parse query parameters
	limit := 50 // default
	if l := c.Query("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil {
			limit = parsed
		}
	}

	stocks, err := h.stockService.GetStocks(limit)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to fetch stocks",
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"data": stocks,
	})
}

// GetStock returns a specific stock by symbol
func (h *StockHandler) GetStock(c *gin.Context) {
	symbol := c.Param("symbol")
	if symbol == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Stock symbol is required",
		})
		return
	}

	stock, err := h.stockService.GetStockBySymbol(symbol)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{
			"error": "Stock not found",
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"data": stock,
	})
}

// GetStockQuote returns real-time quote for a stock
func (h *StockHandler) GetStockQuote(c *gin.Context) {
	symbol := c.Param("symbol")
	if symbol == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Stock symbol is required",
		})
		return
	}

	quote, err := h.stockService.GetStockQuote(symbol)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to fetch stock quote",
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"data": quote,
	})
}

// GetStockHistory returns historical price data
func (h *StockHandler) GetStockHistory(c *gin.Context) {
	symbol := c.Param("symbol")
	if symbol == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Stock symbol is required",
		})
		return
	}

	// Parse query parameters for date range
	period := c.DefaultQuery("period", "1y") // 1d, 5d, 1m, 3m, 6m, 1y, 2y, 5y, 10y, ytd, max

	history, err := h.stockService.GetStockHistory(symbol, period)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to fetch stock history",
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"data": history,
	})
} 