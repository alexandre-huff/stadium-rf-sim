import socket
import proto.signaling_pb2 as pb
from google.protobuf import message, text_format

class Client:
    """
        This class abstracts the OFH TCP connection to E2Sim
    """

    def connect(self, addr: str, port: int):
        """Connects to a given server using a TCP socket

            :raises RuntimeError: If any error happens.
        """
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
        chunks = []
        bytes_rcvd = 0
        msg_len = self.sock.recv(4)
        msg_len = int.from_bytes(msg_len, byteorder='big')        # converting to host byte order

        while bytes_rcvd < msg_len:
            chunk = self.sock.recv(msg_len - bytes_rcvd)
            if chunk == b'':
                raise RuntimeError("socket connection broken")
            chunks.append(chunk)
            bytes_rcvd += len(chunk)

        data = b''.join(chunks)

        msg = pb.OfhMessage()
        try:
            msg.ParseFromString(data)
        except message.DecodeError as e:
            print(f"Error decoding protobuf message: {e}")

        return msg

    def disconnect(self):
        try:
            self.sock.shutdown(socket.SHUT_WR)
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
