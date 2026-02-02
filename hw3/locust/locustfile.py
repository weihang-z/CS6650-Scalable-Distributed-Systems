from locust import FastHttpUser, task, between

class ApiUser(FastHttpUser):

    @task(3)
    def get_health(self):
        self.client.get("/albums")

    @task(1)
    def post_example(self):
        payload = {    
            "id": "4",
            "title": "The Modern Sound of Betty Carter",
            "artist": "Betty Carter",
            "price": 49.99
            }

        self.client.post("/albums", json=payload)