from stadium_simulation import StadiumSimulation
import proto.signaling_pb2 as pb
from ofh import Ofh

import sys
import time

import signal

def example():
    # Create and initialize the simulation
    sim = StadiumSimulation()

    # Add 100 UEs distributed across the stadium tiers
    sim.add_ues(100)

    ue0 = sim.get_ues()[0]

    # Visualize initial state
    print("\nInitial stadium layout and coverage:")
    print("UE 0 connected to RU ", ue0.connected_ru.pci)
    print("Signal Strength from UE 0: ", ue0.get_connected_ru_metrics()['rsrp'])
    sim.visualize_stadium()

    sim.handoff_ue(ue0.imsi, 1)
    print("UE 0 connected to RU ", ue0.connected_ru.pci)
    print("Signal Strength from UE 0: ", ue0.get_connected_ru_metrics()['rsrp'])
    sim.visualize_stadium()

    # Modify some radio unit powers to show the effect
    print("\nModifying radio unit powers...")
    sim.set_ru_power(1, 0) # Set power of RU 1 to 0
    print("UE 0 connected to RU ", ue0.connected_ru.pci)
    print("Signal Strength from UE 0: ", ue0.get_connected_ru_metrics()['rsrp'])

    # Visualize the changes
    print("\nStadium layout after power modifications:")
    sim.visualize_stadium()

def main():
    # Create and initialize the simulation
    sim = StadiumSimulation()
    num_ues = 1

    if len(sys.argv) == 2:
        num_ues = int(sys.argv[1])

    ofh = Ofh("172.17.0.2", 34567, sim)
    if ofh.run():
        added_ues = sim.add_ues(num_ues)

        ue_reg_msg = ofh.create_ue_registration_request(added_ues)
        ofh.send(ue_reg_msg)

        signum = signal.sigwait((signal.SIGINT, signal.SIGTERM))
        print(f'Signal handler called with signal {signal.Signals(signum).name} ({signum})')

        removed_ues = sim.remove_ues(num_ues)
        ue_dereg_msg = ofh.create_ue_deregistration_request(removed_ues)
        ofh.send(ue_dereg_msg)

        # signum = signal.sigwait((signal.SIGINT, signal.SIGTERM))
        # print(f'Signal handler called with signal {signal.Signals(signum).name} ({signum})')
        time.sleep(2)


    ofh.stop()

    # sim.visualize_stadium()


if __name__ == "__main__":
    main()
