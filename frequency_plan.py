from __future__ import annotations

from typing import Sequence


CHANNEL_BANDWIDTH_MHZ = 100
DEFAULT_CARRIER_POOL_MHZ: tuple[int, ...] = (3400, 3500, 3600)
DEFAULT_TIER_OFFSETS: tuple[int, ...] = (0, 1, 2)


def build_frequency_reuse_plan(
    rus_per_tier: Sequence[int],
    carrier_pool_mhz: Sequence[int] = DEFAULT_CARRIER_POOL_MHZ,
    tier_offsets: Sequence[int] = DEFAULT_TIER_OFFSETS,
) -> list[int]:
    """Build a tier-aware RU carrier assignment.

    The default plan models a realistic reuse-3 deployment using three
    contiguous 100 MHz mid-band carriers. Adjacent RUs on the same tier use
    different carriers, while each tier is rotated to reduce vertical reuse.
    """
    if not carrier_pool_mhz:
        raise ValueError("carrier_pool_mhz must contain at least one carrier")

    carrier_count = len(carrier_pool_mhz)
    frequencies: list[int] = []

    for tier_idx, n_tier_rus in enumerate(rus_per_tier):
        tier_offset = tier_offsets[tier_idx % len(tier_offsets)] % carrier_count
        for local_idx in range(n_tier_rus):
            carrier_idx = (local_idx + tier_offset) % carrier_count
            frequencies.append(carrier_pool_mhz[carrier_idx])

    return frequencies


def total_unique_bandwidth_mhz(
    channel_bandwidth_mhz: int = CHANNEL_BANDWIDTH_MHZ,
    carrier_pool_mhz: Sequence[int] = DEFAULT_CARRIER_POOL_MHZ,
) -> int:
    """Return the amount of unique licensed spectrum in the carrier pool."""
    return channel_bandwidth_mhz * len(carrier_pool_mhz)