package main

import (
	"net/http"
	"strconv"
	"sync"

	"github.com/gin-gonic/gin"
)

type Product struct {
    ProductID int32  `json:"product_id"`
    SKU string `json:"sku"`
    Manufacturer string `json:"manufacturer"`
    CategoryID int32  `json:"category_id"`
    Weight int32  `json:"weight"`
    SomeOtherID int32  `json:"some_other_id"`
}

type ProductReq struct {
	ProductID    *int32  `json:"product_id"`
	SKU          *string `json:"sku"`
	Manufacturer *string `json:"manufacturer"`
	CategoryID   *int32  `json:"category_id"`
	Weight       *int32  `json:"weight"`
	SomeOtherID  *int32  `json:"some_other_id"`
}

type ErrorBody struct {
	Error string 
	Message string 
	Details string 
}

var (
	mu sync.RWMutex
	products = map[int32]Product{}
)

func main() {
	products[1] = Product{
		ProductID:    1,
		SKU:          "ABC-123-888",
		Manufacturer: "Hello Company",
		CategoryID:   456,
		Weight:       678,
		SomeOtherID:  789,
	}

	r := gin.New()
	r.Use(gin.CustomRecovery(func(c *gin.Context, recovered any) {
		c.AbortWithStatusJSON(http.StatusInternalServerError, ErrorBody{
			Error:   "INTERNAL_SERVER_ERROR",
			Message: "Internal server error",
		})
	}))

	r.GET("/products/:productId", getProduct)
	r.POST("/products", createProduct)
	r.POST("/products/:productId/details", addProductDetails)

	r.Run(":8080")
}

func createProduct(c *gin.Context) {
    var req Product
    if err := c.ShouldBindJSON(&req); err != nil {
        c.JSON(http.StatusBadRequest, ErrorBody{
            Error:   "INVALID INPUT",
        })
        return
    }

    mu.Lock()
    _, exists := products[req.ProductID]
    if exists {
        mu.Unlock()
        c.JSON(http.StatusBadRequest, ErrorBody{
            Error:   "INVALID INPUT",
            Message: "Invalid input data",
            Details: "product already exists",
        })
        return
    }

    products[req.ProductID] = req
    mu.Unlock()
    c.JSON(http.StatusCreated, req)
}

func getProduct(c *gin.Context) {
	id, _ := parseProductID(c.Param("productId"))

	mu.Lock()
	p, exists := products[id]
	mu.Unlock()

	if !exists {
		c.JSON(http.StatusNotFound, ErrorBody{
			Error:   "NOT FOUND",
		})
		return
	}

	c.JSON(http.StatusOK, p)
}

func addProductDetails(c *gin.Context) {
	id, ok := parseProductID(c.Param("productId"))
	if !ok {
		c.JSON(http.StatusBadRequest, ErrorBody{
			Error:   "INVALID INPUT",
		})
		return
	}

	var req ProductReq
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, ErrorBody{
			Error:   "INVALID INPUT",
		})
		return
	}

	p, message, ok := validateProductReq(req)
	if !ok {
		c.JSON(http.StatusBadRequest, ErrorBody{
			Error:   "INVALID INPUT",
			Message: "Invalid input data",
			Details: message,
		})
		return
	}

	if p.ProductID != id {
		c.JSON(http.StatusBadRequest, ErrorBody{
			Error:   "INVALID INPUT",
			Message: "Invalid input data",
			Details: "path productId must match body product_id",
		})
		return
	}

	mu.Lock()
	_, exists := products[id]
	if !exists {
		mu.Unlock()
		c.JSON(http.StatusNotFound, ErrorBody{
			Error:   "NOT FOUND",
			Message: "Product not found",
		})
		return
	}

	products[id] = p
	mu.Unlock()

	c.Status(http.StatusNoContent)
}

func parseProductID(raw string) (int32, bool) {
	v, err := strconv.ParseInt(raw, 10, 32)
	if err != nil || v < 1 {
		return 0, false
	}
	return int32(v), true
}

func validateProductReq(req ProductReq) (Product, string, bool) {
	if req.ProductID == nil {
		return Product{}, "product_id", false
	}
	if req.SKU == nil {
		return Product{}, "sku", false
	}
	if req.Manufacturer == nil {
		return Product{}, "manufacturer", false
	}
	if req.CategoryID == nil {
		return Product{}, "category_id", false
	}
	if req.Weight == nil {
		return Product{}, "weight", false
	}
	if req.SomeOtherID == nil {
		return Product{}, "some_other_id", false
	}

	if *req.ProductID < 1 {
		return Product{}, "product_id must be >= 1", false
	}
	if len(*req.SKU) < 1 || len(*req.SKU) > 100 {
		return Product{}, "sku length must be 1..100", false
	}
	if len(*req.Manufacturer) < 1 || len(*req.Manufacturer) > 200 {
		return Product{}, "manufacturer length must be 1..200", false
	}
	if *req.CategoryID < 1 {
		return Product{}, "category_id must be >= 1", false
	}
	if *req.Weight < 0 {
		return Product{}, "weight must be >= 0", false
	}
	if *req.SomeOtherID < 1 {
		return Product{}, "some_other_id must be >= 1", false
	}

	return Product{
		ProductID:    *req.ProductID,
		SKU:          *req.SKU,
		Manufacturer: *req.Manufacturer,
		CategoryID:   *req.CategoryID,
		Weight:       *req.Weight,
		SomeOtherID:  *req.SomeOtherID,
	}, "", true
}
