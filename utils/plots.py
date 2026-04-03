"""
utils/plots.py
--------------
Matplotlib diagram functions for the blast management dashboard.
All functions return a ``matplotlib.figure.Figure`` and have no Streamlit
dependencies, making them reusable and independently testable.
"""

from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from utils.calculations import BlastGeometry, BlastCharges


# ---------------------------------------------------------------------------
# BLAST PATTERN (TOP VIEW)
# ---------------------------------------------------------------------------

def plot_blast_pattern(num_holes: int, burden: float, spacing: float) -> plt.Figure:
    """Generate a top-view staggered blast pattern diagram."""
    rows = int(np.ceil(np.sqrt(num_holes)))
    cols = int(np.ceil(num_holes / rows)) + 1

    x_coords: list[float] = []
    y_coords: list[float] = []
    hole_count = 0

    for r in range(rows):
        for c in range(cols):
            if hole_count >= num_holes:
                break
            x = c * spacing + (spacing / 2 if r % 2 != 0 else 0)
            y = r * burden * -1
            x_coords.append(x)
            y_coords.append(y)
            hole_count += 1

    fig, ax = plt.subplots(figsize=(8, 4))
    fig.patch.set_facecolor("#f8f9fa")
    ax.set_facecolor("#f8f9fa")

    ax.scatter(
        x_coords, y_coords,
        c="white", s=70, edgecolors="#004085", linewidth=2, zorder=3,
        label="Trou de Foration",
    )
    ax.axhline(
        y=burden * 0.5, color="#d9534f", linestyle="--", linewidth=2,
        label="Front Libre (Théorique)",
    )
    ax.set_title(
        f"Plan de Tir — Maille {burden} m × {spacing} m (Quinconce)",
        fontsize=10, pad=10, fontweight="bold",
    )
    ax.set_xlabel("Espacement (m)", fontsize=8)
    ax.set_ylabel("Banquette (m)", fontsize=8)
    ax.grid(True, linestyle="--", alpha=0.5, color="grey")
    ax.legend(loc="upper right", fontsize=8)
    ax.set_aspect("equal")
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# HOLE CROSS-SECTION DIAGRAM
# ---------------------------------------------------------------------------

def plot_hole_cross_section(
    geom: BlastGeometry,
    charges: BlastCharges,
) -> plt.Figure:
    """
    Draw a vertical cross-section of a single blast hole showing all loading zones.

    Zone heights are drawn proportionally to the available charge column so the
    diagram always fits the hole regardless of charge density.

    Annotation strategy (no overlaps):
    - LEFT side (double-arrow brackets): Bourrage, Safety Gap, Ammonix  — large zones
    - RIGHT side (horizontal leader lines): Émulsion, Surforation — small zones
    - Inside-column text only when zone visual height >= MIN_LABEL_HEIGHT
    - "Prof. totale" arrow placed far right, clear of all labels
    """
    MIN_LABEL_HEIGHT = 1.0  # minimum zone height (m) to show an in-column label

    hole_depth = geom.hole_depth
    stemming_m = geom.stemming_m
    gap_height = geom.safety_gap
    emulsion_per_hole = charges.emulsion_per_hole
    ammonix_per_hole = charges.ammonix_per_hole
    sub_drill = geom.sub_drill
    bench_height = geom.bench_height
    hole_diameter = geom.hole_diameter

    # ── Compute visual zone heights ──────────────────────────────────────────
    charge_col_height = max(0.01, hole_depth - stemming_m - gap_height)
    total_charge_kg = (emulsion_per_hole + ammonix_per_hole) or 1.0
    emulsion_height = charge_col_height * (emulsion_per_hole / total_charge_kg)
    ammonix_height = charge_col_height * (ammonix_per_hole / total_charge_kg)

    # ── Zone boundary depths (negative = downward) ──────────────────────────
    y_surface = 0.0
    y_stemming_bot = -stemming_m
    y_gap_bot = y_stemming_bot - gap_height
    y_ammonix_bot = y_gap_bot - ammonix_height
    y_emulsion_bot = y_ammonix_bot - emulsion_height
    y_bench_floor = -bench_height
    y_hole_bot = -hole_depth

    half_w = 0.40           # half-width of the drawn column (visual units)
    col_right = half_w
    col_left = -half_w

    # Annotation x-positions
    x_left_arrow = col_left - 0.55
    x_left_text = x_left_arrow - 0.12
    x_right_leader = col_right + 0.15
    x_right_text = col_right + 0.65
    x_depth_arrow = col_right + 1.45

    fig, ax = plt.subplots(figsize=(5.5, 11))
    fig.patch.set_facecolor("#f8f9fa")
    ax.set_facecolor("#f8f9fa")

    # ── Helper: draw a filled rectangle zone ────────────────────────────────
    def draw_zone(y_top: float, y_bot: float, color: str, hatch: str = "") -> None:
        ax.add_patch(plt.Rectangle(
            (col_left, y_bot), 2 * half_w, abs(y_bot - y_top),
            facecolor=color, edgecolor="#333333", linewidth=0.8, hatch=hatch, zorder=2,
        ))

    # ── Zones ────────────────────────────────────────────────────────────────
    draw_zone(y_surface, y_hole_bot, color="#d0d0d0")                      # hole outline
    draw_zone(y_surface, y_stemming_bot, color="#b5651d", hatch="//")      # Bourrage
    if gap_height > 0:
        draw_zone(y_stemming_bot, y_gap_bot, color="#e0e0e0", hatch="..")  # Gap
    draw_zone(y_gap_bot, y_ammonix_bot, color="#f0a500")                   # Ammonix
    draw_zone(y_ammonix_bot, y_emulsion_bot, color="#e63946")              # Emulsion
    if sub_drill > 0:
        draw_zone(y_bench_floor, y_hole_bot, color="#607d8b", hatch="xx")  # Sub-drill

    # ── Reference lines ──────────────────────────────────────────────────────
    ax.axhline(y=0, color="#2c3e50", linewidth=2.5, zorder=4)
    ax.text(x_right_leader, 0.25, "Surface", fontsize=9, color="#2c3e50",
            fontweight="bold", va="bottom", ha="left")

    ax.axhline(y=y_bench_floor, color="#1a6b3c", linewidth=2, linestyle="--", zorder=4)
    ax.text(x_right_leader, y_bench_floor - 0.25,
            f"Fond gradin  ({bench_height:.1f} m)",
            fontsize=8.5, color="#1a6b3c", fontweight="bold", va="top", ha="left")

    # ── LEFT double-arrow annotations (large zones) ──────────────────────────
    def left_arrow_annot(y_top: float, y_bot: float, line1: str, line2: str) -> None:
        if abs(y_bot - y_top) < 0.05:
            return
        mid = (y_top + y_bot) / 2
        ax.plot([x_left_arrow - 0.06, x_left_arrow + 0.06], [y_top, y_top],
                color="#555555", lw=1.0, zorder=5)
        ax.plot([x_left_arrow - 0.06, x_left_arrow + 0.06], [y_bot, y_bot],
                color="#555555", lw=1.0, zorder=5)
        ax.annotate("", xy=(x_left_arrow, y_bot), xytext=(x_left_arrow, y_top),
                    arrowprops=dict(arrowstyle="<->", color="#555555", lw=1.2))
        ax.text(x_left_text, mid,
                f"{line1}\n{line2}",
                fontsize=8, ha="right", va="center", color="#333333",
                linespacing=1.5,
                bbox=dict(boxstyle="round,pad=0.15", facecolor="#f8f9fa",
                          edgecolor="none", alpha=0.85))

    left_arrow_annot(y_surface, y_stemming_bot, "Bourrage", f"{stemming_m:.1f} m")
    if gap_height > 0:
        left_arrow_annot(y_stemming_bot, y_gap_bot, "Sécurité", f"{gap_height:.1f} m")
    left_arrow_annot(y_gap_bot, y_ammonix_bot, "Ammonix", f"{ammonix_per_hole:.1f} kg")

    # ── RIGHT horizontal leader annotations (small / bottom zones) ───────────
    def right_leader_annot(y_zone_mid: float, label: str, dy_offset: float = 0.0) -> None:
        y = y_zone_mid + dy_offset
        ax.annotate(
            label,
            xy=(col_right, y_zone_mid),
            xytext=(x_right_text, y),
            fontsize=8, ha="left", va="center", color="#333333",
            linespacing=1.45,
            bbox=dict(boxstyle="round,pad=0.2", facecolor="#f8f9fa",
                      edgecolor="#aaaaaa", linewidth=0.6),
            arrowprops=dict(arrowstyle="-", color="#888888", lw=1.0,
                            connectionstyle="arc3,rad=0.0"),
        )

    right_leader_annot(
        (y_ammonix_bot + y_emulsion_bot) / 2,
        f"Émulsion\n{emulsion_per_hole:.1f} kg",
    )
    if sub_drill > 0 and charge_col_height > 0.05:
        sub_drill_kg = (sub_drill / charge_col_height) * total_charge_kg
        right_leader_annot(
            (y_bench_floor + y_hole_bot) / 2,
            f"Surforation\n{sub_drill:.1f} m\n{sub_drill_kg:.1f} kg",
        )

    # ── Total depth arrow (far right) ────────────────────────────────────────
    ax.annotate("", xy=(x_depth_arrow, y_hole_bot), xytext=(x_depth_arrow, y_surface),
                arrowprops=dict(arrowstyle="<->", color="#004085", lw=1.8))
    ax.text(x_depth_arrow + 0.12, -hole_depth / 2,
            f"Prof. totale\n{hole_depth:.1f} m",
            fontsize=9, ha="left", va="center", color="#004085",
            fontweight="bold", linespacing=1.5)

    # ── In-column zone labels (only for zones tall enough) ───────────────────
    in_col_zones: list[tuple[float, float, str, str]] = [
        (y_surface, y_stemming_bot, "BOURRAGE", "#ffffff"),
        (y_gap_bot, y_ammonix_bot, "AMMONIX\n(ANFO)", "#333333"),
        (y_ammonix_bot, y_emulsion_bot, "ÉMULSION\n(Booster)", "#ffffff"),
    ]
    for y_top, y_bot, label, tcolor in in_col_zones:
        if abs(y_bot - y_top) >= MIN_LABEL_HEIGHT:
            ax.text(0, (y_top + y_bot) / 2, label,
                    fontsize=8, ha="center", va="center",
                    color=tcolor, fontweight="bold", linespacing=1.3, zorder=5)

    # ── Axis formatting ───────────────────────────────────────────────────────
    ax.set_xlim(-1.8, x_depth_arrow + 1.0)
    ax.set_ylim(y_hole_bot - 0.6, 1.0)
    ax.set_yticks(np.arange(0, int(y_hole_bot) - 1, -1))
    ax.yaxis.set_tick_params(labelsize=8)
    ax.set_xticks([])
    ax.set_ylabel("Profondeur (m)", fontsize=9)
    ax.set_title(
        f"Coupe Transversale du Trou  (Ø {hole_diameter} mm)\n"
        f"Charge totale : {ammonix_per_hole + emulsion_per_hole:.1f} kg/trou",
        fontsize=10, pad=10, fontweight="bold",
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_visible(False)

    fig.tight_layout()
    return fig
