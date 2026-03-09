package main

import (
	"errors"
	"fmt"
	"log"
	"math/rand"
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

type CircuitBreaker struct {
	mu sync.Mutex
	consecutiveFailure int
	openUntil time.Time
}

func (cb *CircuitBreaker) Allow() bool {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	return time.Now().After(cb.openUntil)
}

func (cb *CircuitBreaker) RecordSuccess() {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	cb.consecutiveFailure = 0
	cb.openUntil = time.Time{}
}

func (cb *CircuitBreaker) RecordFailure() {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	cb.consecutiveFailure++
	if cb.consecutiveFailure >= 3 {
		cb.openUntil = time.Now().Add(10 * time.Second)
		cb.consecutiveFailure = 0
	}
}

func (cb *CircuitBreaker) State() string {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	if time.Now().Before(cb.openUntil) {
		return "open"
	}
	return "closed"
}

const (
	MaxResults = 20
)

var productStore sync.Map
var inventoryBreaker CircuitBreaker

func main() {
	var heavySem = make(chan struct{}, 2)
	generateProducts()

	r := gin.New()
	r.Use(gin.Recovery())
	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "ok"})
	})

	r.GET("/products/search/light", func(c *gin.Context) {
		searchProducts(c, 100, false)
	})
	r.GET("/products/search/heavy", func(c *gin.Context) {
		select {
		case heavySem <- struct{}{}:
			defer func() { <-heavySem }()
			searchProducts(c, 100000, false)
		default:
			c.JSON(http.StatusTooManyRequests, gin.H{
				"error": "heavy search capacity full",
			})
		}
})
	r.GET("/products/search/inventory", func(c *gin.Context) {
		searchProducts(c, 100, true)
	})
	r.Run(":8080")
}

func getInventoryWithProtection() (string, string) {
	if !inventoryBreaker.Allow() {
		return "inventory unavailable (circuit open)", inventoryBreaker.State()
	}

	status, err := fetchInventoryStatus()
	if err != nil {
		inventoryBreaker.RecordFailure()
		return "inventory unavailable", inventoryBreaker.State()
	}

	inventoryBreaker.RecordSuccess()
	return status, inventoryBreaker.State()
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

func searchProducts(c *gin.Context, MaxChecks int, fetchInventory bool) {
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
	if (fetchInventory) {
		getInventoryWithProtection()
		
	}

	log.Printf("search q=%q total_found=%d search_time=%s",
		query, totalFound, elapsed)

	resp := SearchResponse{
		Products:   results,
		TotalFound: totalFound,
		SearchTime: elapsed.String(),
	}

	c.JSON(http.StatusOK, resp)
}

func fetchInventoryStatus() (string, error) {
	// 70% chance of timeout
	if rand.Float32() < 0.70 { 
		time.Sleep(3 * time.Second) 
		return "", errors.New("timeout: third-party inventory service is unresponsive") 
	} 
	time.Sleep(50 * time.Millisecond) 
	return fmt.Sprintf("%d in stock", rand.Intn(100)), nil
}
