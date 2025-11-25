import socket
import logging
import threading


class Server:
    def __init__(self, port=25565) -> None:
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.is_running = False

    def start(self) -> None:
        """Start the server and begin listening for connections."""
        
        self.server_socket.bind(("", self.port))
        self.server_socket.listen(5)
        self.is_running = True
        logging.info(f"Server started on port {self.port}")
        threading.Thread(target=self._accept_clients, daemon=True).start()

    def stop(self) -> None:
        """Stop the server."""
        
        self.is_running = False
        self.server_socket.close()
        logging.info("Server stopped")

    def _accept_clients(self) -> None:
        """Thread pool to accept incoming client connections."""
        
        while self.is_running:
            client_socket, addr = self.server_socket.accept()
            logging.info(f"Accepted connection from {addr}")
            threading.Thread(target=self._handle_client, args=(client_socket,), daemon=True).start()

    def _handle_client(self, client_socket: socket.socket) -> None:
        """Handle communication with a connected client."""
        
        with client_socket:
            while True:
                data = client_socket.recv(1024)
                if not data:
                    break
                logging.info(f"Received: {data.decode()}")
                client_socket.sendall(data)  # Echo back the received data
        logging.info("Client disconnected")