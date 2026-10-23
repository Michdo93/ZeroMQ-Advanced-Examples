import os, zmq
ctx=zmq.Context(); s=ctx.socket(zmq.REP); s.bind(os.getenv('ZMQ_ENDPOINT','tcp://127.0.0.1:5555')); print('Service online')
try:
 while True: s.send_json({'ok':True,'echo':s.recv_json()})
except KeyboardInterrupt: pass
finally: s.close(0); ctx.term()
