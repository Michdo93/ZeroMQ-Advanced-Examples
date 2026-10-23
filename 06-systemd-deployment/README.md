# systemd deployment (Ubuntu)

Assumptions: checkout at `/opt/zeromq-server`, virtual environment at `/opt/zeromq-server/venv`, and service user `zmqservice`. Adapt these paths in the unit before installation. Install Python and create a locked-down service account:

```bash
sudo apt update && sudo apt install -y python3 python3-venv
sudo useradd --system --home /var/lib/zeromq-server --shell /usr/sbin/nologin zmqservice
sudo install -d -o root -g zmqservice -m 0750 /opt/zeromq-server
sudo python3 -m venv /opt/zeromq-server/venv
sudo /opt/zeromq-server/venv/bin/pip install pyzmq
```

Install the matching server script as `/opt/zeromq-server/server.py`, set appropriate ownership and create an environment file with restricted permissions (do not commit secrets). For CURVE, store key files in a root-owned directory readable by the service group, mode 0640 for the secret file.

```bash
sudo install -m 0644 zeromq-server.service /etc/systemd/system/zeromq-server.service
sudo systemctl daemon-reload
sudo systemctl enable --now zeromq-server
sudo systemctl status zeromq-server
sudo journalctl -u zeromq-server -f
```

The provided unit expects `/opt/zeromq-server/server.py`. Review the environment file location and endpoint before starting. Update with `systemctl restart`; stop with `systemctl stop`.
