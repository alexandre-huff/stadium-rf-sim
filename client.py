# ==================================================================================
# Copyright 2025 Alexandre Huff.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==================================================================================

import socket
import time
import json
import proto.signaling_pb2 as pb
from google.protobuf import message, text_format

class Client:
    """
        This class abstracts the OFH TCP connection to E2Sim
    """

    def __init__(self):
        self.sock: socket.socket | None = None
        # Telemetry counters
        self.decode_failures: int = 0
        self.partial_frames: int = 0
        self.total_received_bytes: int = 0
        self.last_bad_frame_info: dict | None = None

    def connect(self, addr: str, port: int):
        """Connects to a given server using a TCP socket

            :raises RuntimeError: If any error happens.
        """
        # Close any previous socket before creating a new one
        if getattr(self, 'sock', None):
            try:
                self.sock.close()
            except Exception:
                pass
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect((addr, port))
        except Exception as e:
            raise RuntimeError(f"Unable to open connection on {addr}:{port}. Cause: {e}")

    def send(self, message: pb.OfhMessage):
        """Send a message to the server

            :raises RuntimeError: If any error happens.
        """
        data = message.SerializeToString()
        size = message.ByteSize()

        data_len = size.to_bytes(4, byteorder='big')    # converting to network byte order
        try:
            sent = self.sock.send(data_len)
            if sent == 0:
                raise RuntimeError("socket connection broken")
        except BrokenPipeError as e:
            raise RuntimeError(f"{e}. socket connection broken")

        total_sent = 0
        while total_sent < size:
            try:
                sent = self.sock.send(data[total_sent:])
                if sent == 0:
                    raise RuntimeError("socket connection broken")
                total_sent += sent
            except BrokenPipeError as e:
                raise RuntimeError(f"{e}. socket connection broken")

    def receive(self) -> pb.OfhMessage:
        """Receive a message from the server

            :raises RuntimeError: If any error happens.
        """
        if self.sock is None:
            raise RuntimeError("socket not connected")

        # Helper to receive exactly n bytes or raise
        def _recv_exact(n: int) -> bytes:
            buf = bytearray()
            while len(buf) < n:
                chunk = self.sock.recv(n - len(buf))
                if chunk == b'':
                    # Partial frame marker
                    self.partial_frames += 1
                    raise RuntimeError("socket connection broken")
                buf.extend(chunk)
            return bytes(buf)

        # Read 4-byte length header
        header = _recv_exact(4)
        msg_len = int.from_bytes(header, byteorder='big')  # network to host order

        # Sanity-check message length (avoid pathological frames)
        MAX_LEN = 10 * 1024 * 1024  # 10MB
        if msg_len <= 0 or msg_len > MAX_LEN:
            self.partial_frames += 1
            raise RuntimeError(f"invalid message length: {msg_len}")

        # Read message payload
        data = _recv_exact(msg_len)
        self.total_received_bytes += 4 + len(data)

        # Attempt to parse protobuf
        msg = pb.OfhMessage()
        try:
            msg.ParseFromString(data)
        except message.DecodeError as e:
            self.decode_failures += 1
            # Capture a small hex preview for diagnostics
            hex_head = data[:16].hex()
            hex_tail = data[-16:].hex() if len(data) > 16 else ''
            self.last_bad_frame_info = {
                "ts": time.time(),
                "msg_len": msg_len,
                "data_len": len(data),
                "hex_head": hex_head,
                "hex_tail": hex_tail,
                "error": str(e),
            }
            print(json.dumps({
                "event": "protobuf_decode_error",
                "ts": self.last_bad_frame_info["ts"],
                "msg_len": msg_len,
                "data_len": len(data),
                "hex_head": hex_head,
                "hex_tail": hex_tail,
                "decode_failures": self.decode_failures
            }))
            # Return empty message to allow caller to continue
            return pb.OfhMessage()

        return msg

    def disconnect(self):
        try:
            if self.sock:
                try:
                    self.sock.shutdown(socket.SHUT_WR)
                except OSError:
                    pass
                self.sock.close()
        except OSError as e:
            print(e)


if __name__ == "__main__":
    ue_metrics = pb.UeMetrics()
    ue_metrics.ue.ue_id = "1"
    ue_metrics.primary_cell.cell.pci = 1
    ue_metrics.primary_cell.metrics.rsrp = -50
    ue_metrics.primary_cell.metrics.rsrq = -5
    ue_metrics.primary_cell.metrics.sinr = 10

    cell2_metrics = pb.CellMetrics()
    cell2_metrics.cell.pci = 2
    cell2_metrics.metrics.rsrp = -60
    cell2_metrics.metrics.rsrq = -10
    cell2_metrics.metrics.sinr = 8
    ue_metrics.neighbor_cells.append(cell2_metrics)

    ofh_msg = pb.OfhMessage()
    ofh_msg.registration_request.ue_metrics.append(ue_metrics)
    msg_str = text_format.MessageToString(ofh_msg)
    print(msg_str)

    client = Client()
    client.connect("172.17.0.2", 22222)

    client.send(ofh_msg)
    msg = client.receive()

    msg_str = text_format.MessageToString(msg)
    print(msg_str)

    client.disconnect()
