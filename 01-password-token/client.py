"""Step 1: Client that sends a shared token with every request."""

import os

import zmq

ENDPOINT = os.getenv("ZMQ_ENDPOINT", "tcp://127.0.0.1:5555")
TOKEN = os.getenv("ZMQ_DEMO_TOKEN", "change-me")


def main() -> None:
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    # Never block forever: give up after 3 seconds.
    socket.setsockopt(zmq.RCVTIMEO, 3000)
    socket.setsockopt(zmq.SNDTIMEO, 3000)
    socket.setsockopt(zmq.LINGER, 0)
    socket.connect(ENDPOINT)

    try:
        socket.send_json({"token": TOKEN, "payload": {"action": "status"}})
        print(f"Reply: {socket.recv_json()}")
    except zmq.Again:
        print("Timeout: is the server running and reachable?")
    finally:
        socket.close()
        context.term()


if __name__ == "__main__":
    main()
