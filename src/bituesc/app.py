import os
import logging
import subprocess

from connection.client import Client


class App:
    def __init__(self) -> None:
        self.name = "BitUESC"
        self.version = self._get_commit_hash()

        self.server = tuple()

    def run(self) -> None:
        self.clear_screen()

        print(f"Running {self.name} version {self.version}")
        print("Welcome to BitUESC!")
        print()

        host = input("Enter server host (default: localhost): ") or "localhost"
        port_input = input("Enter server port (default: 25565): ") or "25565"
        port = int(port_input)
        self.server = (host, port)

        logging.info(f"Configured to connect to server at {host}:{port}")

        self.clear_screen()

        while True:
            print("[1] Create Account")
            print("[2] Set Account Balance")
            print("[3] Get Account Balance")
            print("[0] Exit")

            choice = input("Select an option: ")

            match choice:
                case '1':
                    self.create_account()
                case '2':
                    self.set_balance()
                case '3':
                    self.get_balance()
                case '0':
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

        response = self.send_command(f"CREATE {account_id}")
        print(response)

    def set_balance(self) -> None:
        account_id = input("Enter account ID: ")
        amount_input = input("Enter new balance amount: ")

        self.clear_screen()

        logging.info(f"Changing balance for account ID: {account_id} to {amount_input}")

        response = self.send_command(f"SET {account_id} {amount_input}")
        print(response)

    def get_balance(self) -> None:
        account_id = input("Enter account ID: ")

        self.clear_screen()

        logging.info(f"Retrieving balance for account ID: {account_id}")

        response = self.send_command(f"GET {account_id}")
        print(response)

    def clear_screen(self) -> None:
        """Clear the console screen."""

        os.system('clear || cls')

    def send_command(self, command: str) -> str:
        """Send a command to the server and return the response."""

        client = Client(host=self.server[0], port=self.server[1])
        client.connect()
        response = client.send_message(command)
        client.disconnect()
        
        return response

    def _get_commit_hash(self) -> str:
        """Retrieve the current Git commit hash."""
        try:
            commit_hash = subprocess.check_output(
                ['git', 'rev-parse', '--short', 'HEAD']
            ).strip().decode('utf-8')
            return commit_hash
        except Exception as e:
            return "unknown"