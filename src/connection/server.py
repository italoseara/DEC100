import os
import json
import uuid
import socket
import logging
import threading


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
        self.seen_block_ids = set()
        self.block_ready = False  # True when we have 6 transactions

        if os.path.exists(self.block_file):  # clear the archive in each excecution. Idk if it's that way
            os.remove(self.block_file)

    def start(self) -> None:
        """Start the server and begin listening for connections."""

        self.server_socket.bind(("0.0.0.0", self.port))
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

    def _create_block(self) -> int:
        """Mine current block (must have 6 transactions), append id + factors, persist and propagate."""

        if len(self.transactions) != 6:
            raise RuntimeError("Block incomplete; cannot mine")

        # Build block lines, without id and factors
        base_block = [str(self.block_id)]
        for t in self.transactions:
            sign = "-" if t["type"] == "WITHDRAW" else "+"
            base_block.append(f"T {t['account']} {sign}{t['value']}")
        for acc, balance in self.accounts.items():
            sign = "+" if balance >= 0 else "-"
            base_block.append(f"S {acc} {sign}{balance}")

        # Compute ID from the block's text, except ID and Factors
        block_text_without_meta = "\n".join(base_block) + "\n"  # include trailing newline
        block_bytes = block_text_without_meta.encode("utf-8")
        block_id_value = self._compute_block_id(block_bytes)
        prime_factors = self._prime_factors(block_id_value)
        factor_line = ",".join(str(f) for f in prime_factors)

        full_block = list(base_block)
        full_block.append(str(block_id_value))
        full_block.append(factor_line)

        with self.block_log_lock:
            with open(self.block_file, "a") as f:
                for line in full_block:
                    f.write(line + "\n")
                f.write("\n")

        logging.info(f"Block {self.block_id} mined with id {block_id_value} factors {factor_line}")

        # Mark the mined block
        self.seen_block_ids.add(self.block_id)

        # Adjust replication message
        if self.successor:
            msg = {
                "type": "REPLICATE_BLOCK",
                "origin_id": self.node_id,
                "hop": 0,
                "block_id": self.block_id,
                "lines": full_block,
                "id": block_id_value,
                "factors": prime_factors,
            }
            try:
                self._send_to_successor(msg)
            except Exception as e:
                logging.error(f"Failed to propagate block: {e}")

        # Go to next block
        mined_bid = self.block_id
        self.block_id += 1
        self.transactions = []
        self.block_ready = False
        return block_id_value

    def _handle_client(self, client_socket: socket.socket) -> None:
        """Handle communication with a connected client."""

        with client_socket:
            while True:
                data = client_socket.recv(4096)
                if not data:
                    break

                text = data.decode("utf-8").strip()
                logging.debug(f"Received: {text}")

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
                    logging.debug("Response sent: INVALID_JSON")
                    continue

                # Peers use "type"; clients use "action"
                if msg.get("type") == "REPLICATE_TXN":
                    self._handle_replication(msg)
                    # send ACK to peer
                    ack = {"type": "REPLICATE_ACK", "txn_id": msg.get("txn_id"), "node_id": self.node_id}
                    client_socket.sendall((json.dumps(ack) + "\n").encode("utf-8"))
                    continue
                if msg.get("type") == "REPLICATE_BLOCK":
                    self._handle_block_replication(msg)
                    ack = {"type": "BLOCK_ACK", "block_id": msg.get("block_id"), "node_id": self.node_id}
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
                        if self.block_ready and len(self.transactions) == 6:
                            resp = {"status": "error", "error": {"code": "BLOCK_PENDING", "message": "Block full awaiting mining."}}
                        else:
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
                                    self.block_ready = True
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
                        if self.block_ready and len(self.transactions) == 6:
                            resp = {"status": "error", "error": {"code": "BLOCK_PENDING", "message": "Block full awaiting mining."}}
                        else:
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
                                    self.block_ready = True
                    finally:
                        self.lock.release() # Release the Thread lock

                    if replicate_payload:
                        self._replicate_local_txn(replicate_payload)

                elif action == "MINE_BLOCK":
                        # Attempt to mine current block
                        self.lock.acquire()
                        try:
                            if len(self.transactions) != 6:
                                resp = {"status": "error", "error": {"code": "BLOCK_INCOMPLETE", "message": "Block does not yet have 6 transactions."}}
                            elif not self.block_ready:
                                resp = {"status": "error", "error": {"code": "BLOCK_NOT_READY", "message": "Block not ready for mining."}}
                            else:
                                try:
                                    mined_value = self._create_block()
                                    resp = {"status": "ok", "data": {"block_id": self.block_id - 1, "id": mined_value}}
                                except Exception as e:
                                    resp = {"status": "error", "error": {"code": "MINING_FAILED", "message": str(e)}}
                        finally:
                            self.lock.release()
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
                logging.debug(f"Response sent: {resp}")

        logging.info("Client disconnected")

    def _handle_replication(self, msg: dict) -> None:
        """Apply replicated transaction and forward to successor if needed."""

        txn_id = msg.get("txn_id")
        origin_id = msg.get("origin_id")
        hop = int(msg.get("hop", 0))
        payload = msg.get("payload", {})

        # Apply mutation locally
        if txn_id not in self.seen_txn_ids:
            ttype = payload.get("type")
            account = payload.get("account")
            value = int(payload.get("value", 0))
            self.lock.acquire()
            try:
                if self.block_ready and len(self.transactions) == 6:
                    # Ignore further txns until block is mined
                    return
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
                    self.block_ready = True
            finally:
                self.lock.release()

            # Mark as seen only after successfully replicate
            self.seen_txn_ids.add(txn_id)

        # Forward to the next node
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

    def _handle_block_replication(self, msg: dict) -> None:
        """Verify and replicate a mined block across the ring."""
        block_id = msg.get("block_id")
        origin_id = msg.get("origin_id")
        hop = int(msg.get("hop", 0))
        lines = msg.get("lines", [])
        advertised_id = int(msg.get("id"))
        advertised_factors = msg.get("factors", [])

        if block_id in self.seen_block_ids:
            return

        # Verify structure: last two lines must be id and factor list
        if len(lines) < 2:
            logging.warning("Received malformed block (too few lines)")
            return
        try:
            id_line = lines[-2]
            factors_line = lines[-1]
            if int(id_line) != advertised_id:
                logging.warning("Block id mismatch")
                return
            received_factors = [int(x) for x in factors_line.split(",") if x]
        except Exception:
            logging.warning("Malformed id/factors lines")
            return

        # Recompute id from block content
        content_without_meta = "\n".join(lines[:-2]) + "\n"
        recomputed_id = self._compute_block_id(content_without_meta.encode("utf-8"))
        if recomputed_id != advertised_id:
            logging.warning("Block verification failed: id mismatch")
            return

        # Verify if prime factorization is correct (product == id)
        prod = 1
        for f in received_factors:
            prod *= f
        if prod != advertised_id:
            logging.warning("Block verification failed: factors product mismatch")
            return

        # Accept block
        with self.block_log_lock:
            with open(self.block_file, "a") as f:
                for line in lines:
                    f.write(line + "\n")
                f.write("\n")
        logging.info(f"Accepted mined block {block_id} id {advertised_id}")
        self.seen_block_ids.add(block_id)

        # Reset the current block if we were building it
        if len(self.transactions) == 6:
            self.transactions = []
            self.block_ready = False
            self.block_id = max(self.block_id, block_id + 1)

        # Forward
        if self.successor and not (self.node_id == origin_id and hop >= 3):
            fwd = dict(msg)
            fwd["hop"] = hop + 1
            try:
                self._send_to_successor(fwd)
            except Exception as e:
                logging.error(f"Failed to forward block: {e}")

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

        self.seen_txn_ids.add(txn_id)
        
        # Apply locally right now for quick response; don't mark as seen yet
        self._handle_replication(msg)

    def _send_to_successor(self, msg: dict) -> None:
        if not self.successor:
            return

        logging.debug(f"Forwarding txn to successor {self.successor[0]}:{self.successor[1]}")

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

    @staticmethod
    def _compute_block_id(block_bytes: bytes) -> int:
        """Compute block id by multiplying all bytes (0-255 mapped to 1-256) modulo 65535."""
        idlim = 65535
        mult = 1
        for b in block_bytes:
            v = b + 1  # map 0..255 to 1..256
            mult *= v
            if mult > idlim:
                mult = mult % idlim
        return mult

    @staticmethod
    def _prime_factors(n: int) -> list:
        """Return prime factors of n (with multiplicity) in ascending traversal order."""
        factors = []
        # Extract all factors of 2
        while n % 2 == 0:
            factors.append(2)
            n //= 2
        p = 3
        while p * p <= n:
            while n % p == 0:
                factors.append(p)
                n //= p
            p += 2
        if n > 1:
            factors.append(n)
        return factors
