from client import Client
from threading import Thread
from stadium_simulation import StadiumSimulation
from user_equipment import UE
from typing import List
from time import sleep

import proto.signaling_pb2 as pb

class Ofh:
    """Implements an abstraction layer of OFH to interact with E2Sim"""

    def __init__(self, addr: str, port: int, sim: StadiumSimulation):
        self.__addr = addr
        self.__port = port
        self.__sim = sim

    def run(self) -> bool:
        """Starts up the OFH client to interact with E2Sim

            :raises RuntimeError: If it was unable to startup the OFH module.
        """
        self.__client = Client()
        self.__client.connect(self.__addr, self.__port)

        self.__ok2run = True
        self.__listener = Thread(None, self.receiver)
        self.__listener.start()

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
        self.__client.disconnect()
        self.__listener.join()

    def send(self, message: pb.OfhMessage):
        self.__client.send(message)

    def receiver(self):
        print("Starting OFH receiver thread...")

        while self.__ok2run:
            msg = self.__client.receive()
            msg_type = msg.WhichOneof('type')
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
                    if status == True:
                        message = self.create_metrics_request(ues)
                        self.send(message)

                case "ru_setup_response":
                    if msg.ru_setup_response.status == True:
                        print("RU has been setup on gNodeB")
                        self.__ready = True
                    else:
                        print("Unable to fully setup RU on gNodeB. Reason: ", msg.ru_setup_response.error)

                case "ru_teardown_response":
                    if msg.ru_teardown_response.status == True:
                        self.__ready = False
                        print("RU Tear Down has completed on gNodeB")
                    else:
                        print("Unable to fully Tear Down RU on gNodeB")

                case "tx_reference_level_request":
                    print("Received TX Reference Level Request Message")
                    pci = msg.tx_reference_level_request.cell.pci
                    gain = msg.tx_reference_level_request.cell.gain
                    print(f"Updating TX Reference Level for Cell pci={pci} to {gain} dBm")
                    status, ue_list = self.__sim.set_ru_power(pci, gain)
                    response = pb.OfhMessage()
                    response.tx_reference_level_response.cell.pci = pci
                    response.tx_reference_level_response.cell.gain = gain
                    response.tx_reference_level_response.status = status
                    if status == False:
                        response.tx_reference_level_response.error = f"Unable updating TX Reference Level for Cell pci={pci}"

                    self.send(response)

                     # Send updated metrics after updating TX Reference Level from all UEs on that cell
                    if status == True:
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

            for neigh_metrics in ue.get_neighbor_ru_metrics():
                cell_metrics = pb.CellMetrics()
                cell_metrics.cell.pci = neigh_metrics['radio_unit'].pci
                cell_metrics.metrics.rsrp = neigh_metrics['rsrp']
                cell_metrics.metrics.rsrq = neigh_metrics['rsrq']
                cell_metrics.metrics.sinr = neigh_metrics['sinr']
                ue_metrics.neighbor_cells.append(cell_metrics)

            message.registration_request.ue_metrics.append(ue_metrics)

        return message

    def create_metrics_request(self, ues: List[UE]) -> pb.OfhMessage:
        message = pb.OfhMessage()
        for ue in ues:
            pri_metrics = ue.get_connected_ru_metrics()
            ue_metrics = pb.UeMetrics()
            ue_metrics.ue.imsi = ue.imsi
            ue_metrics.primary_cell.cell.pci = ue.connected_ru.pci
            ue_metrics.primary_cell.metrics.rsrp = pri_metrics['rsrp']
            ue_metrics.primary_cell.metrics.rsrq = pri_metrics['rsrq']
            ue_metrics.primary_cell.metrics.sinr = pri_metrics['sinr']

            for neigh_metrics in ue.get_neighbor_ru_metrics():
                cell_metrics = pb.CellMetrics()
                cell_metrics.cell.pci = neigh_metrics['radio_unit'].pci
                cell_metrics.metrics.rsrp = neigh_metrics['rsrp']
                cell_metrics.metrics.rsrq = neigh_metrics['rsrq']
                cell_metrics.metrics.sinr = neigh_metrics['sinr']
                ue_metrics.neighbor_cells.append(cell_metrics)

            message.metrics_request.ue_metrics.append(ue_metrics)

        return message

    def create_ue_deregistration_request(self, ues: List[UE]) -> pb.OfhMessage:
        message = pb.OfhMessage()
        for ue in ues:
            ue_deregistration = pb.UeDeregistration()
            ue_deregistration.ue.imsi = ue.imsi
            ue_deregistration.cell.pci = ue.connected_ru.pci
            message.deregistration_request.ues.append(ue_deregistration)

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
