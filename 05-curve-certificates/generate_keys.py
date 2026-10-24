"""Step 5a: Create CURVE certificates (Curve25519 key pairs).

Uses zmq.auth.create_certificates(), which writes the standard ZeroMQ
certificate format (ZPL text files):
    <name>.key          public certificate  -> may be distributed
    <name>.key_secret   secret certificate  -> never leaves its host

Resulting layout (default --output certs):

    certs/
    |-- server/server.key, server.key_secret     (stays on the server)
    |-- clients/<name>.key, <name>.key_secret    (copy to the client host)
    `-- authorized_clients/<name>.key            (server-side whitelist)

Usage:
    python generate_keys.py                         # server + client "alice"
    python generate_keys.py --client bob --no-server # add another client
"""

import argparse
import os
import shutil
from pathlib import Path

import zmq
import zmq.auth


def create(directory: Path, name: str) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    public_file, secret_file = zmq.auth.create_certificates(str(directory), name)
    os.chmod(secret_file, 0o600)  # readable by the owner only
    return Path(public_file), Path(secret_file)


def main() -> None:
    if not zmq.has("curve"):
        raise SystemExit("This libzmq build has no CURVE support (libsodium missing).")

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", default="certs", help="output directory")
    parser.add_argument("--client", default="alice", help="client certificate name")
    parser.add_argument("--no-server", action="store_true", help="do not (re)create the server key pair")
    args = parser.parse_args()

    root = Path(args.output)
    if not args.no_server:
        pub, _ = create(root / "server", "server")
        print(f"Server certificate : {pub}")

    pub, sec = create(root / "clients", args.client)
    authorized = root / "authorized_clients"
    authorized.mkdir(parents=True, exist_ok=True)
    shutil.copy(pub, authorized / pub.name)
    print(f"Client certificate : {pub} / {sec}")
    print(f"Authorized on server: {authorized / pub.name}")
    print("\nNever copy a *.key_secret file to another machine than its owner.")


if __name__ == "__main__":
    main()
