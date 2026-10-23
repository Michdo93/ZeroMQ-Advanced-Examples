import os, zmq
ctx=zmq.Context(); s=ctx.socket(zmq.REQ); s.setsockopt(zmq.PLAIN_USERNAME,os.getenv("ZMQ_USER","demo").encode()); s.setsockopt(zmq.PLAIN_PASSWORD,os.getenv("ZMQ_PASSWORD","change-me").encode()); s.setsockopt(zmq.RCVTIMEO,3000); s.connect(os.getenv("ZMQ_ENDPOINT","tcp://127.0.0.1:5555"))
try: s.send_json({"payload":{"action":"status"}}); print(s.recv_json())
except zmq.ZMQError as e: print(f"Authentication/connection failed: {e}")
finally: s.close(0); ctx.term()
