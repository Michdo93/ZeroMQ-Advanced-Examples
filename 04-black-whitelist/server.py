import os, zmq
from zmq.auth.thread import ThreadAuthenticator
ctx=zmq.Context(); auth=ThreadAuthenticator(ctx); auth.start(); auth.configure_plain(domain="demo", passwords={{os.getenv("ZMQ_USER","demo"):os.getenv("ZMQ_PASSWORD","change-me")}})
{rule}
s=ctx.socket(zmq.REP); s.zap_domain=b"demo"; s.setsockopt(zmq.PLAIN_SERVER,1); s.bind(os.getenv("ZMQ_ENDPOINT","tcp://127.0.0.1:5555")); print("Listening; Ctrl-C to stop")
try:
 while True:
  msg=s.recv_json(); s.send_json({"ok":True,"received":msg.get("payload")})
except KeyboardInterrupt: pass
finally: s.close(0); auth.stop(); ctx.term()
