import json
import socket
import logging


class Client:
    def __init__(self, host="localhost", port=25565) -> None:
        self.host = host
        self.port = port
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def connect(self) -> None:
        """Connect to the server."""

        self.client_socket.connect((self.host, self.port))
        logging.info(f"Connected to server at {self.host}:{self.port}")

    def send_json(self, payload: dict) -> dict:
        """Send a JSON message (NDJSON line) to the server and return JSON response."""

        message = json.dumps(payload) + "\n"
        logging.info(f"Sending: {message.strip()}")
        self.client_socket.sendall(message.encode("utf-8"))

        data = self.client_socket.recv(4096)
        text = data.decode("utf-8").strip()
        logging.info(f"Received: {text}")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logging.error("Failed to decode JSON response")
            return {"status": "error", "error": {"code": "INVALID_RESPONSE", "message": text}}

    def disconnect(self) -> None:
        """Disconnect from the server."""

        self.client_socket.close()
        logging.info("Disconnected from server")
