import socket
import logging


class Client:
    def __init__(self, host='localhost', port=25565) -> None:
        self.host = host
        self.port = port
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def connect(self) -> None:
        """Connect to the server."""
        
        self.client_socket.connect((self.host, self.port))
        logging.info(f"Connected to server at {self.host}:{self.port}")

    def send_message(self, message: str) -> str:
        """Send a message to the server and receive a response."""

        self.client_socket.sendall(message.encode())
        data = self.client_socket.recv(1024)
        logging.info(f"Received: {data.decode()}")
        return data.decode()

    def disconnect(self) -> None:
        """Disconnect from the server."""
        
        self.client_socket.close()
        logging.info("Disconnected from server")