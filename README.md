# 💥 Blast-calc — Quarry Blast Optimizer

A Streamlit web app for optimizing quarry blast design, specifically tuned for Benslimane geology (Schist/Quartzite mix).

## Features

- **Drill Pattern Blueprint** — Visual top-view of the staggered (quinconce) hole pattern
- **Loading Recipe** — Per-hole explosive loading instructions with a visual side-view profile
- **Financial Report** — Estimated invoice for drilling, Ammonix, emulsion, and accessories
- **Downloadable Plan** — Export your blast plan as a text file

## Live Demo

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://blast-calc.streamlit.app)

## Getting Started

### Prerequisites

- Python 3.8+

### Installation

```bash
git clone https://github.com/deluxrevo/Blast-calc.git
cd Blast-calc
pip install -r requirements.txt
```

### Running the App

```bash
streamlit run blastcalc.py
```

Then open your browser at `http://localhost:8501`.

## Usage

1. Set your **Production Target** (tonnage and rock type) in the sidebar.
2. Adjust **Bench Geometry** (height, hole diameter, rock density).
3. Enter your **Unit Costs** (drilling, explosives, detonators).
4. Review the automatically generated **Drill Pattern**, **Loading Recipe**, and **Financial Report** in the tabs.
5. Download the blast plan using the sidebar button.

## Supported Rock Conditions

| Condition | Burden | Spacing | Powder Factor |
|-----------|--------|---------|---------------|
| Mix: Schist/Quartzite (Standard) | 3.0 m | 3.0 m | 0.55 kg/m³ |
| Hard: Dolerite/Basalt (Tough) | 2.8 m | 3.0 m | 0.65 kg/m³ |

## License

[MIT](LICENSE)
