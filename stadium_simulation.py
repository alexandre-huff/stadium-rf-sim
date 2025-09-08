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
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
from typing import List
from stadium_tier import StadiumTier
from radio_unit import RadioUnit
from user_equipment import UE

class StadiumSimulation:
    def __init__(self, distance_scale: float = 1.1):  # default 10% outward scaling
        # Stadium dimensions (in meters)
        self.field_length = 105  # Standard football field length
        self.field_width = 68    # Standard football field width
        self.technical_area_width = 5  # Width of technical area around the field

        # Multi-tier configuration
        self.tiers = [
            StadiumTier(height=0, depth=20, angle=25),    # Lower tier
            StadiumTier(height=15, depth=15, angle=30),   # Middle tier
            StadiumTier(height=30, depth=10, angle=35)    # Upper tier
        ]

        # Initialize arrays for visualization
        self.ue_positions = np.empty((2, 0))  # 2xN array for x,y positions
        self.ue_heights = np.array([])        # Array for z positions
        self.ue_signal_strength = np.array([]) # Array for signal strengths

        # Keep track of total UEs
        self.total_ues = 0

        # TODO Things to add/modify in the simulation
        # Add CQI measurement and replace RSRP-based colormap by CQI-based colormap
        # CQI is defined in GPP TS 38.214 at Section 5.2.2.1, so, which table should be used?
        # Set the number of RUs based on a configuration file

        # 5G network parameters
        self.frequency = 3500  # Starting frequency in MHz (3.5 GHz typical for 5G mid-band)
        self.channel_bandwidth = 100  # Channel bandwidth in MHz
        self.bs_height = 25   # Height of radio units in meters
        self.ue_height = 1.5  # Height of UEs in meters (when standing)
        self.bs_tx_power = 20 # Radio unit transmission power in dBm

        # Shadow fading parameters
        self.shadow_std_los = 4.0    # Standard deviation for LOS shadow fading
        self.shadow_std_nlos = 7.8   # Standard deviation for NLOS shadow fading

        # Initialize radio units with default power and incrementing channels
        # Generate 56 radio units distributed around the stadium perimeter
        ru_positions: list[list[float]] = []
        num_rus = 56

        # Store scale factor (applied to x,y coordinates)
        self.distance_scale = distance_scale

        for i in range(num_rus):
            angle = (2 * np.pi * i) / num_rus
            # Position RUs at varying distances around the stadium
            if i % 4 == 0:  # Every 4th RU closer to field
                distance_x = self.field_length/2 + 5
                distance_y = self.field_width/2 + 5
            elif i % 4 == 1:  # Slightly further
                distance_x = self.field_length/2 + 8
                distance_y = self.field_width/2 + 8
            elif i % 4 == 2:  # Medium distance
                distance_x = self.field_length/2 + 12
                distance_y = self.field_width/2 + 12
            else:  # Furthest from field
                distance_x = self.field_length/2 + 15
                distance_y = self.field_width/2 + 15

            x = distance_x * np.cos(angle) * self.distance_scale
            y = distance_y * np.sin(angle) * self.distance_scale
            z = self.bs_height
            ru_positions.append([x, y, z])

        self.radio_units: List[RadioUnit] = []
        for i, (x, y, z) in enumerate(ru_positions):
            channel_frequency = self.frequency + (i * self.channel_bandwidth)
            self.radio_units.append(RadioUnit(x, y, z, self.bs_tx_power, channel_frequency, self.channel_bandwidth))

        self.ues: List[UE] = []  # List to store UE objects

    def get_ues(self) -> List[UE]:
        """Get the list of UEs in the simulation"""
        return self.ues

    # --- RU lookup helpers -------------------------------------------------
    def get_ru_index_by_pci(self, pci: int) -> int | None:
        """Return the index of the RadioUnit with the given PCI, or None if not found.

        Note: PCI is a stable cell identifier and must not be assumed to equal
        the position of the RU in the internal list.
        """
        for idx, ru in enumerate(self.radio_units):
            if ru.pci == pci:
                return idx
        return None

    def set_ru_power_by_pci(self, pci: int, power: float) -> tuple[bool, List[UE]]:
        """Set RU power using PCI instead of list index.

        This avoids relying on PCI == list index, which may not hold across runs
        or configurations.
        """
        idx = self.get_ru_index_by_pci(pci)
        if idx is None:
            print(f"Target Cell with PCI {pci} not found")
            return False, []
        return self.set_ru_power(idx, power)

    def add_ues(self, num_ues) -> list:
        """Add a specified number of new UEs to the stadium simulation"""
        added_ues = []

        if num_ues <= 0:
            print("Number of new UEs must be positive")
            return added_ues

        # Generate positions for new UEs
        x_positions = []
        y_positions = []
        z_positions = []

        # Distribute new UEs evenly across tiers
        ues_per_tier = num_ues // len(self.tiers)
        remaining_ues = num_ues % len(self.tiers)

        for tier_idx, tier in enumerate(self.tiers):
            # Add extra UE to this tier if we have remaining ones
            tier_ues = ues_per_tier + (1 if tier_idx < remaining_ues else 0)
            base_height = tier.height

            current_tier_ues = 0
            while current_tier_ues < tier_ues:
                # Generate random position along stadium perimeter
                angle = np.random.uniform(0, 2*np.pi)

                # Calculate base coordinates at the inner edge of tier
                base_x = (self.field_length/2 + self.technical_area_width) * np.cos(angle)
                base_y = (self.field_width/2 + self.technical_area_width) * np.sin(angle)

                # Generate random distance along tier depth
                depth_fraction = np.random.uniform(0, 1)
                distance = depth_fraction * tier.depth

                # Calculate actual position including tier angle
                height_increase = distance * np.tan(np.radians(tier.angle))
                x = base_x + distance * np.cos(angle)
                y = base_y + distance * np.sin(angle)
                z = base_height + height_increase

                # Verify position is valid
                if self.is_valid_position(x, y):
                    x_positions.append(x)
                    y_positions.append(y)
                    z_positions.append(z)
                    current_tier_ues += 1

        # Create UE objects and calculate their signal metrics
        for i in range(len(x_positions)):
            ue = UE(x_positions[i], y_positions[i], z_positions[i] + self.ue_height)
            ue.calculate_signal_metrics(self.radio_units)
            self.ues.append(ue)
            added_ues.append(ue)

        # Update total UE count
        self.total_ues += num_ues

        print(f"Successfully added {num_ues} new UEs. Current UEs: {self.total_ues}")

        return added_ues

    def remove_ues(self, num_ues: int) -> list:
        """Remove a specified number of UEs from the stadium simulation.

        Args:
            num_ues (int): The number of UEs to remove from the simulation

        Returns:
            int: The actual number of UEs removed
        """
        removed_ues = []

        if num_ues <= 0:
            print("Number of UEs to remove must be positive")
            return removed_ues

        if num_ues > self.total_ues:
            print(f"Cannot remove {num_ues} UEs: only {self.total_ues} UEs exist")
            num_ues = self.total_ues

        # Randomly select UEs to remove
        indices_to_remove = np.random.choice(len(self.ues), num_ues, replace=False)

        # Remove UEs from their connected RUs first
        for idx in sorted(indices_to_remove, reverse=True):
            ue = self.ues[idx]
            # Find and remove UE from its connected RU
            for ru in self.radio_units:
                if ue in ru.connected_ues:
                    ru.connected_ues.remove(ue)
            # Remove UE from simulation
            self.ues.pop(idx)
            removed_ues.append(ue)

        # Update total UE count
        self.total_ues -= num_ues

        print(f"Successfully removed {num_ues} UEs. Current UEs: {self.total_ues}")

        return removed_ues

    def generate_ue_positions(self):
        """Generate uniformly distributed UE positions in the multi-tier stands"""
        self.ue_positions = np.empty((2, 0))
        self.ue_heights = np.array([])
        self.total_ues = 0
        self.ues = []

    def is_valid_position(self, x, y):
        """Check if a position is valid within the stadium structure"""
        # Calculate stadium bounds
        max_x = self.field_length/2 + self.technical_area_width + sum(tier.depth for tier in self.tiers)
        max_y = self.field_width/2 + self.technical_area_width + sum(tier.depth for tier in self.tiers)

        # Check if point is within bounds and not in technical/field area
        is_within_bounds = abs(x) <= max_x and abs(y) <= max_y
        is_outside_technical = (abs(x) > (self.field_length/2 + self.technical_area_width) or
                              abs(y) > (self.field_width/2 + self.technical_area_width))

        return is_within_bounds and is_outside_technical

    def set_ru_power(self, ru_idx: int, power: float) -> tuple[bool, List[UE]]:
        """Set the transmission power of a specific radio unit"""
        if ru_idx < 0 or ru_idx >= len(self.radio_units):
            print(f"Invalid radio unit index: {ru_idx}")
            return False, []

        # Early exit if the requested power matches current power (no-op)
        try:
            current_power = float(self.radio_units[ru_idx].tx_power)
            requested_power = float(power)
        except Exception:
            current_power = self.radio_units[ru_idx].tx_power
            requested_power = power
        if abs(current_power - requested_power) <= 1e-3:
            # No change; skip recomputing UE metrics
            return True, []

        self.radio_units[ru_idx].set_tx_power(power)
        # Recalculate signal metrics for all UEs connected on this RU and only
        # compute for this RU since signal power of the other RUs did not change.
        metric_ues: List[UE] = []
        # Create a copy of the set to avoid "Set changed size during iteration" error
        for ue in list(self.radio_units[ru_idx].connected_ues):
            ue.calculate_signal_metrics(self.radio_units)
            metric_ues.append(ue)

        return True, metric_ues

    def visualize_stadium(self,
                          save_path: str | None = None,
                          show: bool = True,
                          annotate_rus: bool = True,
                          base_marker_size: int = 5,
                          dpi: int = 120,
                          show_legend: bool = True,
                          show_tier_info: bool = False,
                          show_title: bool = False,
                          base_font_size: int = 14,
                          legend_ue_size: int = 16,
                          legend_ru_size: int = 14,
                          pdf_path: str | None = None):
        """Visualize the stadium layout with UE distribution and signal strength.

        Args:
            save_path: If provided, saves the figure to this path instead of (or in addition to) showing it.
            show: Whether to display the figure in an interactive window (ignored in headless environments).
            annotate_rus: If True adds per-RU annotations (can clutter with many RUs).
            base_marker_size: Base marker size for UEs (scaled lightly by UE height). Default 5 is suitable for thousands of UEs.
            dpi: Figure DPI when saving.
            show_legend: If True, adds a legend for UE and Radio Unit markers (default True for clarity).
            show_tier_info: If True, shows tier configuration text box (default False for cleaner image).
            show_title: If True, shows the plot title (default False for publication-ready minimalist figure).
            base_font_size: Base font size for plot elements (ticks/legend/annotations); title slightly larger.
            legend_ue_size: Marker size (points) for UE symbol in legend (visual emphasis).
            legend_ru_size: Marker size (points) for RU symbol in legend.
            pdf_path: Optional path to also save a vector PDF copy of the figure.
        """
        # Store data for visualization
        self.ue_positions = np.array([[ue.x, ue.y] for ue in self.ues]).T
        self.ue_heights = np.array([ue.z for ue in self.ues])
        self.ue_signal_strength = np.array([ue.get_connected_ru_metrics()['rsrp'] for ue in self.ues])

        if self.ue_signal_strength is None or self.ue_signal_strength.size == 0:
            print("No UEs to visualize")
            return

        plt.figure(figsize=(15, 10), dpi=dpi)

        # Plot field
        field_rect = plt.Rectangle((-self.field_length/2, -self.field_width/2),
                                 self.field_length, self.field_width,
                                 facecolor='green', alpha=0.5)
        plt.gca().add_patch(field_rect)

        # Plot technical area
        tech_area_rect = plt.Rectangle(
            (-(self.field_length/2 + self.technical_area_width),
             -(self.field_width/2 + self.technical_area_width)),
            self.field_length + 2*self.technical_area_width,
            self.field_width + 2*self.technical_area_width,
            facecolor='gray', alpha=0.3)
        plt.gca().add_patch(tech_area_rect)

        # Create custom colormap for signal strength
        colors = ['red', 'yellow', 'blue']
        n_bins = 100
        cmap = LinearSegmentedColormap.from_list('signal_strength', colors, N=n_bins)

        # Plot UEs with signal strength color coding and size based on height
        # Adaptive marker sizing: for large populations keep size small
        n_ues = len(self.ues)
        if n_ues > 5000:
            size = base_marker_size
            alpha = 0.4
        elif n_ues > 2000:
            size = base_marker_size + 2
            alpha = 0.5
        else:
            size = base_marker_size + 5
            alpha = 0.6
        scatter = plt.scatter(self.ue_positions[0], self.ue_positions[1],
                              c=self.ue_signal_strength, cmap=cmap,
                              s=size + (self.ue_heights - np.min(self.ue_heights, initial=0)) * 0.2,
                              alpha=alpha,
                              vmin=0, vmax=-100)  # vmin and vmax set by Huff

        # Plot radio units with their IDs, power levels, and channel info
        ru_handle = None
        for i, ru in enumerate(self.radio_units):
            handle = plt.scatter(ru.x, ru.y, marker='^', color='black', s=80)
            if ru_handle is None:
                ru_handle = handle
            if annotate_rus:
                plt.annotate(f'RU{i}(Cell{i})\n{ru.tx_power}dBm\n{ru.channel_frequency}-{ru.channel_end_freq}MHz',
                             (ru.x, ru.y),
                             xytext=(4, 4),
                             textcoords='offset points',
                             fontsize=7)

        cbar = plt.colorbar(scatter, label='Reference Signal Received Power (dBm)')
        cbar.ax.tick_params(labelsize=base_font_size - 1)
        cbar.set_label('Reference Signal Received Power (dBm)', size=base_font_size)
        plt.axis('equal')
        plt.grid(True)
        if show_title:
            plt.title('Stadium Layout with 5G Coverage\n(UMi Street Canyon Model with Shadowing and Multi-tier Structure)',
                      fontsize=base_font_size + 2)

        if show_tier_info:
            tier_info = f"Stadium Configuration:\n"
            for i, tier in enumerate(self.tiers, 1):
                tier_info += f"Tier {i}: {tier.height}m height, {tier.angle}° angle\n"
            plt.figtext(0.02, 0.02, tier_info, fontsize=base_font_size - 2,
                        bbox=dict(facecolor='white', alpha=0.8))

        if show_legend:
            # Build proxy artists with larger markers for clarity
            # Derive a representative UE color (use middle color of colormap if none plotted)
            if len(self.ue_signal_strength) > 0:
                # Use colormap at mean value
                norm_val = (np.mean(self.ue_signal_strength) - 0) / (-100 - 0)  # based on vmin=0, vmax=-100
                norm_val = np.clip(norm_val, 0, 1)
                ue_color = cmap(norm_val)
            else:
                ue_color = 'green'
            ue_proxy = Line2D([0], [0], marker='o', linestyle='None', markersize=legend_ue_size,
                              markerfacecolor=ue_color, markeredgecolor='black', alpha=0.7)
            ru_proxy = Line2D([0], [0], marker='^', linestyle='None', markersize=legend_ru_size,
                              markerfacecolor='black', markeredgecolor='black', alpha=0.9)
            handles = [ue_proxy, ru_proxy]
            labels = ['UE', 'Radio Unit']
            plt.legend(handles, labels, loc='upper right', framealpha=0.9,
                       prop={'size': base_font_size})

        # Adjust tick label sizes
        ax = plt.gca()
        ax.tick_params(axis='both', which='major', labelsize=base_font_size - 1)

        if save_path:
            plt.tight_layout()
            plt.savefig(save_path, dpi=dpi, bbox_inches='tight')
        if pdf_path:
            plt.savefig(pdf_path, dpi=dpi, bbox_inches='tight')
        if show:
            plt.show()
        else:
            plt.close()
        self.print_coverage_stats()

    def print_coverage_stats(self):
        """Print detailed statistics about the signal coverage"""
        if not self.ues:
            print("No UEs in the simulation")
            return

        # Calculate statistics based on connected RU metrics
        metrics = [ue.get_connected_ru_metrics() for ue in self.ues]
        rsrp_values = [m['rsrp'] for m in metrics]
        rsrq_values = [m['rsrq'] for m in metrics]
        sinr_values = [m['sinr'] for m in metrics]

        print("\nCoverage Statistics:")
        print(f"Total UEs: {self.total_ues}")

        # RSRP categories
        excellent_signal = np.sum([rsrp > -80 for rsrp in rsrp_values])
        good_signal = np.sum([(rsrp <= -80) & (rsrp > -90) for rsrp in rsrp_values])
        medium_signal = np.sum([(rsrp <= -90) & (rsrp > -100) for rsrp in rsrp_values])
        poor_signal = np.sum([rsrp <= -100 for rsrp in rsrp_values])

        print("\nRSRP Statistics:")
        print(f"Excellent (>-80 dBm): {excellent_signal/self.total_ues*100:.1f}% of UEs")
        print(f"Good (-90 to -80 dBm): {good_signal/self.total_ues*100:.1f}% of UEs")
        print(f"Medium (-100 to -90 dBm): {medium_signal/self.total_ues*100:.1f}% of UEs")
        print(f"Poor (<-100 dBm): {poor_signal/self.total_ues*100:.1f}% of UEs")

        print("\nAverage Metrics:")
        print(f"Average RSRP: {np.mean(rsrp_values):.1f} dBm")
        print(f"Average RSRQ: {np.mean(rsrq_values):.1f} dB")
        print(f"Average SINR: {np.mean(sinr_values):.1f} dB")

        # Print per-tier statistics
        print("\nPer-Tier Statistics:")
        ues_per_tier = self.total_ues // len(self.tiers)
        for i in range(len(self.tiers)):
            start_idx = i * ues_per_tier
            end_idx = (i + 1) * ues_per_tier if i < len(self.tiers) - 1 else self.total_ues
            tier_ues = self.ues[start_idx:end_idx]
            tier_metrics = [ue.get_connected_ru_metrics() for ue in tier_ues]
            tier_rsrp = np.mean([m['rsrp'] for m in tier_metrics])
            tier_rsrq = np.mean([m['rsrq'] for m in tier_metrics])
            tier_sinr = np.mean([m['sinr'] for m in tier_metrics])
            print(f"\nTier {i+1}:")
            print(f"  Average RSRP: {tier_rsrp:.1f} dBm")
            print(f"  Average RSRQ: {tier_rsrq:.1f} dB")
            print(f"  Average SINR: {tier_sinr:.1f} dB")

    def handoff_ue(self, ue_id: str, new_cell_id: int) -> tuple[bool, List[UE]]:
        """Handoff a specific UE to a new cell/radio unit"""
        # Find UE and RU by ID
        target_ue = next((ue for ue in self.ues if ue.imsi == ue_id), None)
        target_cell = next((ru for ru in self.radio_units if ru.pci == new_cell_id), None)

        if target_ue is None:
            print(f"UE with ID {ue_id} not found")
            return False, []

        if target_cell is None:
            print(f"Target Cell with ID {new_cell_id} not found")
            return False, []

        # Getting previous cell to recalculate metrics from its UEs after performing the handover
        old_cell = target_ue.connected_ru

        # Perform handoff
        success = target_ue.force_handoff(target_cell)

        metric_ues: List[UE] = []
        if success:
            # Recalculate metrics for all UEs on previous cell since interference patterns have changed
            # Create a copy of the set to avoid "Set changed size during iteration" error
            for ue in list(old_cell.connected_ues):
                ue.calculate_signal_metrics(self.radio_units)
                metric_ues.append(ue)

            # Recalculate metrics for all UEs on target cell since interference patterns have changed
            # Create a copy of the set to avoid "Set changed size during iteration" error
            for ue in list(target_cell.connected_ues):
                ue.calculate_signal_metrics(self.radio_units)
                metric_ues.append(ue)

            # Recalculate metrics for ALL UEs since interference patterns have changed
            # for ue in self.ues:
            #     ue.calculate_signal_metrics(self.radio_units)

        return success, metric_ues
