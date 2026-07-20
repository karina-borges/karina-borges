#!/usr/bin/env python3
"""Generate languages.svg — aggregated language bytes across repositories
(including private ones) via the GitHub GraphQL API, rendered as a static SVG
committed into this repo. No third-party services involved.

Usage:
  GH_TOKEN=<pat with repo scope> python3 scripts/generate_languages.py
  python3 scripts/generate_languages.py --mock   # render with sample data
"""
import json
import os
import sys
import urllib.request
from xml.sax.saxutils import escape

USER = "karina-borges"
OUTPUT = "languages.svg"
LIMIT = 8
IGNORED = {"HTML", "CSS", "SCSS", "Dockerfile", "Makefile", "Procfile"}
# OWNER only = just your own repos. COLLABORATOR / ORGANIZATION_MEMBER also
# count client work — aggregate bytes only, repo names are never shown.
AFFILIATIONS = "[OWNER, COLLABORATOR, ORGANIZATION_MEMBER]"

FALLBACK_COLORS = ["#3178c6", "#3572A5", "#f1e05a", "#89e051",
                   "#b07219", "#e34c26", "#701516", "#438eff"]

QUERY = """
query($login: String!, $after: String) {
  user(login: $login) {
    repositories(first: 100, after: $after, affiliations: AFF, isFork: false) {
      pageInfo { hasNextPage endCursor }
      nodes {
        languages(first: 20, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
""".replace("AFF", AFFILIATIONS)


def gql(variables, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}",
                 "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        payload = json.load(r)
    if "errors" in payload:
        sys.exit(f"GraphQL errors: {json.dumps(payload['errors'], indent=2)}")
    return payload["data"]


def collect(token):
    sizes, colors, after = {}, {}, None
    while True:
        repos = gql({"login": USER, "after": after}, token)["user"]["repositories"]
        for node in repos["nodes"]:
            for edge in ((node.get("languages") or {}).get("edges") or []):
                name = edge["node"]["name"]
                if name in IGNORED:
                    continue
                sizes[name] = sizes.get(name, 0) + edge["size"]
                colors.setdefault(name, edge["node"]["color"])
        if not repos["pageInfo"]["hasNextPage"]:
            break
        after = repos["pageInfo"]["endCursor"]
    return sizes, colors


def render(sizes, colors):
    top = sorted(sizes.items(), key=lambda kv: kv[1], reverse=True)[:LIMIT]
    total = sum(v for _, v in top) or 1
    items = [{"name": n, "pct": 100.0 * s / total,
              "color": colors.get(n) or FALLBACK_COLORS[i % len(FALLBACK_COLORS)]}
             for i, (n, s) in enumerate(top)]

    W, X, BARW = 480, 15, 450
    bar_y, bar_h = 38, 12
    leg_y, row_h = 72, 22
    H = leg_y + ((len(items) + 1) // 2) * row_h + 4

    seg, x = [], float(X)
    for it in items:
        w = BARW * it["pct"] / 100.0
        seg.append(f'<rect x="{x:.2f}" y="{bar_y}" width="{w:.2f}" '
                   f'height="{bar_h}" fill="{it["color"]}"/>')
        x += w

    legend = []
    for i, it in enumerate(items):
        lx = X + (i % 2) * 230
        ly = leg_y + (i // 2) * row_h
        legend.append(
            f'<circle cx="{lx + 5}" cy="{ly - 4}" r="5" fill="{it["color"]}"/>'
            f'<text x="{lx + 16}" y="{ly}">{escape(it["name"])} '
            f'<tspan class="pct">{it["pct"]:.1f}%</tspan></text>')

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<style>
text {{ font: 400 12px "Segoe UI", Ubuntu, "Helvetica Neue", sans-serif; fill: #24292f; }}
.title {{ font-size: 14px; font-weight: 600; fill: #0969da; }}
.pct {{ fill: #57606a; }}
@media (prefers-color-scheme: dark) {{
  text {{ fill: #c9d1d9; }}
  .title {{ fill: #58a6ff; }}
  .pct {{ fill: #8b949e; }}
}}
</style>
<text class="title" x="{X}" y="22">Most used languages <tspan class="pct" font-weight="400">— all repos, incl. private</tspan></text>
<clipPath id="bar"><rect x="{X}" y="{bar_y}" width="{BARW}" height="{bar_h}" rx="6"/></clipPath>
<g clip-path="url(#bar)">{''.join(seg)}</g>
{''.join(legend)}
</svg>
'''


def main():
    if "--mock" in sys.argv:
        sizes = {"TypeScript": 4_500_000, "Python": 2_600_000,
                 "JavaScript": 1_400_000, "Shell": 520_000, "Java": 400_000,
                 "MDX": 260_000, "PLpgSQL": 150_000, "Go": 120_000}
        colors = {"TypeScript": "#3178c6", "Python": "#3572A5",
                  "JavaScript": "#f1e05a", "Shell": "#89e051",
                  "Java": "#b07219", "MDX": "#fcb32c",
                  "PLpgSQL": "#336790", "Go": "#00ADD8"}
    else:
        token = os.environ.get("GH_TOKEN") or sys.exit("GH_TOKEN env var required")
        sizes, colors = collect(token)
    if not sizes:
        sys.exit("No language data found")
    svg = render(sizes, colors)
    with open(OUTPUT, "w") as f:
        f.write(svg)
    top = sorted(sizes.items(), key=lambda kv: kv[1], reverse=True)[:LIMIT]
    total = sum(v for _, v in top) or 1
    print(f"wrote {OUTPUT}: " +
          ", ".join(f"{n} {100.0 * s / total:.1f}%" for n, s in top))


if __name__ == "__main__":
    main()
