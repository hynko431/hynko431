#!/usr/bin/env python3
"""Offline deterministic static generator and CI drift/SVG/WCAG verifier.

Generates README.md, assets/stack-3d-{dark,light}.svg, and 12 bespoke bento
project cards under assets/cards/{slug}-{dark,light}.svg from profile.json
using Python 3.12 standard library only.
"""

from __future__ import annotations

import argparse
import difflib
import pathlib
import re
import sys
from typing import Any

from scripts.profile_core import (
    PROJECT_CARD_ACCENTS,
    STACK_TIER_ACCENTS,
    get_theme_palette,
    load_profile,
    validate_all_palettes_wcag,
    validate_svg_document,
    write_text_lf,
    xml_attr,
    xml_escape,
)

STATIC_ICON_FILES: tuple[str, ...] = (
    "assets/icons/coldpin-dark.svg",
    "assets/icons/coldpin-light.svg",
    "assets/icons/sentinel-dark.svg",
    "assets/icons/sentinel-light.svg",
    "assets/icons/cutaway-dark.svg",
    "assets/icons/cutaway-light.svg",
    "assets/icons/helix-dark.svg",
    "assets/icons/helix-light.svg",
    "assets/icons/autopilot-dark.svg",
    "assets/icons/autopilot-light.svg",
    "assets/icons/medical-dark.svg",
    "assets/icons/medical-light.svg",
    "assets/icons/contact-portfolio-dark.svg",
    "assets/icons/contact-portfolio-light.svg",
    "assets/icons/contact-linkedin-dark.svg",
    "assets/icons/contact-linkedin-light.svg",
    "assets/icons/contact-email-dark.svg",
    "assets/icons/contact-email-light.svg",
    "assets/icons/contact-x-dark.svg",
    "assets/icons/contact-x-light.svg",
)


def _wrap_items(items: list[str], max_chars: int = 62) -> list[str]:
    """Wrap tech stack items across at most two balanced lines."""
    sep = " · "
    lines: list[str] = []
    current = ""
    for item in items:
        candidate = f"{current}{sep}{item}" if current else item
        if current and len(candidate) > max_chars:
            lines.append(current)
            current = item
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines[:2]


def _wrap_prose(text: str, max_chars: int = 64, max_lines: int = 3) -> list[str]:
    """Word-wrap prose cleanly into balanced lines without mid-word breaks."""
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        cand = f"{cur} {w}" if cur else w
        if cur and len(cand) > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines[:max_lines]


def _extract_icon_inner(icon_svg_path: pathlib.Path) -> str:
    """Extract drawable SVG primitives from an icon SVG (excluding root, title, desc)."""
    raw = icon_svg_path.read_text(encoding="utf-8")
    m = re.search(r"<svg[^>]*>(.*)</svg>", raw, flags=re.DOTALL)
    if not m:
        raise ValueError(f"Could not extract inner SVG from {icon_svg_path}")
    inner = re.sub(r"<title[^>]*>.*?</title>", "", m.group(1), flags=re.DOTALL)
    inner = re.sub(r"<desc[^>]*>.*?</desc>", "", inner, flags=re.DOTALL)
    return inner.strip()


_STACK_SLAB_THEMES: dict[str, dict[str, dict[str, str]]] = {
    "dark": {
        "01": {"top": "#132641", "left": "#13477F", "right": "#0D325B", "grid": "#1F4D80"},
        "02": {"top": "#1C1F42", "left": "#393E8A", "right": "#292D68", "grid": "#43499E"},
        "03": {"top": "#0F2D27", "left": "#156352", "right": "#0F483B", "grid": "#1B7A65"},
        "04": {"top": "#2E210C", "left": "#754E0C", "right": "#553809", "grid": "#8A5C10"},
    },
    "light": {
        "01": {"top": "#EAF3FF", "left": "#B7D6FB", "right": "#8ABBF7", "grid": "#C2DCFB"},
        "02": {"top": "#EEF0FF", "left": "#C4CBFD", "right": "#9FA9FA", "grid": "#CFD4FE"},
        "03": {"top": "#E8F8F2", "left": "#A7E5CD", "right": "#79D6B3", "grid": "#BBEBD8"},
        "04": {"top": "#FEF5E6", "left": "#FBD69A", "right": "#F7BE63", "grid": "#FDE0B0"},
    },
}


def render_project_card_svg(
    proj: dict[str, Any],
    handle: str,
    icon_inner: str,
    mode: str,
) -> str:
    """Render a bespoke 536x222 dark/light bento SVG card for a featured project."""
    pal = get_theme_palette("baseline", mode)
    slug = proj["slug"]
    accent = PROJECT_CARD_ACCENTS[mode].get(slug, pal["eyebrow"])
    card_bg0 = "#0F1622" if mode == "dark" else "#FFFFFF"
    card_bg1 = "#161D29" if mode == "dark" else "#F7FAFE"
    tag_bg = "#0D1117" if mode == "dark" else "#F1F5F9"
    tag_stroke = "#30363D" if mode == "dark" else "#CBD5E1"
    divider = "#242D3A" if mode == "dark" else "#E2E8F0"
    glow_op = "0.18" if mode == "dark" else "0.10"

    name = xml_escape(proj["name"])
    category = xml_escape(proj["category"].upper())
    repo_label = xml_escape(f'{handle}/{proj["repo"]}')
    summary_lines = _wrap_prose(proj["summary"], max_chars=66, max_lines=3)
    summary_svg = "\n".join(
        f'  <text x="24" y="{94 + idx * 17}" class="summary">{xml_escape(line)}</text>'
        for idx, line in enumerate(summary_lines)
    )

    # Top-right link capability pill
    has_docs = bool(proj["links"].get("docs"))
    has_live = bool(proj["links"].get("live"))
    cta_label = "CODE · DOCS ↗" if has_docs else "CODE · LIVE ↗" if has_live else "OPEN CODE ↗"
    cta_w = 104 if (has_docs or has_live) else 98

    # Styled monospace stack pills
    pill_x = 24.0
    pill_y = 148.0
    pills_svg: list[str] = []
    for tech in proj["stack"]:
        tw = max(46.0, len(tech) * 6.9 + 18.0)
        if pill_x + tw > 512.0:
            break
        pills_svg.append(
            f'  <rect x="{pill_x:.1f}" y="{pill_y:.1f}" width="{tw:.1f}" height="22" rx="6" fill="{tag_bg}" stroke="{tag_stroke}" stroke-width="0.9"/>\n'
            f'  <text x="{pill_x + tw * 0.5:.1f}" y="{pill_y + 14.5:.1f}" text-anchor="middle" class="tag">{xml_escape(tech)}</text>'
        )
        pill_x += tw + 7.0

    gid = f"c-{slug}-{mode}"
    desc_text = xml_escape(f'{proj["name"]} ({proj["category"]}): {proj["summary"]} Stack: {", ".join(proj["stack"])}.')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 536 222" width="536" height="222" '
        f'role="img" aria-labelledby="{gid}-t {gid}-d">\n'
        f'  <title id="{gid}-t">{name} — {xml_escape(proj["category"])}</title>\n'
        f'  <desc id="{gid}-d">{desc_text}</desc>\n'
        f'  <defs>\n'
        f'    <linearGradient id="{gid}-bg" x1="0%" y1="0%" x2="100%" y2="100%">\n'
        f'      <stop offset="0%" stop-color="{card_bg0}"/>\n'
        f'      <stop offset="100%" stop-color="{card_bg1}"/>\n'
        f'    </linearGradient>\n'
        f'    <radialGradient id="{gid}-glow" cx="12%" cy="18%" r="48%">\n'
        f'      <stop offset="0%" stop-color="{accent}" stop-opacity="{glow_op}"/>\n'
        f'      <stop offset="100%" stop-color="{card_bg0}" stop-opacity="0"/>\n'
        f'    </radialGradient>\n'
        f'    <linearGradient id="{gid}-top" x1="0%" y1="0%" x2="100%" y2="0%">\n'
        f'      <stop offset="0%" stop-color="{accent}" stop-opacity="0.9"/>\n'
        f'      <stop offset="55%" stop-color="{accent}" stop-opacity="0.22"/>\n'
        f'      <stop offset="100%" stop-color="{accent}" stop-opacity="0"/>\n'
        f'    </linearGradient>\n'
        f'    <style>\n'
        f'      .title {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; font-size: 16px; font-weight: 700; letter-spacing: -0.25px; fill: {pal["title"]}; }}\n'
        f'      .cat {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 10.5px; font-weight: 700; letter-spacing: 0.7px; fill: {accent}; }}\n'
        f'      .summary {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; font-size: 12.5px; fill: {pal["muted"]}; }}\n'
        f'      .tag {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 10.5px; font-weight: 600; fill: {pal["title"]}; }}\n'
        f'      .repo {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 11px; fill: {pal["muted"]}; }}\n'
        f'      .cta {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 10px; font-weight: 700; letter-spacing: 0.6px; fill: {accent}; }}\n'
        f'    </style>\n'
        f'  </defs>\n'
        f'  <rect x="0.75" y="0.75" width="534.5" height="220.5" rx="14" fill="url(#{gid}-bg)" stroke="{pal["border"]}" stroke-width="1.2"/>\n'
        f'  <rect x="1" y="1" width="534" height="220" rx="13.5" fill="url(#{gid}-glow)"/>\n'
        f'  <rect x="14" y="1" width="508" height="2.2" rx="1.1" fill="url(#{gid}-top)"/>\n'
        f'  <g transform="translate(22, 20)">\n'
        f'{icon_inner}\n'
        f'  </g>\n'
        f'  <text x="84" y="40" class="title">{name}</text>\n'
        f'  <text x="84" y="59" class="cat">{category}</text>\n'
        f'{summary_svg}\n'
        + "\n".join(pills_svg)
        + f'\n  <line x1="24" y1="184" x2="512" y2="184" stroke="{divider}" stroke-width="1"/>\n'
        f'  <circle cx="30" cy="201" r="3.2" fill="{accent}"/>\n'
        f'  <text x="41" y="205" class="repo">{repo_label}</text>\n'
        f'  <rect x="{512 - cta_w}" y="191" width="{cta_w}" height="20" rx="6" fill="{tag_bg}" stroke="{accent}" stroke-width="0.9" stroke-opacity="0.7"/>\n'
        f'  <text x="{512 - cta_w / 2:.1f}" y="204.5" text-anchor="middle" class="cta">{cta_label}</text>\n'
        f'</svg>\n'
    )


def render_stack_svg(profile: dict[str, Any], mode: str) -> str:
    """Render deterministic 3D isometric 4-tier Tech Stack Architecture SVG (01 -> 04)."""
    pal = get_theme_palette("baseline", mode)
    tiers = profile["tech_stack_tiers"]
    accents = STACK_TIER_ACCENTS[mode]
    slab_themes = _STACK_SLAB_THEMES[mode]
    card_bg = "#161B22" if mode == "dark" else "#FFFFFF"
    card_stroke = "#30363D" if mode == "dark" else "#D0D7DE"
    pill_bg = "#0D1117" if mode == "dark" else "#F4F7FB"
    pillar_color = "#30363D" if mode == "dark" else "#CBD5E1"
    shadow_fill = "#000000" if mode == "dark" else "#1F2937"
    shadow_op_outer = "0.26" if mode == "dark" else "0.06"
    shadow_op_inner = "0.42" if mode == "dark" else "0.10"

    cx = 236.0
    rx = 162.0
    ry = 44.0
    slab_h = 16.0
    cy_list = [124.0 + i * 76.0 for i in range(len(tiers))]

    def _pts(coords: list[tuple[float, float]]) -> str:
        return " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)

    base_cy = cy_list[-1] + 22.0
    outer_shadow = [
        (cx, base_cy - ry - 4.0),
        (cx + rx + 8.0, base_cy),
        (cx, base_cy + ry + 4.0),
        (cx - rx - 8.0, base_cy),
    ]
    inner_shadow = [
        (cx, base_cy - ry - 1.0),
        (cx + rx + 3.0, base_cy),
        (cx, base_cy + ry + 1.0),
        (cx - rx - 3.0, base_cy),
    ]

    spine_lines = [
        f'  <line x1="{cx:.1f}" y1="{cy_list[0]:.1f}" x2="{cx:.1f}" y2="{cy_list[-1] + slab_h:.1f}" stroke="{pillar_color}" stroke-width="1.2" stroke-dasharray="4 4"/>',
        f'  <line x1="{cx - rx * 0.62:.1f}" y1="{cy_list[0]:.1f}" x2="{cx - rx * 0.62:.1f}" y2="{cy_list[-1]:.1f}" stroke="{pillar_color}" stroke-width="1" stroke-dasharray="3 5" opacity="0.8"/>',
        f'  <line x1="{cx + rx * 0.62:.1f}" y1="{cy_list[0]:.1f}" x2="{cx + rx * 0.62:.1f}" y2="{cy_list[-1]:.1f}" stroke="{pillar_color}" stroke-width="1" stroke-dasharray="3 5" opacity="0.8"/>',
    ]

    slab_blocks: list[str] = []
    for i in range(len(tiers) - 1, -1, -1):
        tier = tiers[i]
        idx = tier["index"]
        cy = cy_list[i]
        accent = accents[idx]
        st = slab_themes[idx]

        p_top = (cx, cy - ry)
        p_right = (cx + rx, cy)
        p_bottom = (cx, cy + ry)
        p_left = (cx - rx, cy)

        b_right = (p_right[0], p_right[1] + slab_h)
        b_bottom = (p_bottom[0], p_bottom[1] + slab_h)
        b_left = (p_left[0], p_left[1] + slab_h)

        grid_lines: list[str] = []
        for frac in (0.28, 0.56, 0.80):
            ax = p_top[0] + (p_left[0] - p_top[0]) * frac
            ay = p_top[1] + (p_left[1] - p_top[1]) * frac
            bx = p_right[0] + (p_bottom[0] - p_right[0]) * frac
            by = p_right[1] + (p_bottom[1] - p_right[1]) * frac
            grid_lines.append(
                f'    <line x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}" stroke="{st["grid"]}" stroke-width="0.7" opacity="0.65"/>'
            )
            cx1 = p_top[0] + (p_right[0] - p_top[0]) * frac
            cy1 = p_top[1] + (p_right[1] - p_top[1]) * frac
            dx1 = p_left[0] + (p_bottom[0] - p_left[0]) * frac
            dy1 = p_left[1] + (p_bottom[1] - p_left[1]) * frac
            grid_lines.append(
                f'    <line x1="{cx1:.1f}" y1="{cy1:.1f}" x2="{dx1:.1f}" y2="{dy1:.1f}" stroke="{st["grid"]}" stroke-width="0.7" opacity="0.65"/>'
            )

        slab_blocks.append(
            f'  <g>\n'
            f'    <polygon points="{_pts([p_left, p_bottom, b_bottom, b_left])}" fill="{st["left"]}" stroke="{accent}" stroke-width="0.9" stroke-linejoin="round"/>\n'
            f'    <polygon points="{_pts([p_bottom, p_right, b_right, b_bottom])}" fill="{st["right"]}" stroke="{accent}" stroke-width="0.9" stroke-linejoin="round"/>\n'
            f'    <polygon points="{_pts([p_top, p_right, p_bottom, p_left])}" fill="{st["top"]}" stroke="{accent}" stroke-width="1.25" stroke-linejoin="round"/>\n'
            + "\n".join(grid_lines)
            + f'\n    <circle cx="{cx - 72:.1f}" cy="{cy:.1f}" r="3.2" fill="{accent}"/>\n'
            f'    <circle cx="{cx + 72:.1f}" cy="{cy:.1f}" r="3.2" fill="{accent}"/>\n'
            f'    <rect x="{cx - 22:.1f}" y="{cy - 11:.1f}" width="44" height="22" rx="6" fill="{pill_bg}" stroke="{accent}" stroke-width="1.1"/>\n'
            f'    <text x="{cx:.1f}" y="{cy + 4:.1f}" text-anchor="middle" class="slab-idx" fill="{accent}">L{xml_escape(idx)}</text>\n'
            f'  </g>'
        )

    card_blocks: list[str] = []
    for i, tier in enumerate(tiers):
        idx = tier["index"]
        cy = cy_list[i]
        accent = accents[idx]
        label = xml_escape(tier["label"])
        wrapped = _wrap_items(tier["items"], max_chars=66)
        card_x = 462.0
        card_w = 632.0
        card_h = 66.0
        card_y = cy - card_h * 0.5

        if len(wrapped) == 1:
            items_svg = (
                f'    <text x="{card_x + 22:.1f}" y="{card_y + 49:.1f}" class="items">{xml_escape(wrapped[0])}</text>'
            )
        else:
            items_svg = (
                f'    <text x="{card_x + 22:.1f}" y="{card_y + 42:.1f}" class="items">{xml_escape(wrapped[0])}</text>\n'
                f'    <text x="{card_x + 22:.1f}" y="{card_y + 58:.1f}" class="items">{xml_escape(wrapped[1])}</text>'
            )

        leader_start_x = cx + rx + 4.0
        card_blocks.append(
            f'  <g>\n'
            f'    <line x1="{leader_start_x:.1f}" y1="{cy:.1f}" x2="{card_x:.1f}" y2="{cy:.1f}" stroke="{accent}" stroke-width="1.2" stroke-dasharray="3 3" opacity="0.85"/>\n'
            f'    <circle cx="{leader_start_x:.1f}" cy="{cy:.1f}" r="3.2" fill="{accent}"/>\n'
            f'    <circle cx="{card_x:.1f}" cy="{cy:.1f}" r="3.2" fill="{accent}"/>\n'
            f'    <rect x="{card_x:.1f}" y="{card_y:.1f}" width="{card_w:.1f}" height="{card_h:.1f}" rx="10" fill="{card_bg}" stroke="{card_stroke}" stroke-width="1"/>\n'
            f'    <rect x="{card_x:.1f}" y="{card_y:.1f}" width="5" height="{card_h:.1f}" rx="2.5" fill="{accent}"/>\n'
            f'    <text x="{card_x + 22:.1f}" y="{card_y + 23:.1f}" class="tier-label" fill="{accent}">{xml_escape(idx)} · {label}</text>\n'
            f'{items_svg}\n'
            f'  </g>'
        )

    desc_summary = "; ".join(f"{t['index']} {t['label']}: {', '.join(t['items'])}" for t in tiers)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 440" width="1120" height="440" '
        f'role="img" aria-labelledby="stack-title stack-desc">\n'
        f'  <title id="stack-title">3D Isometric Tech Stack Architecture — {xml_escape(profile["handle"])}</title>\n'
        f'  <desc id="stack-desc">{xml_escape(desc_summary)}</desc>\n'
        f'  <defs>\n'
        f'    <linearGradient id="st-bg" x1="0%" y1="0%" x2="100%" y2="100%">\n'
        f'      <stop offset="0%" stop-color="{pal["bg0"]}"/>\n'
        f'      <stop offset="100%" stop-color="{pal["bg1"]}"/>\n'
        f'    </linearGradient>\n'
        f'    <pattern id="st-dots" width="24" height="24" patternUnits="userSpaceOnUse">\n'
        f'      <circle cx="2" cy="2" r="0.9" fill="{pal["grid_dot"]}" fill-opacity="0.4"/>\n'
        f'    </pattern>\n'
        f'    <style>\n'
        f'      .eyebrow {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 11px; font-weight: 600; letter-spacing: 1.3px; fill: {pal["eyebrow"]}; }}\n'
        f'      .sub {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; font-size: 12px; fill: {pal["muted"]}; }}\n'
        f'      .meta {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 11px; fill: {pal["muted"]}; }}\n'
        f'      .slab-idx {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 11.5px; font-weight: 700; letter-spacing: 0.6px; }}\n'
        f'      .tier-label {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; font-size: 13.5px; font-weight: 700; }}\n'
        f'      .items {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 11.5px; fill: {pal["title"]}; }}\n'
        f'    </style>\n'
        f'  </defs>\n'
        f'  <rect x="0.5" y="0.5" width="1119" height="439" rx="14" fill="url(#st-bg)" stroke="{pal["border"]}" stroke-width="1"/>\n'
        f'  <rect x="1" y="1" width="1118" height="438" rx="13.5" fill="url(#st-dots)"/>\n'
        f'  <text x="28" y="34" class="eyebrow">3D ISOMETRIC STACK ARCHITECTURE · LAYERS 01 TO 04</text>\n'
        f'  <text x="28" y="53" class="sub">Four-tier AI, Backend, Data &amp; Systems blueprint — click to orbit &amp; cross-filter in 3D Explorer</text>\n'
        f'  <text x="1094" y="34" text-anchor="end" class="meta">@{xml_escape(profile["handle"])}</text>\n'
        f'  <polygon points="{_pts(outer_shadow)}" fill="{shadow_fill}" opacity="{shadow_op_outer}"/>\n'
        f'  <polygon points="{_pts(inner_shadow)}" fill="{shadow_fill}" opacity="{shadow_op_inner}"/>\n'
        + "\n".join(spine_lines)
        + "\n"
        + "\n".join(slab_blocks)
        + "\n"
        + "\n".join(card_blocks)
        + "\n</svg>\n"
    )


def _picture(dark_src: str, light_src: str, alt: str, *, width: str | None = None, height: str | None = None) -> str:
    dims = ""
    if width is not None:
        dims += f' width={xml_attr(width)}'
    if height is not None:
        dims += f' height={xml_attr(height)}'
    return (
        "<picture>"
        f'<source media="(prefers-color-scheme: dark)" srcset={xml_attr(dark_src)} />'
        f'<source media="(prefers-color-scheme: light)" srcset={xml_attr(light_src)} />'
        f'<img alt={xml_attr(alt)} src={xml_attr(light_src)}{dims} />'
        "</picture>"
    )


def render_readme(profile: dict[str, Any], dynamic_assets_base: str) -> str:
    """Deterministically render Layer 1 README.md from profile.json."""
    base = dynamic_assets_base.rstrip("/")
    explorer = profile["explorer_url"]
    handle = profile["handle"]

    banner_pic = _picture(
        f"{base}/banner-3d-dark.svg",
        f"{base}/banner-3d-light.svg",
        f'{profile["name"]} — {profile["role_headline"]} Banner',
        width="100%",
    )

    contact_links: list[str] = []
    for c in profile["contact"]:
        cid = c["id"]
        pic = _picture(
            f"./assets/icons/contact-{cid}-dark.svg",
            f"./assets/icons/contact-{cid}-light.svg",
            c["alt"],
            height="28",
        )
        contact_links.append(f'  <a href={xml_attr(c["url"])}>{pic}</a>')

    lines: list[str] = [
        '<div align="center">',
        f'  <a href={xml_attr(explorer)}>{banner_pic}</a>',
        "",
        "  <br/>",
        "",
        *contact_links,
        "</div>",
        "",
        profile["summary"],
        "",
        "---",
        "",
        "## Experience",
        "",
    ]

    for exp in profile["experience"]:
        lines.append(f'### {exp["company"]} *({exp["location"]})*')
        lines.append("")
        for role in exp["roles"]:
            lines.append(f'**{role["title"]}** · {role["employment_type"]} *({role["period"]})*')
            lines.append("")
            for bullet in role["highlights"]:
                lines.append(f"- {bullet}")
            lines.append("")

    edu = profile["education"]
    lines.extend(
        [
            "---",
            "",
            "## Education",
            "",
            f'**{edu["degree"]}** — {edu["institution"]} *({edu["period"]})*',
            "",
            "---",
            "",
            "## Featured Projects",
            "",
            '<div align="center">',
        ]
    )

    projects = profile["projects"]
    extra_links: list[str] = []
    for row_start in range(0, len(projects), 2):
        pair = projects[row_start : row_start + 2]
        row_cards: list[str] = []
        for proj in pair:
            slug = proj["slug"]
            code_url = proj["links"]["code"]
            card_pic = _picture(
                f"./assets/cards/{slug}-dark.svg",
                f"./assets/cards/{slug}-light.svg",
                f'{proj["name"]} — {proj["category"]}',
                width="49%",
            )
            row_cards.append(f'<a href={xml_attr(code_url)}>{card_pic}</a>')
            if proj["links"].get("docs"):
                extra_links.append(f'[{proj["name"].split(" (")[0]} Docs]({proj["links"]["docs"]})')
            if proj["links"].get("live"):
                extra_links.append(f'[{proj["name"].split(" (")[0]} Live]({proj["links"]["live"]})')
        lines.append("  " + " &nbsp; ".join(row_cards))
        if row_start + 2 < len(projects):
            lines.append("  <br/>")

    other_parts = [
        f'[{op["name"]}]({op["url"]}) *({op["note"]})*' for op in profile["other_projects"]
    ]
    stack_pic = _picture(
        "./assets/stack-3d-dark.svg",
        "./assets/stack-3d-light.svg",
        f"3D Isometric Tech Stack Architecture for {handle}",
        width="100%",
    )
    skyline_pic = _picture(
        f"{base}/contrib-3d-dark.svg",
        f"{base}/contrib-3d-light.svg",
        f"3D Isometric GitHub Contribution Skyline for {handle}",
        width="100%",
    )

    extra_prefix = f'*Docs & Live:* {" · ".join(extra_links)} — ' if extra_links else ""
    lines.extend(
        [
            "</div>",
            "",
            f'{extra_prefix}*Also built:* {" · ".join(other_parts)} — [View all repositories →](https://github.com/{handle}?tab=repositories) · [Filter Projects in 3D Explorer →]({explorer}#projects)',
            "",
            "---",
            "",
            "## Tech Stack Architecture",
            "",
            '<div align="center">',
            f'  <a href={xml_attr(explorer + "#stack")}>{stack_pic}</a>',
            "</div>",
            "",
            f'<p align="center"><a href={xml_attr(explorer + "#stack")}>Explore Interactive 3D Tech Stack &amp; Filter Projects →</a></p>',
            "",
            "---",
            "",
            "## 3D Contribution Skyline",
            "",
            '<div align="center">',
            f'  <a href={xml_attr(explorer + "#skyline")}>{skyline_pic}</a>',
            "</div>",
            "",
            f'<p align="center"><a href={xml_attr(explorer)}>Open Interactive 3D Profile Explorer →</a></p>',
            "",
        ]
    )

    return "\n".join(lines)


def _expected_generated_files(
    repo_root: pathlib.Path,
    profile: dict[str, Any],
    dynamic_assets_base: str,
) -> dict[pathlib.Path, str]:
    files: dict[pathlib.Path, str] = {
        repo_root / "README.md": render_readme(profile, dynamic_assets_base),
        repo_root / "assets" / "stack-3d-dark.svg": render_stack_svg(profile, "dark"),
        repo_root / "assets" / "stack-3d-light.svg": render_stack_svg(profile, "light"),
    }
    for proj in profile["projects"]:
        slug = proj["slug"]
        for mode in ("dark", "light"):
            icon_path = repo_root / "assets" / "icons" / f"{slug}-{mode}.svg"
            icon_inner = _extract_icon_inner(icon_path)
            files[repo_root / "assets" / "cards" / f"{slug}-{mode}.svg"] = render_project_card_svg(
                proj, profile["handle"], icon_inner, mode
            )
    return files


def check_static(repo_root: pathlib.Path, profile: dict[str, Any], dynamic_assets_base: str) -> list[str]:
    """Run zero-drift, WCAG AA, and static SVG/XML checks without writing files."""
    errors: list[str] = []
    errors.extend(validate_all_palettes_wcag())

    expected_files = _expected_generated_files(repo_root, profile, dynamic_assets_base)
    for path, expected in expected_files.items():
        if not path.exists():
            errors.append(f"Missing generated file: {path}")
            continue
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            diff = "".join(
                difflib.unified_diff(
                    actual.splitlines(keepends=True),
                    expected.splitlines(keepends=True),
                    fromfile=str(path),
                    tofile=f"{path} (expected)",
                    n=2,
                )
            )
            errors.append(f"Drift detected in {path}:\n{diff[:1200]}")

    svg_rel_paths = list(STATIC_ICON_FILES) + [
        "assets/stack-3d-dark.svg",
        "assets/stack-3d-light.svg",
    ] + [
        f"assets/cards/{proj['slug']}-{mode}.svg"
        for proj in profile["projects"]
        for mode in ("dark", "light")
    ]
    for rel in svg_rel_paths:
        p = repo_root / rel
        if not p.exists():
            errors.append(f"Missing static SVG: {rel}")
            continue
        errors.extend(validate_svg_document(p.read_text(encoding="utf-8"), rel))

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or verify static Layer 1 README, stack, and project card SVGs.")
    parser.add_argument("--profile", default="profile.json", help="Path to profile.json")
    parser.add_argument("--repo-root", default=".", help="Repository root directory")
    parser.add_argument(
        "--dynamic-assets-base",
        default=None,
        help="Override base path/URL for dynamic Hero and Skyline SVGs (defaults to profile.json dynamic_assets_base)",
    )
    parser.add_argument("--check", action="store_true", help="Verify zero drift, WCAG AA, and static SVGs")
    args = parser.parse_args(argv)

    repo_root = pathlib.Path(args.repo_root).resolve()
    profile_path = pathlib.Path(args.profile)
    if not profile_path.is_absolute():
        profile_path = repo_root / profile_path

    profile = load_profile(profile_path)
    base = args.dynamic_assets_base if args.dynamic_assets_base is not None else profile["dynamic_assets_base"]

    if args.check:
        errors = check_static(repo_root, profile, base)
        if errors:
            for err in errors:
                print(err, file=sys.stderr)
            return 1
        print("OK: zero drift, WCAG AA pass, and all 34 static SVGs valid.")
        return 0

    wcag_errors = validate_all_palettes_wcag()
    if wcag_errors:
        for err in wcag_errors:
            print(err, file=sys.stderr)
        return 1

    expected_files = _expected_generated_files(repo_root, profile, base)
    for path, content in expected_files.items():
        if path.suffix == ".svg":
            svg_errors = validate_svg_document(content, path.name)
            if svg_errors:
                for err in svg_errors:
                    print(err, file=sys.stderr)
                return 1

    for path, content in expected_files.items():
        write_text_lf(path, content)

    readme_bytes = len(expected_files[repo_root / "README.md"])
    print(f"Wrote README.md ({readme_bytes} bytes), stack-3d SVGs, and 12 bento project card SVGs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
