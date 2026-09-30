import uvicorn
import socket
import sys
import os

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

if __name__ == "__main__":
    ip = get_local_ip()
    port = 8000
    print("=" * 65)
    print(" ST. KABIR PUBLIC SCHOOL - INTERNAL FEE SYSTEM")
    print("=" * 65)
    print(f" Local Machine URL : http://localhost:{port}")
    print(f" Campus LAN URL    : http://{ip}:{port}")
    print("=" * 65)
    print(" Launching server on host 0.0.0.0:8000 ... press Ctrl+C to stop.\n")
    
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
