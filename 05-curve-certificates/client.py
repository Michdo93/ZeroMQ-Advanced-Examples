"""Step 5c: CURVE client.

The client needs
  * its OWN secret certificate (contains public + secret key) and
  * the server's PUBLIC certificate (to verify it talks to the right server).

Environment variables:
  ZMQ_ENDPOINT       default tcp://127.0.0.1:5555
  ZMQ_CLIENT_SECRET  default certs/clients/alice.key_secret
  ZMQ_SERVER_PUBLIC  default certs/server/server.key
"""

import os

import zmq
import zmq.auth

ENDPOINT = os.getenv("ZMQ_ENDPOINT", "tcp://127.0.0.1:5555")
CLIENT_SECRET = os.getenv("ZMQ_CLIENT_SECRET", "certs/clients/alice.key_secret")
SERVER_PUBLIC = os.getenv("ZMQ_SERVER_PUBLIC", "certs/server/server.key")


def main() -> None:
    client_public, client_secret = zmq.auth.load_certificate(CLIENT_SECRET)
    server_public, _ = zmq.auth.load_certificate(SERVER_PUBLIC)

    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.curve_publickey = client_public
    socket.curve_secretkey = client_secret
    socket.curve_serverkey = server_public  # setting this makes us a CURVE client
    socket.setsockopt(zmq.RCVTIMEO, 5000)
    socket.setsockopt(zmq.LINGER, 0)
    socket.connect(ENDPOINT)
    try:
        socket.send_json({"sensor": "living_room", "temperature": 21.5})
        print(f"Reply: {socket.recv_json()}")
    except zmq.Again:
        print("No reply: key not authorized, wrong server key or server offline")
    finally:
        socket.close()
        context.term()


if __name__ == "__main__":
    main()
