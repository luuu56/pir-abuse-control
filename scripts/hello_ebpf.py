# scripts/hello_ebpf.py
from bcc import BPF

# 1. 最小 eBPF C 代码 (挂载 kprobe)
bpf_code = """
int hello_world(void *ctx) {
    bpf_trace_printk("Hello eBPF from WSL2 Kernel!\\n");
    return 0;
}
"""

print("🛠️  Compiling and loading eBPF program...")

# 2. JIT 编译代码
b = BPF(text=bpf_code)

# 3. 挂载到系统调用 execve
syscall_name = b.get_syscall_fnname("execve")
b.attach_kprobe(event=syscall_name, fn_name="hello_world")

print("✅ BPF compiler and kprobe attachment verified!")
print("👀 Open another terminal and run commands (e.g., 'ls').")
print("   Waiting for trace... (Ctrl+C to exit)\n")

try:
    b.trace_print()
except KeyboardInterrupt:
    print("\n🛑 Exiting.")