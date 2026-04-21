from locust import HttpUser, task, between, LoadTestShape
import json
import os
import random
import uuid
from pathlib import Path

TEST_MODE = os.getenv("TEST_MODE", "steady")   # steady | burst
CHANNEL_MODE = os.getenv("CHANNEL_MODE", "EMAIL")  # EMAIL | INAPP | MIXED

# steady mode
STEADY_USERS = int(os.getenv("STEADY_USERS", "20"))
STEADY_DURATION_SEC = int(os.getenv("STEADY_DURATION_SEC", "180"))

# burst mode
BASELINE_USERS = int(os.getenv("BASELINE_USERS", "20"))
BASELINE_DURATION_SEC = int(os.getenv("BASELINE_DURATION_SEC", "120"))
SPIKE_USERS = int(os.getenv("SPIKE_USERS", "100"))
SPIKE_DURATION_SEC = int(os.getenv("SPIKE_DURATION_SEC", "120"))
RECOVERY_DURATION_SEC = int(os.getenv("RECOVERY_DURATION_SEC", "180"))

# common
SPAWN_RATE = float(os.getenv("SPAWN_RATE", "5"))
MIN_WAIT = float(os.getenv("MIN_WAIT", "0.01"))
MAX_WAIT = float(os.getenv("MAX_WAIT", "0.05"))
PAYLOAD_BYTES = int(os.getenv("PAYLOAD_BYTES", "256"))
SAMPLED_NOTIFICATION_IDS_FILE = os.getenv("SAMPLED_NOTIFICATION_IDS_FILE", "").strip()
SAMPLED_NOTIFICATION_IDS_RATE = float(os.getenv("SAMPLED_NOTIFICATION_IDS_RATE", "0"))

if SAMPLED_NOTIFICATION_IDS_FILE:
    sample_path = Path(SAMPLED_NOTIFICATION_IDS_FILE)
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    sample_path.write_text("")
else:
    sample_path = None


def build_fixed_size_payload(target_bytes: int) -> dict:
    base = {
        "requestId": str(uuid.uuid4()),
        "message": "x"
    }
    current = json.dumps(base)
    pad_len = max(0, target_bytes - len(current))
    base["message"] = "x" * pad_len
    return base


class NotificationUser(HttpUser):
    wait_time = between(MIN_WAIT, MAX_WAIT)

    def on_start(self):
        self.tenant_ids = ["tenantA", "tenantB", "tenantC"]
        self.event_types = [
            "ORDER_CONFIRMED",
            "PASSWORD_RESET",
            "MARKETING_CAMPAIGN",
            "COMMENT_MENTION"
        ]

    def choose_channels(self):
        mode = CHANNEL_MODE.upper()
        if mode == "EMAIL":
            return ["EMAIL"]
        elif mode == "INAPP":
            return ["INAPP"]
        else:
            return random.choice([
                ["EMAIL"],
                ["INAPP"],
                ["EMAIL", "INAPP"]
            ])

    def maybe_record_sample(self, notification_id, channels):
        if sample_path is None or SAMPLED_NOTIFICATION_IDS_RATE <= 0:
            return
        if random.random() >= SAMPLED_NOTIFICATION_IDS_RATE:
            return
        with sample_path.open("a") as sample_file:
            sample_file.write(f"{notification_id},{'|'.join(channels)}\n")

    @task
    def create_notification(self):
        tenant_id = random.choice(self.tenant_ids)
        event_type = random.choice(self.event_types)
        user_id = f"user-{random.randint(1, 1000000)}"
        channels = self.choose_channels()

        payload = build_fixed_size_payload(PAYLOAD_BYTES)

        body = {
            "tenantId": tenant_id,
            "userId": user_id,
            "eventType": event_type,
            "channels": channels,
            "payloadJson": json.dumps(payload)
        }

        with self.client.post(
            "/notifications",
            json=body,
            name=f"POST /notifications [{CHANNEL_MODE}]",
            catch_response=True
        ) as response:
            if response.status_code != 202:
                response.failure(f"Unexpected status={response.status_code}, body={response.text}")
                return

            try:
                data = response.json()
                if "notificationId" not in data:
                    response.failure(f"Missing notificationId in response: {data}")
                else:
                    self.maybe_record_sample(data["notificationId"], channels)
                    response.success()
            except Exception as e:
                response.failure(f"Invalid JSON response: {e}, body={response.text}")


class ExperimentShape(LoadTestShape):
    def tick(self):
        run_time = self.get_run_time()

        if TEST_MODE == "steady":
            if run_time < STEADY_DURATION_SEC:
                return STEADY_USERS, SPAWN_RATE
            return None

        elif TEST_MODE == "burst":
            if run_time < BASELINE_DURATION_SEC:
                return BASELINE_USERS, SPAWN_RATE
            elif run_time < BASELINE_DURATION_SEC + SPIKE_DURATION_SEC:
                return SPIKE_USERS, SPAWN_RATE
            elif run_time < BASELINE_DURATION_SEC + SPIKE_DURATION_SEC + RECOVERY_DURATION_SEC:
                return BASELINE_USERS, SPAWN_RATE
            return None

        return None