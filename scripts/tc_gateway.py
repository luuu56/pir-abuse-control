# scripts/tc_gateway.py
from bcc import BPF
from pyroute2 import IPRoute
import sys
import socket
import struct
import threading
import time

# --- 1. eBPF C 代码 (严格将 Block 限制在 8002 端口) ---
bpf_text = """
#include <uapi/linux/bpf.h>
#include <uapi/linux/pkt_cls.h>
#include <uapi/linux/if_ether.h>
#include <uapi/linux/ip.h>
#include <uapi/linux/tcp.h>
#include <uapi/linux/in.h>

// 封禁表：Key 为 Source IP, Value 为到期时间 (纳秒)
BPF_HASH(blocklist, u32, u64, 2048);

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
    
    // 【最大修复】：必须先判断是否发往 Verifier 端口，绝不能干扰 Issuer(8001)
    if (tcp->dest != bpf_htons(8002)) return TC_ACT_OK;
    if (tcp->doff < 5) return TC_ACT_OK;

    // --- 动态联动判定 (仅针对 8002 端口生效) ---
    u32 src_ip = ip->saddr;
    u64 *expire_ts = blocklist.lookup(&src_ip);
    if (expire_ts) {
        u64 now = bpf_ktime_get_ns();
        if (now < *expire_ts) {
            bpf_trace_printk("[TC DROP] Derived Block: source IP matched short-term L4 blocklist\\n");
            return TC_ACT_SHOT;
        }
    }

    unsigned char *payload = (unsigned char *)tcp + (tcp->doff * 4);
    if ((void *)payload > data_end) return TC_ACT_OK;

    // Day 38 静态指纹防线
    if ((void *)(payload + 4) <= data_end) {
        if (payload[0] == 'H' && payload[1] == 'A' && payload[2] == 'C' && payload[3] == 'K') {
            bpf_trace_printk("[TC DROP] Static Fingerprint: HACK detected\\n");
            return TC_ACT_SHOT;
        }
    }

    return TC_ACT_OK;
}
"""

def control_plane_worker(b):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 9002))
    blocklist = b.get_table("blocklist")
    print("[INFO] Control Plane (UDP 9002) is ready to receive derived decisions...")
    
    while True:
        try:
            data, _ = sock.recvfrom(1024)
            parts = data.decode().strip().split()
            if len(parts) == 3 and parts[0] == "BLOCK":
                ip_str, duration_sec = parts[1], int(parts[2])
                expire_ns = time.monotonic_ns() + (duration_sec * 10**9)
                ip_u32 = struct.unpack("I", socket.inet_aton(ip_str))[0]
                
                blocklist[blocklist.Key(ip_u32)] = blocklist.Leaf(expire_ns)
                
                # 【小修 1】：强化日志语义，明确这是派生动作
                print(f"[CONTROL] Derived Block Sync from verifier decision: IP {ip_str} for {duration_sec}s")
                
                # 安全清理过期条目
                now_ns = time.monotonic_ns()
                items_snapshot = list(blocklist.items())
                for k, v in items_snapshot:
                    if v.value < now_ns:
                        del blocklist[k]
        except Exception as e:
            print(f"[CONTROL ERROR] {e}")

# --- 2. 挂载逻辑 ---
interface = "eth0"
print(f"--- Day 40: Dynamic State Filtering (Port 8002) ---")

ipr = IPRoute()
matches = ipr.link_lookup(ifname=interface)
if not matches:
    print(f"[ERROR] Interface {interface} not found. Please check 'ip addr'.")
    sys.exit(1)
idx = matches[0]

b = BPF(text=bpf_text)
fn = b.load_func("tc_filter", BPF.SCHED_CLS)

try:
    ipr.tc("del", "clsact", idx)
except Exception:
    pass

ipr.tc("add", "clsact", idx)
ipr.tc("add-filter", "bpf", idx, ":1", fd=fn.fd, name=fn.name,
       parent="ffff:fff2", classid=1, direct_action=True)

ctrl_thread = threading.Thread(target=control_plane_worker, args=(b,), daemon=True)
ctrl_thread.start()

print(f"[SUCCESS] TC Ingress filter attached to {interface}. Trace output follows...")

try:
    b.trace_print()
except KeyboardInterrupt:
    print("\n[INFO] Keyboard interrupt received. Detaching...")
finally:
    try:
        ipr.tc("del", "clsact", idx)
        print(f"[INFO] Detached clsact from {interface} successfully. Cleanup complete.")
    except Exception as e:
        print(f"[WARN] Cleanup failed or already detached: {e}")