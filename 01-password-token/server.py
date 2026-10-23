import hmac, os, zmq
ctx=zmq.Context(); s=ctx.socket(zmq.REP); s.bind(os.getenv("ZMQ_ENDPOINT","tcp://127.0.0.1:5555")); expected=os.getenv("ZMQ_DEMO_TOKEN","change-me").encode(); print("Token demo listening; Ctrl-C to stop")
try:
 while True:
  msg=s.recv_json(); got=str(msg.get("token","" )).encode(); ok=hmac.compare_digest(got,expected); s.send_json({"ok":ok,"result":{"status":"ready"} if ok else None,"error":None if ok else "unauthorized"})
except KeyboardInterrupt: pass
finally: s.close(0); ctx.term()
