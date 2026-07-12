#!/usr/bin/env python3
"""
Generates dark_mode.svg and light_mode.svg — a neofetch-style GitHub
profile card — using live data from the GitHub API.

Requires environment variables:
  GH_TOKEN     - a GitHub token (a PAT is required for GraphQL commit/LOC data)
  GH_USERNAME  - your GitHub username
"""

import os
import datetime
import subprocess
import tempfile
import requests

USERNAME = os.environ["GH_USERNAME"]
TOKEN = os.environ["GH_TOKEN"]
HEADERS = {"Authorization": f"token {TOKEN}"}

DISPLAY_NAME = "emperor@arch"

SYSTEM_INFO = {
    "OS": "Windows 11, Arch Linux",
    "Uptime": "18 years, 5months, 28days",
    "Kernel": "Web Developer",
    "IDE": "VSCode 1.128",
    "Languages.Programming": "C++, Python, JavaScript",
    "Languages.Human": "English, Nepali",
}

CONTACT_INFO = {
    "Email": "samrat.aryal@proton.me",
    "Portfolio": "samrat-aryal.com.np",
    "LinkedIn": "samrataryal",
    "Discord": "empeeror_",
}
# ------------------------------------


def gh_get(url):
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    return r.json()


GRAPHQL_URL = "https://api.github.com/graphql"


def gh_graphql(query, variables=None):
    r = requests.post(
        GRAPHQL_URL,
        json={"query": query, "variables": variables or {}},
        headers=HEADERS,
    )
    r.raise_for_status()
    data = r.json()
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


def get_total_commits():
    """
    Sums contributionsCollection.totalCommitContributions across every
    year the account has existed (GraphQL only returns ~1 year per call).
    """
    user_query = """
    query($login: String!) {
      user(login: $login) {
        createdAt
      }
    }
    """
    created_at = gh_graphql(user_query, {"login": USERNAME})["user"]["createdAt"]
    start_year = int(created_at[:4])
    current_year = datetime.date.today().year

    contrib_query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          totalCommitContributions
          restrictedContributionsCount
        }
      }
    }
    """

    total = 0
    for year in range(start_year, current_year + 1):
        from_date = f"{year}-01-01T00:00:00Z"
        to_date = f"{year}-12-31T23:59:59Z"
        result = gh_graphql(
            contrib_query, {"login": USERNAME, "from": from_date, "to": to_date}
        )
        cc = result["user"]["contributionsCollection"]
        total += cc["totalCommitContributions"] + cc["restrictedContributionsCount"]

    return total


def get_loc_stats(repos):
    """
    Clones each non-fork repo (shallow is not enough for accurate LOC,
    so this does a full clone) and sums `git log --numstat` additions
    and deletions authored by USERNAME.

    NOTE: this is the expensive part. For accounts with many/large repos,
    consider caching results (e.g. commit results to a data file and only
    re-scanning repos that have new commits since the last run).
    """
    additions = 0
    deletions = 0

    with tempfile.TemporaryDirectory() as tmp:
        for repo in repos:
            if repo.get("fork"):
                continue
            name = repo["name"]
            clone_url = repo["clone_url"]
            dest = os.path.join(tmp, name)
            try:
                subprocess.run(
                    ["git", "clone", "--quiet", clone_url, dest],
                    check=True,
                    timeout=120,
                )
                result = subprocess.run(
                    [
                        "git", "-C", dest, "log",
                        f"--author={USERNAME}",
                        "--numstat", "--pretty=tformat:",
                    ],
                    capture_output=True, text=True, check=True,
                )
                for line in result.stdout.splitlines():
                    parts = line.split("\t")
                    if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
                        additions += int(parts[0])
                        deletions += int(parts[1])
            except Exception as e:
                print(f"Skipping {name}: {e}")
                continue

    return additions, deletions


def get_stats(skip_loc=False):
    user = gh_get(f"https://api.github.com/users/{USERNAME}")
    repos = gh_get(f"https://api.github.com/users/{USERNAME}/repos?per_page=100&type=owner")

    total_stars = sum(r["stargazers_count"] for r in repos)
    repo_count = user["public_repos"]
    followers = user["followers"]

    commits = get_total_commits()

    if skip_loc:
        loc = "N/A"
    else:
        additions, deletions = get_loc_stats(repos)
        loc = f"{additions + deletions:,}"

    return {
        "repos": repo_count,
        "stars": total_stars,
        "followers": followers,
        "commits": f"{commits:,}",
        "loc": loc,
    }


def build_svg(stats, dark=True):
    bg = "#0d1117" if dark else "#ffffff"
    fg = "#c9d1d9" if dark else "#24292f"
    accent = "#58A6FF" if dark else "#0969da"

    lines = []
    lines.append(DISPLAY_NAME)
    lines.append("-" * len(DISPLAY_NAME))
    prev_key = None
    for k, v in SYSTEM_INFO.items():
        if k.startswith("Languages.") and prev_key is not None and not prev_key.startswith("Languages."):
            lines.append("")
        dots = "." * max(2, 24 - len(k))
        lines.append(f"{k}: {dots} {v}")
        prev_key = k

    lines.append("")
    lines.append("- Contact " + "-" * 41)
    for k, v in CONTACT_INFO.items():
        dots = "." * max(2, 30 - len(k))
        lines.append(f"{k}: {dots} {v}")

    lines.append("")
    lines.append("- GitHub Stats " + "-" * 36)
    lines.append(f"Repos: ....... {stats['repos']}  |  Stars: ............... {stats['stars']}")
    lines.append(f"Commits: {stats['commits']}")
    lines.append(f"Lines Of Code : {stats['loc']}")

    line_height = 20
    width = 640
    height = 40 + line_height * len(lines)

    svg_lines = []
    for i, line in enumerate(lines):
        y = 40 + i * line_height
        color = accent if i < 2 else fg
        svg_lines.append(
            f'<text x="20" y="{y}" fill="{color}" xml:space="preserve">{escape(line)}</text>'
        )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height - 15}" viewBox="0 0 {width} {height - 15}">
  <rect width="100%" height="100%" fill="{bg}" rx="8"/>
  <style>
    text {{ font-family: 'Fira Code', 'Consolas', monospace; font-size: 14px; }}
  </style>
  {''.join(svg_lines)}
</svg>"""
    return svg


def escape(s):
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def main():
    # Set SKIP_LOC=true in the workflow env if clone-based LOC counting
    # gets too slow/expensive for your account (many/huge repos).
    skip_loc = os.environ.get("SKIP_LOC", "false").lower() == "true"
    stats = get_stats(skip_loc=skip_loc)
    with open("dark_mode.svg", "w") as f:
        f.write(build_svg(stats, dark=True))
    with open("light_mode.svg", "w") as f:
        f.write(build_svg(stats, dark=False))
    print("Wrote dark_mode.svg and light_mode.svg")


if __name__ == "__main__":
    main()