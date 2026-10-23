import os, zmq
from pathlib import Path
def key(name): return Path(os.environ[name]).read_bytes().splitlines()[-1]
ctx=zmq.Context(); s=ctx.socket(zmq.REQ); s.curve_publickey=key('ZMQ_CLIENT_PUBLIC'); s.curve_secretkey=key('ZMQ_CLIENT_SECRET'); s.curve_serverkey=key('ZMQ_SERVER_PUBLIC'); s.setsockopt(zmq.RCVTIMEO,5000); s.connect(os.getenv('ZMQ_ENDPOINT','tcp://127.0.0.1:5555'))
try: s.send_json({'message':'hello over CURVE'}); print(s.recv_json())
finally: s.close(0); ctx.term()
