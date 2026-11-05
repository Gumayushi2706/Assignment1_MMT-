"""
NexusStream - One-Click Multi-Client Collaboration Demo Launcher.
Starts the central server and launches multiple clients with automated browser tabs.

Usage:
    python run_demo.py              # Launch default 2 clients (Alice & Bob)
    python run_demo.py --clients 3  # Launch 3 clients
    python run_demo.py --clients 4  # Launch 4 clients
"""

import argparse
import subprocess
import sys
import time
import os
import webbrowser

DEMO_USERS = ["Alice", "Bob", "Charlie", "David", "Eve", "Frank"]

def main():
    parser = argparse.ArgumentParser(description="NexusStream Multi-Client Collaboration Demo Launcher")
    parser.add_argument("--clients", "-c", type=int, default=2, help="Number of clients to launch (2 to 6, default: 2)")
    args = parser.parse_args()

    num_clients = max(1, min(len(DEMO_USERS), args.clients))
    root_dir = os.path.abspath(os.path.dirname(__file__))

    print(f"[*] Starting demo ({num_clients} clients)...")
    server_proc = subprocess.Popen([sys.executable, "-m", "server.run_server"], cwd=root_dir)
    time.sleep(1.0)

    client_procs = []
    base_port = 5001

    for i in range(num_clients):
        username = DEMO_USERS[i]
        ui_port = base_port + i
        proc = subprocess.Popen(
            [sys.executable, "-m", "client.run_client", username, "--ui-port", str(ui_port), "--no-browser"],
            cwd=root_dir
        )
        client_procs.append(proc)
        time.sleep(0.5)

    time.sleep(0.8)
    for i in range(num_clients):
        webbrowser.open(f"http://127.0.0.1:{base_port + i}")

    print("[✓] Running. Browser tabs opened. Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[-] Stopping demo...")
        for p in client_procs:
            try:
                p.terminate()
            except Exception:
                pass
        try:
            server_proc.terminate()
        except Exception:
            pass
        print("Demo stopped.")

if __name__ == "__main__":
    main()
