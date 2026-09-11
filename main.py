#!/usr/bin/env python3
"""
Generates dark_mode.svg / light_mode.svg for the felippeximenes/felippeximenes
profile README, pulling live data from the GitHub API (GraphQL + REST):
followers, public repos, total stars, all-time commit count, top languages
(by bytes across owned repos), and profile fields (bio/company/location/
socials). Meant to run on a schedule via GitHub Actions (see
.github/workflows/main.yml), authenticated with a Personal Access Token
stored as the ACCESS_TOKEN repo secret.
"""

import base64
import os
import sys
from datetime import datetime, timezone

import requests

USERNAME = os.environ.get("GH_USERNAME", "felippeximenes")
TOKEN = os.environ.get("ACCESS_TOKEN")
if not TOKEN:
    sys.exit("ACCESS_TOKEN env var is required (a GitHub PAT with 'read:user' scope).")

HEADERS_GRAPHQL = {"Authorization": f"bearer {TOKEN}"}
HEADERS_REST = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json"}

W, H = 900, 580
FONT = "ui-monospace, 'Cascadia Code', 'Fira Code', 'JetBrains Mono', Menlo, Consolas, monospace"

BASE_QUERY = """
query($login: String!) {
  user(login: $login) {
    createdAt
    followers { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""

YEAR_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      restrictedContributionsCount
    }
  }
}
"""


def gql(query, variables):
    r = requests.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": variables},
        headers=HEADERS_GRAPHQL,
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]["user"]


def fetch_base():
    return gql(BASE_QUERY, {"login": USERNAME})


def fetch_total_commits(created_at_iso):
    created = datetime.fromisoformat(created_at_iso.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    total = 0
    year = created.year
    while year <= now.year:
        start = max(created, datetime(year, 1, 1, tzinfo=timezone.utc))
        end = min(now, datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc))
        data = gql(YEAR_QUERY, {"login": USERNAME, "from": start.isoformat(), "to": end.isoformat()})
        cc = data["contributionsCollection"]
        total += cc["totalCommitContributions"] + cc["restrictedContributionsCount"]
        year += 1
    return total


def fetch_rest_profile():
    r = requests.get(f"https://api.github.com/users/{USERNAME}", headers=HEADERS_REST, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_social_accounts():
    r = requests.get(f"https://api.github.com/users/{USERNAME}/social_accounts", headers=HEADERS_REST, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_avatar_data_uri(avatar_url):
    """Downloads the GitHub avatar and inlines it as a base64 data URI, so the
    SVG stays fully self-contained (GitHub sandboxes raw SVGs and blocks them
    from loading external images at render time)."""
    r = requests.get(f"{avatar_url}&s=200" if "?" in avatar_url else f"{avatar_url}?s=200", timeout=30)
    r.raise_for_status()
    content_type = r.headers.get("Content-Type", "image/png")
    encoded = base64.b64encode(r.content).decode("ascii")
    return f"data:{content_type};base64,{encoded}"


def aggregate_repos(base):
    repos = base["repositories"]["nodes"]
    total_stars = sum(r["stargazerCount"] for r in repos)
    lang_bytes = {}
    for r in repos:
        for edge in r["languages"]["edges"]:
            name = edge["node"]["name"]
            lang_bytes[name] = lang_bytes.get(name, 0) + edge["size"]
    total_bytes = sum(lang_bytes.values()) or 1
    top = sorted(lang_bytes.items(), key=lambda kv: -kv[1])[:3]
    return total_stars, [f"{name} ({round(100*size/total_bytes)}%)" for name, size in top]


def short_social(url, kind):
    if not url:
        return "-"
    url = url.rstrip("/")
    handle = url.rsplit("/", 1)[-1]
    return f"in/{handle}" if kind == "linkedin" else f"@{handle}"


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_svg(mode, d):
    dark = mode == "dark"
    bg = "#0d1117" if dark else "#ffffff"
    panelbg = "#161b22" if dark else "#f6f8fa"
    border = "#30363d" if dark else "#d0d7de"
    text = "#c9d1d9" if dark else "#24292f"
    dim = "#8b949e" if dark else "#57606a"
    accent = "#79c0ff" if dark else "#0969da"
    accent2 = "#7ee787" if dark else "#1a7f37"
    pink = "#d2a8ff" if dark else "#8250df"
    yellow = "#e3b341" if dark else "#9a6700"

    svg = [f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">']
    svg.append(f'<rect width="{W}" height="{H}" rx="14" fill="{bg}" stroke="{border}" stroke-width="1.5"/>')
    svg.append(f'<rect x="0" y="0" width="{W}" height="44" rx="14" fill="{panelbg}"/>')
    svg.append(f'<rect x="0" y="30" width="{W}" height="14" fill="{panelbg}"/>')
    svg.append(f'<line x1="0" y1="44" x2="{W}" y2="44" stroke="{border}" stroke-width="1"/>')
    for i, c in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        svg.append(f'<circle cx="{28 + i*22}" cy="22" r="6" fill="{c}"/>')
    svg.append(f'<text x="{W/2}" y="27" font-family="{FONT}" font-size="13" fill="{dim}" text-anchor="middle">felippe@github: ~</text>')

    lp_x, lp_y, lp_w, lp_h = 24, 64, 232, H - 88
    svg.append(f'<rect x="{lp_x}" y="{lp_y}" width="{lp_w}" height="{lp_h}" rx="10" fill="{panelbg}" stroke="{border}" stroke-width="1"/>')
    cx, cy = lp_x + lp_w / 2, lp_y + 118
    clip_id = f"avatarClip-{mode}"
    svg.append(
        f'<defs><linearGradient id="g1" x1="0%" y1="0%" x2="100%" y2="100%">'
        f'<stop offset="0%" stop-color="{accent}"/><stop offset="100%" stop-color="{pink}"/>'
        f'</linearGradient>'
        f'<clipPath id="{clip_id}"><circle cx="{cx}" cy="{cy}" r="60"/></clipPath>'
        f'</defs>'
    )
    avatar = d.get("avatar_data_uri")
    if avatar:
        svg.append(
            f'<image href="{avatar}" x="{cx-60}" y="{cy-60}" width="120" height="120" '
            f'preserveAspectRatio="xMidYMid slice" clip-path="url(#{clip_id})"/>'
        )
    else:
        svg.append(f'<text x="{cx}" y="{cy+16}" font-family="{FONT}" font-size="46" font-weight="700" text-anchor="middle" fill="url(#g1)">FX</text>')
    svg.append(f'<circle cx="{cx}" cy="{cy}" r="66" fill="none" stroke="url(#g1)" stroke-width="3" stroke-dasharray="6 7"/>')
    svg.append(f'<text x="{cx}" y="{cy+96}" font-family="{FONT}" font-size="14" text-anchor="middle" fill="{text}">Felippe Ximenes</text>')
    svg.append(f'<text x="{cx}" y="{cy+118}" font-family="{FONT}" font-size="12" text-anchor="middle" fill="{dim}">Full Stack Developer</text>')

    prompt_y = lp_y + lp_h - 74
    svg.append(f'<text x="{lp_x+18}" y="{prompt_y}" font-family="{FONT}" font-size="13" fill="{accent2}">$ whoami</text>')
    svg.append(f'<text x="{lp_x+18}" y="{prompt_y+20}" font-family="{FONT}" font-size="13" fill="{text}">{esc(USERNAME)}</text>')
    svg.append(f'<text x="{lp_x+18}" y="{prompt_y+44}" font-family="{FONT}" font-size="13" fill="{accent2}">$ status</text>')
    svg.append(f'<text x="{lp_x+18}" y="{prompt_y+64}" font-family="{FONT}" font-size="13" fill="{yellow}">open to work ✓</text>')

    rx = lp_x + lp_w + 20
    rw = W - rx - 24
    svg.append(f'<rect x="{rx}" y="{lp_y}" width="{rw}" height="{lp_h}" rx="10" fill="{panelbg}" stroke="{border}" stroke-width="1"/>')

    def rline(label, value, yy, vcolor=None):
        vcolor = vcolor or text
        return (
            f'<text x="{rx+20}" y="{yy}" font-family="{FONT}" font-size="14" fill="{dim}">{esc(label)}</text>'
            f'<text x="{rx+170}" y="{yy}" font-family="{FONT}" font-size="14" fill="{vcolor}">{esc(value)}</text>'
        )

    def rsection(title, yy):
        return f'<text x="{rx+20}" y="{yy}" font-family="{FONT}" font-size="14" font-weight="700" fill="{accent}">{esc(title)}</text>'

    y = lp_y + 34
    svg.append(rsection("About", y)); y += 26
    svg.append(rline("Role:", d["role"], y)); y += 22
    svg.append(rline("Company:", d["company"], y)); y += 22
    svg.append(rline("Location:", d["location"], y)); y += 22
    svg.append(rline("Bio:", d["bio"], y)); y += 34

    svg.append(rsection("Top languages", y)); y += 26
    svg.append(rline("By bytes:", d["top_languages"], y)); y += 34

    svg.append(rsection("GitHub (live)", y)); y += 26
    svg.append(rline("Public repos:", d["public_repos"], y)); y += 22
    svg.append(rline("Followers:", d["followers"], y, accent2)); y += 22
    svg.append(rline("Total stars:", d["total_stars"], y, accent2)); y += 22
    svg.append(rline("All-time commits:", d["total_commits"], y, accent2)); y += 22
    svg.append(rline("Member since:", d["member_since"], y)); y += 34

    svg.append(rsection("Contact", y)); y += 26
    svg.append(rline("LinkedIn:", d["linkedin"], y, accent)); y += 22
    svg.append(rline("Instagram:", d["instagram"], y, accent)); y += 22
    svg.append(rline("GitHub:", f"github.com/{USERNAME}", y, accent))

    svg.append(f'<text x="{rx+20}" y="{lp_y+lp_h-14}" font-family="{FONT}" font-size="10" fill="{dim}">last updated {d["updated"]} UTC · auto-generated by GitHub Actions</text>')
    svg.append("</svg>")
    return "\n".join(svg)


def main():
    base = fetch_base()
    profile = fetch_rest_profile()
    try:
        socials = fetch_social_accounts()
    except requests.HTTPError:
        socials = []

    total_stars, top_languages = aggregate_repos(base)
    total_commits = fetch_total_commits(base["createdAt"])
    linkedin_url = next((s["url"] for s in socials if s["provider"] == "linkedin"), "")
    instagram_url = next((s["url"] for s in socials if s["provider"] == "instagram"), "")

    try:
        avatar_data_uri = fetch_avatar_data_uri(profile["avatar_url"])
    except Exception as exc:  # noqa: BLE001 - fall back to the monogram if this fails
        print(f"Could not fetch avatar, falling back to monogram: {exc}")
        avatar_data_uri = None

    data = {
        "avatar_data_uri": avatar_data_uri,
        "role": "Junior Full Stack Developer",
        "company": profile.get("company") or "-",
        "location": profile.get("location") or "-",
        "bio": (profile.get("bio") or "")[:42] or "-",
        "top_languages": ", ".join(top_languages) or "-",
        "public_repos": str(profile.get("public_repos", base["repositories"]["totalCount"])),
        "followers": str(base["followers"]["totalCount"]),
        "total_stars": str(total_stars),
        "total_commits": str(total_commits),
        "member_since": str(datetime.fromisoformat(base["createdAt"].replace("Z", "+00:00")).year),
        "linkedin": short_social(linkedin_url, "linkedin") if linkedin_url else "-",
        "instagram": short_social(instagram_url, "instagram") if instagram_url else "-",
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
    }

    with open("dark_mode.svg", "w") as f:
        f.write(build_svg("dark", data))
    with open("light_mode.svg", "w") as f:
        f.write(build_svg("light", data))
    print("SVGs generated with live data:", data)


if __name__ == "__main__":
    main()
