from dataclasses import dataclass

@dataclass
class StadiumTier:
    height: float  # Height of the tier from ground level
    depth: float   # Horizontal depth of the tier
    angle: float   # Inclination angle in degrees