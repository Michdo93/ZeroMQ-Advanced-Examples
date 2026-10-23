import os, zmq
from pathlib import Path
from zmq.auth.thread import ThreadAuthenticator
ctx=zmq.Context(); auth=ThreadAuthenticator(ctx); auth.start(); auth.configure_curve(domain='*',location=os.getenv('ZMQ_AUTHORIZED_DIR','./certs/authorized_clients'))
pub=Path(os.getenv('ZMQ_SERVER_PUBLIC','./certs/server.key')).read_bytes().splitlines()[-1]; sec=Path(os.getenv('ZMQ_SERVER_SECRET','./certs/server.key_secret')).read_bytes().splitlines()[-1]
s=ctx.socket(zmq.REP); s.curve_server=True; s.curve_publickey=pub; s.curve_secretkey=sec; s.bind(os.getenv('ZMQ_ENDPOINT','tcp://*:5555')); print('CURVE server ready; Ctrl-C to stop')
try:
 while True: s.send_json({'ok':True,'echo':s.recv_json()})
except KeyboardInterrupt: pass
finally: s.close(0); auth.stop(); ctx.term()
