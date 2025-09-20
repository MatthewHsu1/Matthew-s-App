package main

import (
	"log"
	"net/http"

	"github.com/gin-gonic/gin"
)

func main() {
	// Initialize Gin router
	r := gin.Default()

	// Basic health check endpoint
	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"status":  "ok",
			"message": "Financial App Backend is running",
		})
	})

	// API v1 routes group
	v1 := r.Group("/api/v1")
	{
		v1.GET("/stocks", func(c *gin.Context) {
			c.JSON(http.StatusOK, gin.H{
				"message": "Stocks endpoint - coming soon",
			})
		})
	}

	// Start server on port 8080
	log.Println("Starting server on :8080")
	if err := r.Run(":8080"); err != nil {
		log.Fatal("Failed to start server:", err)
	}
} 