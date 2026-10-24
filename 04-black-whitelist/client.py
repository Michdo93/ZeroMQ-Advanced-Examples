"""PLAIN client used by steps 2, 3 and 4.

Environment variables:
  ZMQ_ENDPOINT  default tcp://127.0.0.1:5555
                A source address can be forced for tests on one machine:
                tcp://127.0.0.2:0;127.0.0.1:5555  (source;destination)
  ZMQ_USER      default demo
  ZMQ_PASSWORD  default change-me

A rejected handshake is silent on the client side: the connection is simply
never established, so the request times out after RCVTIMEO.
"""

import os

import zmq

ENDPOINT = os.getenv("ZMQ_ENDPOINT", "tcp://127.0.0.1:5555")


def main() -> None:
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.plain_username = os.getenv("ZMQ_USER", "demo").encode()
    socket.plain_password = os.getenv("ZMQ_PASSWORD", "change-me").encode()
    socket.setsockopt(zmq.RCVTIMEO, 3000)
    socket.setsockopt(zmq.LINGER, 0)
    socket.connect(ENDPOINT)
    try:
        socket.send_json({"payload": {"action": "status"}})
        print(f"Reply: {socket.recv_json()}")
    except zmq.Again:
        print("No reply: access denied (IP rule / wrong credentials) or server offline")
    finally:
        socket.close()
        context.term()


if __name__ == "__main__":
    main()
