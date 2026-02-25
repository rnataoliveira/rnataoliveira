#!/usr/bin/env python3
import math
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

# --- Config ---
OUT_DIR = Path("assets")
OUT_SVG = OUT_DIR / "top-languages-by-commit.svg"

COLORS = [
    "#3b82f6",  # blue
    "#f59e0b",  # amber
    "#10b981",  # emerald
    "#ef4444",  # red
    "#8b5cf6",  # violet
    "#ec4899",  # pink
    "#14b8a6",  # teal
    "#f97316",  # orange
    "#6b7280",  # gray (Other)
]

# Limit history to keep Actions fast. Increase if you want.
MAX_COMMITS = 2000

# Minimal extension -> language map (extend as you like)
EXT_TO_LANG = {
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".py": "Python",
    ".rb": "Ruby",
    ".go": "Go",
    ".java": "Java",
    ".kt": "Kotlin",
    ".swift": "Swift",
    ".dart": "Dart",
    ".cs": "C#",
    ".cpp": "C++",
    ".c": "C",
    ".h": "C/C++ Header",
    ".rs": "Rust",
    ".php": "PHP",
    ".scala": "Scala",
    ".sh": "Shell",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".json": "JSON",
    ".md": "Markdown",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sql": "SQL",
}

IGNORE_PREFIXES = (
    "node_modules/",
    "dist/",
    "build/",
    ".git/",
    ".github/",
    "coverage/",
)

def run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True).strip()

def get_commits(max_commits: int) -> list[str]:
    # newest -> oldest
    out = run(["git", "rev-list", f"--max-count={max_commits}", "HEAD"])
    return [c for c in out.splitlines() if c]

def files_changed_in_commit(commit: str) -> list[str]:
    # names only, no rename detection complexity
    out = run(["git", "show", "--name-only", "--pretty=format:", commit])
    files = [f.strip() for f in out.splitlines() if f.strip()]
    return files

def language_for_file(path: str) -> str | None:
    p = path.lower()
    if any(p.startswith(pref) for pref in IGNORE_PREFIXES):
        return None
    suffix = Path(p).suffix
    return EXT_TO_LANG.get(suffix)

def compute_language_by_commit(commits: list[str]) -> Counter:
    counts = Counter()
    for c in commits:
        changed = files_changed_in_commit(c)
        langs_in_commit = set()
        for f in changed:
            lang = language_for_file(f)
            if lang:
                langs_in_commit.add(lang)
        for lang in langs_in_commit:
            counts[lang] += 1
    return counts

def _polar(cx: float, cy: float, r: float, deg: float) -> tuple[float, float]:
    rad = math.radians(deg)
    return cx + r * math.cos(rad), cy + r * math.sin(rad)


def _arc_path(cx: float, cy: float, r_out: float, r_in: float, a0: float, a1: float) -> str:
    large = 1 if a1 - a0 > 180 else 0
    ox0, oy0 = _polar(cx, cy, r_out, a0)
    ox1, oy1 = _polar(cx, cy, r_out, a1)
    ix1, iy1 = _polar(cx, cy, r_in, a1)
    ix0, iy0 = _polar(cx, cy, r_in, a0)
    return (
        f"M{ox0:.3f},{oy0:.3f}"
        f"A{r_out},{r_out},0,{large},1,{ox1:.3f},{oy1:.3f}"
        f"L{ix1:.3f},{iy1:.3f}"
        f"A{r_in},{r_in},0,{large},0,{ix0:.3f},{iy0:.3f}Z"
    )


def render_svg(counts: Counter):
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    total = sum(counts.values()) or 1
    top = counts.most_common(8)
    other = total - sum(v for _, v in top)
    labels = [k for k, _ in top]
    values = [v for _, v in top]
    if other > 0:
        labels.append("Other")
        values.append(other)

    W, H = 500, 220
    CX, CY = 385, 117
    R_OUT, R_IN = 88, 55
    GAP = 1.5  # degrees gap between segments

    arc_elems: list[str] = []
    angle = -90.0
    for i, v in enumerate(values):
        frac = v / total
        sweep = frac * 360
        color = COLORS[i % len(COLORS)]
        if sweep >= 359.9:
            mid_r = (R_OUT + R_IN) / 2
            arc_elems.append(
                f'<circle cx="{CX}" cy="{CY}" r="{mid_r:.1f}" '
                f'fill="none" stroke="{color}" stroke-width="{R_OUT - R_IN}"/>'
            )
        else:
            gap = min(GAP, sweep * 0.2)
            d = _arc_path(CX, CY, R_OUT, R_IN, angle, angle + sweep - gap)
            arc_elems.append(f'<path d="{d}" fill="{color}"/>')
        angle += sweep

    legend_elems: list[str] = []
    lx, ly = 20, 45
    for i, (label, v) in enumerate(zip(labels, values)):
        pct = (v / total) * 100
        color = COLORS[i % len(COLORS)]
        legend_elems.append(
            f'<rect x="{lx}" y="{ly - 11}" width="12" height="12" rx="2" fill="{color}"/>'
            f'<text x="{lx + 17}" y="{ly}" font-size="12" class="t">{label}  {pct:.1f}%</text>'
        )
        ly += 19

    font = '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif'
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">\n'
        f'  <defs><style>\n'
        f'    .t,.ttl{{font-family:{font};}}\n'
        f'    .t{{fill:#374151;font-size:12px;}}\n'
        f'    .ttl{{fill:#111827;font-size:15px;font-weight:600;}}\n'
        f'    @media(prefers-color-scheme:dark){{\n'
        f'      .t{{fill:#d1d5db;}} .ttl{{fill:#f3f4f6;}}\n'
        f'    }}\n'
        f'  </style></defs>\n'
        f'  <text x="{lx}" y="22" class="ttl">Top Languages by Commit</text>\n'
        + "\n".join(f"  {e}" for e in arc_elems) + "\n"
        + "\n".join(f"  {e}" for e in legend_elems) + "\n"
        f"</svg>"
    )
    OUT_SVG.write_text(svg, encoding="utf-8")

def main():
    commits = get_commits(MAX_COMMITS)
    counts = compute_language_by_commit(commits)
    render_svg(counts)

    print(f"Generated: {OUT_SVG}")
    print("Top 10:")
    for k, v in counts.most_common(10):
        print(f"  {k}: {v}")

if __name__ == "__main__":
    main()
