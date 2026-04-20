# scripts/day38_test_client.py
import socket
import sys

def test_raw_payload(ip, port, payload):
    print(f"Sending: {payload[:20]}...")
    try:
        with socket.create_connection((ip, port), timeout=2) as sock:
            sock.sendall(payload)
            response = sock.recv(1024)
            print(f"Result: Received Response:\n{response.decode(errors='replace')}")
    except socket.timeout:
        print("Result: Connection Timeout (Client perspective: no response, check Server TC Trace for [TC DROP])")
    except Exception as e:
        print(f"Result: Connection failed ({e})")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/day38_test_client.py <server_eth0_ip>")
        print("[CRITICAL] Do NOT use 127.0.0.1. Traffic must hit the external eth0 interface to trigger TC!")
        sys.exit(1)
        
    target_ip = sys.argv[1]
    
    print(f"\n--- Testing against external IP: {target_ip}:8002 ---")
    
    print("\n--- Case 1: Malicious HACK Fingerprint ---")
    test_raw_payload(target_ip, 8002, b"HACK_ATTACK_GARBAGE_DATA")

    print("\n--- Case 2: Standard HTTP POST with ticket ---")
    # 结合你的小修 1：构造结构完整的标准 HTTP 请求
    body = b'{"ticket": "sample_data"}'
    http_post = (
        b"POST /api/v1/verifier/execute HTTP/1.1\r\n"
        b"Host: test\r\n"
        b"Content-Type: application/json\r\n"
        + f"Content-Length: {len(body)}\r\n".encode()
        + b"Connection: close\r\n"
        + b"\r\n"
        + body
    )
    test_raw_payload(target_ip, 8002, http_post)