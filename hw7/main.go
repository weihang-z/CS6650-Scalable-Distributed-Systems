package main

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"os"
	"strconv"
	"sync"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	snsSvc "github.com/aws/aws-sdk-go-v2/service/sns"
	sqsSvc "github.com/aws/aws-sdk-go-v2/service/sqs"
	sqsTypes "github.com/aws/aws-sdk-go-v2/service/sqs/types"
)

type Item struct {
	SKU      string `json:"sku"`
	Quantity int    `json:"quantity"`
	Price    int    `json:"price"`
}

type Order struct {
	OrderID    string    `json:"order_id"`
	CustomerID int       `json:"customer_id"`
	Status     string    `json:"status"` // pending, processing, completed
	Items      []Item    `json:"items"`
	CreatedAt  time.Time `json:"created_at"`
}

// Simulate a bottlenecked synchronous payment processor.
// Capacity = 1 means only one order can be processed at a time.
var paymentSlots = make(chan struct{}, 1)

type ReceiverServer struct {
	snsClient *snsSvc.Client
	topicARN  string
}

func main() {
	mode := os.Getenv("APP_MODE")
	if mode == "" {
		log.Fatal("APP_MODE is required and must be either 'receiver' or 'processor'")
	}

	ctx := context.Background()

	awsCfg, err := config.LoadDefaultConfig(ctx)
	if err != nil {
		log.Fatalf("failed to load AWS config: %v", err)
	}

	switch mode {
	case "receiver":
		runReceiver(awsCfg)
	case "processor":
		runProcessor(ctx, awsCfg)
	default:
		log.Fatalf("invalid APP_MODE: %s", mode)
	}
}

func runReceiver(awsCfg aws.Config) {
	topicARN := os.Getenv("ORDER_EVENTS_TOPIC_ARN")
	if topicARN == "" {
		log.Fatal("ORDER_EVENTS_TOPIC_ARN is required in receiver mode")
	}

	server := &ReceiverServer{
		snsClient: snsSvc.NewFromConfig(awsCfg),
		topicARN:  topicARN,
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/health", healthHandler)
	mux.HandleFunc("/orders/sync", syncOrderHandler)
	mux.HandleFunc("/orders/async", server.asyncOrderHandler)

	httpServer := &http.Server{
		Addr:              ":8080",
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,
	}

	log.Println("receiver listening on :8080")
	log.Fatal(httpServer.ListenAndServe())
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	writeJSON(w, http.StatusOK, map[string]any{
		"status": "ok",
		"mode":   "receiver",
	})
}

func syncOrderHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	order, err := decodeAndValidateOrder(r)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	order.Status = "processing"

	// Acquire the single payment slot.
	paymentSlots <- struct{}{}

	// Simulate the 3-second bottleneck.
	time.Sleep(3 * time.Second)

	// Release the payment slot.
	<-paymentSlots

	order.Status = "completed"

	writeJSON(w, http.StatusOK, order)
}

func (s *ReceiverServer) asyncOrderHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	order, err := decodeAndValidateOrder(r)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	// Important: async endpoint only accepts and enqueues the order.
	// It does NOT process payment on the request path.
	order.Status = "pending"

	messageBody, err := json.Marshal(order)
	if err != nil {
		http.Error(w, "failed to serialize order", http.StatusInternalServerError)
		return
	}

	_, err = s.snsClient.Publish(r.Context(), &snsSvc.PublishInput{
		TopicArn: aws.String(s.topicARN),
		Message:  aws.String(string(messageBody)),
	})
	if err != nil {
		log.Printf("failed to publish order %s to SNS: %v", order.OrderID, err)
		http.Error(w, "failed to enqueue order", http.StatusInternalServerError)
		return
	}

	writeJSON(w, http.StatusAccepted, map[string]any{
		"order_id":    order.OrderID,
		"customer_id": order.CustomerID,
		"status":      "accepted",
		"message":     "order accepted for asynchronous processing",
		"created_at":  order.CreatedAt,
	})
}

// -------- processor mode --------

func runProcessor(ctx context.Context, awsCfg aws.Config) {
	queueURL := os.Getenv("ORDER_PROCESSING_QUEUE_URL")
	if queueURL == "" {
		log.Fatal("ORDER_PROCESSING_QUEUE_URL is required in processor mode")
	}

	workerCount := getWorkerCount()
	sqsClient := sqsSvc.NewFromConfig(awsCfg)

	log.Printf("processor started with WORKER_COUNT=%d", workerCount)

	for {
		receiveOutput, err := sqsClient.ReceiveMessage(ctx, &sqsSvc.ReceiveMessageInput{
			QueueUrl:            aws.String(queueURL),
			MaxNumberOfMessages: 100,
			WaitTimeSeconds:     20,
			VisibilityTimeout:   30,
		})
		if err != nil {
			log.Printf("failed to receive messages from SQS: %v", err)
			time.Sleep(2 * time.Second)
			continue
		}

		if len(receiveOutput.Messages) == 0 {
			continue
		}

		log.Printf("received %d message(s) from queue", len(receiveOutput.Messages))

		// Limit concurrency inside this single ECS task.
		workerLimiter := make(chan struct{}, workerCount)
		var wg sync.WaitGroup

		for _, msg := range receiveOutput.Messages {
			msg := msg

			wg.Add(1)
			workerLimiter <- struct{}{}

			go func() {
				defer wg.Done()
				defer func() { <-workerLimiter }()

				if err := processOneMessage(ctx, sqsClient, queueURL, msg); err != nil {
					log.Printf("failed to process message: %v", err)
				}
			}()
		}

		wg.Wait()
	}
}

func processOneMessage(
	ctx context.Context,
	sqsClient *sqsSvc.Client,
	queueURL string,
	msg sqsTypes.Message,
) error {
	if msg.Body == nil {
		log.Printf("skipping message with empty body")
		return nil
	}

	var order Order
	if err := json.Unmarshal([]byte(*msg.Body), &order); err != nil {
		log.Printf("failed to unmarshal message body: %v; body=%s", err, *msg.Body)

		return err
	}

	log.Printf("processing order_id=%s customer_id=%d", order.OrderID, order.CustomerID)

	order.Status = "processing"

	// Simulate 3-second payment verification in the background worker.
	time.Sleep(3 * time.Second)

	order.Status = "completed"

	// In this assignment baseline, successful processing means deleting the message.
	_, err := sqsClient.DeleteMessage(ctx, &sqsSvc.DeleteMessageInput{
		QueueUrl:      aws.String(queueURL),
		ReceiptHandle: msg.ReceiptHandle,
	})
	if err != nil {
		return err
	}

	log.Printf("completed order_id=%s and deleted message from queue", order.OrderID)
	return nil
}


func decodeAndValidateOrder(r *http.Request) (Order, error) {
	var order Order

	if err := json.NewDecoder(r.Body).Decode(&order); err != nil {
		return Order{}, err
	}

	if order.OrderID == "" {
		return Order{}, errString("order_id is required")
	}

	if order.CustomerID == 0 {
		return Order{}, errString("customer_id is required")
	}

	if len(order.Items) == 0 {
		return Order{}, errString("items must not be empty")
	}

	if order.CreatedAt.IsZero() {
		order.CreatedAt = time.Now().UTC()
	}

	return order, nil
}

func getWorkerCount() int {
	raw := os.Getenv("WORKER_COUNT")
	if raw == "" {
		return 1
	}

	n, err := strconv.Atoi(raw)
	if err != nil || n <= 0 {
		log.Printf("invalid WORKER_COUNT=%q, defaulting to 1", raw)
		return 1
	}

	return n
}

func writeJSON(w http.ResponseWriter, statusCode int, value any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(statusCode)

	if err := json.NewEncoder(w).Encode(value); err != nil {
		log.Printf("failed to encode JSON response: %v", err)
	}
}

type errString string

func (e errString) Error() string {
	return string(e)
}