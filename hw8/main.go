package main

import (
	"context"
	"encoding/json"
	"errors"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"
)

type Store interface {
	CreateCart(ctx context.Context, customerID int64) (*CartResponse, error)
	GetCart(ctx context.Context, cartID int64) (*CartResponse, bool, error)
	AddOrUpdateItem(ctx context.Context, cartID int64, productID int64, quantity int) error
}

type App struct {
	store Store
}

type ErrorResponse struct {
	Error   string `json:"error"`
	Message string `json:"message"`
	Details string `json:"details,omitempty"`
}

type CreateCartRequest struct {
	CustomerID int64 `json:"customer_id"`
}

type AddItemRequest struct {
	ProductID int64 `json:"product_id"`
	Quantity  int   `json:"quantity"`
}

type CartItem struct {
	ProductID int64 `json:"product_id"`
	Quantity  int   `json:"quantity"`
}

type CartResponse struct {
	ID         int64      `json:"id"`
	CustomerID int64      `json:"customer_id"`
	Items      []CartItem `json:"items"`
	CreatedAt  time.Time  `json:"created_at"`
	UpdatedAt  time.Time  `json:"updated_at"`
}

func main() {
	store, err := openDynamoStore(context.Background())
	if err != nil {
		log.Fatalf("open dynamodb store: %v", err)
	}

	app := &App{store: store}

	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			writeError(w, http.StatusMethodNotAllowed, "METHOD_NOT_ALLOWED", "method not allowed", "")
			return
		}

		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok"))
	})
	mux.HandleFunc("/shopping-carts", app.handleShoppingCarts)
	mux.HandleFunc("/shopping-carts/", app.handleShoppingCartByID)

	port := getEnv("PORT", "8080")
	server := &http.Server{
		Addr:         ":" + port,
		Handler:      loggingMiddleware(mux),
		ReadTimeout:  5 * time.Second,
		WriteTimeout: 10 * time.Second,
		IdleTimeout:  30 * time.Second,
	}

	log.Printf("server listening on :%s", port)
	log.Fatal(server.ListenAndServe())
}

func (a *App) handleShoppingCarts(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/shopping-carts" {
		writeError(w, http.StatusNotFound, "NOT_FOUND", "endpoint not found", "")
		return
	}

	switch r.Method {
	case http.MethodPost:
		a.createShoppingCart(w, r)
	default:
		writeError(w, http.StatusMethodNotAllowed, "METHOD_NOT_ALLOWED", "method not allowed", "")
	}
}

func (a *App) handleShoppingCartByID(w http.ResponseWriter, r *http.Request) {
	parts := strings.Split(strings.Trim(r.URL.Path, "/"), "/")

	if len(parts) < 2 || parts[0] != "shopping-carts" {
		writeError(w, http.StatusNotFound, "NOT_FOUND", "endpoint not found", "")
		return
	}

	cartID, err := strconv.ParseInt(parts[1], 10, 64)
	if err != nil || cartID <= 0 {
		writeError(w, http.StatusBadRequest, "INVALID_INPUT", "invalid cart id", "")
		return
	}

	if len(parts) == 2 && r.Method == http.MethodGet {
		a.getShoppingCart(w, r, cartID)
		return
	}

	if len(parts) == 3 && parts[2] == "items" && r.Method == http.MethodPost {
		a.addOrUpdateCartItem(w, r, cartID)
		return
	}

	writeError(w, http.StatusMethodNotAllowed, "METHOD_NOT_ALLOWED", "method not allowed", "")
}

func (a *App) createShoppingCart(w http.ResponseWriter, r *http.Request) {
	var req CreateCartRequest
	if err := decodeJSON(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, "INVALID_INPUT", "invalid request body", err.Error())
		return
	}
	if req.CustomerID <= 0 {
		writeError(w, http.StatusBadRequest, "INVALID_INPUT", "customer_id must be positive", "")
		return
	}

	ctx, cancel := context.WithTimeout(r.Context(), 3*time.Second)
	defer cancel()

	resp, err := a.store.CreateCart(ctx, req.CustomerID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "INTERNAL_ERROR", "failed to create shopping cart", err.Error())
		return
	}

	writeJSON(w, http.StatusCreated, resp)
}

func (a *App) getShoppingCart(w http.ResponseWriter, r *http.Request, cartID int64) {
	ctx, cancel := context.WithTimeout(r.Context(), 3*time.Second)
	defer cancel()

	resp, found, err := a.store.GetCart(ctx, cartID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "INTERNAL_ERROR", "failed to retrieve shopping cart", err.Error())
		return
	}
	if !found {
		writeError(w, http.StatusNotFound, "NOT_FOUND", "shopping cart not found", "")
		return
	}

	writeJSON(w, http.StatusOK, resp)
}

func (a *App) addOrUpdateCartItem(w http.ResponseWriter, r *http.Request, cartID int64) {
	var req AddItemRequest
	if err := decodeJSON(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, "INVALID_INPUT", "invalid request body", err.Error())
		return
	}
	if req.ProductID <= 0 {
		writeError(w, http.StatusBadRequest, "INVALID_INPUT", "product_id must be positive", "")
		return
	}
	if req.Quantity <= 0 {
		writeError(w, http.StatusBadRequest, "INVALID_INPUT", "quantity must be positive", "")
		return
	}

	ctx, cancel := context.WithTimeout(r.Context(), 3*time.Second)
	defer cancel()

	err := a.store.AddOrUpdateItem(ctx, cartID, req.ProductID, req.Quantity)
	if err != nil {
		if errors.Is(err, ErrCartNotFound) {
			writeError(w, http.StatusNotFound, "NOT_FOUND", "shopping cart not found", "")
			return
		}
		writeError(w, http.StatusInternalServerError, "INTERNAL_ERROR", "failed to add/update cart item", err.Error())
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

func decodeJSON(r *http.Request, dst any) error {
	defer r.Body.Close()

	decoder := json.NewDecoder(r.Body)
	decoder.DisallowUnknownFields()

	return decoder.Decode(dst)
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func writeError(w http.ResponseWriter, status int, code, message, details string) {
	writeJSON(w, status, ErrorResponse{
		Error:   code,
		Message: message,
		Details: details,
	})
}

func getEnv(key, fallback string) string {
	v := os.Getenv(key)
	if v == "" {
		return fallback
	}
	return v
}

func loggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		next.ServeHTTP(w, r)
		log.Printf("%s %s (%s)", r.Method, r.URL.Path, time.Since(start))
	})
}
