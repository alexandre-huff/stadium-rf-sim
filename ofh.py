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

from client import Client
from threading import Thread
from stadium_simulation import StadiumSimulation
from user_equipment import UE
from typing import List
from time import sleep
import csv
import time
import os

import proto.signaling_pb2 as pb

class Ofh:
    """Implements an abstraction layer of OFH to interact with E2Sim"""

    def __init__(self, addr: str, port: int, sim: StadiumSimulation):
        self.__addr = addr
        self.__port = port
        self.__sim = sim
        self.__connected = False
        self.__hb_thread = None  # type: ignore[var-annotated]
        self.__hb_running = False

        # Cache of last-sent primary-cell metrics per UE to avoid redundant sends
        # imsi -> { 'pci': int, 'rsrp': float, 'rsrq': float, 'sinr': float }
        self.__last_ue_metrics = {}
        # Threshold in dB to consider a signal-level change (avoid float noise)
        self.__metric_change_epsilon = 0.1

        # Initialize CSV logging for power changes in logs/ with timestamped filename
        self.__experiment_start_time = time.time()
        timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime(self.__experiment_start_time))
        logs_dir = "logs"
        try:
            os.makedirs(logs_dir, exist_ok=True)
        except Exception as e:
            print(f"Warning: Unable to ensure logs directory exists: {e}")
        self.__power_log_file = os.path.join(logs_dir, f"cell_power_changes_{timestamp}.csv")
        # Build header dynamically: Time + one column per PCI in sorted order
        try:
            self.__pci_order = sorted([ru.pci for ru in self.__sim.radio_units])
        except Exception:
            # Fallback: assume indices 0..N-1 if something goes wrong
            self.__pci_order = list(range(len(self.__sim.radio_units)))
        self.__fieldnames = ["Time(h)"] + [f"pci_{pci}" for pci in self.__pci_order]
        self.__init_power_log_csv()

    def __extract_primary_metrics(self, ue: UE) -> tuple[int, float, float, float] | None:
        """Return (pci, rsrp, rsrq, sinr) for UE's primary (connected) cell.
        Returns None if UE not attached yet.
        """
        if ue.connected_ru is None:
            return None
        m = ue.get_connected_ru_metrics()
        # m keys: rsrp, rsrq, sinr
        return (ue.connected_ru.pci, float(m['rsrp']), float(m['rsrq']), float(m['sinr']))

    def __has_signal_change(self, imsi: str, cur: tuple[int, float, float, float]) -> bool:
        """Decide if the current primary metrics changed vs last sent."""
        last = self.__last_ue_metrics.get(imsi)
        if last is None:
            # No baseline -> treat as changed so we send once
            return True
        last_pci = int(last['pci'])
        if cur[0] != last_pci:
            return True
        # Compare any metric change above epsilon
        eps = self.__metric_change_epsilon
        return (
            abs(cur[1] - float(last['rsrp'])) > eps or
            abs(cur[2] - float(last['rsrq'])) > eps or
            abs(cur[3] - float(last['sinr'])) > eps
        )

    def __update_last_metrics(self, imsi: str, cur: tuple[int, float, float, float]) -> None:
        self.__last_ue_metrics[imsi] = {
            'pci': int(cur[0]),
            'rsrp': float(cur[1]),
            'rsrq': float(cur[2]),
            'sinr': float(cur[3]),
        }

    def run(self) -> bool:
        """Starts up the OFH client to interact with E2Sim

            :raises RuntimeError: If it was unable to startup the OFH module.
        """
        self.__client = Client()
        self.__connect_with_backoff()

        self.__ok2run = True
        self.__listener = Thread(None, self.receiver)
        self.__listener.start()

        # Start heartbeat sender thread
        self.__start_heartbeat()

        self.__ready = False
        message = self.create_ru_setup_request()
        self.send(message)
        retries = 10
        while (not self.__ready and retries > 0):
            sleep(1)
            retries -= 1

        if not self.__ready:
            print("Unable to setup RU on gNodeB. Exitting...")
            return False

        return True

    def stop(self):
        message = self.create_ru_teardown_request()
        self.send(message)
        retries = 10
        while self.__ready and retries > 0:
            sleep(1)
            retries -= 1
        if self.__ready:
            print("Unable to tear down RU on gNodeB. Exitting anyway...")

        self.__ok2run = False
        self.__stop_heartbeat()
        self.__client.disconnect()
        self.__listener.join()

    def __connect_with_backoff(self):
        """Try connecting with exponential backoff; block until connected or max wait."""
        base_delay = 0.5
        max_delay = 10.0
        attempt = 0
        while True:
            try:
                self.__client.connect(self.__addr, self.__port)
                self.__connected = True
                print(f"Connected to OFH server at {self.__addr}:{self.__port}")
                return
            except RuntimeError as e:
                self.__connected = False
                delay = min(max_delay, base_delay * (2 ** attempt))
                # Add small jitter to avoid thundering herd
                delay = delay * (1.0 + (0.1 * (attempt % 3)))
                print(f"Connection failed: {e}. Retrying in {delay:.1f}s...")
                time.sleep(delay)
                attempt += 1

    def __start_heartbeat(self):
        if self.__hb_thread and self.__hb_thread.is_alive():
            return
        self.__hb_running = True
        self.__hb_thread = Thread(target=self.__heartbeat_loop, daemon=True)
        self.__hb_thread.start()

    def __stop_heartbeat(self):
        self.__hb_running = False
        t = self.__hb_thread
        if t and t.is_alive():
            t.join(timeout=2.0)

    def __heartbeat_loop(self):
        import random
        base_interval = 10.0  # seconds
        jitter_pct = 0.15
        while self.__hb_running and getattr(self, "__ok2run", False):
            # Skip heartbeat if not connected
            if not self.__connected:
                time.sleep(1.0)
                continue
            # Construct and send heartbeat; do not await any response
            hb = pb.OfhMessage()
            ts_ms = int(time.time() * 1000)
            hb.heartbeat.ts_ms = ts_ms
            try:
                self.__client.send(hb)
            except Exception as e:
                # Mark disconnected; receiver will try to reconnect
                print(f"Heartbeat send failed: {e}")
                self.__connected = False
            # Sleep with jitter to avoid synchronization bursts
            jitter = 1.0 + random.uniform(-jitter_pct, jitter_pct)
            time.sleep(max(1.0, base_interval * jitter))

    def __init_power_log_csv(self):
        """Initialize the CSV file for logging cell power changes"""
        try:
            # Ensure directory exists for the log file
            directory = os.path.dirname(self.__power_log_file)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(self.__power_log_file, 'w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.__fieldnames)
                writer.writeheader()
        except Exception as e:
            print(f"Warning: Unable to initialize power log CSV: {e}")

    def __log_power_change(self):
        """Log a snapshot row of all PCI power levels to the CSV file"""
        try:
            current_time = time.time()
            elapsed_time_seconds = current_time - self.__experiment_start_time
            elapsed_time_hours = elapsed_time_seconds / 3600.0  # Convert to hours

            # Build a map from PCI to current power
            pci_to_power = {ru.pci: ru.tx_power for ru in self.__sim.radio_units}

            # Construct the row using the predefined order
            row = {"Time(h)": elapsed_time_hours}
            for pci in self.__pci_order:
                row[f"pci_{pci}"] = pci_to_power.get(pci, None)

            with open(self.__power_log_file, 'a', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.__fieldnames)
                writer.writerow(row)
        except Exception as e:
            print(f"Warning: Unable to log power change to CSV: {e}")

    def send(self, message: pb.OfhMessage):
        # Gate sends on connection status and ensure message has a type set
        msg_type = message.WhichOneof('type')
        if msg_type is None:
            # Nothing to send; do not treat as a transport error and do not reconnect
            print("Skip send: refusing to send zero-length OfhMessage (no type set)")
            return

        try:
            self.__client.send(message)
        except Exception as e:
            err = str(e)
            # If the failure is due to empty message/zero-length frame, don't reconnect
            if "zero-length frame" in err or "empty OfhMessage" in err:
                print("Send failed: empty OfhMessage. Not reconnecting; fix the message and retry.")
                return

            # Otherwise this is a real I/O error; attempt to reconnect and retry once
            self.__connected = False
            print(f"Send failed: {e}. Attempting to reconnect and retry once...")
            try:
                self.__connect_with_backoff()
                self.__client.send(message)
                self.__connected = True
                print("Retry send succeeded after reconnect.")
            except Exception as e2:
                self.__connected = False
                print(f"Retry send failed: {e2}. Marking OFH as disconnected.")

    def receiver(self):
        print("Starting OFH receiver thread...")

        while self.__ok2run:
            try:
                msg = self.__client.receive()
                # If parsing failed, receive() returns empty message; skip
                msg_type = msg.WhichOneof('type')
            except Exception as e:
                # Socket error or invalid frame length
                print(f"OFH receive error: {e}")
                self.__connected = False
                # Try to reconnect while still allowed to run
                if not self.__ok2run:
                    break
                self.__connect_with_backoff()
                # After reconnect, request a resync if needed (e.g., RU setup)
                # Mark not ready and request setup again
                self.__ready = False
                try:
                    self.send(self.create_ru_setup_request())
                except Exception:
                    pass
                # Continue to next loop iteration
                continue

            match msg_type:
                case "registration_response":
                    if msg.registration_response.status == False:
                        print("E2Sim was unable to register all UEs")

                case "deregistration_response":
                    if msg.deregistration_response.status == False:
                        print("E2Sim was unable to deregister all UEs")

                case "metrics_response":
                    pass # nothing to do here

                case "handover_request":
                    print("Received Handover Request Message")
                    request = msg.handover_request
                    imsi = request.ue.imsi
                    pci = request.target_cell.pci

                    response = pb.OfhMessage()
                    response.handover_response.ue.imsi = imsi
                    response.handover_response.target_cell.pci = request.target_cell.pci
                    print(f"Handing over ue_id={imsi} to pci={pci}")
                    status, ues = self.__sim.handoff_ue(imsi, pci)
                    if status == True:
                        response.handover_response.status = True
                    else:
                        response.handover_response.status = False
                        response.handover_response.error = "Unable to run handoff procedure"

                    self.send(response)

                    # Send updated metrics after handover from all UEs on old cell and target cell
                    # Only send if there is at least one UE to report to avoid empty OfhMessage
                    if status == True and ues:
                        message = self.create_metrics_request(ues)
                        self.send(message)

                case "ru_setup_response":
                    if msg.ru_setup_response.status == True:
                        print("RU has been setup on gNodeB")
                        self.__ready = True
                        self.__connected = True
                    else:
                        print("Unable to fully setup RU on gNodeB. Reason: ", msg.ru_setup_response.error)

                case "ru_teardown_response":
                    if msg.ru_teardown_response.status == True:
                        self.__ready = False
                        print("RU Tear Down has completed on gNodeB")
                        self.__connected = True
                    else:
                        print("Unable to fully Tear Down RU on gNodeB")

                case "tx_reference_level_request":
                    print("Received TX Reference Level Request Message")
                    pci = msg.tx_reference_level_request.cell.pci
                    gain = msg.tx_reference_level_request.cell.gain
                    print(f"Updating TX Reference Level for Cell pci={pci} to {gain} dBm")
                    status, ue_list = self.__sim.set_ru_power(pci, gain)
                    
                    # Log a full snapshot row to CSV when any cell power changes
                    if status:
                        self.__log_power_change()
                    
                    response = pb.OfhMessage()
                    response.tx_reference_level_response.cell.pci = pci
                    response.tx_reference_level_response.cell.gain = gain
                    response.tx_reference_level_response.status = status
                    if status == False:
                        response.tx_reference_level_response.error = f"Unable updating TX Reference Level for Cell pci={pci}"

                    self.send(response)

                     # Send updated metrics after updating TX Reference Level from all UEs on that cell
                    # Only send if there is at least one UE to report to avoid empty OfhMessage
                    if status == True and ue_list:
                        message = self.create_metrics_request(ue_list)
                        self.send(message)

                case _:
                    if msg_type is not None:
                        print("Unexpected message type", msg_type)

        print("OFH receiver thread has finished")

    def create_ue_registration_request(self, ues: List[UE]) -> pb.OfhMessage:
        message = pb.OfhMessage()
        for ue in ues:
            pri_metrics = ue.get_connected_ru_metrics()
            ue_metrics = pb.UeMetrics()
            ue_metrics.ue.imsi = ue.imsi
            ue_metrics.primary_cell.cell.pci = ue.connected_ru.pci
            ue_metrics.primary_cell.metrics.rsrp = pri_metrics['rsrp']
            ue_metrics.primary_cell.metrics.rsrq = pri_metrics['rsrq']
            ue_metrics.primary_cell.metrics.sinr = pri_metrics['sinr']

            # Get only the best 8 neighbor cells (sorted by SINR in descending order)
            best_neighbors = ue.get_neighbor_ru_metrics_by_sinr()[:8]
            for neigh_metrics in best_neighbors:
                cell_metrics = pb.CellMetrics()
                cell_metrics.cell.pci = neigh_metrics['radio_unit'].pci
                cell_metrics.metrics.rsrp = neigh_metrics['rsrp']
                cell_metrics.metrics.rsrq = neigh_metrics['rsrq']
                cell_metrics.metrics.sinr = neigh_metrics['sinr']
                ue_metrics.neighbor_cells.append(cell_metrics)

            message.registration_request.ue_metrics.append(ue_metrics)
            # Establish baseline so later metrics are sent only on change
            self.__update_last_metrics(
                ue.imsi,
                (ue.connected_ru.pci, float(pri_metrics['rsrp']), float(pri_metrics['rsrq']), float(pri_metrics['sinr']))
            )

        return message

    def create_metrics_request(self, ues: List[UE]) -> pb.OfhMessage:
        # Build metrics only for UEs whose primary signal-level changed
        message = pb.OfhMessage()
        for ue in ues:
            cur = self.__extract_primary_metrics(ue)
            if cur is None:
                continue
            if not self.__has_signal_change(ue.imsi, cur):
                continue

            ue_metrics = pb.UeMetrics()
            ue_metrics.ue.imsi = ue.imsi
            ue_metrics.primary_cell.cell.pci = cur[0]
            ue_metrics.primary_cell.metrics.rsrp = cur[1]
            ue_metrics.primary_cell.metrics.rsrq = cur[2]
            ue_metrics.primary_cell.metrics.sinr = cur[3]

            # Get only the best 4 neighbor cells (sorted by SINR in descending order)
            best_neighbors = ue.get_neighbor_ru_metrics_by_sinr()[:4]
            for neigh_metrics in best_neighbors:
                cell_metrics = pb.CellMetrics()
                cell_metrics.cell.pci = neigh_metrics['radio_unit'].pci
                cell_metrics.metrics.rsrp = neigh_metrics['rsrp']
                cell_metrics.metrics.rsrq = neigh_metrics['rsrq']
                cell_metrics.metrics.sinr = neigh_metrics['sinr']
                ue_metrics.neighbor_cells.append(cell_metrics)

            message.metrics_request.ue_metrics.append(ue_metrics)
            # Update cache only when we're actually sending this UE
            self.__update_last_metrics(ue.imsi, cur)

        return message

    def create_ue_deregistration_request(self, ues: List[UE]) -> pb.OfhMessage:
        message = pb.OfhMessage()
        for ue in ues:
            ue_deregistration = pb.UeDeregistration()
            ue_deregistration.ue.imsi = ue.imsi
            ue_deregistration.cell.pci = ue.connected_ru.pci
            message.deregistration_request.ues.append(ue_deregistration)
            # Remove baseline cache for this UE
            if ue.imsi in self.__last_ue_metrics:
                self.__last_ue_metrics.pop(ue.imsi, None)

        return message

    def create_ru_setup_request(self) -> pb.OfhMessage:
        message = pb.OfhMessage()
        for ru in self.__sim.radio_units:
            cell = pb.Cell(pci=ru.pci, gain=ru.tx_power)
            message.ru_setup_request.cells.append(cell)

        return message

    def create_ru_teardown_request(self) -> pb.OfhMessage:
        message = pb.OfhMessage()
        for ru in self.__sim.radio_units:
            cell = pb.Cell(pci=ru.pci, gain=ru.tx_power)
            message.ru_teardown_request.cells.append(cell)

        return message
