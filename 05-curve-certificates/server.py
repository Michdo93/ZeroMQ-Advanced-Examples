"""Step 5b: CURVE-encrypted and authenticated REP server.

* The whole connection is encrypted (CurveZMQ, Curve25519 + XSalsa20/Poly1305).
* Clients are authenticated by their public key: only certificates located in
  ZMQ_AUTHORIZED_DIR are accepted (cryptographic whitelist).
* Optionally an IP whitelist can be added on top (ZMQ_ALLOW_IP).

Environment variables:
  ZMQ_ENDPOINT        default tcp://*:5555
  ZMQ_SERVER_SECRET   default certs/server/server.key_secret
  ZMQ_AUTHORIZED_DIR  default certs/authorized_clients
  ZMQ_ALLOW_IP        optional comma separated IP whitelist
"""

import json
import logging
import os
import signal

import zmq
import zmq.auth
from zmq.auth.thread import ThreadAuthenticator

ENDPOINT = os.getenv("ZMQ_ENDPOINT", "tcp://*:5555")
SERVER_SECRET = os.getenv("ZMQ_SERVER_SECRET", "certs/server/server.key_secret")
AUTHORIZED_DIR = os.getenv("ZMQ_AUTHORIZED_DIR", "certs/authorized_clients")
ALLOW_IPS = [ip.strip() for ip in os.getenv("ZMQ_ALLOW_IP", "").split(",") if ip.strip()]

running = True


def handle_signal(signum, _frame):
    global running
    running = False


def main() -> None:
    logging.basicConfig(level=os.getenv("ZMQ_LOG_LEVEL", "INFO"))
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    if not os.path.isdir(AUTHORIZED_DIR):
        raise SystemExit(f"{AUTHORIZED_DIR} missing - run generate_keys.py first")

    context = zmq.Context()
    auth = ThreadAuthenticator(context)
    auth.start()
    if ALLOW_IPS:
        auth.allow(*ALLOW_IPS)
    # Every *.key file in this directory is an accepted client public key.
    # domain="*" applies to all sockets without an explicit ZAP domain.
    auth.configure_curve(domain="*", location=AUTHORIZED_DIR)

    server_public, server_secret = zmq.auth.load_certificate(SERVER_SECRET)

    socket = context.socket(zmq.REP)
    socket.curve_secretkey = server_secret
    socket.curve_publickey = server_public
    socket.curve_server = True  # must be set before bind()
    socket.bind(ENDPOINT)
    print(f"CURVE server on {ENDPOINT}, server key {server_public.decode()}")

    poller = zmq.Poller()
    poller.register(socket, zmq.POLLIN)
    try:
        while running:
            if dict(poller.poll(500)).get(socket):
                frame = socket.recv(copy=False)
                # User-Id is the Z85 public key of the authenticated client.
                client_key = frame.get("User-Id")
                request = json.loads(frame.bytes)
                print(f"Request from {client_key[:12]}...: {request}")
                socket.send_json({"ok": True, "echo": request})
    finally:
        socket.close(linger=0)
        auth.stop()
        context.term()


if __name__ == "__main__":
    main()
