package main

import (
	"fmt"
	"log"
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
)

type Product struct {
	ID          int    `json:"id"`
	Name        string `json:"name"`
	Category    string `json:"category"`
	Description string `json:"description"`
	Brand       string `json:"brand"`
}

type SearchResponse struct {
	Products   []Product `json:"products"`
	TotalFound int       `json:"total_found"`
	SearchTime string    `json:"search_time"`
}

const (
	MaxChecks = 100
	MaxResults = 20
)

var productStore sync.Map

func main() {
	generateProducts()

	r := gin.New()
	r.Use(gin.Recovery())
	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "ok"})
	})

	r.GET("/products/search/light", searchProducts)
	r.Run(":8080")
}

func generateProducts() {
	brands := []string{
		"Alpha", "Beta", "Gamma", "Delta", "Omega",
		"Nexus", "Vertex", "Nova", "Prime", "Apex",
	}
	categories := []string{
		"Electronics", "Books", "Home", "Beauty", "Sports",
		"Toys", "Clothing", "Garden", "Office", "Automotive",
	}
	descriptors := []string{
		"High quality", "Budget friendly", "Premium", "Compact", "Durable",
		"Lightweight", "Advanced", "Classic", "Popular", "New generation",
	}

	for i := range 100000 {
		brand := brands[i%len(brands)]
		category := categories[i%len(categories)]
		desc := descriptors[i%len(descriptors)]

		p := Product{
			ID: i,
			Name: "Product" + brand + fmt.Sprintf("%d", i),
			Category: category,
			Description: desc,
			Brand: brand,
		}

		productStore.Store(i, p)
	}
}

func searchProducts(c *gin.Context) {
	query := c.Query("q")
	queryLower := strings.ToLower(query)

	start := time.Now()

	results := make([]Product, 0, MaxResults)
	totalFound := 0

	for id := 0; id < MaxChecks; id++ {
		v, _ := productStore.Load(id)

		p := v.(Product)

		nameLower := strings.ToLower(p.Name)
		categoryLower := strings.ToLower(p.Category)

		matched := 
			strings.Contains(nameLower, queryLower) ||
			strings.Contains(categoryLower, queryLower)

		if matched {
			totalFound++
			if len(results) < MaxResults {
				results = append(results, p)
			}
		}
	}

	elapsed := time.Since(start)

	log.Printf("search q=%q total_found=%d search_time=%s",
		query, totalFound, elapsed)

	resp := SearchResponse{
		Products:   results,
		TotalFound: totalFound,
		SearchTime: elapsed.String(),
	}

	c.JSON(http.StatusOK, resp)
}
