# CURVE certificate example

Install the root dependencies, then create a key set:

```bash
python generate_keys.py --output ./certs --client alice
```

The script creates a server public/secret pair, an Alice client pair, and an `authorized_clients` directory. Keep `*.key_secret` private. Copy the server public key and Alice's public and secret key to the client machine; copy only Alice's public key to the server authorization directory. Use a secure transfer channel and verify public-key fingerprints. Never copy the server secret key to a client.

```bash
# server host
export ZMQ_SERVER_SECRET=./certs/server.key_secret
export ZMQ_AUTHORIZED_DIR=./certs/authorized_clients
python server.py
# client host
export ZMQ_CLIENT_PUBLIC=./certs/alice.key
export ZMQ_CLIENT_SECRET=./certs/alice.key_secret
export ZMQ_SERVER_PUBLIC=/secure/path/server.key
export ZMQ_ENDPOINT=tcp://SERVER_IP:5555
python client.py
```

For a real deployment, provision keys through a managed secret channel, set restrictive file permissions, and rotate keys. Bind/firewall the port deliberately.
