import os
import logging
import datetime
import threading
from connection.server import Server
from connection.client import Client
from bituesc.app import App


os.makedirs('logs', exist_ok=True)
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s,%(msecs)03d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',
                    datefmt='%Y-%m-%dT%H:%M:%S',
                    filename=f'logs/log-{datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")}.log',
                    filemode='w')


def main() -> None:
    # Pergunta ao usuário a porta que o servidor deve usar
    port = input("Type the port number for the server to use (default: 25565): ") or '25565'
    port = int(port)

    server = Server(port=port)
    server_thread = threading.Thread(target=server.start)
    server_thread.start()

    app = App(server_host='localhost', server_port=port)
    app.run()
    server.stop()

    logging.info("Application has exited.")


if __name__ == "__main__":
    main()