#!/usr/bin/env python3
"""Online GitHub GraphQL telemetry fetcher, 3D Contribution Skyline renderer, and dist/ bundler.

Uses Python 3.12 standard library only. Reuses the isometric projection,
Painter's algorithm bar renderer, perceptual bar height curve, and streak/stats
calculator while replacing HTML scraping with GitHub GraphQL v4.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import pathlib
import shutil
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from scripts.profile_core import (
    IST,
    get_theme_palette,
    load_profile,
    resolve_active_theme,
    validate_svg_document,
    write_text_lf,
    xml_escape,
)
from scripts.render_hero import render_hero_svg

GRAPHQL_ENDPOINT = "https://api.github.com/graphql"
USER_AGENT = "hynko431-profile-builder/2.0"
RETRY_BACKOFF_SECONDS: tuple[int, ...] = (1, 3, 7)

LEVEL_MAP: dict[str, int] = {
    "NONE": 0,
    "FIRST_QUARTILE": 1,
    "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3,
    "FOURTH_QUARTILE": 4,
}


@dataclass
class DayContrib:
    date: dt.date
    week: int
    dow: int
    level: int
    count: int


def compute_ist_window_utc(today_ist: dt.date) -> tuple[str, str]:
    """Compute IST-aligned trailing 365-day UTC ISO-8601 window (span < 1 year)."""
    from_dt = dt.datetime.combine(
        today_ist - dt.timedelta(days=364),
        dt.time(0, 0, 0),
        tzinfo=IST,
    ).astimezone(dt.timezone.utc)
    to_dt = dt.datetime.combine(
        today_ist,
        dt.time(23, 59, 59),
        tzinfo=IST,
    ).astimezone(dt.timezone.utc)
    return (
        from_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        to_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def build_graphql_request(
    username: str,
    repo_slugs: list[str],
    from_iso: str,
    to_iso: str,
) -> dict[str, Any]:
    """Build parameterized GraphQL v4 query + variables for calendar and featured repos."""
    var_decls = ["$login: String!", "$from: DateTime!", "$to: DateTime!"]
    repo_fields: list[str] = []
    variables: dict[str, Any] = {"login": username, "from": from_iso, "to": to_iso}

    for idx, slug in enumerate(repo_slugs):
        vname = f"r{idx}"
        var_decls.append(f"${vname}: String!")
        variables[vname] = slug
        repo_fields.append(
            f"  repo_{idx}: repository(owner: $login, name: ${vname}) {{\n"
            f"    stargazerCount\n"
            f"    pushedAt\n"
            f"    primaryLanguage {{ name }}\n"
            f"  }}"
        )

    query = (
        f"query ({', '.join(var_decls)}) {{\n"
        f"  user(login: $login) {{\n"
        f"    contributionsCollection(from: $from, to: $to) {{\n"
        f"      contributionCalendar {{\n"
        f"        weeks {{\n"
        f"          contributionDays {{\n"
        f"            date\n"
        f"            contributionCount\n"
        f"            contributionLevel\n"
        f"            weekday\n"
        f"          }}\n"
        f"        }}\n"
        f"      }}\n"
        f"    }}\n"
        f"  }}\n"
        + "\n".join(repo_fields)
        + "\n}"
    )
    return {"query": query, "variables": variables}


def parse_graphql_payload(payload: dict[str, Any], repo_slugs: list[str]) -> dict[str, Any]:
    """Parse and validate GraphQL response; fail closed on calendar errors, warn on repo errors."""
    if not isinstance(payload, dict):
        raise RuntimeError("GraphQL payload must be a JSON object")

    for err in payload.get("errors") or []:
        path = err.get("path") if isinstance(err, dict) else None
        msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        if isinstance(path, list) and path and isinstance(path[0], str) and path[0].startswith("repo_"):
            print(f"Warning: GraphQL repo error at {path[0]}: {msg}", file=sys.stderr)
        else:
            raise RuntimeError(f"Fatal GraphQL error (path={path!r}): {msg}")

    data = payload.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("user"), dict):
        raise RuntimeError("GraphQL response missing data.user")

    try:
        weeks = data["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(f"GraphQL response missing contributionCalendar.weeks: {exc}") from exc

    if not isinstance(weeks, list) or not weeks:
        raise RuntimeError("GraphQL contributionCalendar.weeks is empty")

    days: list[DayContrib] = []
    for week_idx, week_obj in enumerate(weeks):
        for day_obj in week_obj.get("contributionDays") or []:
            count = int(day_obj["contributionCount"])
            if count < 0:
                raise RuntimeError(f"Negative contributionCount {count} on {day_obj.get('date')}")
            lvl_str = day_obj["contributionLevel"]
            if lvl_str not in LEVEL_MAP:
                raise RuntimeError(f"Unknown contributionLevel: {lvl_str!r}")
            days.append(
                DayContrib(
                    date=dt.date.fromisoformat(day_obj["date"]),
                    week=week_idx,
                    dow=int(day_obj["weekday"]),
                    level=LEVEL_MAP[lvl_str],
                    count=count,
                )
            )

    if not (365 <= len(days) <= 372):
        raise RuntimeError(f"Expected 365..372 calendar days, parsed {len(days)}")

    days.sort(key=lambda d: (d.week, d.dow))

    repositories: dict[str, dict[str, Any]] = {}
    for idx, slug in enumerate(repo_slugs):
        alias = f"repo_{idx}"
        r_obj = data.get(alias)
        if not isinstance(r_obj, dict):
            print(f"Warning: Missing repository metadata for {slug} ({alias}); using null defaults", file=sys.stderr)
            repositories[slug] = {
                "stars": 0,
                "display_stars": False,
                "primary_language": None,
                "pushed_at": None,
            }
            continue
        stars = int(r_obj.get("stargazerCount") or 0)
        lang_obj = r_obj.get("primaryLanguage")
        primary_lang = lang_obj.get("name") if isinstance(lang_obj, dict) else None
        pushed_at = r_obj.get("pushedAt") if isinstance(r_obj.get("pushedAt"), str) else None
        repositories[slug] = {
            "stars": stars,
            "display_stars": stars >= 5,
            "primary_language": primary_lang,
            "pushed_at": pushed_at,
        }

    return {"days": days, "repositories": repositories}


def fetch_telemetry(
    username: str,
    repo_slugs: list[str],
    token: str,
    today_ist: dt.date,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Fetch contribution calendar and featured repo metadata via GitHub GraphQL v4."""
    from_iso, to_iso = compute_ist_window_utc(today_ist)
    body = json.dumps(build_graphql_request(username, repo_slugs, from_iso, to_iso)).encode("utf-8")

    last_err: Exception | None = None
    total_attempts = 1 + len(RETRY_BACKOFF_SECONDS)
    for attempt in range(total_attempts):
        req = urllib.request.Request(
            GRAPHQL_ENDPOINT,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read().decode("utf-8")
            payload = json.loads(raw)
            return parse_graphql_payload(payload, repo_slugs)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise RuntimeError(
                    f"GitHub GraphQL authentication failed with HTTP {exc.code}; "
                    f"verify GH_PROFILE_READ_TOKEN (Classic PAT with read:user scope) is valid."
                ) from exc
            last_err = exc
            if exc.code == 429 or 500 <= exc.code < 600:
                if attempt < len(RETRY_BACKOFF_SECONDS):
                    sleep_fn(RETRY_BACKOFF_SECONDS[attempt])
                    continue
            raise RuntimeError(f"GitHub GraphQL request failed with HTTP {exc.code}: {exc}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last_err = exc
            if attempt < len(RETRY_BACKOFF_SECONDS):
                sleep_fn(RETRY_BACKOFF_SECONDS[attempt])
                continue
            raise RuntimeError(f"GitHub GraphQL request failed after {total_attempts} attempts: {last_err}") from exc

    raise RuntimeError(f"GitHub GraphQL request failed: {last_err}")


def compute_stats(days: list[DayContrib]) -> dict[str, Any]:
    """Compute rolling contribution totals, active days, and streaks (no single-day peak KPI)."""
    chron = sorted(days, key=lambda d: d.date)
    total = sum(d.count for d in chron)
    active = sum(1 for d in chron if d.count > 0)

    best_streak = 0
    running = 0
    for d in chron:
        if d.count > 0:
            running += 1
            if running > best_streak:
                best_streak = running
        else:
            running = 0

    current_streak = 0
    idx = len(chron) - 1
    if idx >= 0 and chron[idx].count == 0:
        idx -= 1
    while idx >= 0 and chron[idx].count > 0:
        current_streak += 1
        idx -= 1

    return {
        "total": total,
        "active": active,
        "total_days": len(chron),
        "best_streak": best_streak,
        "current_streak": current_streak,
        "start_date": chron[0].date,
        "end_date": chron[-1].date,
    }


def bar_height(count: int, max_count: int) -> float:
    """Balanced perceptual bar height curve reused from baseline generator."""
    if count <= 0:
        return 3.0
    linear_part = min(count, 16) * 2.45
    if count <= 16:
        return 6.0 + linear_part
    boost = (math.log1p(count - 16) / math.log1p(max(max_count - 16, 1))) * 64.0
    return 6.0 + linear_part + boost


def fmt_pts(pts: list[tuple[float, float]]) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)


def render_svg(
    username: str,
    days: list[DayContrib],
    stats: dict[str, Any],
    theme_name: str,
    mode: str,
) -> str:
    """Render 1200x456 3D isometric contribution skyline SVG without peak callouts or blur filters."""
    t = get_theme_palette(theme_name, mode)
    n_weeks = max(d.week for d in days) + 1
    max_count = max(d.count for d in days) or 1

    ox, oy = 216.0, 178.0
    wx, wy = 16.5, 3.15
    dx, dy = -17.4, 9.8

    def proj(w: float, d: float, z: float = 0.0) -> tuple[float, float]:
        return (ox + w * wx + d * dx, oy + w * wy + d * dy - z)

    pad = 0.75
    p_back = proj(-pad, -pad, 0)
    p_right = proj(n_weeks - 1 + 1.0 + pad, -pad, 0)
    p_front = proj(n_weeks - 1 + 1.0 + pad, 7.0 + pad, 0)
    p_left = proj(-pad, 7.0 + pad, 0)
    plinth_h = 14.0
    pb_left = (p_left[0], p_left[1] + plinth_h)
    pb_front = (p_front[0], p_front[1] + plinth_h)
    pb_right = (p_right[0], p_right[1] + plinth_h)

    # Concentric unblurred floor shadows bounded within viewBox height 456 even at 54 weeks
    inner_shadow_pts = [
        (p_back[0], p_back[1] + 17.0),
        (p_right[0] + 2.0, p_right[1] + 17.0),
        (p_front[0], p_front[1] + 17.0 + 3.0),
        (p_left[0] - 2.0, p_left[1] + 17.0),
    ]
    outer_shadow_pts = [
        (p_back[0], p_back[1] + 20.0),
        (p_right[0] + 4.0, p_right[1] + 20.0),
        (p_front[0], p_front[1] + 20.0 + 4.0),
        (p_left[0] - 4.0, p_left[1] + 20.0),
    ]

    bars_svg: list[str] = []
    s = 0.80
    margin = (1.0 - s) * 0.5
    today_day = max(days, key=lambda d: d.date)
    today_top_center: tuple[float, float] = (0.0, 0.0)
    today_ring_pts: list[tuple[float, float]] = []

    for day in days:
        w0 = day.week + margin
        d0 = day.dow + margin
        h = bar_height(day.count, max_count)
        top_c, left_c, right_c, edge_c = t["levels"][str(day.level)]
        is_today = day.date == today_day.date

        b0 = proj(w0, d0, 0)
        b1 = proj(w0 + s, d0, 0)
        b2 = proj(w0 + s, d0 + s, 0)
        b3 = proj(w0, d0 + s, 0)
        t0 = (b0[0], b0[1] - h)
        t1 = (b1[0], b1[1] - h)
        t2 = (b2[0], b2[1] - h)
        t3 = (b3[0], b3[1] - h)

        bars_svg.append(
            f'<polygon points="{fmt_pts([t3, t2, b2, b3])}" fill="{left_c}"/>'
            f'<polygon points="{fmt_pts([t2, t1, b1, b2])}" fill="{right_c}"/>'
            f'<polygon points="{fmt_pts([t0, t1, t2, t3])}" fill="{top_c}" stroke="{t["accent"] if is_today else edge_c}" stroke-width="{"1.35" if is_today else "0.55"}" stroke-linejoin="round"/>'
        )
        if day.level == 4 and day.count >= 15:
            bars_svg.append(
                f'<polyline points="{fmt_pts([t3, t2, t1])}" fill="none" stroke="{t["peak_cap"]}" stroke-width="0.9" stroke-opacity="0.85"/>'
            )
        if is_today:
            today_top_center = ((t0[0] + t2[0]) * 0.5, (t0[1] + t2[1]) * 0.5)
            pad_r = 0.24
            r0 = proj(w0 - pad_r, d0 - pad_r, h)
            r1 = proj(w0 + s + pad_r, d0 - pad_r, h)
            r2 = proj(w0 + s + pad_r, d0 + s + pad_r, h)
            r3 = proj(w0 - pad_r, d0 + s + pad_r, h)
            today_ring_pts = [r0, r1, r2, r3]

    # "We are here · Today" beacon callout anchored strictly inside viewBox (1200x456) and below top HUD
    tx, ty = today_top_center
    today_date_label = today_day.date.strftime("%b %d, %Y")
    today_noun = "commit" if today_day.count == 1 else "commits"
    pin_w = 204.0
    pin_h = 40.0
    pin_x = min(max(tx - pin_w * 0.58, 40.0), 1180.0 - pin_w)
    pin_y = min(max(ty - 126.0, 94.0), 308.0)
    anchor_x = min(max(tx, pin_x + 16.0), pin_x + pin_w - 16.0)
    today_beacon_svg = (
        f'  <g>\n'
        f'    <polygon points="{fmt_pts(today_ring_pts)}" fill="none" stroke="{t["accent"]}" stroke-width="1.2" stroke-opacity="0.85"/>\n'
        f'    <line x1="{anchor_x:.1f}" y1="{pin_y + pin_h:.1f}" x2="{tx:.1f}" y2="{ty:.1f}" stroke="{t["accent"]}" stroke-width="1.25" stroke-dasharray="3 3"/>\n'
        f'    <circle cx="{tx:.1f}" cy="{ty:.1f}" r="6.0" fill="none" stroke="{t["accent"]}" stroke-width="1.1" opacity="0.65"/>\n'
        f'    <circle cx="{tx:.1f}" cy="{ty:.1f}" r="3.1" fill="{t["accent"]}"/>\n'
        f'    <rect x="{pin_x:.1f}" y="{pin_y:.1f}" width="{pin_w:.1f}" height="{pin_h:.1f}" rx="8" fill="{t["hud_bg"]}" stroke="{t["accent"]}" stroke-width="1.15"/>\n'
        f'    <circle cx="{pin_x + 14:.1f}" cy="{pin_y + 14:.1f}" r="3.0" fill="{t["accent"]}"/>\n'
        f'    <text x="{pin_x + 23:.1f}" y="{pin_y + 17.5:.1f}" class="pin-eyebrow">WE ARE HERE · TODAY</text>\n'
        f'    <text x="{pin_x + 14:.1f}" y="{pin_y + 32.0:.1f}" class="pin-val">{xml_escape(today_date_label)} · {today_day.count} {today_noun}</text>\n'
        f'  </g>'
    )

    month_labels: list[str] = []
    seen_months: set[tuple[int, int]] = set()
    last_label_week = -4
    for day in days:
        if day.dow == 0:
            ym = (day.date.year, day.date.month)
            if ym not in seen_months and day.week - last_label_week >= 3:
                seen_months.add(ym)
                last_label_week = day.week
                mx, my = proj(day.week + 0.5, 8.9, -plinth_h)
                month_labels.append(
                    f'<text x="{mx:.1f}" y="{my:.1f}" class="axis" text-anchor="middle">{day.date.strftime("%b")}</text>'
                )

    day_labels: list[str] = []
    for dow_idx, label in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        lx, ly = proj(-1.9, dow_idx + 0.6, -6.0)
        day_labels.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" class="axis" text-anchor="end">{label}</text>'
        )

    legend_items: list[str] = []
    for lvl in range(5):
        lx = 92 + lvl * 18
        lvl_colors = t["levels"][str(lvl)]
        legend_items.append(
            f'<rect x="{lx}" y="420" width="12" height="12" rx="2.5" fill="{lvl_colors[0]}" stroke="{lvl_colors[3]}" stroke-width="0.6"/>'
        )

    esc_user = xml_escape(username)
    total_fmt = f'{stats["total"]:,}'
    desc_text = xml_escape(
        f'3D GitHub Contribution Skyline for {username}: {total_fmt} contributions over '
        f'{stats["total_days"]} days, {stats["active"]} active days, '
        f'{stats["best_streak"]}-day best streak, {stats["current_streak"]}-day current streak.'
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 456" width="1200" height="456" role="img" aria-labelledby="c3d-title c3d-desc">
  <title id="c3d-title">3D Contribution Skyline — {esc_user}</title>
  <desc id="c3d-desc">{desc_text}</desc>
  <defs>
    <linearGradient id="c-bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{t["bg0"]}"/>
      <stop offset="100%" stop-color="{t["bg1"]}"/>
    </linearGradient>
    <radialGradient id="c-glow" cx="55%" cy="32%" r="55%">
      <stop offset="0%" stop-color="{t["glow"]}" stop-opacity="0.14"/>
      <stop offset="100%" stop-color="{t["bg0"]}" stop-opacity="0"/>
    </radialGradient>
    <pattern id="c-dots" width="24" height="24" patternUnits="userSpaceOnUse">
      <circle cx="2" cy="2" r="0.9" fill="{t["grid_dot"]}" fill-opacity="0.45"/>
    </pattern>
    <style>
      .eyebrow {{
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 1.4px;
        fill: {t["eyebrow"]};
      }}
      .heading {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
        font-size: 20px;
        font-weight: 700;
        letter-spacing: -0.3px;
        fill: {t["title"]};
      }}
      .sub {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
        font-size: 12px;
        fill: {t["muted"]};
      }}
      .kpi-val {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
        font-size: 17px;
        font-weight: 700;
        fill: {t["hud_val"]};
      }}
      .kpi-lbl {{
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        font-size: 10px;
        letter-spacing: 0.6px;
        fill: {t["muted"]};
      }}
      .axis {{
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        font-size: 10.5px;
        fill: {t["axis_text"]};
      }}
      .pin-eyebrow {{
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        font-size: 9.5px;
        font-weight: 700;
        letter-spacing: 0.8px;
        fill: {t["accent"]};
      }}
      .pin-val {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
        font-size: 11.5px;
        font-weight: 600;
        fill: {t["title"]};
      }}
    </style>
  </defs>

  <rect x="0.5" y="0.5" width="1199" height="455" rx="14" fill="url(#c-bg)" stroke="{t["border"]}" stroke-width="1"/>
  <rect x="1" y="1" width="1198" height="454" rx="13.5" fill="url(#c-dots)"/>
  <rect x="1" y="1" width="1198" height="454" rx="13.5" fill="url(#c-glow)"/>

  <text x="36" y="38" class="eyebrow">3D ISOMETRIC CONTRIBUTION SKYLINE · @{esc_user}</text>
  <text x="36" y="64" class="heading">Last 12 Months Commit Terrain</text>
  <text x="36" y="83" class="sub">{stats["start_date"].strftime("%b %Y")} – {stats["end_date"].strftime("%b %Y")} · Tower height reflects daily commit intensity</text>

  <g transform="translate(588, 22)">
    <rect x="0" y="0" width="136" height="52" rx="9" fill="{t["hud_bg"]}" stroke="{t["hud_border"]}"/>
    <text x="14" y="24" class="kpi-val">{total_fmt}</text>
    <text x="14" y="40" class="kpi-lbl">CONTRIBUTIONS</text>

    <rect x="146" y="0" width="136" height="52" rx="9" fill="{t["hud_bg"]}" stroke="{t["hud_border"]}"/>
    <text x="160" y="24" class="kpi-val">{stats["active"]}</text>
    <text x="160" y="40" class="kpi-lbl">ACTIVE DAYS</text>

    <rect x="292" y="0" width="136" height="52" rx="9" fill="{t["hud_bg"]}" stroke="{t["hud_border"]}"/>
    <text x="306" y="24" class="kpi-val">{stats["best_streak"]}d</text>
    <text x="306" y="40" class="kpi-lbl">BEST STREAK</text>

    <rect x="438" y="0" width="152" height="52" rx="9" fill="{t["hud_bg"]}" stroke="{t["hud_border"]}"/>
    <text x="452" y="24" class="kpi-val" fill="{t["accent"]}">{stats["current_streak"]}d</text>
    <text x="452" y="40" class="kpi-lbl">CURRENT STREAK</text>
  </g>

  <polygon points="{fmt_pts(outer_shadow_pts)}" fill="{t["shadow_color"]}" opacity="{t["shadow_opacity_outer"]}"/>
  <polygon points="{fmt_pts(inner_shadow_pts)}" fill="{t["shadow_color"]}" opacity="{t["shadow_opacity_inner"]}"/>
  <polygon points="{fmt_pts([p_left, p_front, pb_front, pb_left])}" fill="{t["plinth_left"]}" stroke="{t["plinth_stroke"]}" stroke-width="0.8"/>
  <polygon points="{fmt_pts([p_front, p_right, pb_right, pb_front])}" fill="{t["plinth_right"]}" stroke="{t["plinth_stroke"]}" stroke-width="0.8"/>
  <polygon points="{fmt_pts([p_back, p_right, p_front, p_left])}" fill="{t["plinth_top"]}" stroke="{t["plinth_stroke"]}" stroke-width="0.9"/>

  <g>
    {"".join(bars_svg)}
  </g>
{today_beacon_svg}

  <g>{"".join(month_labels)}</g>
  <g>{"".join(day_labels)}</g>

  <text x="56" y="430" class="axis">Less</text>
  {"".join(legend_items)}
  <text x="188" y="430" class="axis">More</text>
</svg>
'''


def build_dist(
    profile_path: pathlib.Path,
    repo_root: pathlib.Path,
    out_dir: pathlib.Path,
    today_ist: dt.date,
    telemetry_data: dict[str, Any],
) -> dict[str, Any]:
    """Validate and write complete dist/ bundle for GitHub Pages."""
    profile = load_profile(profile_path)
    active_theme = resolve_active_theme(today_ist)
    days: list[DayContrib] = telemetry_data["days"]
    stats = compute_stats(days)

    rendered_svgs: dict[str, str] = {}
    for mode in ("dark", "light"):
        contrib_svg = render_svg(profile["handle"], days, stats, active_theme, mode)
        hero_svg = render_hero_svg(profile, active_theme, mode)
        rendered_svgs[f"contrib-3d-{mode}.svg"] = contrib_svg
        rendered_svgs[f"banner-3d-{mode}.svg"] = hero_svg

    # Fail-closed validation before writing any output to dist/
    validation_errors: list[str] = []
    for fname, content in rendered_svgs.items():
        validation_errors.extend(validate_svg_document(content, fname))
    if validation_errors:
        raise RuntimeError("SVG validation failed:\n" + "\n".join(validation_errors))

    telemetry_json = {
        "schema_version": 1,
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "today_date": today_ist.isoformat(),
        "username": profile["handle"],
        "active_theme": active_theme,
        "theme_palettes": {
            "dark": get_theme_palette(active_theme, "dark"),
            "light": get_theme_palette(active_theme, "light"),
        },
        "stats": {
            "total": stats["total"],
            "active_days": stats["active"],
            "total_days": stats["total_days"],
            "best_streak": stats["best_streak"],
            "current_streak": stats["current_streak"],
            "start_date": stats["start_date"].isoformat(),
            "end_date": stats["end_date"].isoformat(),
        },
        "calendar_days": [
            {
                "date": d.date.isoformat(),
                "week": d.week,
                "dow": d.dow,
                "level": d.level,
                "count": d.count,
            }
            for d in days
        ],
        "repositories": telemetry_data["repositories"],
    }

    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "assets" / "icons").mkdir(parents=True, exist_ok=True)

    for fname, content in rendered_svgs.items():
        write_text_lf(out_dir / "assets" / fname, content)

    write_text_lf(out_dir / "telemetry.json", json.dumps(telemetry_json, indent=2) + "\n")
    write_text_lf(out_dir / "profile.json", profile_path.read_text(encoding="utf-8"))

    icons_src = repo_root / "assets" / "icons"
    for svg_file in sorted(icons_src.glob("*.svg")):
        write_text_lf(out_dir / "assets" / "icons" / svg_file.name, svg_file.read_text(encoding="utf-8"))

    for mode in ("dark", "light"):
        stack_src = repo_root / "assets" / f"stack-3d-{mode}.svg"
        write_text_lf(out_dir / "assets" / stack_src.name, stack_src.read_text(encoding="utf-8"))

    explorer_src = repo_root / "explorer"
    for web_file in sorted(explorer_src.iterdir()):
        if web_file.is_file():
            write_text_lf(out_dir / web_file.name, web_file.read_text(encoding="utf-8"))

    return telemetry_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build nightly dist/ bundle with GraphQL telemetry and dynamic SVGs.")
    parser.add_argument("--profile", default="profile.json", help="Path to profile.json")
    parser.add_argument("--repo-root", default=None, help="Repository root directory (defaults to profile.json parent)")
    parser.add_argument("--out-dir", default="dist", help="Output bundle directory")
    parser.add_argument("--date", default=None, help="Override IST date (YYYY-MM-DD)")
    parser.add_argument("--telemetry-fixture", default=None, help="Raw GraphQL JSON fixture path for offline builds")
    args = parser.parse_args(argv)

    profile_path = pathlib.Path(args.profile).resolve()
    repo_root = pathlib.Path(args.repo_root).resolve() if args.repo_root else profile_path.parent
    out_dir = pathlib.Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = repo_root / out_dir

    profile = load_profile(profile_path)
    today_ist = (
        dt.date.fromisoformat(args.date)
        if args.date
        else dt.datetime.now(dt.timezone.utc).astimezone(IST).date()
    )
    repo_slugs = [p["repo"] for p in profile["projects"]]

    if args.telemetry_fixture:
        fixture_path = pathlib.Path(args.telemetry_fixture)
        if not fixture_path.is_absolute():
            fixture_path = repo_root / fixture_path
        raw_payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        telemetry_data = parse_graphql_payload(raw_payload, repo_slugs)
    else:
        token = os.environ.get("GH_PROFILE_READ_TOKEN", "").strip()
        if not token:
            raise RuntimeError(
                "GH_PROFILE_READ_TOKEN environment variable is empty; "
                "set a Classic PAT with read:user scope or pass --telemetry-fixture."
            )
        telemetry_data = fetch_telemetry(profile["handle"], repo_slugs, token, today_ist)

    result = build_dist(profile_path, repo_root, out_dir, today_ist, telemetry_data)
    print(
        f"Built {out_dir} for @{result['username']} (theme={result['active_theme']}, "
        f"total={result['stats']['total']}, active_days={result['stats']['active_days']}, "
        f"best_streak={result['stats']['best_streak']}d, current_streak={result['stats']['current_streak']}d)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
