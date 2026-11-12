"""Normal web traffic: mostly reading items, sometimes adding one, now and then the home page."""

import random

from locust import HttpUser, between, task

WORDS = ["apple", "book", "chair", "lamp", "pencil", "phone", "plant", "mug", "notebook", "bottle"]


class NormalUser(HttpUser):
    wait_time = between(2, 8)  # seconds a user "thinks" between actions

    @task(7)
    def read_items(self):
        self.client.get("/api/items")

    @task(2)
    def add_item(self):
        self.client.post("/api/items", json={"name": f"{random.choice(WORDS)} {random.randint(1, 999)}"})

    @task(1)
    def home_page(self):
        self.client.get("/")
