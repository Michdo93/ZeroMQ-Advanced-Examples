"""Step 1: Application-level token check (no ZeroMQ security mechanism).

The client sends a shared token inside every JSON request. The server compares
it in constant time (hmac.compare_digest) to avoid timing side channels.

Important: The token travels in PLAINTEXT. This step only shows the idea of
authentication; it does not protect against eavesdropping. Steps 2-5 move the
check into ZeroMQ itself (ZAP) and finally encrypt the connection (CURVE).
"""

import hmac
import os
import signal

import zmq

ENDPOINT = os.getenv("ZMQ_ENDPOINT", "tcp://127.0.0.1:5555")
EXPECTED_TOKEN = os.getenv("ZMQ_DEMO_TOKEN", "change-me").encode("utf-8")

running = True


def handle_signal(signum, _frame):
    global running
    print(f"\nSignal {signum} received, shutting down...")
    running = False


def is_authorized(message: dict) -> bool:
    token = str(message.get("token", "")).encode("utf-8")
    return hmac.compare_digest(token, EXPECTED_TOKEN)


def main() -> None:
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind(ENDPOINT)

    poller = zmq.Poller()
    poller.register(socket, zmq.POLLIN)
    print(f"Token server listening on {ENDPOINT} (Ctrl+C to stop)")

    try:
        while running:
            # Poll with timeout so that the loop can react to signals.
            if not dict(poller.poll(500)).get(socket):
                continue
            message = socket.recv_json()
            if is_authorized(message):
                payload = message.get("payload", {})
                print(f"Authorized request: {payload}")
                socket.send_json({"ok": True, "result": {"status": "ready", "echo": payload}})
            else:
                print("Rejected request with wrong token")
                socket.send_json({"ok": False, "error": "unauthorized"})
    finally:
        socket.close(linger=0)
        context.term()


if __name__ == "__main__":
    main()
