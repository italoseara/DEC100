import socket
import logging
import threading
import os
import json
import uuid


class Server:
    def __init__(self, port=25565, node_id=0, successor_host=None, successor_port=None) -> None:
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.node_id = int(node_id)
        self.successor = (successor_host, successor_port) if successor_host and successor_port else None
        self.is_running = False
        self.lock = threading.Lock()

        self.accounts = {}  # Dictionary to store account balances

        self.transactions = []  # store transactions before creating a block
        self.block_id = 0  # initial ID
        self.block_file = f"transactions_{node_id}.log"
        self.block_log_lock = threading.Lock()
        self.seen_txn_ids = set()

        if os.path.exists(self.block_file):  # clear the archive in each excecution. Idk if it's that way
            os.remove(self.block_file)

    def start(self) -> None:
        """Start the server and begin listening for connections."""

        self.server_socket.bind(("", self.port))
        self.server_socket.listen(5)
        self.is_running = True

        logging.info(f"Server started on port {self.port}")
        threading.Thread(target=self._accept_clients, daemon=True).start()

        if self.successor:
            logging.info(f"Configured successor: {self.successor[0]}:{self.successor[1]}")

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

        with self.block_log_lock:
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

                # Peer messages use `type` field; client messages use `action`
                if msg.get("type") == "REPLICATE_TXN":
                    self._handle_replication(msg)
                    # peer protocol replies with ACK
                    ack = {"type": "REPLICATE_ACK", "txn_id": msg.get("txn_id"), "node_id": self.node_id}
                    client_socket.sendall((json.dumps(ack) + "\n").encode("utf-8"))
                    continue

                action = msg.get("action")
                payload = msg.get("data", {})

                resp: dict
                if action == "CREATE_ACCOUNT":
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

                        self._replicate_local_txn({"account": account_id, "type": "CREATE", "value": 0})

                elif action == "SET_BALANCE":
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

                        self._replicate_local_txn({"account": account_id, "type": "SET", "value": int(amount)})

                elif action == "GET_BALANCE":
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

                elif action == "WITHDRAW":
                    account_id = payload.get("account_id")
                    amount = int(payload.get("amount", 0))
                    replicate_payload = None
                    self.lock.acquire()
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
                            replicate_payload = {"account": account_id, "type": "WITHDRAW", "value": amount}
                            if len(self.transactions) == 6:
                                self._create_block()
                    finally:
                        self.lock.release()

                    if replicate_payload:
                        self._replicate_local_txn(replicate_payload)

                elif action == "DEPOSIT":
                    account_id = payload.get("account_id")
                    amount = int(payload.get("amount", 0))
                    replicate_payload = None
                    self.lock.acquire()
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
                            replicate_payload = {"account": account_id, "type": "DEPOSIT", "value": amount}
                            if len(self.transactions) == 6:
                                self._create_block()
                    finally:
                        self.lock.release()

                    if replicate_payload:
                        self._replicate_local_txn(replicate_payload)

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

    def _handle_replication(self, msg: dict) -> None:
        """Apply replicated transaction and forward to successor if needed."""

        txn_id = msg.get("txn_id")
        origin_id = msg.get("origin_id")
        hop = int(msg.get("hop", 0))
        payload = msg.get("payload", {})

        # Idempotence: if we've already processed this txn, ignore
        if txn_id in self.seen_txn_ids:
            logging.debug(f"Duplicate txn {txn_id} ignored")
            return

        # Apply mutation locally
        ttype = payload.get("type")
        account = payload.get("account")
        value = int(payload.get("value", 0))
        self.lock.acquire()
        try:
            if ttype == "CREATE":
                if account not in self.accounts:
                    self.accounts[account] = 0
            elif ttype == "SET":
                self.accounts[account] = value
            elif ttype == "DEPOSIT":
                if account not in self.accounts:
                    self.accounts[account] = 0
                self.accounts[account] += value
                self.transactions.append({"account": account, "type": "DEPOSIT", "value": value})
            elif ttype == "WITHDRAW":
                if account not in self.accounts:
                    self.accounts[account] = 0
                self.accounts[account] -= value
                self.transactions.append({"account": account, "type": "WITHDRAW", "value": value})

            if len(self.transactions) == 6:
                self._create_block()
        finally:
            self.lock.release()

        # Mark as seen only after successfully applying
        self.seen_txn_ids.add(txn_id)

        # Forward along the ring
        if self.successor:
            next_msg = {
                "type": "REPLICATE_TXN",
                "txn_id": txn_id,
                "origin_id": origin_id,
                "hop": hop + 1,
                "payload": payload,
            }
            # Stop when it returns to origin after 4 hops
            if not (self.node_id == origin_id and hop >= 3):
                try:
                    self._send_to_successor(next_msg)
                except Exception as e:
                    logging.error(f"Failed to forward to successor: {e}")

    def _replicate_local_txn(self, payload: dict) -> None:
        """Inject a local transaction into the ring (entry node)."""

        txn_id = str(uuid.uuid4())
        msg = {
            "type": "REPLICATE_TXN",
            "txn_id": txn_id,
            "origin_id": self.node_id,
            "hop": 0,
            "payload": payload,
        }
        # Apply locally immediately to keep UX responsive; don't pre-mark as seen
        self._handle_replication(msg)

    def _send_to_successor(self, msg: dict) -> None:
        if not self.successor:
            return

        host, port = self.successor
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect((host, int(port)))
        s.sendall((json.dumps(msg) + "\n").encode("utf-8"))

        # Optionally read ack but don't block the main flow
        try:
            s.recv(1024)
        except Exception:
            pass
        s.close()
