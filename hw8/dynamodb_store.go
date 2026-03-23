package main

import (
	"context"
	"errors"
	"os"
	"sort"
	"strconv"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/feature/dynamodb/attributevalue"
	"github.com/aws/aws-sdk-go-v2/service/dynamodb"
	dynamodbTypes "github.com/aws/aws-sdk-go-v2/service/dynamodb/types"
)

var ErrCartNotFound = errors.New("shopping cart not found")

type DynamoStore struct {
	client    *dynamodb.Client
	tableName string
}

type DynamoCart struct {
	CartID     int64          `dynamodbav:"cart_id"`
	CustomerID int64          `dynamodbav:"customer_id"`
	Items      map[string]int `dynamodbav:"items"`
	CreatedAt  string         `dynamodbav:"created_at"`
	UpdatedAt  string         `dynamodbav:"updated_at"`
}

func openDynamoStore(ctx context.Context) (*DynamoStore, error) {
	tableName := os.Getenv("DYNAMODB_TABLE")
	if tableName == "" {
		return nil, errors.New("missing DYNAMODB_TABLE")
	}

	cfg, err := config.LoadDefaultConfig(ctx)
	if err != nil {
		return nil, err
	}

	return &DynamoStore{
		client:    dynamodb.NewFromConfig(cfg),
		tableName: tableName,
	}, nil
}

func newNow() string {
	return time.Now().UTC().Format(time.RFC3339)
}

func newCartID() int64 {
	return time.Now().UTC().UnixNano()
}

func (s *DynamoStore) CreateCart(ctx context.Context, customerID int64) (*CartResponse, error) {
	now := newNow()
	cart := DynamoCart{
		CartID:     newCartID(),
		CustomerID: customerID,
		Items:      map[string]int{},
		CreatedAt:  now,
		UpdatedAt:  now,
	}

	item, err := attributevalue.MarshalMap(cart)
	if err != nil {
		return nil, err
	}

	_, err = s.client.PutItem(ctx, &dynamodb.PutItemInput{
		TableName: aws.String(s.tableName),
		Item:      item,
	})
	if err != nil {
		return nil, err
	}

	nowTime, err := time.Parse(time.RFC3339, now)
	if err != nil {
		return nil, err
	}

	return &CartResponse{
		ID:         cart.CartID,
		CustomerID: cart.CustomerID,
		Items:      []CartItem{},
		CreatedAt:  nowTime,
		UpdatedAt:  nowTime,
	}, nil
}

func (s *DynamoStore) GetCart(ctx context.Context, cartID int64) (*CartResponse, bool, error) {
	out, err := s.client.GetItem(ctx, &dynamodb.GetItemInput{
		TableName: aws.String(s.tableName),
		Key: map[string]dynamodbTypes.AttributeValue{
			"cart_id": &dynamodbTypes.AttributeValueMemberN{Value: strconv.FormatInt(cartID, 10)},
		},
	})
	if err != nil {
		return nil, false, err
	}
	if out.Item == nil {
		return nil, false, nil
	}

	var cart DynamoCart
	if err := attributevalue.UnmarshalMap(out.Item, &cart); err != nil {
		return nil, false, err
	}

	items := make([]CartItem, 0, len(cart.Items))
	for productID, qty := range cart.Items {
		pid, err := strconv.ParseInt(productID, 10, 64)
		if err != nil {
			return nil, false, err
		}
		items = append(items, CartItem{
			ProductID: pid,
			Quantity:  qty,
		})
	}
	sort.Slice(items, func(i, j int) bool {
		return items[i].ProductID < items[j].ProductID
	})

	createdAt, err := time.Parse(time.RFC3339, cart.CreatedAt)
	if err != nil {
		return nil, false, err
	}
	updatedAt, err := time.Parse(time.RFC3339, cart.UpdatedAt)
	if err != nil {
		return nil, false, err
	}

	return &CartResponse{
		ID:         cart.CartID,
		CustomerID: cart.CustomerID,
		Items:      items,
		CreatedAt:  createdAt,
		UpdatedAt:  updatedAt,
	}, true, nil
}

func (s *DynamoStore) AddOrUpdateItem(ctx context.Context, cartID int64, productID int64, quantity int) error {
	out, err := s.client.GetItem(ctx, &dynamodb.GetItemInput{
		TableName: aws.String(s.tableName),
		Key: map[string]dynamodbTypes.AttributeValue{
			"cart_id": &dynamodbTypes.AttributeValueMemberN{Value: strconv.FormatInt(cartID, 10)},
		},
	})
	if err != nil {
		return err
	}
	if out.Item == nil {
		return ErrCartNotFound
	}

	var cart DynamoCart
	if err := attributevalue.UnmarshalMap(out.Item, &cart); err != nil {
		return err
	}

	if cart.Items == nil {
		cart.Items = map[string]int{}
	}
	cart.Items[strconv.FormatInt(productID, 10)] = quantity
	cart.UpdatedAt = newNow()

	item, err := attributevalue.MarshalMap(cart)
	if err != nil {
		return err
	}

	_, err = s.client.PutItem(ctx, &dynamodb.PutItemInput{
		TableName:           aws.String(s.tableName),
		Item:                item,
		ConditionExpression: aws.String("attribute_exists(cart_id)"),
	})
	if err != nil {
		var conditionalErr *dynamodbTypes.ConditionalCheckFailedException
		if errors.As(err, &conditionalErr) {
			return ErrCartNotFound
		}
		return err
	}

	return nil
}
