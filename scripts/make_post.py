#!/usr/bin/env python3
"""Generate the NeuralClaw + Claude explainer post (SVG -> PNG)."""

import cairosvg

W, H = 1080, 1350
GREEN = "#00ff88"
GREEN_DIM = "#3ddc97"
BG = "#08090a"
PANEL = "#0e130f"
PANEL_BORDER = "#1d2a1f"
WHITE = "#eaf2ea"
GRAY = "#8a988a"
MONO = "DejaVu Sans Mono"
SANS = "DejaVu Sans"


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, s, size, fill=WHITE, font=SANS, weight="normal", anchor="start", spacing=0, opacity=1):
    ls = f' letter-spacing="{spacing}"' if spacing else ""
    op = f' opacity="{opacity}"' if opacity != 1 else ""
    return (f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"{ls}{op}>'
            f'{esc(s)}</text>')


parts = []
parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')

# Background + subtle grid
parts.append(f'<rect width="{W}" height="{H}" fill="{BG}"/>')
grid = []
for gx in range(0, W + 1, 45):
    grid.append(f'<line x1="{gx}" y1="0" x2="{gx}" y2="{H}" stroke="{GREEN}" stroke-width="1" opacity="0.035"/>')
for gy in range(0, H + 1, 45):
    grid.append(f'<line x1="0" y1="{gy}" x2="{W}" y2="{gy}" stroke="{GREEN}" stroke-width="1" opacity="0.035"/>')
parts.extend(grid)
# top + bottom glow accents
parts.append(f'<rect x="0" y="0" width="{W}" height="6" fill="{GREEN}"/>')
parts.append(f'<rect x="0" y="{H-6}" width="{W}" height="6" fill="{GREEN}" opacity="0.6"/>')

# ---- Header: brain mark ----
cx, cy = 110, 150
# glow underlays
parts.append(f'<circle cx="{cx}" cy="{cy}" r="50" fill="none" stroke="{GREEN}" stroke-width="14" opacity="0.10"/>')
parts.append(f'<circle cx="{cx}" cy="{cy}" r="46" fill="none" stroke="{GREEN}" stroke-width="3"/>')
# circuit nodes inside
nodes = [(-22, -10), (0, -24), (22, -8), (-12, 16), (16, 18), (0, 2)]
node_pts = [(cx + dx, cy + dy) for dx, dy in nodes]
edges = [(0,1),(1,2),(0,5),(2,5),(3,5),(4,5),(3,0),(4,2)]
for a, b in edges:
    parts.append(f'<line x1="{node_pts[a][0]}" y1="{node_pts[a][1]}" x2="{node_pts[b][0]}" y2="{node_pts[b][1]}" stroke="{GREEN_DIM}" stroke-width="2" opacity="0.85"/>')
for px, py in node_pts:
    parts.append(f'<circle cx="{px}" cy="{py}" r="5" fill="{GREEN}"/>')

# Title + tagline
parts.append(text(178, 138, "NeuralClaw", 62, WHITE, SANS, "bold"))
parts.append(text(180, 182, "memoria activa local para Claude", 26, GREEN, MONO))

# divider
parts.append(f'<line x1="60" y1="225" x2="{W-60}" y2="225" stroke="{PANEL_BORDER}" stroke-width="2"/>')


def panel(y, h):
    parts.append(f'<rect x="50" y="{y}" width="{W-100}" height="{h}" rx="18" fill="{PANEL}" stroke="{PANEL_BORDER}" stroke-width="2"/>')
    parts.append(f'<rect x="50" y="{y}" width="6" height="{h}" rx="3" fill="{GREEN}"/>')


def kicker(x, y, s):
    parts.append(text(x, y, s, 24, GREEN, MONO, "bold", spacing=2))


def bullet(x, y, head, body):
    # diamond marker
    parts.append(f'<path d="M {x} {y-7} L {x+8} {y+1} L {x} {y+9} L {x-8} {y+1} Z" fill="{GREEN}"/>')
    parts.append(text(x + 26, y + 8, head, 27, WHITE, SANS, "bold"))
    if body:
        parts.append(text(x + 26, y + 38, body, 22, GRAY, SANS))


# ---- Section ¿QUÉ ES? ----
panel(255, 150)
kicker(86, 300, "// ¿QUÉ ES?")
parts.append(text(86, 345, "Un Context OS local que recuerda las decisiones,", 26, WHITE, SANS))
parts.append(text(86, 380, "errores y variables de tu proyecto — entre sesiones.", 26, WHITE, SANS))

# ---- Section ¿QUÉ HACE? ----
panel(440, 280)
kicker(86, 485, "// ¿QUÉ HACE?")
bullet(96, 540, "Auto-recall al iniciar sesión", "inyecta tu contexto relevante automáticamente")
bullet(96, 615, "Herramientas MCP de memoria", "Claude lee y escribe contexto sobre la marcha")
bullet(96, 690, "Snapshot del contexto activo", "una foto al instante de lo que importa ahora")

# ---- Section ¿POR QUÉ AYUDA EN CLAUDE? ----
panel(755, 280)
kicker(86, 800, "// ¿POR QUÉ AYUDA EN CLAUDE?")
bullet(96, 855, "Optimización de tokens", "solo lo relevante, rankeado y con presupuesto")
bullet(96, 930, "Contexto persistente", "sin re-explicar ni copiar y pegar nunca más")
bullet(96, 1005, "100% local-first", "tu contexto vive en tu máquina, sin nube")

# ---- Terminal command box ----
ty = 1075
parts.append(f'<rect x="50" y="{ty}" width="{W-100}" height="120" rx="14" fill="#05070a" stroke="{GREEN}" stroke-width="2" opacity="0.95"/>')
# window dots
for i, c in enumerate(["#ff5f56", "#ffbd2e", GREEN]):
    parts.append(f'<circle cx="{84 + i*26}" cy="{ty+28}" r="7" fill="{c}"/>')
parts.append(text(170, ty + 34, "bash", 18, GRAY, MONO))
parts.append(text(84, ty + 86, "$ ", 30, GREEN, MONO, "bold"))
parts.append(text(118, ty + 86, "neuralclaw cc install", 30, WHITE, MONO, "bold"))
parts.append(f'<rect x="510" y="{ty+64}" width="14" height="28" fill="{GREEN}"/>')  # cursor

# ---- Footer slogan ----
parts.append(text(W/2, 1265, "Deja de copiar contexto. Empieza a construir.", 27, GREEN, SANS, "bold", anchor="middle"))
parts.append(text(W/2, 1300, "github.com/maxsarlijagit/neuralclaw", 20, GRAY, MONO, anchor="middle"))

parts.append('</svg>')
svg = "\n".join(parts)

import os
os.makedirs("assets", exist_ok=True)
with open("assets/neuralclaw_post.svg", "w") as f:
    f.write(svg)

cairosvg.svg2png(bytestring=svg.encode("utf-8"),
                 write_to="assets/neuralclaw_post.png",
                 output_width=W*2, output_height=H*2)
print("written assets/neuralclaw_post.png", W*2, "x", H*2)
