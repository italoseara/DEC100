import os
import logging
import datetime
import threading
from connection.server import Server
from connection.client import Client


os.makedirs('logs', exist_ok=True)
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s,%(msecs)03d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',
                    datefmt='%Y-%m-%dT%H:%M:%S',
                    filename=f'logs/log-{datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")}.log',
                    filemode='w')


def main() -> None:
    # Start the server in a separate thread
    server = Server(port=25565)
    server_thread = threading.Thread(target=server.start)
    server_thread.start()

    # Create a client and connect to the server
    client = Client(host='localhost', port=25565)
    client.connect()

    # Send a message from the client to the server
    response = client.send_message("Hello, Server!")
    logging.info(f"Client received response: {response}")

    # Disconnect the client
    client.disconnect()

    # Stop the server
    server.stop()
    server_thread.join()


if __name__ == "__main__":
    main()