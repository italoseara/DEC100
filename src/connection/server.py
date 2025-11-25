import socket
import logging
import threading
import os


class Server:
    def __init__(self, port=25565) -> None:
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.is_running = False

        self.accounts = {}  # Dictionary to store account balances

        self.transactions = []     # store transactions before creating a block
        self.block_id = 0          # initial ID
        self.block_file = "transactions_blocks.log"

        if os.path.exists(self.block_file): # clear the archive in each excecution. Idk if it's that way
            os.remove(self.block_file)


    def start(self) -> None:
        """Start the server and begin listening for connections."""
        
        self.server_socket.bind(("", self.port))
        self.server_socket.listen(5)
        self.is_running = True
        self.my_lock = threading.Lock()
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

    def _create_block(self):
        """Create a new transaction block and write it to the block file."""

        block = []
        block.append(str(self.block_id))

        for t in self.transactions:
            sign = "-" if t["type"] == "WITHDRAW" else "+"
            block.append(f"T {t['account']} {sign}{t['value']}")
        for acc, balance in self.accounts.items():
            sign = "+" if balance >= 0 else ""
            block.append(f"S {acc} {sign}{balance}")

        with open(self.block_file, "a") as f:
            for line in block:
                f.write(line + "\n")
            f.write("\n")

        logging.info(f"Block {self.block_id} created with transactions: {self.transactions}")

        self.block_id += 1
        self.transactions = []

    def _handle_client(self, client_socket: socket.socket) -> None:
        """Handle communication with a connected client."""
        
        with client_socket:
            while True:
                data = client_socket.recv(1024)
                if not data:
                    break

                logging.info(f"Received: {data.decode()}")

                response = None
                match data.decode().split():
                    case ["CREATE", account_id]:
                        if account_id in self.accounts:
                            response = f"Account {account_id} already exists."
                        else:
                            self.accounts[account_id] = 0
                            response = f"Account {account_id} created with balance 0."

                        client_socket.sendall(response.encode())

                    case ["SET", account_id, amount]:
                        if account_id in self.accounts:
                            self.accounts[account_id] = int(amount)
                            response = f"Account {account_id} balance set to {amount}."
                        else:
                            response = f"Account {account_id} does not exist."

                        client_socket.sendall(response.encode())

                    case ["GET", account_id]:
                        if account_id in self.accounts:
                            balance = self.accounts[account_id]
                            response = f"Account {account_id} balance is {balance}."
                        else:
                            response = f"Account {account_id} does not exist."

                        client_socket.sendall(response.encode())
                    
                    case ["WITHDRAW", account_id, amount]:
                        self.my_lock.acquire()
                        if account_id in self.accounts:
                            if self.accounts[account_id] >= int(amount):
                                self.accounts[account_id] -= int(amount)
                                response = f"Withdrew {amount} from account {account_id}. New balance is {self.accounts[account_id]}."

                                self.transactions.append({"account": account_id, "type": "WITHDRAW", "value": int(amount)})

                                if len(self.transactions) == 6:
                                    self._create_block()

                            else:
                                response = f"Insufficient funds in account {account_id}."
                        else:
                            response = f"Account {account_id} does not exist."

                        client_socket.sendall(response.encode())
                        self.my_lock.release()
                    
                    case ["DEPOSIT", account_id, amount]:
                        self.my_lock.acquire()
                        if account_id in self.accounts:
                            self.accounts[account_id] += int(amount)
                            response = f"Deposited {amount} to account {account_id}. New balance is {self.accounts[account_id]}."

                            self.transactions.append({"account": account_id, "type": "DEPOSIT", "value": int(amount)})

                            if len(self.transactions) == 6:
                                self._create_block()

                        else:
                            response = f"Account {account_id} does not exist."
                            
                        client_socket.sendall(response.encode())
                        self.my_lock.release()

                    case _:
                        response = "Invalid command."
                        client_socket.sendall(response.encode())

                logging.info(f"Response sent: {response}")

        logging.info("Client disconnected")