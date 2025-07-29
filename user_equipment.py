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

import numpy as np
from typing import Optional, List, Dict
from radio_unit import RadioUnit

MCC = "001"
MNC = "001"

class UE:
    _next_id = 0  # Class variable to track the next available ID

    def __init__(self, x: float, y: float, z: float):
        msin = str(UE._next_id)
        UE._next_id += 1
        msin = msin.zfill(15 - len(MCC) - len(MNC))
        self.imsi = MCC + MNC + msin
        self.x = x
        self.y = y
        self.z = z
        self.connected_ru: Optional[RadioUnit] = None
        self.rsrp_measurements: Dict[RadioUnit, float] = {}  # RU -> RSRP
        self.rsrq_measurements: Dict[RadioUnit, float] = {}  # RU -> RSRQ
        self.sinr_measurements: Dict[RadioUnit, float] = {}  # RU -> SINR

    def calculate_signal_metrics(self, radio_units: List[RadioUnit]):
        """Calculate RSRP, RSRQ, and SINR for all radio units according to 3GPP standards
        
        Args:
            radio_units: List of radio units to calculate metrics for
        """
        # Calculate thermal noise floor based on channel bandwidth
        # 3GPP TS 36.101: -174 dBm/Hz is the thermal noise density
        thermal_noise_density = -174  # dBm/Hz at 290K
        
        # Calculate noise floor for the bandwidth
        if self.connected_ru:
            # Convert bandwidth from MHz to Hz
            bandwidth_hz = self.connected_ru.channel_bandwidth * 1e6
            noise_floor = thermal_noise_density + 10 * np.log10(bandwidth_hz)
            # Number of resource blocks (assuming 180 kHz per RB for LTE)
            num_rb = int(self.connected_ru.channel_bandwidth * 1e6 / 180e3)
        else:
            noise_floor = thermal_noise_density + 60  # Default 1 MHz
            num_rb = 5  # Default 5 RBs
        
        # Calculate distances to all radio units
        distances = {ru: np.sqrt(
            (ru.x - self.x)**2 +
            (ru.y - self.y)**2 +
            (ru.z - self.z)**2
        ) for ru in radio_units}
        
        # Calculate path loss using 3GPP Urban Macro model (simplified)
        # TR 38.901 Table 7.4.1-1 for UMa-LOS
        path_losses = {}
        for ru, dist in distances.items():
            freq_ghz = ru.channel_frequency / 1000
            if dist < 10:  # Minimum distance
                dist = 10
            # Simplified UMa path loss model
            pl = 28.0 + 22 * np.log10(dist) + 20 * np.log10(freq_ghz)
            path_losses[ru] = pl
        
        # Calculate RSRP for all radio units
        # RSRP is measured on reference signals, not total power
        # Assuming reference signal power is 3dB below total power
        rs_power_offset = -3  # dB
        rsrp_values = {ru: ru.tx_power + rs_power_offset - path_losses[ru] 
                       for ru in radio_units}
        self.rsrp_measurements = rsrp_values
        
        # Calculate RSSI per radio unit (total received power)
        rssi_values = {}
        for ru in radio_units:
            # RSSI includes power from all sources on the carrier
            total_power_linear = 0
            
            # Power from the RU itself
            ru_power_linear = 10**(rsrp_values[ru]/10)
            total_power_linear += ru_power_linear
            
            # Interference from all other RUs on same frequency
            for other_ru in radio_units:
                if other_ru != ru and other_ru.channel_frequency == ru.channel_frequency:
                    interference_power = other_ru.tx_power - path_losses[other_ru]
                    total_power_linear += 10**(interference_power/10)
            
            # Add thermal noise
            total_power_linear += 10**(noise_floor/10)
            
            rssi_values[ru] = 10 * np.log10(total_power_linear)
        
        # Calculate RSRQ according to 3GPP formula
        # RSRQ = N × RSRP / RSSI (in linear scale, then convert to dB)
        self.rsrq_measurements = {}
        for ru in radio_units:
            rsrp_linear = 10**(rsrp_values[ru]/10)
            rssi_linear = 10**(rssi_values[ru]/10)
            rsrq_linear = num_rb * rsrp_linear / rssi_linear
            self.rsrq_measurements[ru] = 10 * np.log10(rsrq_linear)
        
        # Calculate SINR for all radio units
        for ru in radio_units:
            signal_power = 10**(rsrp_values[ru]/10)
            
            # Calculate interference from all other RUs on same frequency
            interference_power = 0
            for other_ru in radio_units:
                if other_ru != ru and other_ru.channel_frequency == ru.channel_frequency:
                    interf_rsrp = other_ru.tx_power - path_losses[other_ru]
                    interference_power += 10**(interf_rsrp/10)
            
            # Add thermal noise
            noise_power = 10**(noise_floor/10)
            
            # SINR calculation
            sinr = 10 * np.log10(signal_power / (interference_power + noise_power))
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
            print(f"Invalid radio unit: {new_ru.pci}")
            return False

        if new_ru == self.connected_ru:
            print(f"UE {self.imsi} is already connected on RU {new_ru.pci}")
            return True

        # Remove UE from current radio unit
        # if self.connected_ru is not None:
            # print(f"Old measurements {{RSRP: \"{self.rsrp_measurements[self.connected_ru]:.1f} dBm\",",
                #   f"RSRQ: \"{self.rsrq_measurements[self.connected_ru]:.1f} dB\", SINR: \"{self.sinr_measurements[self.connected_ru]:.1f} dB\"}}")
            # print(f"Old RSRP: {self.rsrp_measurements[self.connected_ru]:.1f} dBm")
            # print(f"Old RSRQ: {self.rsrq_measurements[self.connected_ru]:.1f} dB")
            # print(f"Old SINR: {self.sinr_measurements[self.connected_ru]:.1f} dB")
            # self.connected_ru.remove_connected_ue(self)

        # Update connection
        self.connected_ru.remove_connected_ue(self)
        old_ru = self.connected_ru
        self.connected_ru = new_ru
        self.connected_ru.add_connected_ue(self)

        print(f"UE {self.imsi} handed off from RU {old_ru.pci} to RU {new_ru.pci}")
        print(f"Old measurements {{RSRP: \"{self.rsrp_measurements[old_ru]:.1f} dBm\",",
              f"RSRQ: \"{self.rsrq_measurements[old_ru]:.1f} dB\", SINR: \"{self.sinr_measurements[old_ru]:.1f} dB\"}}")
        print(f"New measurements {{RSRP: \"{self.rsrp_measurements[new_ru]:.1f} dBm\",",
              f"RSRQ: \"{self.rsrq_measurements[new_ru]:.1f} dB\", SINR: \"{self.sinr_measurements[new_ru]:.1f} dB\"}}")
        # print(f"New RSRP: {self.rsrp_measurements[new_ru]:.1f} dBm")
        # print(f"New RSRQ: {self.rsrq_measurements[new_ru]:.1f} dB")
        # print(f"New SINR: {self.sinr_measurements[new_ru]:.1f} dB")

        return True
