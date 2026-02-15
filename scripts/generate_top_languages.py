#!/usr/bin/env python3
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

# --- Config ---
OUT_DIR = Path("assets")
OUT_SVG = OUT_DIR / "top-languages-by-commit.svg"
OUT_PNG = OUT_DIR / "top-languages-by-commit.png"

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

def render_donut(counts: Counter):
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    total = sum(counts.values()) or 1
    top = counts.most_common(8)  # show top 8
    other = total - sum(v for _, v in top)
    labels = [k for k, _ in top]
    values = [v for _, v in top]
    if other > 0:
        labels.append("Other")
        values.append(other)

    # Matplotlib is available on GitHub Actions ubuntu runners
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(10, 4), dpi=150)
    ax = fig.add_subplot(1, 2, 2)
    ax.set_aspect("equal")

    wedges, _ = ax.pie(
        values,
        startangle=90,
        wedgeprops=dict(width=0.38, edgecolor="white"),
    )

    # Legend panel on the left
    ax2 = fig.add_subplot(1, 2, 1)
    ax2.axis("off")

    title = "Top Languages by Commit"
    ax2.text(0.0, 0.95, title, fontsize=18, fontweight="bold", va="top")

    y = 0.78
    for (label, v), w in zip(list(zip(labels, values)), wedges):
        pct = (v / total) * 100
        ax2.add_patch(plt.Rectangle((0.0, y - 0.03), 0.05, 0.05, color=w.get_facecolor()))
        ax2.text(0.07, y, f"{label}  ({pct:.1f}%)", fontsize=12, va="center")
        y -= 0.09

    plt.tight_layout()
    fig.savefig(OUT_SVG, format="svg", bbox_inches="tight")
    fig.savefig(OUT_PNG, format="png", bbox_inches="tight")
    plt.close(fig)

def main():
    commits = get_commits(MAX_COMMITS)
    counts = compute_language_by_commit(commits)
    render_donut(counts)

    print(f"Generated: {OUT_SVG} and {OUT_PNG}")
    print("Top 10:")
    for k, v in counts.most_common(10):
        print(f"  {k}: {v}")

if __name__ == "__main__":
    main()
