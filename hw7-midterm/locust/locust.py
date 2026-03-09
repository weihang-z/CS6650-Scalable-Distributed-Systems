import random
from locust import FastHttpUser, task


search_terms = [
    "electronics",
    "books",
    "home",
    "alpha",
    "beta",
    "product"
]

class ApiUser(FastHttpUser):

    @task(5)
    def search_products_light(self):
        q = random.choice(search_terms)
        self.client.get(f"/products/search/light?q={q}")

    @task(2)
    def search_products_inventory(self):
        q = random.choice(search_terms)
        self.client.get(f"/products/search/inventory?q={q}")
