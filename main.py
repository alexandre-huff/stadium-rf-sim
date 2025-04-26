from stadium_simulation import StadiumSimulation

def main():
    # Create and initialize the simulation
    sim = StadiumSimulation()

    # Add 100 UEs distributed across the stadium tiers
    sim.add_ues(100)

    ue0 = sim.get_ues()[0]

    # Visualize initial state
    print("\nInitial stadium layout and coverage:")
    print("UE 0 connected to RU ", ue0.connected_ru.id)
    print("Signal Strength from UE 0: ", sim.ue_signal_strength[0])
    sim.visualize_stadium()

    sim.handoff_ue(0, 1)
    print("UE 0 connected to RU ", ue0.connected_ru.id)
    print("Signal Strength from UE 0: ", sim.ue_signal_strength[0])
    sim.visualize_stadium()

    # Modify some radio unit powers to show the effect
    print("\nModifying radio unit powers...")
    sim.set_ru_power(1, 0) # Set power of RU 1 to 0
    print("UE 0 connected to RU ", ue0.connected_ru.id)
    print("Signal Strength from UE 0: ", sim.ue_signal_strength[0])

    # Visualize the changes
    print("\nStadium layout after power modifications:")
    sim.visualize_stadium()

if __name__ == "__main__":
    main()