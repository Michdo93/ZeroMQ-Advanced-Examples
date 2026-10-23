import os, zmq
endpoint=os.getenv("ZMQ_ENDPOINT","tcp://127.0.0.1:5555")
ctx=zmq.Context(); s=ctx.socket(zmq.REQ); s.setsockopt(zmq.RCVTIMEO,3000); s.setsockopt(zmq.SNDTIMEO,3000); s.connect(endpoint)
try:
 s.send_json({"token":os.getenv("ZMQ_DEMO_TOKEN","change-me"),"payload":{"action":"status"}})
 print(s.recv_json())
except zmq.ZMQError as e: print(f"Request failed: {e}")
finally: s.close(0); ctx.term()
