#!/usr/bin/env python3
"""
TC/eBPF gateway for the PIR verifier.

Key changes from the original version:
  1. Dynamic source-level blocking is thresholded by default instead of being
     installed on the first replay signal.
  2. Optional shadow mode records verifier block signals but does not install
     them into the eBPF blocklist.
  3. A small HTTP control API exposes /metrics, /blocks, and /clear so the
     experiment script can collect confirmed drop counters and clear state
     without deleting the clsact qdisc.
  4. The eBPF filter still only applies to TCP traffic whose destination port is
     the verifier port, 8002 by default.

Recommended same-source diagnostic run:
  sudo python scripts/tc_gateway_safe.py eth0 --shadow-derived-block

Recommended separated-source/full run:
  sudo python scripts/tc_gateway_safe.py eth0 --strike-threshold 3 --max-block-ttl 3

Experiment script hooks:
  --ebpf-metrics-url http://124.223.46.199:9003/metrics
  --ebpf-clear-url   http://124.223.46.199:9003/clear
"""

from bcc import BPF
from pyroute2 import IPRoute
import argparse
import json
import socket
import struct
import sys
import threading
import time
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BPF_TEXT_TEMPLATE = r"""
#include <uapi/linux/bpf.h>
#include <uapi/linux/pkt_cls.h>
#include <uapi/linux/if_ether.h>
#include <uapi/linux/ip.h>
#include <uapi/linux/tcp.h>
#include <uapi/linux/in.h>

// Key: source IPv4 address. Value: expiration time in ns.
BPF_HASH(blocklist, u32, u64, 2048);

// counters[0] = packets inspected on verifier port
// counters[1] = dynamic block drops
// counters[2] = static fingerprint drops
// counters[3] = expired blocklist hits that were allowed through
BPF_ARRAY(counters, u64, 4);

static __always_inline void inc_counter(u32 idx) {
    u64 *value = counters.lookup(&idx);
    if (value) {
        __sync_fetch_and_add(value, 1);
    }
}

int tc_filter(struct __sk_buff *skb) {
    void *data = (void *)(long)skb->data;
    void *data_end = (void *)(long)skb->data_end;

    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end) return TC_ACT_OK;
    if (eth->h_proto != bpf_htons(ETH_P_IP)) return TC_ACT_OK;

    struct iphdr *ip = (void *)(eth + 1);
    if ((void *)(ip + 1) > data_end) return TC_ACT_OK;
    if (ip->protocol != IPPROTO_TCP) return TC_ACT_OK;
    if (ip->ihl < 5) return TC_ACT_OK;

    struct tcphdr *tcp = (void *)ip + ip->ihl * 4;
    if ((void *)(tcp + 1) > data_end) return TC_ACT_OK;

    // Important: only protect the verifier port. Do not interfere with issuer,
    // PIR server, auditor, SSH, Redis, etc.
    if (tcp->dest != bpf_htons(__VERIFIER_PORT__)) return TC_ACT_OK;
    if (tcp->doff < 5) return TC_ACT_OK;

    inc_counter(0);

    u32 src_ip = ip->saddr;
    u64 *expire_ts = blocklist.lookup(&src_ip);
    if (expire_ts) {
        u64 now = bpf_ktime_get_ns();
        if (now < *expire_ts) {
            inc_counter(1);
            return TC_ACT_SHOT;
        }
        inc_counter(3);
    }

    unsigned char *payload = (unsigned char *)tcp + (tcp->doff * 4);
    if ((void *)payload > data_end) return TC_ACT_OK;

    // Static toy fingerprint defense retained for compatibility with earlier tests.
    if ((void *)(payload + 4) <= data_end) {
        if (payload[0] == 'H' && payload[1] == 'A' && payload[2] == 'C' && payload[3] == 'K') {
            inc_counter(2);
            return TC_ACT_SHOT;
        }
    }

    return TC_ACT_OK;
}
"""


def ip_to_key(ip_str: str) -> int:
    # Matches ip->saddr representation used by the eBPF program on little-endian hosts.
    return struct.unpack("I", socket.inet_aton(ip_str))[0]


def key_to_ip(value: int) -> str:
    return socket.inet_ntoa(struct.pack("I", value))


class GatewayState:
    def __init__(self, bpf: BPF, args: argparse.Namespace):
        self.bpf = bpf
        self.args = args
        self.blocklist = bpf.get_table("blocklist")
        self.counters = bpf.get_table("counters")
        self.lock = threading.RLock()
        self.strikes = defaultdict(deque)
        self.control_signals_total = 0
        self.blocks_installed_total = 0
        self.shadow_blocks_total = 0
        self.last_signal = None
        self.started_at = time.time()

    def _counter(self, idx: int) -> int:
        try:
            return int(self.counters[self.counters.Key(idx)].value)
        except Exception:
            return 0

    def cleanup_expired_locked(self) -> int:
        now_ns = time.monotonic_ns()
        removed = 0
        for k, v in list(self.blocklist.items()):
            if int(v.value) < now_ns:
                try:
                    del self.blocklist[k]
                    removed += 1
                except Exception:
                    pass
        return removed

    def clear(self) -> dict:
        with self.lock:
            removed = 0
            for k, _ in list(self.blocklist.items()):
                try:
                    del self.blocklist[k]
                    removed += 1
                except Exception:
                    pass
            self.strikes.clear()
            return {"ok": True, "removed_block_entries": removed, "strikes_cleared": True}

    def blocks(self) -> list[dict]:
        with self.lock:
            now_ns = time.monotonic_ns()
            out = []
            for k, v in list(self.blocklist.items()):
                remaining = max(0.0, (int(v.value) - now_ns) / 1e9)
                out.append({"ip": key_to_ip(int(k.value)), "remaining_sec": round(remaining, 3)})
            return out

    def metrics(self) -> dict:
        with self.lock:
            active_blocks = self.blocks()
            return {
                "ok": True,
                "mode": "shadow" if self.args.shadow_derived_block else "enforcing",
                "interface": self.args.interface,
                "verifier_port": self.args.verifier_port,
                "udp_control_port": self.args.control_port,
                "http_metrics_port": self.args.metrics_port,
                "strike_threshold": self.args.strike_threshold,
                "strike_window_sec": self.args.strike_window,
                "max_block_ttl_sec": self.args.max_block_ttl,
                "uptime_sec": round(time.time() - self.started_at, 3),
                "control_signals_total": self.control_signals_total,
                "blocks_installed_total": self.blocks_installed_total,
                "shadow_blocks_total": self.shadow_blocks_total,
                "last_signal": self.last_signal,
                "active_blocks": len(active_blocks),
                "block_entries": active_blocks,
                "tc_packets_on_verifier_port": self._counter(0),
                "tc_dynamic_block_drops": self._counter(1),
                "tc_static_fingerprint_drops": self._counter(2),
                "tc_expired_block_hits_allowed": self._counter(3),
                # Aliases expected by some experiment scripts.
                "ebpf_drop_total": self._counter(1) + self._counter(2),
                "ebpf_dynamic_drop_total": self._counter(1),
                "ebpf_static_drop_total": self._counter(2),
            }

    def process_block_signal(self, ip_str: str, duration_sec: int) -> None:
        now = time.monotonic()
        now_ns = time.monotonic_ns()
        duration_sec = max(0, min(int(duration_sec), int(self.args.max_block_ttl)))

        with self.lock:
            self.control_signals_total += 1
            self.last_signal = {"ip": ip_str, "duration_sec": duration_sec, "ts": time.time()}

            q = self.strikes[ip_str]
            q.append(now)
            while q and now - q[0] > self.args.strike_window:
                q.popleft()

            self.cleanup_expired_locked()

            if self.args.shadow_derived_block:
                self.shadow_blocks_total += 1
                print(
                    f"[CONTROL] Shadow derived block signal: ip={ip_str}, "
                    f"strikes={len(q)}/{self.args.strike_threshold}, ttl={duration_sec}s"
                )
                return

            if len(q) < self.args.strike_threshold:
                print(
                    f"[CONTROL] Derived block signal observed but below threshold: "
                    f"ip={ip_str}, strikes={len(q)}/{self.args.strike_threshold}"
                )
                return

            if duration_sec <= 0:
                print(f"[CONTROL] Block skipped because effective ttl is 0: ip={ip_str}")
                return

            expire_ns = now_ns + duration_sec * 10**9
            ip_u32 = ip_to_key(ip_str)
            self.blocklist[self.blocklist.Key(ip_u32)] = self.blocklist.Leaf(expire_ns)
            self.blocks_installed_total += 1
            q.clear()
            print(
                f"[CONTROL] Derived block installed: ip={ip_str}, ttl={duration_sec}s, "
                f"threshold={self.args.strike_threshold}/{self.args.strike_window}s"
            )


def control_plane_worker(state: GatewayState) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", state.args.control_port))
    print(f"[INFO] UDP control plane ready on 0.0.0.0:{state.args.control_port}")

    while True:
        try:
            data, _ = sock.recvfrom(1024)
            parts = data.decode(errors="replace").strip().split()
            if len(parts) == 3 and parts[0] == "BLOCK":
                ip_str, duration_sec = parts[1], int(parts[2])
                # Validate IPv4 string.
                socket.inet_aton(ip_str)
                state.process_block_signal(ip_str, duration_sec)
            else:
                print(f"[CONTROL WARN] Ignoring malformed control message: {data!r}")
        except Exception as e:
            print(f"[CONTROL ERROR] {type(e).__name__}: {e}")


def make_handler(state: GatewayState):
    class Handler(BaseHTTPRequestHandler):
        def _send_json(self, status: int, obj: dict | list) -> None:
            body = json.dumps(obj, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            # Keep experiment logs clean.
            return

        def do_GET(self):
            if self.path.startswith("/metrics"):
                self._send_json(200, state.metrics())
            elif self.path.startswith("/blocks"):
                self._send_json(200, {"ok": True, "blocks": state.blocks()})
            elif self.path.startswith("/clear"):
                self._send_json(200, state.clear())
            else:
                self._send_json(404, {"ok": False, "error": "not found"})

        def do_POST(self):
            if self.path.startswith("/clear"):
                self._send_json(200, state.clear())
            else:
                self._send_json(404, {"ok": False, "error": "not found"})

    return Handler


def http_metrics_worker(state: GatewayState) -> None:
    server = ThreadingHTTPServer(("0.0.0.0", state.args.metrics_port), make_handler(state))
    print(f"[INFO] HTTP metrics/control API ready on http://0.0.0.0:{state.args.metrics_port}")
    server.serve_forever()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Safe TC/eBPF gateway for PIR verifier")
    parser.add_argument("interface", nargs="?", default="eth0", help="network interface, default: eth0")
    parser.add_argument("--verifier-port", type=int, default=8002, help="protected verifier TCP port")
    parser.add_argument("--control-port", type=int, default=9002, help="UDP port for verifier BLOCK signals")
    parser.add_argument("--metrics-port", type=int, default=9003, help="HTTP metrics/control port")
    parser.add_argument("--strike-threshold", type=int, default=3, help="BLOCK signals required before installing L4 block")
    parser.add_argument("--strike-window", type=float, default=2.0, help="seconds for counting strike threshold")
    parser.add_argument("--max-block-ttl", type=int, default=3, help="cap verifier-requested block TTL")
    parser.add_argument("--shadow-derived-block", action="store_true", help="observe verifier BLOCK signals but do not install eBPF block entries")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bpf_text = BPF_TEXT_TEMPLATE.replace("__VERIFIER_PORT__", str(args.verifier_port))

    print(f"--- Safe TC/eBPF Gateway on {args.interface} | verifier port {args.verifier_port} ---")
    print(
        f"[CONFIG] mode={'shadow' if args.shadow_derived_block else 'enforcing'}, "
        f"threshold={args.strike_threshold}/{args.strike_window}s, max_ttl={args.max_block_ttl}s"
    )

    ipr = IPRoute()
    matches = ipr.link_lookup(ifname=args.interface)
    if not matches:
        print(f"[ERROR] Interface {args.interface} not found. Please check 'ip addr'.")
        sys.exit(1)
    idx = matches[0]

    b = BPF(text=bpf_text, cflags=["-Wno-macro-redefined"])
    fn = b.load_func("tc_filter", BPF.SCHED_CLS)

    try:
        ipr.tc("del", "clsact", idx)
    except Exception:
        pass

    ipr.tc("add", "clsact", idx)
    ipr.tc(
        "add-filter",
        "bpf",
        idx,
        ":1",
        fd=fn.fd,
        name=fn.name,
        parent="ffff:fff2",
        classid=1,
        direct_action=True,
    )

    state = GatewayState(b, args)
    threading.Thread(target=control_plane_worker, args=(state,), daemon=True).start()
    threading.Thread(target=http_metrics_worker, args=(state,), daemon=True).start()

    print(f"[SUCCESS] TC ingress filter attached to {args.interface}.")
    print(f"[HINT] Metrics: http://<server-ip>:{args.metrics_port}/metrics")
    print(f"[HINT] Clear blocklist without detaching TC: curl -X POST http://<server-ip>:{args.metrics_port}/clear")

    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\n[INFO] Keyboard interrupt received. Detaching...")
    finally:
        try:
            ipr.tc("del", "clsact", idx)
            print(f"[INFO] Detached clsact from {args.interface}. Cleanup complete.")
        except Exception as e:
            print(f"[WARN] Cleanup failed or already detached: {e}")


if __name__ == "__main__":
    main()
