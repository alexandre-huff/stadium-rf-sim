import numpy as np
from typing import Optional, List, Dict
from radio_unit import RadioUnit

class UE:
    _next_id = 0  # Class variable to track the next available ID

    def __init__(self, x: float, y: float, z: float):
        self.id = UE._next_id
        UE._next_id += 1
        self.x = x
        self.y = y
        self.z = z
        self.connected_ru: Optional[RadioUnit] = None
        self.rsrp_measurements: Dict[RadioUnit, float] = {}  # RU -> RSRP
        self.rsrq_measurements: Dict[RadioUnit, float] = {}  # RU -> RSRQ
        self.sinr_measurements: Dict[RadioUnit, float] = {}  # RU -> SINR

    def calculate_signal_metrics(self, radio_units: List[RadioUnit]):
        """Calculate RSRP, RSRQ, and SINR for all radio units

        Args:
            radio_units: List of radio units to calculate metrics for
        """
        # Calculate thermal noise floor based on channel bandwidth
        # The noise floor value of -174 dBm is a fundamental physical constant derived
        # from thermal noise in wireless communications.
        thermal_noise_density = -174  # dBm/Hz at room temperature of 290K (16.85 Celsius)
        # Add bandwidth factor for connected RU's channel bandwidth (1000000 Hz = 1 MHz)
        noise_floor = thermal_noise_density + 10 * np.log10(self.connected_ru.channel_bandwidth * 1000000) \
            if self.connected_ru else thermal_noise_density  # -94 dBm for 100MHz

        # Calculate distances to all radio units
        distances = {ru: np.sqrt(
            (ru.x - self.x)**2 +
            (ru.y - self.y)**2 +
            (ru.z - self.z)**2
        ) for ru in radio_units}

        # Calculate path loss for all radio units using their specific frequencies (in GHz)
        path_losses = {ru: 21 * np.log10(dist) + 20 * np.log10(ru.channel_frequency/1000) + 32.4
                      for ru, dist in distances.items()}

        # Calculate RSRP for all radio units
        rsrp_values = {ru: ru.tx_power - path_losses[ru] for ru in radio_units}
        self.rsrp_measurements = rsrp_values

        # Calculate RSSI per radio unit (considering only UEs on same channel)
        rssi_values = {}
        for ru in radio_units:
            # Get all UEs connected to this RU (except self)
            interfering_ues = [ue for ue in ru.connected_ues if ue != self]
            # Sum up power from all interfering UEs
            interference_power = sum(10**(rsrp_values[ru]/10) for ue in interfering_ues)
            # Add noise floor
            rssi = 10 * np.log10(interference_power + 10**(noise_floor/10)) if interfering_ues else noise_floor
            rssi_values[ru] = rssi

        # Calculate RSRQ for all radio units using per-RU RSSI
        self.rsrq_measurements = {ru: rsrp - rssi + 30
                                for ru, (rsrp, rssi) in
                                ((ru, (rsrp_values[ru], rssi_values[ru]))
                                 for ru in radio_units)}

        # Calculate SINR for all radio units
        for ru in radio_units:
            target_power = 10**(rsrp_values[ru]/10)
            # Only consider interference from UEs on the same RU
            interference_power = sum(10**(rsrp_values[ru]/10)
                                  for ue in ru.connected_ues if ue != self)
            noise_power = 10**(noise_floor/10)
            sinr = 10 * np.log10(target_power / (interference_power + noise_power))
            self.sinr_measurements[ru] = sinr

        if self.connected_ru is None: # Huff: avoids the UE to always connect to the RU with the highest RSRP, enabling handover
            # Update connected radio unit to the one with highest RSRP
            old_ru = self.connected_ru
            self.connected_ru = max(rsrp_values.items(), key=lambda x: x[1])[0]

            # Update radio unit connections
            if old_ru is not None and old_ru != self.connected_ru:
                old_ru.remove_connected_ue(self)
            self.connected_ru.add_connected_ue(self)

    def get_connected_ru_metrics(self) -> Dict[str, float]:
        """Get signal metrics for the connected radio unit"""
        if self.connected_ru is None:
            return {}

        return {
            'rsrp': self.rsrp_measurements[self.connected_ru],
            'rsrq': self.rsrq_measurements[self.connected_ru],
            'sinr': self.sinr_measurements[self.connected_ru]
        }

    def get_neighbor_ru_metrics(self) -> List[Dict[str, float]]:
        """Get signal metrics for neighbor radio units"""
        if self.connected_ru is None:
            return []

        neighbor_metrics = []
        for ru, rsrp in self.rsrp_measurements.items():
            if ru != self.connected_ru:
                neighbor_metrics.append({
                    'radio_unit': ru,
                    'rsrp': rsrp,
                    'rsrq': self.rsrq_measurements[ru],
                    'sinr': self.sinr_measurements[ru]
                })

        # Sort by RSRP
        return sorted(neighbor_metrics, key=lambda x: x['rsrp'], reverse=True)

    def force_handoff(self, new_ru: RadioUnit) -> bool:
        """Force a handoff to a specific radio unit

        Args:
            new_ru: The new radio unit to connect to

        Returns:
            bool: True if handoff was successful, False otherwise
        """
        if new_ru not in self.rsrp_measurements:
            print(f"Invalid radio unit: {new_ru.id}")
            return False

        if new_ru == self.connected_ru:
            print(f"\nUE {self.id} is already connected to RU {new_ru.id}\n")
            return False

        # Remove UE from current radio unit
        if self.connected_ru is not None:
            print(f"Old RSRP: {self.rsrp_measurements[self.connected_ru]:.1f} dBm")
            print(f"Old RSRQ: {self.rsrq_measurements[self.connected_ru]:.1f} dB")
            print(f"Old SINR: {self.sinr_measurements[self.connected_ru]:.1f} dB")
            self.connected_ru.remove_connected_ue(self)

        # Update connection
        old_ru = self.connected_ru
        self.connected_ru = new_ru
        new_ru.add_connected_ue(self)

        print(f"\nUE {self.id} handed off from RU {old_ru.id if old_ru else 'None'} to RU {new_ru.id}\n")
        print(f"New RSRP: {self.rsrp_measurements[new_ru]:.1f} dBm")
        print(f"New RSRQ: {self.rsrq_measurements[new_ru]:.1f} dB")
        print(f"New SINR: {self.sinr_measurements[new_ru]:.1f} dB")

        return True