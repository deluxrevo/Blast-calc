# SGT — Système de Gestion de Tir (Blast-calc)

Streamlit tool for quarry blast planning: pattern geometry, powder factor (PF),
explosive quantities, costs and PDF report.

## Quick start

```bash
pip install -r requirements.txt
streamlit run app.py          # PIN login screen, then the dashboard
pip install -r requirements-dev.txt && python -m pytest   # core-math tests
```

`app.py` is the UI, `utils/calculations.py` holds all formulas (no Streamlit
imports), `utils/plots.py` the diagrams, `utils/config.py` geology profiles.
`blastcalc.py` is a legacy single-file version, kept untouched.

## Unit model

| Quantity | Unit |
|---|---|
| Hole diameter | mm |
| Burden B, spacing S, heights | m |
| Area per hole | m² |
| Hole volume per metre | m³/m |
| Total hole volume | m³ |
| Explosive bulk density | kg/m³ |
| Rock density | t/m³ |
| Rock volume | m³ |
| PF | kg/t **or** kg/m³ (selectable) |

## Formulas

- Hole volume per metre = π (d/2)², d in m (89 mm → 0.006221 m³/m)
- Total hole volume = m³/m × drilled metres
- Explosive capacity (kg) = hole volume (m³) × bulk density (kg/m³)
- Area per hole = B × S ÷ holes-per-cell
- Rock volume per hole = area per hole × bench height H
- Tonnage = volume × rock density
- PF (kg/m³) = explosive ÷ volume; PF (kg/t) = explosive ÷ tonnage
- kg/m³ = kg/t × density; kg/t = kg/m³ ÷ density

## Pattern assumptions

| Mode | Area per hole | Example B=5, S=5.5 |
|---|---|---|
| Rectangular grid | B × S | 27.5 m² |
| Staggered (quinconce) | B × S (offset rows keep the same density) | 27.5 m² |
| Grid + centre hole in every rectangle | B × S ÷ 2 (density doubled) | 13.75 m² |

Adding a centre hole to every 5 × 5.5 rectangle gives 13.75 m²/hole; it is **not**
a 2.5 × 2.75 grid (6.875 m²/hole, 4× denser). With H = 10 m, a hole then
represents 137.5 m³ instead of 275 m³.

## PF unit options

- **kg/t** — per tonne blasted; use it when targets/sheets are expressed per tonne
  (e.g. 0.25 kg/t). Depends on rock density.
- **kg/m³** — per in-situ cubic metre; independent of density, common in design
  tables. Geology defaults are stored in kg/m³ (the kg/t default is derived).

The target is converted once to kg/m³ for charge sizing; the actual PF is then
computed in the unit you selected, so target and actual are never compared across units.

Worked example (regression test): 520 m drilled × 13.75 m²/hole = 7 150 m³ →
17 875 t at 2.5 t/m³. Target 0.25 kg/t = 4 469 kg; 2 000 kg loaded gives
0.112 kg/t (≈ 45 % of target → "low").

## Input validation

Non-positive values, unrealistic density (1–4.5 t/m³) or diameter (30–250 mm), and
stemming deeper than the hole stop the calculation with an explicit message.
