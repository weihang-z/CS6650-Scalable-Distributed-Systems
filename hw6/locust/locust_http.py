from random import random
from locust import HttpUser, task, between


search_terms = [
    "electronics",
    "books",
    "home",
    "alpha",
    "beta",
    "product"
]

class ApiUser(HttpUser):

    @task(3)
    def search_products(self):
        q = random.choice(search_terms)
        self.client.get(f"/products/search?q={q}")
