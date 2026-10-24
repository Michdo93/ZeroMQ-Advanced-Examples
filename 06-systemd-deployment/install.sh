#!/usr/bin/env bash
# Installs the ZeroMQ example service on Ubuntu (tested target: Ubuntu 26.04).
# Run from the repository root:  sudo bash 06-systemd-deployment/install.sh
set -euo pipefail

APP_DIR=/opt/zeromq-server
CONF_DIR=/etc/zeromq-server
SERVICE_USER=zmqservice
HERE="$(cd "$(dirname "$0")" && pwd)"

if [[ $EUID -ne 0 ]]; then
  echo "Please run with sudo" >&2
  exit 1
fi

apt-get install -y python3 python3-venv

# 1. Dedicated system user without login shell
id -u "$SERVICE_USER" >/dev/null 2>&1 || \
  useradd --system --home /var/lib/zeromq-server --shell /usr/sbin/nologin "$SERVICE_USER"

# 2. Application directory + virtual environment (owned by root, read-only for the service)
install -d -o root -g "$SERVICE_USER" -m 0750 "$APP_DIR"
[[ -d "$APP_DIR/venv" ]] || python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --quiet --upgrade pip pyzmq
install -o root -g "$SERVICE_USER" -m 0640 "$HERE/server.py" "$APP_DIR/server.py"

# 3. Configuration and certificates (secret key readable only by the service user)
install -d -o root -g "$SERVICE_USER" -m 0750 "$CONF_DIR" "$CONF_DIR/certs" "$CONF_DIR/certs/authorized_clients"
[[ -f "$CONF_DIR/zeromq-server.env" ]] || \
  install -o root -g "$SERVICE_USER" -m 0640 "$HERE/zeromq-server.env" "$CONF_DIR/zeromq-server.env"
if [[ ! -f "$CONF_DIR/certs/server.key_secret" ]]; then
  "$APP_DIR/venv/bin/python" -c "import zmq.auth; zmq.auth.create_certificates('$CONF_DIR/certs', 'server')"
fi
chown root:"$SERVICE_USER" "$CONF_DIR/certs/server.key" "$CONF_DIR/certs/server.key_secret"
chmod 0644 "$CONF_DIR/certs/server.key"
chmod 0640 "$CONF_DIR/certs/server.key_secret"

# 4. systemd unit
install -m 0644 "$HERE/zeromq-server.service" /etc/systemd/system/zeromq-server.service
systemctl daemon-reload
systemctl enable --now zeromq-server
systemctl --no-pager status zeromq-server || true

echo
echo "Server public key (give this file to your clients): $CONF_DIR/certs/server.key"
echo "Authorize a client: copy its <name>.key into $CONF_DIR/certs/authorized_clients/ and"
echo "  sudo systemctl restart zeromq-server"
