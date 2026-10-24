"""Step 7: Small, reproducible ZeroMQ vs. MQTT comparison on ONE machine.

Measures for both technologies
  1. round-trip latency (ping -> pong) with small messages, and
  2. one-way throughput of N messages,
plus CPU time and memory (RSS) of all involved processes - including the
MQTT broker, which ZeroMQ simply does not need.

This is not a scientific benchmark. Results depend on hardware, OS, payload
size, Python version and broker configuration. It is meant to make the
architectural difference (direct peer connection vs. hop over a broker)
measurable on your own system.

Requirements:
    sudo apt install mosquitto
    # Start the broker with TCP_NODELAY, otherwise QoS 1 round trips are
    # dominated by Nagle/delayed-ACK effects (~40-90 ms):
    mosquitto -c mosquitto-bench.conf
    pip install pyzmq paho-mqtt psutil

Usage:
    python benchmark.py                       # defaults
    python benchmark.py --roundtrips 5000 --messages 100000 --size 256
"""

import argparse
import multiprocessing as mp
import socket
import statistics
import time

import psutil
import zmq

try:
    import paho.mqtt.client as mqtt
except ImportError:  # MQTT part is optional
    mqtt = None

ZMQ_RT = "tcp://127.0.0.1:5601"
ZMQ_TP = "tcp://127.0.0.1:5602"
BROKER = ("127.0.0.1", 1883)


# --------------------------------------------------------------------------
# ZeroMQ peers
# --------------------------------------------------------------------------
def zmq_echo(n: int) -> None:
    ctx = zmq.Context()
    s = ctx.socket(zmq.REP)
    s.bind(ZMQ_RT)
    for _ in range(n):
        s.send(s.recv())
    s.close()
    ctx.term()


def zmq_sink(n: int, ready) -> None:
    ctx = zmq.Context()
    s = ctx.socket(zmq.PULL)
    s.setsockopt(zmq.RCVHWM, 0)
    s.bind(ZMQ_TP)
    ready.set()
    for _ in range(n):
        s.recv()
    s.close()
    ctx.term()


def zmq_roundtrip(n: int, size: int) -> list:
    proc = mp.Process(target=zmq_echo, args=(n,))
    proc.start()
    ctx = zmq.Context()
    s = ctx.socket(zmq.REQ)
    s.connect(ZMQ_RT)
    payload = b"x" * size
    s.send(payload)
    s.recv()  # warm-up, connection established
    samples = []
    for _ in range(n - 1):
        t0 = time.perf_counter_ns()
        s.send(payload)
        s.recv()
        samples.append((time.perf_counter_ns() - t0) / 1000)
    s.close()
    ctx.term()
    proc.join()
    return samples


def zmq_throughput(n: int, size: int):
    ready = mp.Event()
    proc = mp.Process(target=zmq_sink, args=(n, ready))
    proc.start()
    ready.wait()
    ctx = zmq.Context()
    s = ctx.socket(zmq.PUSH)
    s.setsockopt(zmq.SNDHWM, 0)
    s.connect(ZMQ_TP)
    payload = b"x" * size
    me = psutil.Process()
    cpu0 = me.cpu_times().user + me.cpu_times().system
    t0 = time.perf_counter()
    for _ in range(n):
        s.send(payload)
    proc.join()
    elapsed = time.perf_counter() - t0
    cpu = me.cpu_times().user + me.cpu_times().system - cpu0
    rss = me.memory_info().rss
    s.close()
    ctx.term()
    return n / elapsed, cpu, rss, None


# --------------------------------------------------------------------------
# MQTT peers (paho-mqtt 2.x, via local mosquitto)
# --------------------------------------------------------------------------
def _client(name: str):
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=name)
    c.max_queued_messages_set(0)  # 0 = unlimited client-side queue
    c.max_inflight_messages_set(100)  # allow more unacknowledged QoS>0 messages
    c.connect(*BROKER)
    # Disable Nagle on the client side as well (fair comparison: libzmq
    # sets TCP_NODELAY on its TCP sockets by default).
    c.socket().setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    return c


def mqtt_echo(n: int, qos: int, ready) -> None:
    c = _client("echo")
    count = {"n": 0}

    def on_message(client, _userdata, msg):
        client.publish("bench/pong", msg.payload, qos=qos)
        count["n"] += 1

    c.on_message = on_message
    c.subscribe("bench/ping", qos=qos)
    c.loop_start()
    time.sleep(0.3)
    ready.set()
    while count["n"] < n:
        time.sleep(0.01)
    time.sleep(0.2)
    c.loop_stop()
    c.disconnect()


def mqtt_roundtrip(n: int, size: int, qos: int) -> list:
    ready = mp.Event()
    proc = mp.Process(target=mqtt_echo, args=(n, qos, ready))
    proc.start()
    ready.wait()
    import threading

    got = threading.Event()
    c = _client("pinger")
    c.on_message = lambda *_: got.set()
    c.subscribe("bench/pong", qos=qos)
    c.loop_start()
    time.sleep(0.3)
    payload = b"x" * size
    samples = []
    for i in range(n):
        got.clear()
        t0 = time.perf_counter_ns()
        c.publish("bench/ping", payload, qos=qos)
        got.wait(5)
        if i:  # first one is warm-up
            samples.append((time.perf_counter_ns() - t0) / 1000)
    c.loop_stop()
    c.disconnect()
    proc.join()
    return samples


def mqtt_sink(n: int, qos: int, ready) -> None:
    c = _client("sink")
    count = {"n": 0}

    def on_message(*_):
        count["n"] += 1

    c.on_message = on_message
    c.subscribe("bench/data", qos=qos)
    c.loop_start()
    time.sleep(0.3)
    ready.set()
    deadline = time.time() + 120
    while count["n"] < n and time.time() < deadline:
        time.sleep(0.005)
    c.loop_stop()
    c.disconnect()


def mqtt_throughput(n: int, size: int, qos: int):
    broker = next((p for p in psutil.process_iter(["name"]) if p.info["name"] == "mosquitto"), None)
    ready = mp.Event()
    proc = mp.Process(target=mqtt_sink, args=(n, qos, ready))
    proc.start()
    ready.wait()
    c = _client("producer")
    c.loop_start()
    payload = b"x" * size
    me = psutil.Process()
    cpu0 = me.cpu_times().user + me.cpu_times().system
    b_cpu0 = sum(broker.cpu_times()[:2]) if broker else 0
    t0 = time.perf_counter()
    for _ in range(n):
        c.publish("bench/data", payload, qos=qos)
    proc.join()
    elapsed = time.perf_counter() - t0
    cpu = me.cpu_times().user + me.cpu_times().system - cpu0
    broker_cpu = (sum(broker.cpu_times()[:2]) - b_cpu0) if broker else None
    rss = me.memory_info().rss
    broker_rss = broker.memory_info().rss if broker else None
    c.loop_stop()
    c.disconnect()
    return n / elapsed, cpu, rss, (broker_cpu, broker_rss)


# --------------------------------------------------------------------------
def report(name: str, samples: list) -> None:
    samples = sorted(samples)
    p99 = samples[int(len(samples) * 0.99) - 1]
    print(f"{name:<18} median {statistics.median(samples):8.1f} us   "
          f"mean {statistics.mean(samples):8.1f} us   p99 {p99:8.1f} us")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--roundtrips", type=int, default=2000)
    ap.add_argument("--messages", type=int, default=50000)
    ap.add_argument("--size", type=int, default=64, help="payload size in bytes")
    a = ap.parse_args()

    print(f"pyzmq {zmq.__version__} / libzmq {zmq.zmq_version()}, payload {a.size} bytes\n")
    print("Round-trip latency (ping -> pong):")
    report("ZeroMQ REQ/REP", zmq_roundtrip(a.roundtrips, a.size))
    if mqtt:
        report("MQTT QoS 0", mqtt_roundtrip(a.roundtrips, a.size, 0))
        report("MQTT QoS 1", mqtt_roundtrip(a.roundtrips, a.size, 1))

    print(f"\nOne-way throughput, {a.messages} messages:")
    rows = [("ZeroMQ PUSH/PULL", zmq_throughput(a.messages, a.size))]
    if mqtt:
        rows.append(("MQTT QoS 0", mqtt_throughput(a.messages, a.size, 0)))
        rows.append(("MQTT QoS 1", mqtt_throughput(a.messages, a.size, 1)))
    for name, (rate, cpu, rss, broker) in rows:
        line = f"{name:<18} {rate:10.0f} msg/s   sender CPU {cpu:5.2f} s   sender RSS {rss/2**20:5.1f} MiB"
        if broker and broker[0] is not None:
            line += f"   broker CPU {broker[0]:5.2f} s, broker RSS {broker[1]/2**20:5.1f} MiB"
        print(line)


if __name__ == "__main__":
    main()
