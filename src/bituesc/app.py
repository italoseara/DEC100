import os
import json
import logging
import subprocess

from connection.client import Client


class App:
    def __init__(self, server_host: str = "localhost", server_port: int = 25565) -> None:
        self.name = "BitUESC"
        self.version = self._get_commit_hash()

        self.server = (server_host, server_port)

    def run(self) -> None:
        self.clear_screen()

        print(f"Running {self.name} version {self.version}")
        print()
        print("Welcome to BitUESC!")
        print()

        logging.info(f"Client configured to connect to server at {self.server[0]}:{self.server[1]}")

        while True:
            print("[1] Create Account")
            print("[2] Set Account Balance")
            print("[3] Get Account Balance")
            print("[4] Withdraw")
            print("[5] Deposit")
            print("[0] Exit")

            choice = input("Select an option: ")

            match choice:
                case "1":
                    self.create_account()
                case "2":
                    self.set_balance()
                case "3":
                    self.get_balance()
                case "4":
                    self.withdraw()
                case "5":
                    self.deposit()
                case "0":
                    self.clear_screen()
                    logging.info("Exiting application.")
                    print("Exiting application.")
                    break
                case _:
                    self.clear_screen()
                    logging.warning("Invalid option selected.")
                    print("Invalid option. Please try again.")
            print()

    def create_account(self) -> None:
        account_id = input("Enter new account ID: ")

        self.clear_screen()

        logging.info(f"Creating account with ID: {account_id}")

        response = self.send_request({
            "action": "create_account", 
            "data": {
                "account_id": account_id
            }
        })
        
        if response["status"] == "ok":
            print(f"Account {response["data"]["account_id"]} created successfully.")
        else:
            print(f"Error creating account: {response['error']['message']}")

    def set_balance(self) -> None:
        account_id = input("Enter account ID: ")
        amount_input = input("Enter new balance amount: ")

        self.clear_screen()

        logging.info(f"Changing balance for account ID: {account_id} to {amount_input}")

        response = self.send_request({
            "action": "set_balance", 
            "data": {
                "account_id": account_id, 
                "amount": int(amount_input)
            }
        })

        if response["status"] == "ok":
            print(f"Balance for account {response["data"]["account_id"]} set to {response["data"]["balance"]}.")
        else:
            print(f"Error setting balance: {response['error']['message']}")

    def get_balance(self) -> None:
        account_id = input("Enter account ID: ")

        self.clear_screen()

        logging.info(f"Retrieving balance for account ID: {account_id}")

        response = self.send_request({
            "action": "get_balance", 
            "data": {
                "account_id": account_id
            }
        })
        
        if response["status"] == "ok":
            print(f"Account {response["data"]["account_id"]} has balance {response["data"]["balance"]}.")
        else:
            print(f"Error retrieving balance: {response['error']['message']}")

    def withdraw(self) -> None:
        account_id = input("Enter account ID: ")
        ammount_input = input("Enter amount to withdraw: ")

        self.clear_screen()

        logging.info(f"Withdrawing from account ID: {account_id}")

        response = self.send_request({
            "action": "withdraw", 
            "data": {
                "account_id": account_id, 
                "amount": int(ammount_input)
            }
        })

        if response["status"] == "ok":
            print(f"Withdrew {ammount_input} from account {response["data"]["account_id"]}. New balance is {response["data"]["balance"]}.")
        else:
            print(f"Error withdrawing amount: {response['error']['message']}")

    def deposit(self) -> None:
        account_id = input("Enter account ID: ")
        amount_input = input("Enter amount to deposit: ")

        self.clear_screen()

        logging.info(f"Depositing to account ID: {account_id}")

        response = self.send_request({
            "action": "deposit", 
            "data": {
                "account_id": account_id, 
                "amount": int(amount_input)
            }
        })
        
        if response["status"] == "ok":
            print(f"Deposited {amount_input} to account {response["data"]["account_id"]}. New balance is {response["data"]["balance"]}.")
        else:
            print(f"Error depositing amount: {response['error']['message']}")

    def clear_screen(self) -> None:
        """Clear the console screen."""

        os.system("clear || cls")

    def send_request(self, payload: dict) -> dict:
        """Send a JSON request to the server and return the JSON response."""

        client = Client(host=self.server[0], port=self.server[1])
        client.connect()
        response = client.send_json(payload)
        client.disconnect()

        return response

    def _get_commit_hash(self) -> str:
        """Retrieve the current Git commit hash."""
        try:
            commit_hash = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).strip().decode("utf-8")
            return commit_hash
        except Exception as e:
            return "unknown"
