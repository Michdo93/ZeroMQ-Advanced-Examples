# ZeroMQ Advanced Examples

Step-by-step security and deployment examples for **ZeroMQ in Python (pyzmq)** – from a simple application token up to a hardened, CURVE-encrypted **systemd** service on Ubuntu, plus a small **ZeroMQ vs. MQTT** benchmark.

Companion repository of the book *From Zero to Hero – ZeroMQ in Python meistern*.

| Step | Folder | Topic | Encrypted? |
|-----:|--------|-------|:----------:|
| 1 | [`01-password-token`](01-password-token) | Shared token inside the JSON payload (application level) | no |
| 2 | [`02-blacklist`](02-blacklist) | ZAP: PLAIN username/password + IP **blacklist** | no |
| 3 | [`03-whitelist`](03-whitelist) | ZAP: PLAIN username/password + IP **whitelist** | no |
| 4 | [`04-black-whitelist`](04-black-whitelist) | Own ZAP handler: CIDR whitelist **and** blacklist + PLAIN | no |
| 5 | [`05-curve-certificates`](05-curve-certificates) | CURVE certificates, key distribution, client whitelist | **yes** |
| 6 | [`06-systemd-deployment`](06-systemd-deployment) | Production service: CURVE + SIGTERM + journald + systemd hardening | **yes** |
| 7 | [`07-mqtt-comparison`](07-mqtt-comparison) | Latency/throughput/CPU/RAM: ZeroMQ vs. MQTT (mosquitto) | – |

---

## Installation

Tested with Python 3.12/3.13, pyzmq 27, libzmq 4.3.5 on Ubuntu.

```bash
sudo apt update
sudo apt install -y python3 python3-venv
git clone https://github.com/Michdo93/ZeroMQ-Advanced-Examples.git
cd ZeroMQ-Advanced-Examples
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Check that your libzmq supports CURVE (the pyzmq wheels always do):

```bash
python -c "import zmq; print(zmq.zmq_version(), 'CURVE:', zmq.has('curve'))"
```

All examples are configured through **environment variables**, never by editing secrets into source code. Run every command from the repository root, server and client in separate terminals.

> **Testing IP rules on one machine:** ZeroMQ can force the *source* address of a TCP connection: `tcp://127.0.0.2:0;127.0.0.1:5555` means "connect from 127.0.0.2 to 127.0.0.1:5555". All of `127.0.0.0/8` is loopback on Linux, so you can simulate several "hosts" locally.

---

## Step 1 – Application token

```bash
# Terminal A
export ZMQ_DEMO_TOKEN='my-local-token'
python 01-password-token/server.py
# Terminal B
export ZMQ_DEMO_TOKEN='my-local-token'
python 01-password-token/client.py      # -> {'ok': True, ...}
ZMQ_DEMO_TOKEN=wrong python 01-password-token/client.py   # -> unauthorized
```

The token is compared with `hmac.compare_digest` (constant time). It is still sent in **plaintext** – this step only illustrates the idea.

## Step 2 – PLAIN + IP blacklist (ZAP)

```bash
# Terminal A
export ZMQ_USER=demo ZMQ_PASSWORD=change-me ZMQ_DENY_IP=127.0.0.2
python 02-blacklist/server.py
# Terminal B
python 02-blacklist/client.py                                        # accepted
ZMQ_ENDPOINT='tcp://127.0.0.2:0;127.0.0.1:5555' python 02-blacklist/client.py   # blacklisted
ZMQ_PASSWORD=wrong python 02-blacklist/client.py                     # wrong password
```

`ThreadAuthenticator` runs a ZAP handler thread. **The ZAP domain configured with `configure_plain(domain=...)` must match `socket.zap_domain`** (`"*"` is only used for sockets without a domain).

Set `ZMQ_LOG_LEVEL=DEBUG` to see every ZAP decision. Warning: pyzmq then also logs PLAIN passwords in clear text.

## Step 3 – PLAIN + IP whitelist

```bash
export ZMQ_ALLOW_IP=127.0.0.1
python 03-whitelist/server.py
# other terminal
python 03-whitelist/client.py                                         # accepted
ZMQ_ENDPOINT='tcp://127.0.0.3:0;127.0.0.1:5555' python 03-whitelist/client.py    # rejected
```

As soon as one address is allowed, **all others are rejected**.

## Step 4 – Whitelist *and* blacklist (own ZAP handler)

pyzmq's authenticator raises `ValueError` if `allow()` and `deny()` are combined and only matches exact IP strings. Step 4 implements the ZAP protocol directly (REP socket on `inproc://zeromq.zap.01`) and supports CIDR networks:

```bash
export ZMQ_ALLOW_NET=127.0.0.0/8,192.168.1.0/24 ZMQ_DENY_NET=127.0.0.2/32,192.168.1.50/32
python 04-black-whitelist/server.py
# other terminal
python 04-black-whitelist/client.py
ZMQ_ENDPOINT='tcp://127.0.0.2:0;127.0.0.1:5555' python 04-black-whitelist/client.py
```

The server log shows every decision, e.g. `127.0.0.2 PLAIN -> 400 IP is blacklisted`. The authenticated user name is read from the message metadata (`frame.get("User-Id")`).

**PLAIN and IP rules do not encrypt anything.** For untrusted networks continue with step 5.

## Step 5 – CURVE certificates

### 5.1 Generate certificates

```bash
python 05-curve-certificates/generate_keys.py                    # server + client "alice"
python 05-curve-certificates/generate_keys.py --client bob --no-server
```

```
certs/
├── server/server.key, server.key_secret      # stays on the server
├── clients/alice.key, alice.key_secret       # alice.* go to Alice's machine
└── authorized_clients/alice.key              # server-side whitelist (public keys only)
```

`*.key` = public certificate, `*.key_secret` = secret certificate (mode 0600). Files use the standard ZeroMQ certificate format (`zmq.auth.create_certificates` / `zmq.auth.load_certificate`).

### 5.2 Run locally

```bash
python 05-curve-certificates/server.py
python 05-curve-certificates/client.py
```

### 5.3 Distribute to a second system

| File | Server host | Client host (Alice) |
|------|:-----------:|:-------------------:|
| `server/server.key_secret` | ✅ | ❌ never |
| `server/server.key` | ✅ | ✅ |
| `clients/alice.key_secret` | ❌ (delete after copying) | ✅ |
| `clients/alice.key` | ✅ in `authorized_clients/` | ✅ |

Ideally create Alice's key pair **on Alice's machine** and only transfer her public key:

```bash
# on the client host
python 05-curve-certificates/generate_keys.py --client alice --no-server
scp certs/clients/alice.key admin@server:/path/to/certs/authorized_clients/
scp admin@server:/path/to/certs/server/server.key certs/server/
# compare fingerprints out of band, e.g.
sha256sum certs/server/server.key
```

Client on the other host:

```bash
export ZMQ_ENDPOINT=tcp://SERVER_IP:5555
export ZMQ_CLIENT_SECRET=certs/clients/alice.key_secret
export ZMQ_SERVER_PUBLIC=certs/server/server.key
python 05-curve-certificates/client.py
```

Revoking a client = deleting its file from `authorized_clients/` and restarting the server (pyzmq loads the directory once at startup). Combine with `ZMQ_ALLOW_IP` for an additional IP whitelist. Open the port in the firewall only for known networks, e.g. `sudo ufw allow from 192.168.1.0/24 to any port 5555 proto tcp`.

## Step 6 – systemd service on Ubuntu

```bash
sudo bash 06-systemd-deployment/install.sh
```

The script creates the system user `zmqservice`, installs the code + venv to `/opt/zeromq-server`, the configuration to `/etc/zeromq-server/zeromq-server.env`, generates the server certificate in `/etc/zeromq-server/certs/` and enables `zeromq-server.service`.

```bash
# authorize a client
sudo cp alice.key /etc/zeromq-server/certs/authorized_clients/
sudo systemctl restart zeromq-server
# operate
systemctl status zeromq-server
journalctl -u zeromq-server -f
sudo systemctl restart zeromq-server    # SIGTERM -> graceful shutdown -> start
sudo systemctl disable --now zeromq-server
```

Key points of the unit file: dedicated user, `Restart=on-failure`, `TimeoutStopSec`, `StateDirectory`, `ProtectSystem=strict`, `NoNewPrivileges`, empty `CapabilityBoundingSet`. Check the hardening score with `systemd-analyze security zeromq-server`.

Updating the code: copy the new `server.py` to `/opt/zeromq-server/` and `sudo systemctl restart zeromq-server`. Connected ZeroMQ clients reconnect automatically; clients should use timeouts/retries (see the *Lazy Pirate* pattern) so that a request sent during the restart is repeated.

## Step 7 – ZeroMQ vs. MQTT

```bash
sudo apt install -y mosquitto
pip install paho-mqtt psutil
sudo systemctl stop mosquitto          # free port 1883 for the benchmark config
mosquitto -c 07-mqtt-comparison/mosquitto-bench.conf &
python 07-mqtt-comparison/benchmark.py
python 07-mqtt-comparison/benchmark.py --size 50000 --messages 5000 --roundtrips 500
```

Example output (2 vCPU Xeon @ 2.1 GHz, loopback, 64-byte payload):

```
ZeroMQ REQ/REP     median    114.5 us   p99    237.8 us
MQTT QoS 0         median    240.5 us   p99    557.7 us
MQTT QoS 1         median    260.5 us   p99    865.7 us
ZeroMQ PUSH/PULL   820632 msg/s   sender CPU 0.07 s
MQTT QoS 0          26386 msg/s   sender CPU 0.68 s   broker CPU 0.24 s
MQTT QoS 1          14309 msg/s   sender CPU 2.32 s   broker CPU 0.71 s
```

`mosquitto-bench.conf` enables `set_tcp_nodelay`; without it QoS-1 round trips are dominated by Nagle/delayed-ACK effects (40–90 ms). Throughput numbers include the overhead of the pure-Python MQTT client – treat them as indicative only.

---

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| Client prints "No reply" | Rejected by ZAP (IP, password, key), wrong endpoint or server down. A rejected handshake is silent on the client side. Start the server with `ZMQ_LOG_LEVEL=DEBUG`. |
| `Address already in use` | Another example still runs on port 5555 – stop it or change `ZMQ_ENDPOINT` on both sides. |
| `ValueError: Only use allow or deny, not both` | pyzmq authenticator limitation – use step 4. |
| CURVE client always rejected | Public key not in `authorized_clients/`, server not restarted, or wrong `ZMQ_SERVER_PUBLIC`. |
| Service restarts in a loop | `journalctl -u zeromq-server -e` – usually missing certificates or wrong permissions. |

Never commit `*.key_secret` files or production passwords (see `.gitignore`).
