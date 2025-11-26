import socket
import logging
import threading
import os
import json


class Server:
    def __init__(self, port=25565) -> None:
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.is_running = False

        self.accounts = {}  # Dictionary to store account balances

        self.transactions = []  # store transactions before creating a block
        self.block_id = 0  # initial ID
        self.block_file = "transactions.log"

        if os.path.exists(self.block_file):  # clear the archive in each excecution. Idk if it's that way
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

    def _create_block(self) -> None:
        """Create a new transaction block and write it to the block file."""

        block = []
        block.append(str(self.block_id))

        for t in self.transactions:
            sign = "-" if t["type"] == "WITHDRAW" else "+"
            block.append(f"T {t['account']} {sign}{t['value']}")
        for acc, balance in self.accounts.items():
            sign = "+" if balance >= 0 else "-"
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
                data = client_socket.recv(4096)
                if not data:
                    break

                text = data.decode("utf-8").strip()
                logging.info(f"Received: {text}")

                try:
                    msg = json.loads(text)
                except json.JSONDecodeError:
                    resp = {
                        "status": "error", 
                        "error": {
                            "code": "INVALID_JSON", 
                            "message": "Could not parse request"
                        }
                    }

                    client_socket.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                    logging.info("Response sent: INVALID_JSON")
                    continue

                action = msg.get("action")
                payload = msg.get("data", {})

                resp: dict
                if action == "create_account":
                    account_id = payload.get("account_id")
                    if not account_id:
                        resp = {
                            "status": "error",
                            "error": {
                                "code": "INVALID_PARAMS", 
                                "message": "account_id required"
                            },
                        }
                    elif account_id in self.accounts:
                        resp = {
                            "status": "error",
                            "error": {
                                "code": "ACCOUNT_EXISTS", 
                                "message": f"Account {account_id} already exists"
                            },
                        }
                    else:
                        self.accounts[account_id] = 0
                        resp = {
                            "status": "ok", 
                            "data": {
                                "account_id": account_id, 
                                "balance": 0
                            }
                        }

                elif action == "set_balance":
                    account_id = payload.get("account_id")
                    amount = payload.get("amount")
                    if account_id not in self.accounts:
                        resp = {
                            "status": "error",
                            "error": {
                                "code": "ACCOUNT_NOT_FOUND", 
                                "message": f"Account {account_id} does not exist"
                            },
                        }
                    else:
                        self.accounts[account_id] = int(amount)
                        resp = {
                            "status": "ok",
                            "data": {
                                "account_id": account_id, 
                                "balance": self.accounts[account_id]
                            },
                        }

                elif action == "get_balance":
                    account_id = payload.get("account_id")
                    if account_id not in self.accounts:
                        resp = {
                            "status": "error",
                            "error": {
                                "code": "ACCOUNT_NOT_FOUND", 
                                "message": f"Account {account_id} does not exist"
                            },
                        }
                    else:
                        resp = {
                            "status": "ok",
                            "data": {
                                "account_id": account_id, 
                                "balance": self.accounts[account_id]
                            },
                        }

                elif action == "withdraw":
                    account_id = payload.get("account_id")
                    amount = int(payload.get("amount", 0))
                    self.my_lock.acquire()
                    try:
                        if account_id not in self.accounts:
                            resp = {
                                "status": "error",
                                "error": {
                                    "code": "ACCOUNT_NOT_FOUND",
                                    "message": f"Account {account_id} does not exist",
                                },
                            }
                        elif self.accounts[account_id] < amount:
                            resp = {
                                "status": "error",
                                "error": {
                                    "code": "INSUFFICIENT_FUNDS",
                                    "message": f"Insufficient funds in account {account_id}",
                                },
                            }
                        else:
                            self.accounts[account_id] -= amount
                            resp = {
                                "status": "ok",
                                "data": {
                                    "account_id": account_id, 
                                    "balance": self.accounts[account_id]
                                },
                            }
                            self.transactions.append({"account": account_id, "type": "WITHDRAW", "value": amount})
                            if len(self.transactions) == 6:
                                self._create_block()
                    finally:
                        self.my_lock.release()

                elif action == "deposit":
                    account_id = payload.get("account_id")
                    amount = int(payload.get("amount", 0))
                    self.my_lock.acquire()
                    try:
                        if account_id not in self.accounts:
                            resp = {
                                "status": "error",
                                "error": {
                                    "code": "ACCOUNT_NOT_FOUND",
                                    "message": f"Account {account_id} does not exist",
                                },
                            }
                        else:
                            self.accounts[account_id] += amount
                            resp = {
                                "status": "ok",
                                "data": {
                                    "account_id": account_id, 
                                    "balance": self.accounts[account_id]
                                },
                            }
                            self.transactions.append({"account": account_id, "type": "DEPOSIT", "value": amount})
                            if len(self.transactions) == 6:
                                self._create_block()
                    finally:
                        self.my_lock.release()

                else:
                    resp = {
                        "status": "error", 
                        "error": {
                            "code": "INVALID_ACTION", 
                            "message": "Unknown action"
                        }
                    }

                out = json.dumps(resp) + "\n"
                client_socket.sendall(out.encode("utf-8"))
                logging.info(f"Response sent: {resp}")

        logging.info("Client disconnected")
