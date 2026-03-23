package main

import (
	"context"
	"encoding/json"
	"log"
	"time"

	"github.com/aws/aws-lambda-go/events"
	"github.com/aws/aws-lambda-go/lambda"
)

type Item struct {
	SKU      string `json:"sku"`
	Quantity int    `json:"quantity"`
	Price    int    `json:"price"`
}

type Order struct {
	OrderID    string    `json:"order_id"`
	CustomerID int       `json:"customer_id"`
	Status     string    `json:"status"`
	Items      []Item    `json:"items"`
	CreatedAt  time.Time `json:"created_at"`
}

func handler(ctx context.Context, event events.SNSEvent) error {
	log.Printf("received %d SNS record(s)", len(event.Records))

	for _, record := range event.Records {
		var order Order
		if err := json.Unmarshal([]byte(record.SNS.Message), &order); err != nil {
			log.Printf("failed to unmarshal SNS message: %v", err)
			continue
		}

		log.Printf("start processing order_id=%s customer_id=%d", order.OrderID, order.CustomerID)

		// same 3-second payment processing delay
		time.Sleep(3 * time.Second)

		log.Printf("completed order_id=%s", order.OrderID)
	}

	return nil
}

func main() {
	lambda.Start(handler)
}