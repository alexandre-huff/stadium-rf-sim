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
import signal
import time
import json
import proto.signaling_pb2 as pb
from threading import Lock
from google.protobuf import message, text_format

# Helper placed before class to avoid forward reference issues
def _safe_int_from_header(header: bytes) -> int:
    """Best-effort integer representation of a 4-byte header for error messages.
    Tries BE, LE, and ASCII decimal; returns -1 on failure.
    """
    try:
        be = int.from_bytes(header, 'big')
        if be >= 0:
            return be
    except Exception:
        pass
    try:
        le = int.from_bytes(header, 'little')
        if le >= 0:
            return le
    except Exception:
        pass
    try:
        if all(48 <= b <= 57 for b in header):
            return int(header.decode('ascii'))
    except Exception:
        pass
    return -1

class Client:
    """
        This class abstracts the OFH TCP connection to E2Sim
    """

    def __init__(self):
        self.sock = None  # type: socket.socket | None
        self._addr = None  # type: str | None
        self._port = None  # type: int | None
        self._send_lock = Lock()
        # Telemetry counters
        self.decode_failures = 0
        self.partial_frames = 0
        self.total_received_bytes = 0
        self.last_bad_frame_info = None  # type: dict | None
        # Persistent receive buffer to handle TCP segmentation/coalescing
        self._recv_buf = bytearray()

        # Suppress SIGPIPE globally on POSIX so failed sends raise exceptions instead of killing the proc
        if hasattr(signal, "SIGPIPE"):
            try:
                signal.signal(signal.SIGPIPE, signal.SIG_IGN)
            except Exception:
                # Best-effort; ignore if not permitted in current context
                pass

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
        # Enable TCP keepalive with sensible defaults (Linux)
        try:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            # Tune keepalive parameters if available (Linux specific)
            if hasattr(socket, "TCP_KEEPIDLE"):
                self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30)
            if hasattr(socket, "TCP_KEEPINTVL"):
                self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
            if hasattr(socket, "TCP_KEEPCNT"):
                self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 5)
        except Exception:
            # Non-fatal; proceed without keepalive tuning if not supported
            pass
        try:
            self._addr, self._port = addr, port
            self.sock.connect((addr, port))
        except Exception as e:
            raise RuntimeError(f"Unable to open connection on {addr}:{port}. Cause: {e}")

    def send(self, ofh_msg: pb.OfhMessage):
        """Send a message to the server

            :raises RuntimeError: If any error happens.
        """
        if self.sock is None:
            raise RuntimeError("socket not connected")

        data = ofh_msg.SerializeToString()
        size = len(data)

        # Do not send zero-length frames; caller should avoid sending empty messages
        if size == 0:
            raise RuntimeError("refusing to send zero-length frame (empty OfhMessage)")

        header = size.to_bytes(4, byteorder='big')  # 4-byte big-endian length prefix

        # Prefer to suppress SIGPIPE per-send if available
        send_flags = getattr(socket, 'MSG_NOSIGNAL', 0)

        # Serialize multi-part frame writes to prevent interleaving across threads
        with self._send_lock:
            # Send header fully
            total_sent = 0
            while total_sent < 4:
                try:
                    sent = self.sock.send(header[total_sent:], send_flags)
                    if sent == 0:
                        raise RuntimeError("socket connection broken")
                    total_sent += sent
                except (BrokenPipeError, OSError) as e:
                    raise RuntimeError(f"{e}. socket connection broken")

            # Send payload fully
            total_sent = 0
            while total_sent < size:
                try:
                    sent = self.sock.send(data[total_sent:], send_flags)
                    if sent == 0:
                        raise RuntimeError("socket connection broken")
                    total_sent += sent
                except (BrokenPipeError, OSError) as e:
                    raise RuntimeError(f"{e}. socket connection broken")

    def receive(self) -> pb.OfhMessage:
        """Receive a message from the server

            :raises RuntimeError: If any error happens.
        """
        if self.sock is None:
            raise RuntimeError("socket not connected")

        # Helper: ensure at least n bytes in buffer, otherwise read more.
        def _fill_buf(n: int):
            while len(self._recv_buf) < n:
                try:
                    chunk = self.sock.recv(max(1, n - len(self._recv_buf)))
                except OSError as e:
                    raise RuntimeError(f"socket recv error: {e}")
                if chunk == b'':
                    # Peer closed connection -> let caller handle reconnect
                    self.partial_frames += 1
                    raise RuntimeError("socket connection broken")
                self._recv_buf.extend(chunk)

        MAX_LEN = 10 * 1024 * 1024  # 10MB

        # Strict 4-byte big-endian length-prefixed framing with resync on bad header
        while True:
            # Ensure we have a header
            _fill_buf(4)
            header = bytes(self._recv_buf[:4])
            msg_len = int.from_bytes(header, 'big')

            if not (1 <= msg_len <= MAX_LEN):
                # Bad header: do not tear down; drop one byte and try to resync
                # Optionally record minimal diagnostics for observability
                self.partial_frames += 1
                # Drop just the first byte and keep scanning
                del self._recv_buf[:1]
                continue

            # We have a plausible frame; ensure entire payload is available
            _fill_buf(4 + msg_len)
            data = bytes(self._recv_buf[4:4 + msg_len])
            del self._recv_buf[:4 + msg_len]
            self.total_received_bytes += 4 + len(data)

            # Try to decode protobuf payload
            msg = pb.OfhMessage()
            try:
                msg.ParseFromString(data)
                return msg
            except message.DecodeError as e:
                # Log first 16 bytes and continue without tearing down
                self.decode_failures += 1
                hex_head = data[:16].hex()
                ts = time.time()
                self.last_bad_frame_info = {
                    "ts": ts,
                    "msg_len": msg_len,
                    "data_len": len(data),
                    "hex_head": hex_head,
                    "error": str(e),
                    "hdr_hex": header.hex(),
                }
                print(json.dumps({
                    "event": "protobuf_decode_error",
                    "ts": ts,
                    "msg_len": msg_len,
                    "data_len": len(data),
                    "hex_head": hex_head,
                    "decode_failures": self.decode_failures,
                    "hdr_hex": header.hex(),
                }))
                # Return empty message to allow caller to continue; connection stays up
                return pb.OfhMessage()

    def disconnect(self):
        try:
            if self.sock:
                try:
                    # Attempt full-duplex shutdown before close
                    self.sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    # Socket may already be closed or half-closed
                    pass
                try:
                    self.sock.close()
                finally:
                    self.sock = None
        except OSError as e:
            print(e)


if __name__ == "__main__":
    ue_metrics = pb.UeMetrics()
    ue_metrics.ue.imsi = "1"
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
