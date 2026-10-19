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

from utils.calculations import (
    BlastGeometry,
    BlastCharges,
    PATTERN_RECTANGULAR,
    PATTERN_CENTER_HOLE,
    area_per_hole,
)


# ---------------------------------------------------------------------------
# BLAST PATTERN (TOP VIEW)
# ---------------------------------------------------------------------------

_PATTERN_LABELS = {
    "rectangular": "Grille rectangulaire",
    "staggered": "Quinconce",
    "center_hole": "Grille + trou central",
}


def plot_blast_pattern(
    num_holes: int,
    burden: float,
    spacing: float,
    pattern: str = "staggered",
) -> plt.Figure:
    """
    Generate a top-view blast pattern diagram.

    Rows are drawn every `burden` m (every burden/2 m for the centre-hole
    pattern, whose offset rows are what the added centre holes form).  The
    free face is the top line (y = 0); the first row sits one burden behind it.
    """
    row_pitch = burden / 2 if pattern == PATTERN_CENTER_HOLE else burden
    stagger = pattern != PATTERN_RECTANGULAR
    num_holes = max(1, int(num_holes))
    # Roughly square layout in metres: rows x row_pitch ~ cols x spacing
    rows = max(1, int(round(np.sqrt(num_holes * spacing / row_pitch))))
    rows = min(rows, num_holes)
    cols = int(np.ceil(num_holes / rows))

    x_coords: list[float] = []
    y_coords: list[float] = []
    for i in range(num_holes):
        r, c = divmod(i, cols)
        x_coords.append(c * spacing + (spacing / 2 if stagger and r % 2 else 0.0))
        y_coords.append(burden + r * row_pitch)

    fig, ax = plt.subplots(figsize=(8, 5))
    fig.patch.set_facecolor("#f8f9fa")
    ax.set_facecolor("#f8f9fa")

    ax.scatter(
        x_coords, y_coords,
        c="white", s=60, edgecolors="#004085", linewidth=2, zorder=3,
        label=f"Trou de foration ({num_holes})",
    )
    x_min = min(x_coords) - spacing / 2
    x_max = max(x_coords) + spacing / 2
    ax.plot(
        [x_min, x_max], [0.0, 0.0], color="#d9534f", linestyle="--", linewidth=2,
        label=f"Front libre (B = {burden:.2f} m devant la 1ère rangée)",
    )
    n_rows_used = int(np.ceil(num_holes / cols))
    ax.set_title(
        f"Plan de Tir — Maille {burden:.2f} m × {spacing:.2f} m "
        f"({_PATTERN_LABELS.get(pattern, pattern)})\n"
        f"{area_per_hole(burden, spacing, pattern):.2f} m²/trou — "
        f"{num_holes} trous sur {n_rows_used} rangée(s)",
        fontsize=10, pad=10, fontweight="bold",
    )
    ax.set_xlabel("Espacement (m)", fontsize=8)
    ax.set_ylabel("Distance au front libre (m)", fontsize=8)
    ax.tick_params(labelsize=8)
    ax.set_xlim(x_min - spacing / 2, x_max + spacing / 2)
    ax.set_ylim(max(y_coords) + row_pitch, -row_pitch)  # front libre en haut
    ax.grid(True, linestyle="--", alpha=0.5, color="grey")
    ax.set_aspect("equal", adjustable="box")
    ax.legend(
        loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2, fontsize=8,
        frameon=False,
    )
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# HOLE CROSS-SECTION DIAGRAM
# ---------------------------------------------------------------------------

def _spread_labels(ys: list[float], min_gap: float, y_min: float, y_max: float) -> list[float]:
    """
    Shift label y-positions (data units) so consecutive labels are at least
    `min_gap` apart while staying inside [y_min, y_max].  Order is preserved.
    """
    if not ys:
        return []
    order = sorted(range(len(ys)), key=lambda i: -ys[i])  # top to bottom
    placed = [ys[i] for i in order]
    placed[0] = min(placed[0], y_max)
    for k in range(1, len(placed)):
        placed[k] = min(placed[k], placed[k - 1] - min_gap)
    overflow = y_min - placed[-1]
    if overflow > 0:  # pushed below the frame: shift the whole stack up
        placed[-1] = y_min
        for k in range(len(placed) - 2, -1, -1):
            placed[k] = max(placed[k], placed[k + 1] + min_gap)
    out = [0.0] * len(ys)
    for k, i in enumerate(order):
        out[i] = placed[k]
    return out


def plot_hole_cross_section(
    geom: BlastGeometry,
    charges: BlastCharges,
) -> plt.Figure:
    """
    Draw a vertical cross-section of a single blast hole, to scale.

    Zone lengths are physical: the booster (émulsion) sits at the bottom, the
    Ammonix column above it (length = kg / linear density), then the optional
    air deck and the stemming up to the collar.  When the designed charge is
    smaller than the hole capacity, the stemming is longer than the minimum
    entered by the operator; the effective stemming is shown.

    Annotation strategy (no overlaps):
    - LEFT side (double-arrow brackets): Bourrage, Tampon, Ammonix
    - RIGHT side (leader lines, de-conflicted vertically): Émulsion,
      Surforation, bench floor
    - "Prof. totale" arrow placed far right, clear of all labels
    """
    MIN_LABEL_HEIGHT = 1.0  # minimum zone height (m) to show an in-column label

    hole_depth = geom.hole_depth
    gap_height = geom.safety_gap
    emulsion_kg = charges.emulsion_per_hole
    ammonix_kg = charges.ammonix_per_hole
    sub_drill = geom.sub_drill
    bench_height = geom.bench_height
    hole_diameter = geom.hole_diameter

    # ── Physical zone lengths (m) ────────────────────────────────────────────
    emulsion_height = min(geom.emulsion_length(emulsion_kg), hole_depth)
    ammonix_height = min(geom.ammonix_length(ammonix_kg), hole_depth - emulsion_height)
    gap_drawn = min(gap_height, max(0.0, hole_depth - emulsion_height - ammonix_height))
    stemming_eff = max(0.0, hole_depth - emulsion_height - ammonix_height - gap_drawn)

    # ── Zone boundary depths (negative = downward) ──────────────────────────
    y_surface = 0.0
    y_hole_bot = -hole_depth
    y_emulsion_top = y_hole_bot + emulsion_height
    y_ammonix_top = y_emulsion_top + ammonix_height
    y_stemming_bot = y_ammonix_top + gap_drawn
    y_bench_floor = -bench_height

    half_w = 0.40           # half-width of the drawn column (visual units)
    col_right = half_w
    col_left = -half_w

    # Annotation x-positions
    x_left_arrow = col_left - 0.35
    x_left_text = x_left_arrow - 0.12
    x_right_text = col_right + 0.45
    x_depth_arrow = col_right + 2.0

    fig, ax = plt.subplots(figsize=(6, 10))
    fig.patch.set_facecolor("#f8f9fa")
    ax.set_facecolor("#f8f9fa")

    def draw_zone(y_top: float, y_bot: float, color: str, hatch: str = "") -> None:
        if abs(y_top - y_bot) <= 0:
            return
        ax.add_patch(plt.Rectangle(
            (col_left, y_bot), 2 * half_w, abs(y_bot - y_top),
            facecolor=color, edgecolor="#333333", linewidth=0.8, hatch=hatch, zorder=2,
        ))

    # ── Zones ────────────────────────────────────────────────────────────────
    draw_zone(y_surface, y_hole_bot, color="#d0d0d0")                      # hole outline
    draw_zone(y_surface, y_stemming_bot, color="#b5651d", hatch="//")      # Bourrage
    draw_zone(y_stemming_bot, y_ammonix_top, color="#e0e0e0", hatch="..")  # Tampon
    draw_zone(y_ammonix_top, y_emulsion_top, color="#f0a500")              # Ammonix
    draw_zone(y_emulsion_top, y_hole_bot, color="#e63946")                 # Émulsion
    if sub_drill > 0:                                                      # Sub-drill outline
        ax.add_patch(plt.Rectangle(
            (col_left, y_hole_bot), 2 * half_w, sub_drill, facecolor="none",
            edgecolor="#607d8b", linewidth=1.5, linestyle=":", zorder=3,
        ))

    # ── Reference lines ──────────────────────────────────────────────────────
    ax.axhline(y=0, color="#2c3e50", linewidth=2.5, zorder=4)
    ax.text(col_right + 0.1, 0.12, "Surface", fontsize=9, color="#2c3e50",
            fontweight="bold", va="bottom", ha="left")
    ax.axhline(y=y_bench_floor, color="#1a6b3c", linewidth=2, linestyle="--", zorder=4)

    # ── LEFT double-arrow annotations ────────────────────────────────────────
    left_items: list[tuple[float, float, str]] = []
    stem_label = f"Bourrage\n{stemming_eff:.1f} m"
    if stemming_eff > geom.stemming_m + 0.05:
        stem_label += f"\n(min. {geom.stemming_m:.1f} m)"
    left_items.append((y_surface, y_stemming_bot, stem_label))
    if gap_drawn > 0:
        left_items.append((y_stemming_bot, y_ammonix_top, f"Tampon\n{gap_drawn:.1f} m"))
    if ammonix_height > 0:
        left_items.append((
            y_ammonix_top, y_emulsion_top,
            f"Ammonix\n{ammonix_kg:.1f} kg\n{ammonix_height:.1f} m",
        ))
    y_lo, y_hi = y_hole_bot - 0.3, 0.6
    left_ys = _spread_labels(
        [(t + b) / 2 for t, b, _ in left_items], 1.2, y_lo + 0.5, y_hi - 0.5,
    )
    for (y_top, y_bot, label), y_txt in zip(left_items, left_ys):
        if abs(y_bot - y_top) >= 0.05:
            for yy in (y_top, y_bot):
                ax.plot([x_left_arrow - 0.06, x_left_arrow + 0.06], [yy, yy],
                        color="#555555", lw=1.0, zorder=5)
            ax.annotate("", xy=(x_left_arrow, y_bot), xytext=(x_left_arrow, y_top),
                        arrowprops=dict(arrowstyle="<->", color="#555555", lw=1.2))
        ax.annotate(
            label, xy=(x_left_arrow, (y_top + y_bot) / 2), xytext=(x_left_text, y_txt),
            fontsize=8, ha="right", va="center", color="#333333", linespacing=1.4,
            bbox=dict(boxstyle="round,pad=0.15", facecolor="#f8f9fa",
                      edgecolor="none", alpha=0.85),
            arrowprops=(
                dict(arrowstyle="-", color="#aaaaaa", lw=0.8)
                if abs(y_txt - (y_top + y_bot) / 2) > 0.1 else None
            ),
        )

    # ── RIGHT leader annotations (small / bottom zones) ──────────────────────
    right_items: list[tuple[float, float, str, str]] = []  # (anchor_y, x_anchor, text, color)
    right_items.append((
        y_bench_floor, col_right, f"Fond de gradin\nH = {bench_height:.1f} m", "#1a6b3c",
    ))
    right_items.append((
        (y_emulsion_top + y_hole_bot) / 2, col_right,
        f"Émulsion\n{emulsion_kg:.1f} kg ({emulsion_height:.2f} m)", "#333333",
    ))
    if sub_drill > 0:
        # Mass physically located below the bench floor (booster first, then Ammonix)
        lin_e = geom.emulsion_linear_density
        lin_a = geom.linear_charge_density
        in_sub_e = min(emulsion_height, sub_drill)
        in_sub_a = max(0.0, min(sub_drill - emulsion_height, ammonix_height))
        sub_drill_kg = in_sub_e * lin_e + in_sub_a * lin_a
        right_items.append((
            (y_bench_floor + y_hole_bot) / 2, col_right,
            f"Surforation J = {sub_drill:.1f} m\n{sub_drill_kg:.1f} kg sous le gradin",
            "#455a64",
        ))
    right_ys = _spread_labels(
        [it[0] for it in right_items], 0.9, y_lo + 0.4, -0.6,
    )
    for (y_anchor, x_anchor, label, color), y_txt in zip(right_items, right_ys):
        ax.annotate(
            label, xy=(x_anchor, y_anchor), xytext=(x_right_text, y_txt),
            fontsize=8, ha="left", va="center", color=color, linespacing=1.35,
            bbox=dict(boxstyle="round,pad=0.2", facecolor="#f8f9fa",
                      edgecolor="#aaaaaa", linewidth=0.6),
            arrowprops=dict(arrowstyle="-", color="#888888", lw=1.0),
        )

    # ── Total depth arrow (far right) ────────────────────────────────────────
    ax.annotate("", xy=(x_depth_arrow, y_hole_bot), xytext=(x_depth_arrow, y_surface),
                arrowprops=dict(arrowstyle="<->", color="#004085", lw=1.8))
    ax.text(x_depth_arrow + 0.1, -hole_depth / 2,
            f"Prof.\ntotale\n{hole_depth:.1f} m",
            fontsize=9, ha="left", va="center", color="#004085",
            fontweight="bold", linespacing=1.4)

    # ── In-column zone labels (only for zones tall enough) ───────────────────
    in_col_zones: list[tuple[float, float, str, str]] = [
        (y_surface, y_stemming_bot, "BOURRAGE", "#ffffff"),
        (y_ammonix_top, y_emulsion_top, "AMMONIX\n(ANFO)", "#333333"),
        (y_emulsion_top, y_hole_bot, "ÉMULSION", "#ffffff"),
    ]
    for y_top, y_bot, label, tcolor in in_col_zones:
        if abs(y_bot - y_top) >= MIN_LABEL_HEIGHT:
            ax.text(0, (y_top + y_bot) / 2, label, rotation=90,
                    fontsize=8, ha="center", va="center",
                    color=tcolor, fontweight="bold", linespacing=1.3, zorder=5)

    # ── Axis formatting ───────────────────────────────────────────────────────
    ax.set_xlim(-2.2, x_depth_arrow + 0.9)
    ax.set_ylim(y_lo, y_hi)
    ax.set_yticks(np.arange(0, -int(np.ceil(hole_depth)) - 1, -1))
    ax.set_yticklabels([f"{abs(t):g}" for t in ax.get_yticks()])
    ax.yaxis.set_tick_params(labelsize=8)
    ax.set_xticks([])
    ax.set_ylabel("Profondeur (m)", fontsize=9)
    total_kg = ammonix_kg + emulsion_kg
    ax.set_title(
        f"Coupe du Trou (Ø {hole_diameter} mm) — à l'échelle\n"
        f"Charge chargée : {total_kg:.1f} kg/trou",
        fontsize=10, pad=10, fontweight="bold",
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_visible(False)

    fig.tight_layout()
    return fig
