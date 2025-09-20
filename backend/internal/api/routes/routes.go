package routes

import (
	"financial-app-backend/internal/api/handlers"
	"financial-app-backend/internal/api/middleware"

	"github.com/gin-gonic/gin"
)

func SetupRoutes(r *gin.Engine, stockHandler *handlers.StockHandler) {
	// Add CORS middleware
	r.Use(middleware.CORS())

	// Health check endpoint
	r.GET("/health", func(c *gin.Context) {
		c.JSON(200, gin.H{
			"status":  "ok",
			"message": "Financial App Backend is running",
		})
	})

	// API v1 routes
	v1 := r.Group("/api/v1")
	{
		// Stock routes
		stocks := v1.Group("/stocks")
		{
			stocks.GET("", stockHandler.GetStocks)
			stocks.GET("/:symbol", stockHandler.GetStock)
			stocks.GET("/:symbol/quote", stockHandler.GetStockQuote)
			stocks.GET("/:symbol/history", stockHandler.GetStockHistory)
		}
	}
} 