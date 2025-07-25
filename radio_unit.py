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
from typing import Set, TYPE_CHECKING

if TYPE_CHECKING:
    from user_equipment import UE

class RadioUnit:
    _next_id = 0  # Class variable to track the next available Cell ID

    def __init__(self, x: float, y: float, z: float, tx_power: float = 20, channel_frequency: float = 3500, channel_bandwidth: float = 100):
        """Initialize a radio unit

        Args:
            x (float): X coordinate
            y (float): Y coordinate
            z (float): Z coordinate (height)
            tx_power (float): Transmission power in dBm (default: 20 dBm)
            channel_frequency (float): Frequency of the channel in MHz
            channel_bandwidth (float): Bandwidth in MHz
        """
        self.pci = RadioUnit._next_id # Each RadioUnit manages a single cell identified as the Physical Cell ID (pci)
        RadioUnit._next_id += 1
        self.x = x
        self.y = y
        self.z = z
        self.tx_power = tx_power
        self.channel_bandwidth = channel_bandwidth  # Bandwidth in MHz
        self.channel_frequency = channel_frequency  # Frequency in MHz
        self.connected_ues: Set['UE'] = set()  # Set of connected UE objects

    @property
    def channel_end_freq(self) -> float:
        """Get the end frequency of the channel in MHz"""
        if self.channel_frequency is None:
            return None
        return self.channel_frequency + self.channel_bandwidth - 1 # Considering the start frequency as inclusive

    @property
    def position(self) -> np.ndarray:
        """Get radio unit position as numpy array"""
        return np.array([self.x, self.y, self.z])

    def set_tx_power(self, power: float):
        """Set the transmission power of the radio unit"""
        if power < 0 or power > 60:
            raise ValueError("Transmission power must be between 0 and 60 dBm")
        self.tx_power = power

    def add_connected_ue(self, ue: 'UE'):
        """Add a UE to the connected UEs set"""
        self.connected_ues.add(ue)

    def remove_connected_ue(self, ue: 'UE'):
        """Remove a UE from the connected UEs set"""
        self.connected_ues.discard(ue)
