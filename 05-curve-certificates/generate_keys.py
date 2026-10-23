import argparse, os
from pathlib import Path
import zmq
p=argparse.ArgumentParser(); p.add_argument('--output',default='certs'); p.add_argument('--client',default='client'); a=p.parse_args(); root=Path(a.output); auth=root/'authorized_clients'; auth.mkdir(parents=True,exist_ok=True)
def save(path,pub,sec=None):
 path.write_bytes(b'# public
'+pub+b'
');
 if sec is not None: path.with_name(path.stem+'.key_secret').write_bytes(b'# secret
'+sec+b'
'); os.chmod(path.with_name(path.stem+'.key_secret'),0o600)
sp,ss=zmq.curve_keypair(); save(root/'server.key',sp,ss); cp,cs=zmq.curve_keypair(); save(root/f'{a.client}.key',cp,cs); save(auth/f'{a.client}.key',cp)
print(f'Created key files in {root}. Keep all *_secret files private; install client public key under authorized_clients/.')
