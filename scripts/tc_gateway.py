# scripts/tc_gateway.py
from bcc import BPF
from pyroute2 import IPRoute
import sys

# --- 1. eBPF C 代码 (基于指纹的浅层丢弃 + 多信号轻量观测) ---
bpf_text = """
#include <uapi/linux/bpf.h>
#include <uapi/linux/pkt_cls.h>
#include <uapi/linux/if_ether.h>
#include <uapi/linux/ip.h>
#include <uapi/linux/tcp.h>
#include <uapi/linux/in.h>    // <--- 就是加上这一行

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

    if (tcp->dest != bpf_htons(8002)) return TC_ACT_OK;
    
    if (tcp->doff < 5) return TC_ACT_OK;

    unsigned char *payload = (unsigned char *)tcp + (tcp->doff * 4);
    
    if ((void *)payload > data_end) return TC_ACT_OK;

    // --- Level 1 硬丢弃规则 (HACK 指纹) ---
    if ((void *)(payload + 4) <= data_end) {
        if (payload[0] == 'H' && payload[1] == 'A' && payload[2] == 'C' && payload[3] == 'K') {
            bpf_trace_printk("[TC DROP] Malicious HACK fingerprint!\\n");
            return TC_ACT_SHOT;
        }
    }

    // --- Level 2 观测信号 (HTTP-like POST) ---
    if ((void *)(payload + 5) <= data_end) {
        if (payload[0] == 'P' && payload[1] == 'O' && payload[2] == 'S' && payload[3] == 'T' && payload[4] == ' ') {
            bpf_trace_printk("[TC OBSERVE] HTTP POST detected\\n");
        }
    }

    // --- Level 2 观测信号 (ticket 关键词扫描，窗口 96 字节) ---
    #pragma unroll
    for (int i = 0; i < 96; i++) {
        if ((void *)(payload + i + 6) > data_end) break;
        
        if (payload[i] == 't' && payload[i+1] == 'i' && payload[i+2] == 'c' && 
            payload[i+3] == 'k' && payload[i+4] == 'e' && payload[i+5] == 't') {
            bpf_trace_printk("[TC OBSERVE] Found 'ticket' in payload buffer\\n");
            break; 
        }
    }

    return TC_ACT_OK;
}
"""

# --- 2. 挂载逻辑 ---
interface = "eth0"
print(f"--- Day 38: eBPF/TC Shallow Filtering (Port 8002) ---")

ipr = IPRoute()
matches = ipr.link_lookup(ifname=interface)
if not matches:
    print(f"[ERROR] Interface {interface} not found. Please check 'ip addr'.")
    sys.exit(1)
idx = matches[0]

# 加载 BPF
b = BPF(text=bpf_text)
fn = b.load_func("tc_filter", BPF.SCHED_CLS)

# 清理旧 qdisc
try:
    ipr.tc("del", "clsact", idx)
except Exception:
    pass

ipr.tc("add", "clsact", idx)
ipr.tc("add-filter", "bpf", idx, ":1", fd=fn.fd, name=fn.name,
       parent="ffff:fff2", classid=1, direct_action=True)

print(f"[SUCCESS] TC Ingress filter attached to {interface}. Trace output follows...")

try:
    b.trace_print()
except KeyboardInterrupt:
    print("\n[INFO] Keyboard interrupt received. Detaching...")
finally:
    # 关键修正 2：优雅收口并打印明确的清理日志
    try:
        ipr.tc("del", "clsact", idx)
        print(f"[INFO] Detached clsact from {interface} successfully. Cleanup complete.")
    except Exception as e:
        print(f"[WARN] Cleanup failed or already detached: {e}")