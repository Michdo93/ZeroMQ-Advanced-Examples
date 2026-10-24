"""Step 6: Production-style ZeroMQ service for systemd.

Combines everything from steps 1-5:
  * CURVE encryption + client certificate whitelist (step 5)
  * optional IP whitelist (step 3)
  * graceful shutdown on SIGTERM (sent by `systemctl stop/restart`)
  * logging to stdout -> captured by journald (`journalctl -u zeromq-server`)
  * configuration only via environment (EnvironmentFile in the unit)
  * keys from /etc/zeromq-server/certs (readable by the service user only)

When ZMQ_CURVE=0 the service runs unencrypted (useful for a first smoke test).
"""

import json
import logging
import os
import signal
import sys

import zmq
import zmq.auth
from zmq.auth.thread import ThreadAuthenticator

ENDPOINT = os.getenv("ZMQ_ENDPOINT", "tcp://127.0.0.1:5555")
USE_CURVE = os.getenv("ZMQ_CURVE", "1") == "1"
CERT_DIR = os.getenv("ZMQ_CERT_DIR", "/etc/zeromq-server/certs")
ALLOW_IPS = [ip.strip() for ip in os.getenv("ZMQ_ALLOW_IP", "").split(",") if ip.strip()]

log = logging.getLogger("zeromq-server")


class Service:
    def __init__(self) -> None:
        self.running = True
        self.context = zmq.Context()
        self.auth = None
        self.socket = self.context.socket(zmq.REP)
        # Do not keep unsent replies around after close() during shutdown.
        self.socket.setsockopt(zmq.LINGER, 0)

    def stop(self, signum, _frame) -> None:
        log.info("Signal %s received - finishing current request and stopping", signum)
        self.running = False

    def setup_security(self) -> None:
        if not USE_CURVE and not ALLOW_IPS:
            log.warning("Running WITHOUT encryption (ZMQ_CURVE=0)")
            return
        self.auth = ThreadAuthenticator(self.context, log=logging.getLogger("zap"))
        self.auth.start()
        if ALLOW_IPS:
            self.auth.allow(*ALLOW_IPS)
            log.info("IP whitelist: %s", ALLOW_IPS)
        if USE_CURVE:
            authorized = os.path.join(CERT_DIR, "authorized_clients")
            self.auth.configure_curve(domain="*", location=authorized)
            public, secret = zmq.auth.load_certificate(os.path.join(CERT_DIR, "server.key_secret"))
            self.socket.curve_publickey = public
            self.socket.curve_secretkey = secret
            self.socket.curve_server = True
            log.info("CURVE enabled, authorized clients from %s", authorized)
        else:
            self.socket.zap_domain = b"global"  # NULL mechanism + IP filter

    def handle(self, request: dict) -> dict:
        """Business logic - replace with your own."""
        return {"ok": True, "echo": request}

    def run(self) -> int:
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)
        try:
            self.setup_security()
            self.socket.bind(ENDPOINT)
        except (OSError, zmq.ZMQError) as exc:
            log.error("Startup failed: %s", exc)
            return 1  # non-zero exit -> systemd restarts us (Restart=on-failure)

        log.info("Service online at %s", ENDPOINT)
        poller = zmq.Poller()
        poller.register(self.socket, zmq.POLLIN)
        try:
            while self.running:
                if not dict(poller.poll(500)).get(self.socket):
                    continue
                raw = self.socket.recv()
                try:
                    reply = self.handle(json.loads(raw))
                except ValueError:
                    reply = {"ok": False, "error": "invalid JSON"}
                self.socket.send_json(reply)  # REP must always answer
        finally:
            self.socket.close()
            if self.auth:
                self.auth.stop()
            self.context.term()
            log.info("Service stopped cleanly")
        return 0


def main() -> None:
    logging.basicConfig(
        level=os.getenv("ZMQ_LOG_LEVEL", "INFO"),
        # journald adds its own timestamps
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    sys.exit(Service().run())


if __name__ == "__main__":
    main()
