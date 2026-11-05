"""
NexusStream - Client Entry-Point Runner.
Usage:
    # Web UI (default, auto-increments port if busy):
    python -m client.run_client Alice

    # Interactive CLI mode:
    python -m client.run_client Bob --cli
"""

import argparse
import sys
import os
import time
import webbrowser

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from client.client import CollaborationClient
from client.web_server import RawSocketHTTPServer

def run_cli_loop(client):
    """Interactive command-line loop for terminal mode."""
    print("[CLI] Commands: /send <msg> | /msg <user> <msg> | /file <user> <path> | /peers | /status | /quit")

    while client.running and client.is_connected:
        try:
            line = input(f"[{client.username}]> ").strip()
            if not line:
                continue

            if line.startswith("/send "):
                text = line[6:].strip()
                client.send_broadcast_message(text)

            elif line.startswith("/msg "):
                parts = line[5:].split(" ", 1)
                if len(parts) == 2:
                    client.send_unicast_message(parts[0], parts[1])
                else:
                    print("Usage: /msg <user> <message>")

            elif line.startswith("/file "):
                parts = line[6:].split(" ", 1)
                if len(parts) == 2:
                    ok, msg = client.send_file(parts[0], parts[1])
                    print(f"[File] {msg}")
                else:
                    print("Usage: /file <user> <path>")

            elif line == "/peers":
                peers = ", ".join(u['username'] for u in client.active_users) or "None"
                print(f"Online ({len(client.active_users)}): {peers}")

            elif line == "/status":
                if not client.transfers:
                    print("No active transfers.")
                for tid, t in client.transfers.items():
                    print(f"[{t['role'].upper()}] {t['filename']}: {t['progress']}% ({t['status']})")

            elif line in ("/quit", "/exit"):
                client.disconnect()
                break

            else:
                print("Unknown command. Type /send, /msg, /file, /peers, /status, or /quit.")

        except (KeyboardInterrupt, EOFError):
            client.disconnect()
            break


def main():
    parser = argparse.ArgumentParser(description="NexusStream Collaboration Client Runner")
    parser.add_argument("name", nargs="?", default="", help="Username to login with (e.g. Alice or Bob)")
    parser.add_argument("--username", default="", help="Username to login with")
    parser.add_argument("--host", default="127.0.0.1", help="Server Host IP (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8888, help="Server TCP Port (default: 8888)")
    parser.add_argument("--ui-port", type=int, default=5001, help="Local Web UI HTTP Port (default: 5001)")
    parser.add_argument("--cli", action="store_true", help="Run in terminal CLI mode instead of Web UI")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open browser")
    args = parser.parse_args()

    username = (args.name or args.username).strip()

    client = CollaborationClient(server_host=args.host, server_tcp_port=args.port)

    if args.cli:
        uname = username or input("Enter username: ").strip()
        ok, msg = client.connect_and_login(uname, host=args.host, port=args.port)
        if not ok:
            print(f"Login failed: {msg}")
            return
        print(f"[+] Logged in as '{uname}'")
        run_cli_loop(client)
    else:
        # Start raw-socket HTTP Web UI server (automatically increments port if occupied)
        web_server = RawSocketHTTPServer(client, host="127.0.0.1", port=args.ui_port)
        web_server.start()
        url = f"http://127.0.0.1:{web_server.port}"

        if username:
            ok, msg = client.connect_and_login(username, host=args.host, port=args.port)
            status = f"Logged in as '{username}'" if ok else f"Login error: {msg}"
            print(f"[+] {status} | Web UI: {url}")
        else:
            print(f"[+] Client running | Web UI: {url}")

        if not args.no_browser:
            try:
                webbrowser.open(url)
            except Exception:
                pass

        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            print("[-] Client stopped.")
        finally:
            client.disconnect()
            web_server.stop()

if __name__ == "__main__":
    main()
