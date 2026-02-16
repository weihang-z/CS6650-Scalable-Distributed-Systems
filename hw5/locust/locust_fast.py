from locust import FastHttpUser, task, between

product_body = {
    "product_id": 1,
    "sku": "ABC-123-XYZ",
    "manufacturer": "Acme Corporation",
    "category_id": 456,
    "weight": 1250,
    "some_other_id": 789
}

class ApiUser(FastHttpUser):

    @task(3)
    def get_test(self):
        self.client.get(f"/products/1")

    @task(1)
    def post_detail(self):
        self.client.post("/products/1/details", json=product_body, headers={"Content-Type": "application/json"})