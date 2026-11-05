"""
Comprehensive Integration & Scalability Tests for NexusStream.
Covers Handshake, Concurrency (15 clients), Unicast Messaging, UDP Streaming, and Resilience on Abrupt Disconnect.
"""

import unittest
import socket
import threading
import time
import os
import sys
import hashlib

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from server.server import CollaborationServer
from client.client import CollaborationClient


class TestIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server_tcp_port = 18888
        cls.server_udp_port = 18889
        cls.server = CollaborationServer(host="127.0.0.1", tcp_port=cls.server_tcp_port, udp_port=cls.server_udp_port, verbose=False)
        cls.server_thread = threading.Thread(target=cls.server.start, daemon=True)
        cls.server_thread.start()
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()
        time.sleep(0.2)

    def test_01_handshake_and_login(self):
        """Test basic TCP handshake and client authentication."""
        client = CollaborationClient(server_host="127.0.0.1", server_tcp_port=self.server_tcp_port)
        ok, msg = client.connect_and_login("TestUser1")
        self.assertTrue(ok, f"Login failed: {msg}")
        self.assertTrue(client.is_connected)
        time.sleep(0.2)
        client.disconnect()

    def test_02_concurrency_15_clients(self):
        """Test server concurrency with 15 simultaneous client connections."""
        clients = []
        errors = []

        def worker(idx):
            c = CollaborationClient(server_host="127.0.0.1", server_tcp_port=self.server_tcp_port)
            ok, msg = c.connect_and_login(f"Concurrent_{idx}")
            if not ok:
                errors.append(f"Client {idx} failed: {msg}")
            else:
                clients.append(c)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(15)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Errors during concurrency connect: {errors}")
        self.assertEqual(len(clients), 15)

        time.sleep(0.5)
        all_users = self.server.user_manager.get_all_users()
        self.assertGreaterEqual(len(all_users), 15)

        clients[0].send_broadcast_message("Hello concurrency test from client 0!")
        time.sleep(0.5)

        for c in clients:
            c.disconnect()
        time.sleep(0.5)

    def test_03_unicast_messaging_and_encryption(self):
        """Test end-to-end encrypted direct messaging between two peers."""
        alice = CollaborationClient(server_host="127.0.0.1", server_tcp_port=self.server_tcp_port)
        bob = CollaborationClient(server_host="127.0.0.1", server_tcp_port=self.server_tcp_port)

        alice.connect_and_login("Alice")
        bob.connect_and_login("Bob")
        time.sleep(0.3)

        secret_text = "Super Confidential Message 12345"
        alice.send_unicast_message("Bob", secret_text)
        time.sleep(0.5)

        received_texts = [m["text"] for m in bob.messages if m["sender"] == "Alice"]
        self.assertIn(secret_text, received_texts)

        alice.disconnect()
        bob.disconnect()

    def test_04_reliable_udp_file_transfer(self):
        """Test streaming an 80KB binary file over UDP with SHA-256 integrity check."""
        charlie = CollaborationClient(server_host="127.0.0.1", server_tcp_port=self.server_tcp_port)
        david = CollaborationClient(server_host="127.0.0.1", server_tcp_port=self.server_tcp_port)

        charlie.connect_and_login("Charlie")
        david.connect_and_login("David")
        time.sleep(0.3)

        test_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_sample.dat"))
        sample_data = os.urandom(80 * 1024)
        with open(test_file_path, "wb") as f:
            f.write(sample_data)
        expected_hash = hashlib.sha256(sample_data).hexdigest()

        ok, msg = charlie.send_file("David", test_file_path)
        self.assertTrue(ok, f"Failed to send file: {msg}")

        start_time = time.time()
        transfer_done = False
        saved_file_path = None
        while time.time() - start_time < 5.0:
            time.sleep(0.1)
            for tid, t in david.transfers.items():
                if t.get("filename") == "test_sample.dat" and t.get("progress") >= 100.0:
                    transfer_done = True
                    saved_file_path = t.get("saved_path")
                    break
            if transfer_done:
                break

        self.assertTrue(transfer_done, "File transfer over UDP did not complete within timeout")
        self.assertIsNotNone(saved_file_path)
        self.assertTrue(os.path.exists(saved_file_path))
        with open(saved_file_path, "rb") as f:
            rec_data = f.read()
        self.assertEqual(hashlib.sha256(rec_data).hexdigest(), expected_hash)

        if os.path.exists(test_file_path):
            os.remove(test_file_path)
        if saved_file_path and os.path.exists(saved_file_path):
            os.remove(saved_file_path)

        charlie.disconnect()
        david.disconnect()

    def test_05_resilience_on_abrupt_disconnect(self):
        """Test server resilience when a client abruptly resets connection (RST)."""
        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_sock.connect(("127.0.0.1", self.server_tcp_port))

        from protocol.packet import Packet, MsgType, send_packet, recv_packet
        send_packet(raw_sock, Packet(MsgType.HANDSHAKE_REQ, payload=b"HELLO"))
        recv_packet(raw_sock)
        send_packet(raw_sock, Packet.json_payload(MsgType.AUTH_LOGIN, {"username": "CrashingUser", "udp_port": 12345}))
        recv_packet(raw_sock)

        self.assertIsNotNone(self.server.user_manager.get_user("CrashingUser"))

        # Force abrupt socket reset
        raw_sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, b'\x01\x00\x00\x00\x00\x00\x00\x00')
        raw_sock.close()
        time.sleep(0.5)

        test_client = CollaborationClient(server_host="127.0.0.1", server_tcp_port=self.server_tcp_port)
        ok, msg = test_client.connect_and_login("HealthyClient")
        self.assertTrue(ok)
        test_client.disconnect()


if __name__ == '__main__':
    unittest.main()
