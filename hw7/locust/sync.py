from locust import HttpUser, task, between
import uuid
from datetime import datetime, timezone

class OrderSyncUser(HttpUser):
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
    def create_order_sync(self):
        payload = self.build_order_payload()

        self.client.post(
            "/orders/sync",
            json=payload,
            name="POST /orders/sync"
        )