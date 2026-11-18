#!/usr/bin/env python3
"""Gera um SVG animado de um carro fazendo drift no gráfico de contribuições do GitHub, soltando fumaça e deixando marcas de pneu.

Uso:
    GITHUB_TOKEN=... python drift.py --user GregoryKz --out dist
    python drift.py --fake --out dist      # dados aleatórios para teste
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
        "car": "#d32f2f",
        "roof": "#b71c1c",
        "wing": "#212121",
        "smoke": "#6e7781",
        "mark": "#57606a",
    },
    "dark": {
        "levels": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"],
        "ash": "#30363d",
        "car": "#ff5252",
        "roof": "#d32f2f",
        "wing": "#e0e0e0",
        "smoke": "#c9d1d9",
        "mark": "#8b949e",
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


def drift_svg(grid, theme_name):
    t = THEMES[theme_name]
    ncols = len(grid)
    width = PAD_X * 2 + ncols * STEP - (STEP - CELL)
    height = PAD_Y * 2 + ROWS * STEP - (STEP - CELL)
    path, total, dist = build_path(ncols)

    speed = 150.0  # px por segundo
    dur = total / speed
    mark_ahead = 2  # a marca de pneu aparece quando o carro passa

    out = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" '
        f'width="{width:.0f}" height="{height:.0f}">'
    )
    out.append(
        '<defs><filter id="blur" x="-50%" y="-50%" width="200%" height="200%">'
        '<feGaussianBlur stdDeviation="1.3"/></filter></defs>'
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
            f = max(0.0, (dist[(w, row)] - mark_ahead) / total)
            a = 0.35 / dur  # passo de ~0,35 s
            keys = [0, f, f + a, f + 2 * a, f + 4 * a, f + 8 * a, 0.985, 1]
            keys = [min(k, 0.98 if i < 6 else k) for i, k in enumerate(keys)]
            for i in range(1, len(keys)):
                if keys[i] <= keys[i - 1]:
                    keys[i] = keys[i - 1] + 0.0001
            vals = [color, color, t["mark"], t["mark"], t["ash"], t["ash"], t["ash"], color]
            kt = ";".join(f"{k:.5f}" for k in keys)
            out.append(
                rect
                + f'><animate attributeName="fill" values="{";".join(vals)}" keyTimes="{kt}" '
                f'dur="{dur:.2f}s" repeatCount="indefinite"/></rect>'
            )

    def motion(delay, rotate="auto"):
        begin = -((dur - delay) % dur)
        return (
            f'<animateMotion dur="{dur:.2f}s" begin="{begin:.3f}s" repeatCount="indefinite" '
            f'rotate="{rotate}" path="{path}"/>'
        )

    # Fumaça: nuvens que seguem o carro, crescendo e sumindo
    npuff = 14
    for k in range(npuff, 0, -1):
        delay = 0.05 + k * 0.045
        base_r = 3 + k * 0.75
        op = max(0.0, 0.55 - k * 0.035)
        side = 4 if k % 2 else -4
        out.append(
            f'<g><g transform="translate(0,{side})">'
            f'<circle r="{base_r:.1f}" fill="{t["smoke"]}" filter="url(#blur)" opacity="{op:.2f}">'
            f'<animate attributeName="r" values="{base_r:.1f};{base_r * 1.35:.1f};{base_r:.1f}" '
            f'dur="{0.5 + (k % 3) * 0.15:.2f}s" repeatCount="indefinite"/>'
            "</circle></g>"
            + motion(delay)
            + "</g>"
        )

    # Carro visto de cima, apontando para +x, com ângulo de drift oscilando
    car = (
        "<g>"
        "<g>"
        '<animateTransform attributeName="transform" type="rotate" '
        'values="-28;-42;-22;-36;-28" dur="1.3s" repeatCount="indefinite"/>'
        f'<g transform="scale({SCALE})">'
        # rodas
        '<rect x="-9" y="-8" width="6" height="3" rx="1" fill="#111"/>'
        '<rect x="-9" y="5" width="6" height="3" rx="1" fill="#111"/>'
        '<rect x="5" y="-8" width="6" height="3" rx="1" fill="#111"/>'
        '<rect x="5" y="5" width="6" height="3" rx="1" fill="#111"/>'
        # carroceria
        f'<rect x="-12" y="-6.5" width="25" height="13" rx="4" fill="{t["car"]}"/>'
        # faixa
        '<rect x="-12" y="-1.2" width="25" height="2.4" fill="#ffffff" opacity="0.85"/>'
        # para-brisa e teto
        '<path d="M 3 -5 L 7 -4 L 7 4 L 3 5 Z" fill="#1c2833"/>'
        f'<rect x="-5" y="-4.5" width="8" height="9" rx="1.5" fill="{t["roof"]}"/>'
        '<path d="M -5 -4 L -8 -3.5 L -8 3.5 L -5 4 Z" fill="#1c2833"/>'
        # faróis e lanternas
        '<rect x="11.5" y="-5" width="1.6" height="2.6" rx="0.6" fill="#fff59d"/>'
        '<rect x="11.5" y="2.4" width="1.6" height="2.6" rx="0.6" fill="#fff59d"/>'
        '<rect x="-12.4" y="-5" width="1.4" height="2.4" fill="#ff1744"/>'
        '<rect x="-12.4" y="2.6" width="1.4" height="2.4" fill="#ff1744"/>'
        # aerofólio
        f'<rect x="-13.5" y="-7" width="2" height="14" rx="0.8" fill="{t["wing"]}"/>'
        "</g></g>"
        + motion(0)
        + "</g>"
    )
    out.append(car)
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
    for name, fname in (("light", "drift.svg"), ("dark", "drift-dark.svg")):
        with open(os.path.join(args.out, fname), "w", encoding="utf-8") as fh:
            fh.write(drift_svg(grid, name))
    print("ok", len(grid), "semanas")


if __name__ == "__main__":
    main()
