#!/usr/bin/env python3
"""Generate a stadium coverage plot with 8192 UEs.

Usage:
    python plot_8192_ues.py [--output filename.png] [--no-show] [--no-annot]

Defaults:
    Saves figure to plots/stadium_8192_ues.png and shows the window if possible.
"""
from __future__ import annotations
import argparse
from pathlib import Path
from stadium_simulation import StadiumSimulation


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--ues', type=int, default=8192, help='Number of UEs to add (default: 8192)')
    p.add_argument('--output', type=str, default='plots/stadium_8192_ues.png', help='Output image path')
    p.add_argument('--no-show', action='store_true', help='Do not display the figure')
    p.add_argument('--annot', action='store_true', help='Enable RU annotations')
    p.add_argument('--no-height-lines', action='store_true', help='Disable stadium height lines')
    p.add_argument('--dpi', type=int, default=160, help='Figure DPI when saving')
    p.add_argument('--legend-ue-size', type=int, default=22, help='Legend UE marker size (points)')
    p.add_argument('--legend-ru-size', type=int, default=18, help='Legend RU marker size (points)')
    p.add_argument('--font-size', type=int, default=24, help='Base font size for plot text')
    return p.parse_args()


def main():
    args = parse_args()
    sim = StadiumSimulation()  # default includes 10% antenna distance increase
    sim.add_ues(args.ues)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    pdf_out = out_path.with_suffix('.pdf')
    sim.visualize_stadium(save_path=str(out_path),
                          show=not args.no_show,
                          annotate_rus=args.annot,
                          show_stadium_height=not args.no_height_lines,
                          base_marker_size=4,
                          dpi=args.dpi,
                          show_legend=True,
                          show_tier_info=False,
                          show_title=False,
                          base_font_size=args.font_size,
                          legend_ue_size=args.legend_ue_size,
                          legend_ru_size=args.legend_ru_size,
                          pdf_path=str(pdf_out))
    print(f"Saved plot to {out_path} and {pdf_out} with {args.ues} UEs")


if __name__ == '__main__':
    main()
