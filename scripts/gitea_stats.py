#!/usr/bin/env python3
"""Fetch stats from a self-hosted Gitea instance and render an SVG card.

Reads configuration from environment variables:
  GITEA_URL      Base URL of the Gitea instance (e.g. https://gitea.example.com)
  GITEA_TOKEN    API token with read access to the user's repositories

Writes the resulting card to assets/gitea-stats.svg
"""
import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone

GITEA_URL = os.environ.get("GITEA_URL", "").rstrip("/")
GITEA_TOKEN = os.environ.get("GITEA_TOKEN", "")
OUT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "gitea-stats.svg")


def api(path):
    url = f"{GITEA_URL}/api/v1{path}"
    req = urllib.request.Request(url, headers={"Authorization": f"token {GITEA_TOKEN}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_repos():
    repos = []
    page = 1
    while True:
        batch = api(f"/user/repos?limit=50&page={page}")
        if not isinstance(batch, list) or not batch:
            break
        repos.extend(batch)
        if len(batch) < 50:
            break
        page += 1
    return repos


def fetch_heatmap(username):
    try:
        data = api(f"/users/{username}/heatmap")
    except urllib.error.URLError:
        return 0
    total = 0
    year = datetime.now(timezone.utc).year
    for entry in data or []:
        ts = entry.get("timestamp")
        if ts is None:
            continue
        try:
            dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
        except (ValueError, OSError):
            continue
        if dt.year == year:
            total += int(entry.get("contributions", 0))
    return total


def render(repos, contributions, username):
    repo_count = len(repos)
    stars = sum(r.get("stars_count", 0) for r in repos)
    forks = sum(r.get("forks_count", 0) for r in repos)
    private = sum(1 for r in repos if r.get("private"))
    public = repo_count - private

    width = 420
    height = 170
    lines = [
        ("Repositories", str(repo_count)),
        ("Stars", str(stars)),
        ("Forks", str(forks)),
        ("Private / Public", f"{private} / {public}"),
        ("Contributions (this year)", str(contributions)),
    ]

    rows = ""
    y = 62
    for label, value in lines:
        rows += (
            f'<text x="24" y="{y}" fill="#94a3b8" font-size="13" font-family="ui-monospace, SFMono-Regular, Menlo, monospace">{label}</text>'
            f'<text x="{width-24}" y="{y}" fill="#a5b4fc" font-size="13" font-weight="600" text-anchor="end" font-family="ui-monospace, SFMono-Regular, Menlo, monospace">{value}</text>'
        )
        y += 20

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Gitea stats for {username}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0b1220"/>
      <stop offset="100%" stop-color="#1a2238"/>
    </linearGradient>
  </defs>
  <rect width="{width}" height="{height}" rx="12" fill="url(#bg)" stroke="#334155" stroke-width="1"/>
  <text x="24" y="34" fill="#e2e8f0" font-size="15" font-weight="700" font-family="ui-sans-serif, system-ui, sans-serif">Gitea · Private Work</text>
  <text x="{width-24}" y="34" fill="#64748b" font-size="11" text-anchor="end" font-family="ui-monospace, SFMono-Regular, Menlo, monospace">@{username}</text>
  <line x1="24" y1="46" x2="{width-24}" y2="46" stroke="#334155" stroke-width="1"/>
  {rows}
</svg>
'''


def main():
    if not GITEA_URL or not GITEA_TOKEN:
        raise SystemExit("GITEA_URL and GITEA_TOKEN must be set")
    user = api("/user")
    username = user.get("login") or user.get("username") or "user"
    repos = fetch_repos()
    contributions = fetch_heatmap(username)
    svg = render(repos, contributions, username)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Wrote {OUT_PATH}: {len(repos)} repos, {contributions} contributions")


if __name__ == "__main__":
    main()
