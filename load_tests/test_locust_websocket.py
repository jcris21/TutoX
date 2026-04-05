import json
import time

from locust import HttpUser, between, task
from websocket import create_connection


class WebSocketUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        """Setup WebSocket connection on start"""
        self.ws = create_connection(
            f"ws://{self.host.replace('http://', '')}/ws?user_login=test_user&db=test_db"
        )
        # Receive initial connection message
        self.ws.recv()

    def on_stop(self):
        """Clean up WebSocket connection"""
        self.ws.close()

    @task(3)
    def chat_message(self):
        """Send chat messages"""
        message = {
            "type": "chat",
            "message": "How do I create a sale order?",
            "context": {"model": "sale.order"},
        }
        start_time = time.time()
        self.ws.send(json.dumps(message))
        response = json.loads(self.ws.recv())

        # Record latency
        latency = (time.time() - start_time) * 1000
        if latency > 200:
            print(f"High latency detected: {latency}ms")

        self.environment.events.request.fire(
            request_type="WebSocket",
            name="chat_message",
            response_time=latency,
            response_length=len(json.dumps(response)),
            exception=None,
        )

    @task(2)
    def ui_event(self):
        """Send UI events"""
        event = {
            "type": "ui_event",
            "event_name": "button_click",
            "event_data": {"button_id": "create_order"},
        }
        start_time = time.time()
        self.ws.send(json.dumps(event))
        response = json.loads(self.ws.recv())

        latency = (time.time() - start_time) * 1000
        self.environment.events.request.fire(
            request_type="WebSocket",
            name="ui_event",
            response_time=latency,
            response_length=len(json.dumps(response)),
            exception=None,
        )
