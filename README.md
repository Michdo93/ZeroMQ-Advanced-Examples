# ZeroMQ Advanced Examples

Progressive PyZMQ examples for tokens, ZAP IP policies, CURVE security, and Ubuntu systemd. Python 3.10+; Ubuntu/Debian commands below. These are educational examples and do not replace production security review.

## Install

```bash
sudo apt update && sudo apt install -y python3 python3-venv
python3 -m venv .venv && source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Keep the environment active in each terminal. Windows PowerShell: `.venv\Scripts\Activate.ps1`.

## 1. Application token

Terminal A: `export ZMQ_DEMO_TOKEN='my-local-token'; python 01-password-token/server.py`
Terminal B: `export ZMQ_DEMO_TOKEN='my-local-token'; python 01-password-token/client.py`

Use separate terminals, both from repo root with venv activated. Default endpoint `tcp://127.0.0.1:5555`; customize both peers with the same `ZMQ_ENDPOINT`. Set `ZMQ_DEMO_TOKEN` on both peers to change the token, or use different values to see rejection. The token is sent in plaintext as message data; it is not a secure password transport.

## 2–4. PLAIN credentials and IP rules

Start the chosen server in Terminal A and its matching client in Terminal B. Example blacklist:

```bash
# Terminal A
export ZMQ_USER=demo ZMQ_PASSWORD=change-me ZMQ_DENY_IP=192.0.2.10
python 02-blacklist/server.py
# Terminal B
export ZMQ_USER=demo ZMQ_PASSWORD=change-me
python 02-blacklist/client.py
```

For whitelist use `03-whitelist/server.py` and `ZMQ_ALLOW_IP=127.0.0.1`. For combined rules use `04-black-whitelist/server.py` with both `ZMQ_ALLOW_IP` and `ZMQ_DENY_IP`. Clients read `ZMQ_USER` and `ZMQ_PASSWORD`; change these in both terminals to customize credentials. Defaults are demo/change-me. All use port 5555; set the same `ZMQ_ENDPOINT` in both peers and a free port if another example runs. ZAP rules filter the peer IP as seen by the host; NAT, containers, and proxies affect it. PLAIN and IP rules do not encrypt traffic; use firewall policy and CURVE for remote deployment.

## 5. CURVE keys, distribution, and run

Generate keys:

```bash
python 05-curve-certificates/generate_keys.py --output ./certs --client alice
```

`server.key` and `alice.key` are public; files ending `_secret` are private. Alice's public key is copied under `certs/authorized_clients/`. Never commit or transmit secret keys. For another host, securely transfer the server public key to the client, Alice public key to server authorization directory, and Alice secret key only to Alice's client host. Never transfer server secret to clients. Verify public-key fingerprints out of band and restrict file permissions.

Server terminal:

```bash
export ZMQ_SERVER_PUBLIC=./certs/server.key ZMQ_SERVER_SECRET=./certs/server.key_secret
export ZMQ_AUTHORIZED_DIR=./certs/authorized_clients ZMQ_ENDPOINT='tcp://*:5555'
python 05-curve-certificates/server.py
```

Client terminal (adjust file paths and server IP):

```bash
export ZMQ_CLIENT_PUBLIC=./certs/alice.key ZMQ_CLIENT_SECRET=./certs/alice.key_secret
export ZMQ_SERVER_PUBLIC=./certs/server.key ZMQ_ENDPOINT='tcp://SERVER_IP:5555'
python 05-curve-certificates/client.py
```

For local use set client endpoint to `tcp://127.0.0.1:5555`. Add a client by generating a named pair and placing only its public key under server authorization directory. Configure that client's public/secret paths and the server public path. For rotation replace keys securely and restart as needed. CURVE encrypts the transport and authenticates keys; protect and rotate secrets.

## 6. systemd service on Ubuntu

The unit expects `/opt/zeromq-server/server.py`, virtualenv `/opt/zeromq-server/venv`, and user `zmqservice`. Review the unit and adapt paths before use.

```bash
sudo apt install -y python3 python3-venv
sudo useradd --system --home /var/lib/zeromq-server --shell /usr/sbin/nologin zmqservice
sudo install -d -o root -g zmqservice -m 0750 /opt/zeromq-server /etc/zeromq-server
sudo python3 -m venv /opt/zeromq-server/venv
sudo /opt/zeromq-server/venv/bin/pip install pyzmq
sudo install -o root -g zmqservice -m 0640 06-systemd-deployment/server.py /opt/zeromq-server/server.py
sudo install -m 0644 06-systemd-deployment/zeromq-server.service /etc/systemd/system/zeromq-server.service
```

Optional environment file and start:

```bash
sudo sh -c 'printf "%s\n" "ZMQ_ENDPOINT=tcp://127.0.0.1:5555" > /etc/zeromq-server/zeromq-server.env'
sudo chown root:zmqservice /etc/zeromq-server/zeromq-server.env
sudo chmod 0640 /etc/zeromq-server/zeromq-server.env
sudo systemctl daemon-reload
sudo systemctl enable --now zeromq-server
sudo systemctl status zeromq-server
sudo journalctl -u zeromq-server -f
```

Edit environment file then `sudo systemctl restart zeromq-server`; stop/disable with `systemctl stop zeromq-server` / `systemctl disable zeromq-server`. The supplied systemd script is a basic REP example, not the CURVE server. To deploy CURVE, install CURVE server code, provision secret keys with service-account-only read permissions, and configure paths.

## Testing and troubleshooting

For every paired example, start server first and run its named client; success prints JSON. `Address already in use`: stop another server or choose a matching new endpoint. Timeout: check server, port, firewall, endpoint. CURVE authorization errors: check client's public key in authorized directory and matching paths. Customize request JSON in client and keep server handling aligned. Never place production passwords/private keys in source or public archives.
