from stadium_simulation import StadiumSimulation
import proto.signaling_pb2 as pb
from ofh import Ofh

import os
import sys
import time

import signal
import pandas as pd

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

def run_experiment(addr: str):
    # Create and initialize the simulation
    sim = StadiumSimulation()

    # Read the CSV file
    data = pd.read_csv('input.csv')

    # Convert hours to seconds
    data['Time(s)'] = data['Time(h)'] * 3600

    # Initialize variables
    current_ues = 0
    last_time = 0

    # Create OFH connection
    ofh = Ofh(addr, 34567, sim)
    try:
        connected = ofh.run()
        if not connected:
            print("Failed to establish OFH connection")
    except RuntimeError as e:
        print(e)
        sys.exit(os.EX_IOERR)

    try:
        # Process each row in the data
        for _, row in data.iterrows():
            # Calculate sleep time (time difference from last action)
            sleep_time = row['Time(s)'] - last_time

            target_ues = int(row['Connected UEs'])
            ue_difference = target_ues - current_ues

            # Distribute UE changes evenly over the interval
            if sleep_time > 0 and ue_difference != 0:
                steps = abs(ue_difference)
                step_sleep = sleep_time / steps
                step_sign = 1 if ue_difference > 0 else -1
                for _ in range(steps):
                    print(f"Time: {row['Time(h)']}h, Interval: {step_sleep:.3f}s")
                    time.sleep(step_sleep)

                    if step_sign > 0:
                        added_ues = sim.add_ues(1)
                        if added_ues:
                            ue_reg_msg = ofh.create_ue_registration_request(added_ues)
                            ofh.send(ue_reg_msg)
                        current_ues += 1
                    else:
                        removed_ues = sim.remove_ues(1)
                        if removed_ues:
                            ue_dereg_msg = ofh.create_ue_deregistration_request(removed_ues)
                            ofh.send(ue_dereg_msg)
                        current_ues -= 1
            else:
                print(f"Time: {row['Time(h)']}h, Interval: {sleep_time:.3f}s")

                # No time interval or no UE change, just sleep if needed
                if sleep_time > 0:
                    time.sleep(sleep_time)
                # If UE count changed but no time, do it instantly
                if ue_difference > 0:
                    added_ues = sim.add_ues(ue_difference)
                    if added_ues:
                        ue_reg_msg = ofh.create_ue_registration_request(added_ues)
                        ofh.send(ue_reg_msg)
                    current_ues += ue_difference
                elif ue_difference < 0:
                    removed_ues = sim.remove_ues(abs(ue_difference))
                    if removed_ues:
                        ue_dereg_msg = ofh.create_ue_deregistration_request(removed_ues)
                        ofh.send(ue_dereg_msg)
                    current_ues += ue_difference
            last_time = row['Time(s)']
    except KeyboardInterrupt:
        print("\nExperiment interrupted by user\n")
    except SystemExit as e:
        print(f"\n{e} Shutting down...\n")
    except RuntimeError as e:
        print(f"\nRuntime Error: {e}\n")
        current_ues = 0
    finally:
        # Clean up
        if current_ues > 0:
            seconds = 5
            print(f"Waiting {seconds} seconds before removing all remaining UEs")
            time.sleep(seconds)
            removed_ues = sim.remove_ues(current_ues)
            if removed_ues:
                ue_dereg_msg = ofh.create_ue_deregistration_request(removed_ues)
                try:
                    ofh.send(ue_dereg_msg)
                    time.sleep(2)  # Give time for final messages to be processed
                except RuntimeError as e:
                    print(f"\nRuntime Error: {e}\n")

        try:
            ofh.stop()
        except:
            os._exit(1)

def signal_handler(sig, frame):
    raise(SystemExit(f"{signal.Signals(sig).name} was received."))

if __name__ == "__main__":
    # example()
    # main()

    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} {{destination-address}}")
        sys.exit(os.EX_USAGE)

    signal.signal(signal.SIGTERM, signal_handler)
    run_experiment(sys.argv[1])
