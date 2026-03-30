from locust import HttpUser, task, between
import json
import random
import uuid


class NotificationUser(HttpUser):
    wait_time = between(0.01, 0.05)

    def on_start(self):
        self.tenant_ids = ["tenantA", "tenantB", "tenantC"]
        self.user_prefix = "user"
        self.event_types = [
            "ORDER_CONFIRMED",
            "PASSWORD_RESET",
            "MARKETING_CAMPAIGN",
            "COMMENT_MENTION"
        ]
        self.channel_patterns = [
            ["EMAIL"],
            ["INAPP"],
            ["EMAIL", "INAPP"]
        ]

    def build_payload(self):
        tenant_id = random.choice(self.tenant_ids)
        event_type = random.choice(self.event_types)
        channels = random.choice(self.channel_patterns)
        user_id = f"{self.user_prefix}-{random.randint(1, 100000)}"

        business_payload = {
            "requestId": str(uuid.uuid4()),
            "eventType": event_type,
            "message": "test notification payload",
            "orderId": f"order-{random.randint(1, 100000)}",
            "amount": round(random.uniform(10, 500), 2)
        }

        return {
            "tenantId": tenant_id,
            "userId": user_id,
            "eventType": event_type,
            "channels": channels,
            "payloadJson": json.dumps(business_payload)
        }

    @task
    def create_notification(self):
        body = self.build_payload()

        with self.client.post(
                "/notifications",
                json=body,
                name="POST /notifications",
                catch_response=True
        ) as response:
            if response.status_code != 202:
                response.failure(
                    f"Unexpected status={response.status_code}, body={response.text}"
                )
            else:
                try:
                    data = response.json()
                    if "notificationId" not in data:
                        response.failure(f"Missing notificationId in response: {data}")
                    else:
                        response.success()
                except Exception as e:
                    response.failure(f"Invalid JSON response: {e}, body={response.text}")