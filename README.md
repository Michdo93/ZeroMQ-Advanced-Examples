# ZeroMQ Advanced Examples

A progressive Python learning repository for ZeroMQ application authentication, IP access rules, CURVE encryption, key distribution, and supervised Linux deployment. These examples use Ubuntu 22.04+ and Python 3.10+; commands also apply to compatible Debian-based systems.

> Security note: a password exchanged by application messages is not encrypted on a NULL socket. IP filtering is access control, not cryptography. Use CURVE for confidentiality and peer authentication, and protect secret keys and network exposure. Do not expose the demo endpoints to untrusted networks.

## Install

```bash
sudo apt update && sudo apt install -y python3 python3-venv
python3 -m venv .venv && . .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Run each server in one terminal and its client in another from the repository root. The demos bind to loopback by default where practical. Set `ZMQ_ENDPOINT` to change the endpoint. The default token is for local learning only; set `ZMQ_DEMO_TOKEN` on both sides.

## Examples

1. `01-password-token`: application-level shared-token challenge, with constant-time comparison.
2. `02-blacklist`: deny a peer using the ZAP authenticator.
3. `03-whitelist`: allow only configured peer addresses.
4. `04-black-whitelist`: apply allow rules and explicit denies.
5. `05-curve-certificates`: CURVE server/client keys, authorized client-key directory, and key deployment guidance.
6. `06-systemd-deployment`: dedicated service account, virtual environment, hardened systemd unit, and journal commands.

The ZAP IP policy examples are intentionally local demonstrations. NAT, proxies, containers, and multiple interfaces affect the address observed by the authenticator. Firewall rules are the right place for network perimeter policy.

## CURVE key generation and second-system setup

```bash
python 05-curve-certificates/generate_keys.py --output ./local-certs
```

Install `server.key_secret` only on the server, `server.key` on each client, and each client's `client-<name>.key` on the server under `authorized_clients/`. The files ending in `.key_secret` contain secrets and must never be committed or sent over chat. Transfer keys through a secure channel, restrict permissions (`chmod 600` for secret files), and rotate them if exposed. Configure `ZMQ_CERT_DIR` and `ZMQ_AUTHORIZED_DIR` as described in that folder's README. Public keys are not secret, but still verify their fingerprints out of band.

## Run the systemd example

Read `06-systemd-deployment/README.md` before installation. It explains paths, user creation, environment settings, permissions, service activation, updates, and logs. The unit is a template: review and adapt the paths before installing.

## Limitations

These are educational starting points, not a complete production security review. Add monitoring, resource limits, firewall policy, key rotation, protocol versioning, request validation, and operational recovery appropriate to your service. Never use `auth.allow("*")` as an access policy.
