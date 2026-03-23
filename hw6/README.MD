## Project Layout

structure:
.
├── api.yaml
├── main.go
├── go.mod / go.sum
├── Dockerfile
├── terraform/
│ ├── provider.tf
│ ├── variables.tf
│ ├── main.tf
│ ├── output.tf
│ └── modules/
└── README.md

## `GET /products/{productId}`

- Path param: `productId` is `int32`, `minimum: 1`
- Responses:
  - `200` → `Product`
  - `404` → `Error`
  - `500` → `Error`

## `POST /products/{productId}/details`

- Path param: `productId` is `int32`, `minimum: 1`
- Body: `Product` (all required fields must exist and satisfy constraints)
- Responses:
  - `204` → no body
  - `400` → `Error`
  - `404` → `Error`
  - `500` → `Error`

## `Product` schema (required + constraints)

Required fields:

- `product_id` (int32, min 1)
- `sku` (string, length 1..100)
- `manufacturer` (string, length 1..200)
- `category_id` (int32, min 1)
- `weight` (int32, min 0)
- `some_other_id` (int32, min 1)

---

## Run Locally (Go)

go run .

## Run on Docker

# Build image

docker build -t product-api:latest .

# Run container

docker run --rm -p 8080:8080 product-api:latest

---

## API Examples (All Response Codes)

# (1) GET — 200

curl -i http://localhost:8080/products/1

Expected:
Status: HTTP/1.1 200 OK
Body: Product JSON
{
"product_id": 1,
"sku": "ABC-123-888",
"manufacturer": "Hello Company",
"category_id": 456,
"weight": 678,
"some_other_id": 789
}

# (2) GET — 404

curl -i http://localhost:8080/products/999

Expected:
Status: HTTP/1.1 404 Not Found
Body: Error JSON
{
"error": "NOT_FOUND",
"message": "Product not found"
}

# (3) POST — 204

curl -i -X POST "http://localhost:8080/products/1/details" \
 -H "Content-Type: application/json" \
 -d '{
"product_id": 1,
"sku": "ABC-123-XYZ",
"manufacturer": "Acme Corporation",
"category_id": 456,
"weight": 1250,
"some_other_id": 789
}'

Expected:
Status: HTTP/1.1 204 No Content
No response body

# (4) POST — 400 (invalid input)

curl -i -X POST "http://localhost:8080/products/1/details" \
 -H "Content-Type: application/json" \
 -d '{
"product_id": 1,
"sku": "ABC-123-XYZ",
"manufacturer": "Acme Corporation",
"category_id": 456,
"some_other_id": 789
}'

Expected:
Status: HTTP/1.1 400 Bad Request
Body: Error JSON
{
"error": "INVALID_INPUT",
"message": "Invalid input data",
"details": "weight"
}

# (5) POST — 404 (product not found)

curl -i -X POST "http://localhost:8080/products/999/details" \
 -H "Content-Type: application/json" \
 -d '{
"product_id": 999,
"sku": "S",
"manufacturer": "M",
"category_id": 1,
"weight": 0,
"some_other_id": 1
}'

Expected:
Status: HTTP/1.1 404 Not Found
Body: Error JSON
{
"error": "NOT_FOUND",
"message": "Product not found"
}

# (6) 500 (internal server error)

If an unexpected internal error occurs, the server returns:
Status: HTTP/1.1 500 Internal Server Error
Body: Error JSON
{
"error": "INTERNAL_SERVER_ERROR",
"message": "Internal server error"
}
