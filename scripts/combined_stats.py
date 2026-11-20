#!/usr/bin/env python3
"""Generate a single heatmap combining GitHub and Gitea contributions.

Writes assets/combined-activity.svg

Env:
  GITHUB_TOKEN   (auto-provided in GitHub Actions) for the GraphQL API
  GITEA_URL, GITEA_TOKEN  for the self-hosted Gitea instance
"""
import json
import os
import urllib.request
from datetime import date, datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(ROOT, "assets", "combined-activity.svg")

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITEA_URL = os.environ.get("GITEA_URL", "").rstrip("/")
GITEA_TOKEN = os.environ.get("GITEA_TOKEN", "")


def github_contributions():
    """Return dict date->count from GitHub GraphQL contribution calendar."""
    if not GITHUB_TOKEN:
        return {}
    query = {
        "query": """query {
          viewer {
            login
            contributionsCollection {
              contributionCalendar {
                totalContributions
                weeks {
                  contributionDays { date contributionCount }
                }
              }
            }
          }
        }"""
    }
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps(query).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "combined-stats",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    out = {}
    try:
        weeks = data["data"]["viewer"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    except (KeyError, TypeError):
        return out
    for w in weeks:
        for d in w.get("contributionDays", []):
            out[d["date"]] = out.get(d["date"], 0) + int(d.get("contributionCount", 0))
    return out


def gitea_contributions():
    if not GITEA_URL or not GITEA_TOKEN:
        return {}
    # Resolve username first
    with urllib.request.urlopen(
        urllib.request.Request(f"{GITEA_URL}/api/v1/user", headers={"Authorization": f"token {GITEA_TOKEN}"}),
        timeout=30,
    ) as resp:
        user = json.loads(resp.read().decode("utf-8"))
    username = user.get("login") or user.get("username")
    with urllib.request.urlopen(
        urllib.request.Request(f"{GITEA_URL}/api/v1/users/{username}/heatmap", headers={"Authorization": f"token {GITEA_TOKEN}"}),
        timeout=30,
    ) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    out = {}
    for entry in data or []:
        ts = entry.get("timestamp")
        if ts is None:
            continue
        d = datetime.fromtimestamp(int(ts), tz=timezone.utc).date().isoformat()
        out[d] = out.get(d, 0) + int(entry.get("contributions", 0))
    return out


def render(merged, github_total, gitea_total):
    # Build a 52-week x 7-day grid ending today
    today = date.today()
    # align to Sunday-based weeks like GitHub: start 364 days ago aligned to Sunday
    start = today - timedelta(days=364)
    # move start back to Sunday
    start = start - timedelta(days=(start.weekday() + 1) % 7)

    days = []
    cur = start
    while cur <= today:
        days.append(cur)
        cur += timedelta(days=1)

    # levels
    def level(n):
        if n <= 0:
            return 0
        if n < 3:
            return 1
        if n < 6:
            return 2
        if n < 10:
            return 3
        return 4

    colors = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]

    cell = 11
    gap = 3
    step = cell + gap
    weeks = (len(days) + 6) // 7
    width = weeks * step + 40
    height = 7 * step + 50

    rects = ""
    for i, d in enumerate(days):
        week = i // 7
        dow = i % 7
        x = 30 + week * step
        y = 30 + dow * step
        n = merged.get(d.isoformat(), 0)
        rects += f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{colors[level(n)]}"/>'

    total = sum(merged.values())
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Combined activity">
  <rect width="{width}" height="{height}" rx="12" fill="#0b1220" stroke="#334155" stroke-width="1"/>
  <text x="16" y="20" fill="#e2e8f0" font-size="13" font-weight="700" font-family="ui-sans-serif, system-ui, sans-serif">Combined Activity · GitHub + Gitea</text>
  <text x="{width-16}" y="20" fill="#64748b" font-size="11" text-anchor="end" font-family="ui-monospace, Menlo, monospace">{total} contributions</text>
  {rects}
  <text x="16" y="{height-8}" fill="#64748b" font-size="10" font-family="ui-monospace, Menlo, monospace">GitHub: {github_total} · Gitea: {gitea_total}</text>
</svg>
'''


def main():
    gh = github_contributions()
    gt = gitea_contributions()
    merged = dict(gh)
    for k, v in gt.items():
        merged[k] = merged.get(k, 0) + v
    svg = render(merged, sum(gh.values()), sum(gt.values()))
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Wrote {OUT_PATH}: {sum(merged.values())} total contributions")


if __name__ == "__main__":
    main()
