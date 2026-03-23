from locust import HttpUser, task, between
import uuid
from datetime import datetime, timezone


class OrderAsyncUser(HttpUser):
    # assignment spec: random 100-500ms between requests
    wait_time = between(0.1, 0.5)

    def build_order_payload(self):
        return {
            "order_id": str(uuid.uuid4()),
            "customer_id": 1001,
            "status": "pending",
            "items": [
                {
                    "sku": "sku-1",
                    "quantity": 1,
                    "price": 100
                }
            ],
            "created_at": datetime.now(timezone.utc).isoformat()
        }

    @task
    def create_order_async(self):
        payload = self.build_order_payload()

        with self.client.post(
            "/orders/async",
            json=payload,
            name="POST /orders/async",
            catch_response=True
        ) as response:
            if response.status_code != 202:
                response.failure(f"Expected 202, got {response.status_code}")