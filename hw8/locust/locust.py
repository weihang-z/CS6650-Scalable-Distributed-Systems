import json
import os
from datetime import datetime, timezone

from locust import HttpUser, task, constant

RESULTS_FILE = os.getenv("RESULTS_FILE", "mysql_test_results.json")


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ShoppingCartUser(HttpUser):
    # Force exactly one Locust user, so request counts stay deterministic.
    fixed_count = 1
    wait_time = constant(0)

    def on_start(self):
        self.results = []
        self.created_cart_ids = []

        self.run_create_phase()
        self.run_add_phase()
        self.run_get_phase()

        with open(RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2)

        # Stop the run automatically after the 150 operations are done.
        self.environment.runner.quit()

    @task
    def idle(self):
        # on_start already does all the work.
        pass

    def record_result(self, operation, response, success):
        self.results.append(
            {
                "operation": operation,
                "response_time": round(response.elapsed.total_seconds() * 1000, 2),
                "success": success,
                "status_code": response.status_code,
                "timestamp": utc_now_iso(),
            }
        )

    def run_create_phase(self):
        for i in range(50):
            payload = {"customer_id": i + 1}

            with self.client.post(
                "/shopping-carts",
                json=payload,
                name="create_cart",
                catch_response=True,
            ) as response:
                success = response.status_code == 201

                if success:
                    try:
                        data = response.json()
                        cart_id = data.get("id") or data.get("shopping_cart_id")
                        if cart_id is not None:
                            self.created_cart_ids.append(int(cart_id))
                    except Exception:
                        pass
                    response.success()
                else:
                    response.failure(f"expected 201, got {response.status_code}")

                self.record_result("create_cart", response, success)

    def run_add_phase(self):
        cart_ids = self.created_cart_ids if self.created_cart_ids else [1]

        for i in range(50):
            cart_id = cart_ids[i % len(cart_ids)]
            payload = {
                "product_id": 1000 + i,
                "quantity": 1 + (i % 3),
            }

            with self.client.post(
                f"/shopping-carts/{cart_id}/items",
                json=payload,
                name="add_items",
                catch_response=True,
            ) as response:
                success = response.status_code == 204

                if success:
                    response.success()
                else:
                    response.failure(f"expected 204, got {response.status_code}")

                self.record_result("add_items", response, success)

    def run_get_phase(self):
        cart_ids = self.created_cart_ids if self.created_cart_ids else [1]

        for i in range(50):
            cart_id = cart_ids[i % len(cart_ids)]

            with self.client.get(
                f"/shopping-carts/{cart_id}",
                name="get_cart",
                catch_response=True,
            ) as response:
                success = response.status_code == 200

                if success:
                    response.success()
                else:
                    response.failure(f"expected 200, got {response.status_code}")

                self.record_result("get_cart", response, success)