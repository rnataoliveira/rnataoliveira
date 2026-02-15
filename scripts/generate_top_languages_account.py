#!/usr/bin/env python3
import json
import os
import subprocess
from collections import Counter
from pathlib import Path
from urllib.request import Request, urlopen

# -------------------------
# Config (tweak if needed)
# -------------------------
GITHUB_ACTOR = os.environ.get("GITHUB_ACTOR", "")
TOKEN = os.environ.get("GITHUB_TOKEN", "")  # Provided by Actions
OUT_DIR = Path("assets")
OUT_SVG = OUT_DIR / "top-languages-by-commit.svg"
OUT_PNG = OUT_DIR / "top-languages-by-commit.png"

MAX_REPOS = int(os.environ.get("MAX_REPOS", "30"))              # most recently pushed repos
MAX_COMMITS_PER_REPO = int(os.environ.get("MAX_COMMITS", "400")) # cap per repo for speed

# extension -> language mapping (extend freely)
EXT_TO_LANG = {
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".dart": "Dart",
    ".py": "Python",
    ".rb": "Ruby",
    ".go": "Go",
    ".java": "Java",
    ".kt": "Kotlin",
    ".swift": "Swift",
    ".cs": "C#",
    ".rs": "Rust",
    ".php": "PHP",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sh": "Shell",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".sql": "SQL",
    ".md": "Markdown",
}

IGNORE_PREFIXES = (
    "node_modules/",
    "dist/",
    "build/",
    ".git/",
    ".github/",
    "coverage/",
    ".next/",
)

def run(cmd, cwd=None) -> str:
    return subprocess.check_output(cmd, text=True, cwd=cwd).strip()

def gh_get(url: str):
    if not TOKEN:
        raise RuntimeError("Missing GITHUB_TOKEN in environment.")
    req = Request(url)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    with urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def list_repos(owner: str):
    # sorted by last push, includes public/private based on token perms (profile repo action will see your repos)
    repos = []
    page = 1
    while True:
        url = f"https://api.github.com/users/{owner}/repos?per_page=100&page={page}&sort=pushed"
        data = gh_get(url)
        if not data:
            break
        repos.extend(data)
        page += 1
        if len(repos) >= MAX_REPOS:
            break

    # filter out forks/archived to reduce noise
    filtered = []
    for r in repos:
        if r.get("fork"):
            continue
        if r.get("archived"):
            continue
        filtered.append(r)
        if len(filtered) >= MAX_REPOS:
            break

    return filtered

def language_for_file(path: str):
    p = path.lower()
    if any(p.startswith(pref) for pref in IGNORE_PREFIXES):
        return None
    suffix = Path(p).suffix
    return EXT_TO_LANG.get(suffix)

def compute_language_by_commit(repo_dir: Path) -> Counter:
    counts = Counter()
    commits = run(["git", "rev-list", f"--max-count={MAX_COMMITS_PER_REPO}", "HEAD"], cwd=repo_dir)
    commit_list = [c for c in commits.splitlines() if c]

    for c in commit_list:
        changed = run(["git", "show", "--name-only", "--pretty=format:", c], cwd=repo_dir)
        files = [f.strip() for f in changed.splitlines() if f.strip()]

        langs_in_commit = set()
        for f in files:
            lang = language_for_file(f)
            if lang:
                langs_in_commit.add(lang)

        for lang in langs_in_commit:
            counts[lang] += 1

    return counts

def clone_repo(clone_url: str, target_dir: Path):
    # partial clone to reduce bandwidth (keeps trees/commit history; blobs fetched only if needed)
    # We need history, so no --depth. This is still reasonably light with blob filter.
    run(["git", "clone", "--filter=blob:none", "--no-checkout", clone_url, str(target_dir)])

def render_donut(counts: Counter):
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    total = sum(counts.values()) or 1
    top = counts.most_common(8)
    other = total - sum(v for _, v in top)

    labels = [k for k, _ in top]
    values = [v for _, v in top]
    if other > 0:
        labels.append("Other")
        values.append(other)

    import matplotlib.pyplot as plt

    # Smaller overall output than before
    fig = plt.figure(figsize=(8.2, 3.2), dpi=160)

    # Donut (right)
    ax = fig.add_subplot(1, 2, 2)
    ax.set_aspect("equal")
    wedges, _ = ax.pie(
        values,
        startangle=90,
        wedgeprops=dict(width=0.35, edgecolor="white"),
        radius=0.92,
    )
    ax.set_title("")  # keep clean

    # Legend (left)
    ax2 = fig.add_subplot(1, 2, 1)
    ax2.axis("off")
    ax2.text(0.0, 0.95, "Top Languages by Commit", fontsize=16, fontweight="bold", va="top")

    y = 0.78
    for (label, v), w in zip(list(zip(labels, values)), wedges):
        pct = (v / total) * 100
        ax2.add_patch(plt.Rectangle((0.0, y - 0.03), 0.05, 0.05, color=w.get_facecolor()))
        ax2.text(0.07, y, f"{label}  ({pct:.1f}%)", fontsize=11, va="center")
        y -= 0.09

    plt.tight_layout()
    fig.savefig(OUT_SVG, format="svg", bbox_inches="tight")
    fig.savefig(OUT_PNG, format="png", bbox_inches="tight")
    plt.close(fig)

def main():
    owner = GITHUB_ACTOR
    if not owner:
        raise RuntimeError("Missing GITHUB_ACTOR (Actions sets this automatically).")

    repos = list_repos(owner)
    if not repos:
        raise RuntimeError(f"No repos found for user: {owner}")

    work = Path(".work_repos")
    if work.exists():
        run(["rm", "-rf", str(work)])
    work.mkdir(parents=True, exist_ok=True)

    total_counts = Counter()

    for r in repos:
        name = r["name"]
        clone_url = r["clone_url"]  # uses HTTPS; token auth will work via extraheader set in workflow
        repo_dir = work / name
        print(f"Cloning {name}...")
        clone_repo(clone_url, repo_dir)

        print(f"Counting commits/languages in {name}...")
        total_counts.update(compute_language_by_commit(repo_dir))

    render_donut(total_counts)

    print("Generated chart files:")
    print(f"- {OUT_SVG}")
    print(f"- {OUT_PNG}")
    print("Top 10:")
    for k, v in total_counts.most_common(10):
        print(f"  {k}: {v}")

if __name__ == "__main__":
    main()
