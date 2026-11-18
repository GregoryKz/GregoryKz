#!/usr/bin/env python3
"""Gera um SVG animado de um dragão sobrevoando e queimando o gráfico de contribuições do GitHub.

Uso:
    GITHUB_TOKEN=... python dragon.py --user GregoryKz --out dist
    python dragon.py --fake --out dist      # dados aleatórios para teste
"""
import argparse
import json
import math
import os
import random
import urllib.request

CELL = 11
STEP = 14
PAD_X = 50
PAD_Y = 48
SCALE = 1.3
ROWS = 7

THEMES = {
    "light": {
        "levels": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"],
        "ash": "#d0d7de",
        "body": "#c62828",
        "belly": "#ff8a65",
        "wing": "#8e1b1b",
        "horn": "#3e2723",
    },
    "dark": {
        "levels": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"],
        "ash": "#30363d",
        "body": "#e53935",
        "belly": "#ffab91",
        "wing": "#b71c1c",
        "horn": "#ffe0b2",
    },
}

LEVEL_MAP = {
    "NONE": 0,
    "FIRST_QUARTILE": 1,
    "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3,
    "FOURTH_QUARTILE": 4,
}

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        weeks { contributionDays { contributionLevel weekday } }
      }
    }
  }
}
"""


def fetch_grid(user, token):
    body = json.dumps({"query": QUERY, "variables": {"login": user}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        data = json.load(r)
    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    grid = []
    for w in weeks:
        col = [None] * ROWS
        for d in w["contributionDays"]:
            col[d["weekday"]] = LEVEL_MAP[d["contributionLevel"]]
        grid.append(col)
    return grid


def fake_grid():
    random.seed(7)
    grid = []
    for w in range(53):
        col = []
        for d in range(ROWS):
            if w == 52 and d > 3:
                col.append(None)
            else:
                r = random.random()
                col.append(0 if r < 0.45 else random.randint(1, 4))
        grid.append(col)
    return grid


def cell_center(w, d):
    return PAD_X + w * STEP + CELL / 2, PAD_Y + d * STEP + CELL / 2


def build_path(ncols):
    """Caminho em zigue-zague: desce uma coluna, faz uma curva, sobe a próxima.
    Devolve (string do path, comprimento total, função distância-até-célula)."""
    r = STEP / 2
    top = cell_center(0, 0)[1]
    bot = cell_center(0, ROWS - 1)[1]
    col_len = bot - top
    arc_len = math.pi * r
    lead = 70

    x0, _ = cell_center(0, 0)
    d = [f"M {x0 - lead:.1f} {top:.1f}", f"L {x0:.1f} {top:.1f}"]
    # a primeira coluna entra horizontalmente pelo topo, então faz uma curva para baixo
    dist = {}
    s = lead
    for w in range(ncols):
        x, _ = cell_center(w, 0)
        down = w % 2 == 0
        for row in range(ROWS):
            off = (row * STEP) if down else ((ROWS - 1 - row) * STEP)
            dist[(w, row)] = s + off
        end_y = bot if down else top
        d.append(f"L {x:.1f} {end_y:.1f}")
        s += col_len
        if w < ncols - 1:
            sweep = 0 if down else 1
            d.append(f"A {r:.1f} {r:.1f} 0 0 {sweep} {x + STEP:.1f} {end_y:.1f}")
            s += arc_len
    last_x, _ = cell_center(ncols - 1, 0)
    end_y = bot if (ncols - 1) % 2 == 0 else top
    d.append(f"L {last_x + lead:.1f} {end_y:.1f}")
    s += lead
    return " ".join(d), s, dist


def dragon_svg(grid, theme_name):
    t = THEMES[theme_name]
    ncols = len(grid)
    width = PAD_X * 2 + ncols * STEP - (STEP - CELL)
    height = PAD_Y * 2 + ROWS * STEP - (STEP - CELL)
    path, total, dist = build_path(ncols)

    speed = 170.0  # px por segundo
    dur = total / speed
    fire_ahead = 18  # o fogo alcança a célula antes da cabeça

    out = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" '
        f'width="{width:.0f}" height="{height:.0f}">'
    )
    out.append(
        "<defs>"
        '<linearGradient id="fire" x1="0" x2="1">'
        '<stop offset="0" stop-color="#fff59d"/>'
        '<stop offset="0.35" stop-color="#ffb300"/>'
        '<stop offset="0.75" stop-color="#ff5722" stop-opacity="0.8"/>'
        '<stop offset="1" stop-color="#d84315" stop-opacity="0"/>'
        "</linearGradient>"
        '<filter id="glow" x="-50%" y="-50%" width="200%" height="200%">'
        '<feGaussianBlur stdDeviation="1.6" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>'
        "</filter>"
        "</defs>"
    )

    # Células
    for w, col in enumerate(grid):
        for row, lvl in enumerate(col):
            if lvl is None:
                continue
            x = PAD_X + w * STEP
            y = PAD_Y + row * STEP
            color = t["levels"][lvl]
            rect = f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" fill="{color}"'
            if lvl == 0:
                out.append(rect + "/>")
                continue
            f = max(0.0, (dist[(w, row)] - fire_ahead) / total)
            a = 0.35 / dur  # passo de ~0,35 s
            keys = [0, f, f + a, f + 2 * a, f + 4 * a, f + 8 * a, 0.985, 1]
            keys = [min(k, 0.98 if i < 6 else k) for i, k in enumerate(keys)]
            for i in range(1, len(keys)):
                if keys[i] <= keys[i - 1]:
                    keys[i] = keys[i - 1] + 0.0001
            vals = [color, color, "#fff59d", "#ff9800", "#d84315", t["ash"], t["ash"], color]
            kt = ";".join(f"{k:.5f}" for k in keys)
            out.append(
                rect
                + f'><animate attributeName="fill" values="{";".join(vals)}" keyTimes="{kt}" '
                f'dur="{dur:.2f}s" repeatCount="indefinite"/></rect>'
            )

    def motion(delay):
        begin = -((dur - delay) % dur)
        return (
            f'<animateMotion dur="{dur:.2f}s" begin="{begin:.3f}s" repeatCount="indefinite" '
            f'rotate="auto" path="{path}"/>'
        )

    spacing_px = 6.5 * SCALE
    nseg = 11
    seg_delay = spacing_px / speed

    # Cauda e corpo (desenhados do fim para o começo, para a cabeça ficar por cima)
    for k in range(nseg, 0, -1):
        rad = 5.2 - (k / nseg) * 3.6
        delay = k * seg_delay
        g = [f'<g transform="scale({SCALE})">']
        if k == nseg:
            # ponta da cauda em forma de seta
            g.append(f'<path d="M 2 0 L -7 -4.5 L -4 0 L -7 4.5 Z" fill="{t["body"]}"/>')
        g.append(f'<circle r="{rad:.2f}" fill="{t["body"]}"/>')
        g.append(f'<ellipse rx="{rad * 0.8:.2f}" ry="{rad * 0.45:.2f}" fill="{t["belly"]}" opacity="0.55"/>')
        # espinhos nas costas
        g.append(
            f'<path d="M -1.5 {-rad:.2f} L 0 {-rad - 2.6:.2f} L 1.5 {-rad:.2f} Z" fill="{t["horn"]}" opacity="0.85"/>'
        )
        if k == 3:
            # asas batendo
            wing = (
                f'<path d="M 3 0 Q -2 -18 -12 -16 Q -7 -10 -9 -6 Q -4 -6 -3 0 Z" fill="{t["wing"]}" opacity="0.92">'
                '<animateTransform attributeName="transform" type="scale" values="1 1;1 0.35;1 1" '
                'dur="0.45s" repeatCount="indefinite"/></path>'
            )
            g.append(wing)
            g.append(f'<g transform="scale(1,-1)">{wing}</g>')
        g.append(motion(delay))
        g.append("</g>")
        out.append("".join(g))

    # Cabeça + fogo
    head = [
        f'<g transform="scale({SCALE})">',
        # fogo
        '<g filter="url(#glow)">'
        '<path d="M 9 0 Q 20 -7 34 -5 Q 28 0 34 5 Q 20 7 9 0 Z" fill="url(#fire)">'
        '<animate attributeName="opacity" values="1;0.55;1;0.8;1" dur="0.3s" repeatCount="indefinite"/>'
        '<animateTransform attributeName="transform" type="scale" values="1 1;1.15 0.8;0.95 1.1;1 1" '
        'dur="0.4s" repeatCount="indefinite"/></path></g>',
        # chifres
        f'<path d="M -3 -4 L -10 -10 L -1 -5 Z" fill="{t["horn"]}"/>',
        f'<path d="M -3 4 L -10 10 L -1 5 Z" fill="{t["horn"]}"/>',
        # crânio e focinho
        f'<ellipse cx="0" cy="0" rx="7" ry="5.6" fill="{t["body"]}"/>',
        f'<path d="M 3 -3.6 Q 11 -2.5 11 0 Q 11 2.5 3 3.6 Z" fill="{t["body"]}"/>',
        f'<ellipse cx="6" cy="0" rx="4" ry="2" fill="{t["belly"]}" opacity="0.6"/>',
        # narinas
        '<circle cx="9.6" cy="-1.1" r="0.6" fill="#3e2723"/>',
        '<circle cx="9.6" cy="1.1" r="0.6" fill="#3e2723"/>',
        # olhos
        '<circle cx="1.5" cy="-3" r="1.7" fill="#ffeb3b"/>',
        '<circle cx="1.5" cy="3" r="1.7" fill="#ffeb3b"/>',
        '<ellipse cx="1.9" cy="-3" rx="0.45" ry="1.2" fill="#000"/>',
        '<ellipse cx="1.9" cy="3" rx="0.45" ry="1.2" fill="#000"/>',
        motion(0),
        "</g>",
    ]
    out.append("".join(head))
    out.append("</svg>")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default=os.environ.get("GITHUB_USER"))
    ap.add_argument("--out", default="dist")
    ap.add_argument("--fake", action="store_true")
    args = ap.parse_args()

    grid = fake_grid() if args.fake else fetch_grid(args.user, os.environ["GITHUB_TOKEN"])
    os.makedirs(args.out, exist_ok=True)
    for name, fname in (("light", "dragon.svg"), ("dark", "dragon-dark.svg")):
        with open(os.path.join(args.out, fname), "w", encoding="utf-8") as fh:
            fh.write(dragon_svg(grid, name))
    print("ok", len(grid), "semanas")


if __name__ == "__main__":
    main()
