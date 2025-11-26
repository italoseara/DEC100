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
    # Config simples para rodar em anel local
    port = int(input("Server port (default 25565): ") or '25565')
    node_id = int(input("Node ID [0-3] (default 0): ") or '0')
    succ_host = input("Successor host (default localhost): ") or 'localhost'
    succ_port = int(input("Successor port (default 25565): ") or str(port))

    server = Server(port=port, node_id=node_id, successor_host=succ_host, successor_port=succ_port)
    server_thread = threading.Thread(target=server.start)
    server_thread.start()

    app = App(server_host='localhost', server_port=port)
    app.run()
    server.stop()

    logging.info("Application has exited.")


if __name__ == "__main__":
    main()