"""Step 2: PLAIN username/password authentication + IP blacklist via ZAP.

ZeroMQ checks every new connection through the ZAP protocol (ZeroMQ
Authentication Protocol). pyzmq's ThreadAuthenticator implements a ZAP handler
in a background thread. Here it
  * rejects connections from blacklisted IP addresses (auth.deny), and
  * verifies username/password with the PLAIN mechanism.

PLAIN sends credentials unencrypted. Use it only on trusted networks or
combine the idea with CURVE (step 5).

Environment variables:
  ZMQ_ENDPOINT   default tcp://127.0.0.1:5555
  ZMQ_USER       default demo
  ZMQ_PASSWORD   default change-me
  ZMQ_LOG_LEVEL  INFO (default) or DEBUG (shows ZAP decisions AND passwords!)
  ZMQ_DENY_IP    comma separated list, default 192.0.2.10
"""

import logging
import os
import signal

import zmq
from zmq.auth.thread import ThreadAuthenticator

ENDPOINT = os.getenv("ZMQ_ENDPOINT", "tcp://127.0.0.1:5555")
USER = os.getenv("ZMQ_USER", "demo")
PASSWORD = os.getenv("ZMQ_PASSWORD", "change-me")
DENY_IPS = [ip.strip() for ip in os.getenv("ZMQ_DENY_IP", "192.0.2.10").split(",") if ip.strip()]

running = True


def handle_signal(signum, _frame):
    global running
    running = False


def main() -> None:
    # DEBUG shows every ZAP decision, but pyzmq then also logs PLAIN passwords
    # in clear text. Use it only for local experiments.
    logging.basicConfig(level=os.getenv("ZMQ_LOG_LEVEL", "INFO"),
                        format="%(asctime)s %(name)s %(message)s")
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    context = zmq.Context()

    # 1. Start the ZAP handler BEFORE binding any socket that needs it.
    auth = ThreadAuthenticator(context, log=logging.getLogger("zap"))
    auth.start()
    auth.deny(*DENY_IPS)
    # The domain must match socket.zap_domain below ("*" is only used for
    # sockets without a ZAP domain).
    auth.configure_plain(domain="demo", passwords={USER: PASSWORD})

    # 2. Server socket: act as PLAIN server -> ZAP is consulted automatically.
    socket = context.socket(zmq.REP)
    socket.plain_server = True
    socket.zap_domain = b"demo"
    socket.bind(ENDPOINT)
    print(f"Blacklist server on {ENDPOINT}, denied IPs: {DENY_IPS}")

    poller = zmq.Poller()
    poller.register(socket, zmq.POLLIN)
    try:
        while running:
            if dict(poller.poll(500)).get(socket):
                message = socket.recv_json()
                socket.send_json({"ok": True, "received": message.get("payload")})
    finally:
        socket.close(linger=0)
        auth.stop()
        context.term()


if __name__ == "__main__":
    main()
