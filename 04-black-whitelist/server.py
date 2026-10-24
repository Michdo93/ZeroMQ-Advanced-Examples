"""Step 4: Combined whitelist + blacklist with a hand-written ZAP handler.

pyzmq's ThreadAuthenticator treats allow() and deny() as mutually exclusive
(using both raises ValueError) and only compares exact IP strings. Real
networks need rules like "allow 192.168.1.0/24, but deny 192.168.1.50".

This example therefore implements the ZAP protocol (RFC 27/ZAP) itself:
libzmq sends every handshake as a multipart request to the REP socket bound on
inproc://zeromq.zap.01. We answer with status code 200 (accept) or 400 (deny).

Decision order:
  1. Blacklist (CIDR) matches  -> deny
  2. Whitelist (CIDR) matches  -> continue, otherwise deny
  3. PLAIN username/password   -> accept or deny

Environment variables:
  ZMQ_ENDPOINT   default tcp://127.0.0.1:5555
  ZMQ_USER       default demo
  ZMQ_PASSWORD   default change-me
  ZMQ_ALLOW_NET  comma separated CIDR list, default 127.0.0.0/8
  ZMQ_DENY_NET   comma separated CIDR list, default 127.0.0.2/32
"""

import hmac
import ipaddress
import json
import os
import signal
import threading

import zmq

ENDPOINT = os.getenv("ZMQ_ENDPOINT", "tcp://127.0.0.1:5555")
USERS = {os.getenv("ZMQ_USER", "demo"): os.getenv("ZMQ_PASSWORD", "change-me")}


def parse_networks(value: str):
    return [ipaddress.ip_network(n.strip(), strict=False) for n in value.split(",") if n.strip()]


ALLOW_NETS = parse_networks(os.getenv("ZMQ_ALLOW_NET", "127.0.0.0/8"))
DENY_NETS = parse_networks(os.getenv("ZMQ_DENY_NET", "127.0.0.2/32"))

ZAP_ENDPOINT = "inproc://zeromq.zap.01"  # fixed by the ZAP specification


class CombinedZapHandler(threading.Thread):
    """Minimal ZAP 1.0 handler running in its own thread."""

    def __init__(self, context: zmq.Context):
        super().__init__(daemon=True)
        self.context = context
        self.stop_event = threading.Event()
        self.ready = threading.Event()

    def check_ip(self, address: str):
        ip = ipaddress.ip_address(address)
        if any(ip in net for net in DENY_NETS):
            return False, "IP is blacklisted"
        if ALLOW_NETS and not any(ip in net for net in ALLOW_NETS):
            return False, "IP is not whitelisted"
        return True, "OK"

    def check_plain(self, username: str, password: str):
        expected = USERS.get(username)
        if expected is not None and hmac.compare_digest(expected.encode(), password.encode()):
            return True, "OK"
        return False, "Invalid username or password"

    def run(self) -> None:
        zap = self.context.socket(zmq.REP)
        zap.bind(ZAP_ENDPOINT)
        self.ready.set()
        poller = zmq.Poller()
        poller.register(zap, zmq.POLLIN)
        try:
            while not self.stop_event.is_set():
                if not dict(poller.poll(200)).get(zap):
                    continue
                frames = zap.recv_multipart()
                # version, request_id, domain, address, identity, mechanism, credentials...
                version, request_id, domain, address, identity, mechanism = frames[:6]
                credentials = frames[6:]
                ip = address.decode()

                allowed, reason = self.check_ip(ip)
                user_id = b""
                if allowed and mechanism == b"PLAIN":
                    username, password = (c.decode() for c in credentials[:2])
                    allowed, reason = self.check_plain(username, password)
                    user_id = username.encode()
                elif allowed and mechanism != b"NULL":
                    allowed, reason = False, f"Mechanism {mechanism.decode()} not supported"

                status = b"200" if allowed else b"400"
                print(f"[ZAP] {ip:<15} {mechanism.decode():<6} -> {status.decode()} {reason}")
                zap.send_multipart([version, request_id, status, reason.encode(), user_id, b""])
        finally:
            zap.close(linger=0)


running = True


def handle_signal(signum, _frame):
    global running
    running = False


def main() -> None:
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    context = zmq.Context()
    zap_handler = CombinedZapHandler(context)
    zap_handler.start()
    zap_handler.ready.wait()  # the handler must be bound before clients connect

    socket = context.socket(zmq.REP)
    socket.plain_server = True
    socket.zap_domain = b"combined"
    socket.bind(ENDPOINT)
    print(f"Combined server on {ENDPOINT}")
    print(f"  allow: {[str(n) for n in ALLOW_NETS]}")
    print(f"  deny : {[str(n) for n in DENY_NETS]}")

    poller = zmq.Poller()
    poller.register(socket, zmq.POLLIN)
    try:
        while running:
            if dict(poller.poll(500)).get(socket):
                message = socket.recv(copy=False)
                # The authenticated user id is attached to every frame as metadata.
                user = message.get("User-Id")
                payload = json.loads(message.bytes)
                socket.send_json({"ok": True, "user": user, "received": payload.get("payload")})
    finally:
        socket.close(linger=0)
        zap_handler.stop_event.set()
        zap_handler.join(timeout=2)
        context.term()


if __name__ == "__main__":
    main()
