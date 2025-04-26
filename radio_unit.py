import numpy as np
from typing import Set, TYPE_CHECKING

if TYPE_CHECKING:
    from user_equipment import UE

class RadioUnit:
    _next_id = 0  # Class variable to track the next available ID

    def __init__(self, x: float, y: float, z: float, tx_power: float = 46):
        """Initialize a radio unit

        Args:
            x (float): X coordinate
            y (float): Y coordinate
            z (float): Z coordinate (height)
            tx_power (float): Transmission power in dBm (default: 46 dBm)
        """
        self.id = RadioUnit._next_id
        RadioUnit._next_id += 1
        self.x = x
        self.y = y
        self.z = z
        self.tx_power = tx_power
        self.connected_ues: Set['UE'] = set()  # Set of connected UE objects

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