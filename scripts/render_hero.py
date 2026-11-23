"""Dynamic Hero Banner SVG renderer (Python 3.12 stdlib only).

Renders viewBox="0 0 1080 270" dark/light banners featuring a bespoke
isometric hexagonal AI-Backend-RAG-Security constellation artwork on the right
with seasonal geometric accents when theme != baseline.
"""

from __future__ import annotations

import math
from typing import Any

from scripts.profile_core import get_theme_palette, xml_escape


def _seasonal_motifs(theme_name: str, pal: dict[str, Any]) -> str:
    """Render bounded geometric seasonal motifs inside x=712..1046, y=22..254."""
    if theme_name == "baseline":
        return ""
    eyebrow = pal["eyebrow"]
    accent = pal["accent"]
    cap = pal["peak_cap"]

    if theme_name == "new_year":
        return (
            f'    <g opacity="0.78" stroke-width="1.4" stroke-linecap="round">\n'
            f'      <path d="M736 38V52M729 45H743" stroke="{eyebrow}"/>\n'
            f'      <path d="M1018 36V52M1010 44H1026" stroke="{accent}"/>\n'
            f'      <path d="M1028 214V226M1022 220H1034" stroke="{cap}"/>\n'
            f'      <circle cx="842" cy="34" r="2.2" fill="{cap}"/>\n'
            f'      <circle cx="944" cy="232" r="2.1" fill="{eyebrow}"/>\n'
            f'    </g>\n'
        )
    if theme_name == "diwali":
        return (
            f'    <g opacity="0.82" stroke-width="1.25" stroke-linejoin="round">\n'
            f'      <polygon points="736,36 742,46 736,54 730,46" fill="{eyebrow}" stroke="{cap}"/>\n'
            f'      <polygon points="1018,34 1024,44 1018,52 1012,44" fill="{accent}" stroke="{cap}"/>\n'
            f'      <polygon points="1024,212 1029,220 1024,227 1019,220" fill="{eyebrow}" stroke="{cap}"/>\n'
            f'    </g>\n'
        )
    if theme_name == "halloween":
        return (
            f'    <g opacity="0.78" fill="none" stroke-width="1.4" stroke-linecap="round">\n'
            f'      <path d="M1014 36A13 13 0 1 0 1026 55A9.8 9.8 0 1 1 1014 36Z" fill="{eyebrow}" stroke="{eyebrow}"/>\n'
            f'      <polyline points="724,44 742,34 758,42" stroke="{accent}" stroke-dasharray="2.5 3"/>\n'
            f'      <circle cx="724" cy="44" r="2.1" fill="{accent}"/>\n'
            f'      <circle cx="742" cy="34" r="2.1" fill="{eyebrow}"/>\n'
            f'    </g>\n'
        )
    if theme_name == "christmas":
        return (
            f'    <g opacity="0.78" stroke-width="1.4" stroke-linejoin="round">\n'
            f'      <polygon points="736,32 746,52 726,52" fill="none" stroke="{eyebrow}"/>\n'
            f'      <polygon points="1018,30 1028,52 1008,52" fill="none" stroke="{eyebrow}"/>\n'
            f'      <circle cx="736" cy="30" r="2.2" fill="{accent}"/>\n'
            f'      <circle cx="1018" cy="28" r="2.2" fill="{accent}"/>\n'
            f'    </g>\n'
        )
    return ""


def _hex_pts(cx: float, cy: float, rx: float, ry: float) -> list[tuple[float, float]]:
    """Return 6 isometric-flattened hexagon vertices starting at right (0 deg)."""
    pts: list[tuple[float, float]] = []
    for k in range(6):
        ang = math.radians(k * 60.0)
        pts.append((cx + rx * math.cos(ang), cy + ry * math.sin(ang)))
    return pts


def _fmt(pts: list[tuple[float, float]]) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)


def _hex_prism(
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    depth: float,
    top_fill: str,
    front_left: str,
    front_mid: str,
    front_right: str,
    stroke: str,
    stroke_w: float = 1.25,
) -> str:
    """Render an extruded 3D isometric hexagonal prism (top + 3 front walls)."""
    top = _hex_pts(cx, cy, rx, ry)
    bot = [(x, y + depth) for x, y in top]
    # Front-facing edges in screen space (y downwards): 0->1 (right-front), 1->2 (bottom-front), 2->3 (left-front)
    w_right = [top[0], top[1], bot[1], bot[0]]
    w_mid = [top[1], top[2], bot[2], bot[1]]
    w_left = [top[2], top[3], bot[3], bot[2]]
    return (
        f'    <polygon points="{_fmt(w_left)}" fill="{front_left}" stroke="{stroke}" stroke-width="0.9" stroke-linejoin="round"/>\n'
        f'    <polygon points="{_fmt(w_mid)}" fill="{front_mid}" stroke="{stroke}" stroke-width="0.9" stroke-linejoin="round"/>\n'
        f'    <polygon points="{_fmt(w_right)}" fill="{front_right}" stroke="{stroke}" stroke-width="0.9" stroke-linejoin="round"/>\n'
        f'    <polygon points="{_fmt(top)}" fill="{top_fill}" stroke="{stroke}" stroke-width="{stroke_w}" stroke-linejoin="round"/>\n'
    )


def _build_constellation(theme_name: str, mode: str, pal: dict[str, Any]) -> str:
    """Render bespoke Distributed AI Core + API / RAG / SEC satellite constellation (x=706..1054, y=22..254)."""
    cx, cy = 882.0, 128.0
    lvl0 = pal["levels"]["0"]
    lvl1 = pal["levels"]["1"]
    lvl2 = pal["levels"]["2"]
    lvl3 = pal["levels"]["3"]
    lvl4 = pal["levels"]["4"]
    accent = pal["accent"]
    eyebrow = pal["eyebrow"]
    cap = pal["peak_cap"]
    surface = pal["hud_bg"]
    border = pal["border"]
    muted = pal["muted"]
    ring_stroke = "#26364D" if mode == "dark" else "#C8D7EA"
    core_inner = "#0D1A2B" if mode == "dark" else "#F4F9FF"

    # Outer orbital telemetry ring & blueprint coordinate crosshairs
    orbital_plane = (
        f'    <ellipse cx="{cx:.1f}" cy="{cy + 16:.1f}" rx="152" ry="74" fill="none" stroke="{ring_stroke}" stroke-width="1" stroke-dasharray="4 5"/>\n'
        f'    <ellipse cx="{cx:.1f}" cy="{cy + 16:.1f}" rx="108" ry="52" fill="none" stroke="{eyebrow}" stroke-width="1" stroke-opacity="0.32"/>\n'
        f'    <line x1="726" y1="{cy + 16:.1f}" x2="1038" y2="{cy + 16:.1f}" stroke="{ring_stroke}" stroke-width="0.8" opacity="0.6"/>\n'
        f'    <line x1="{cx:.1f}" y1="42" x2="{cx:.1f}" y2="238" stroke="{ring_stroke}" stroke-width="0.8" opacity="0.6"/>\n'
    )

    # Isometric PCB data-bus traces connecting the 3 domain satellites to the hexagonal AI Core
    traces = (
        f'    <g fill="none" stroke-width="1.45" stroke-linecap="round" stroke-linejoin="round">\n'
        # API (top-left) -> Core
        f'      <polyline points="776,78 824,78 848,104" stroke="{eyebrow}"/>\n'
        f'      <circle cx="824" cy="78" r="2.6" fill="{cap}"/>\n'
        # RAG (bottom-left) -> Core
        f'      <polyline points="784,198 830,198 854,166" stroke="{accent}"/>\n'
        f'      <circle cx="830" cy="198" r="2.6" fill="{accent}"/>\n'
        # Core -> SEC (right)
        f'      <polyline points="932,128 968,128" stroke="{cap}"/>\n'
        f'      <circle cx="952" cy="128" r="2.5" fill="{cap}"/>\n'
        # Subtle feedback arc from SEC -> top telemetry node
        f'      <path d="M994 106C986 72 946 56 908 62" stroke="{eyebrow}" stroke-dasharray="3 3.5" opacity="0.65"/>\n'
        f'      <circle cx="908" cy="62" r="2.3" fill="{eyebrow}"/>\n'
        f'    </g>\n'
    )

    # Centerpiece: Extruded 3D Hexagonal AI Agent Core
    core_shadow = f'    <polygon points="{_fmt(_hex_pts(cx, cy + 38.0, 56.0, 30.0))}" fill="{pal["shadow_color"]}" opacity="{pal["shadow_opacity_inner"]}"/>\n'
    core_base = _hex_prism(cx, cy + 16.0, 56.0, 30.0, 12.0, pal["plinth_top"], pal["plinth_left"], pal["plinth_right"], pal["plinth_left"], pal["plinth_stroke"], 1.0)
    core_prism = _hex_prism(cx, cy - 4.0, 44.0, 24.0, 18.0, lvl1[0], lvl2[1], lvl1[2], lvl2[2], accent, 1.35)

    # Inner neural lattice & floating central prism crystal on top of core
    inner_hex = _hex_pts(cx, cy - 4.0, 26.0, 14.0)
    lattice_lines = []
    for k in range(6):
        p = inner_hex[k]
        p_opp = inner_hex[(k + 2) % 6]
        lattice_lines.append(
            f'    <line x1="{p[0]:.1f}" y1="{p[1]:.1f}" x2="{p_opp[0]:.1f}" y2="{p_opp[1]:.1f}" stroke="{cap}" stroke-width="0.85" opacity="0.65"/>'
        )
    lattice_nodes = [
        f'    <circle cx="{x:.1f}" cy="{y:.1f}" r="2.1" fill="{cap}"/>' for x, y in inner_hex
    ]
    core_gem = _hex_prism(cx, cy - 18.0, 14.0, 7.5, 11.0, lvl4[0], lvl3[1], lvl4[2], lvl3[2], cap, 1.1)
    core_detail = (
        f'    <polygon points="{_fmt(inner_hex)}" fill="{core_inner}" stroke="{eyebrow}" stroke-width="0.9" opacity="0.92"/>\n'
        + "\n".join(lattice_lines)
        + "\n"
        + "\n".join(lattice_nodes)
        + "\n"
        + core_gem
    )

    # Satellite 1 (Top-Left): API / Async Queue Gateway node
    sat_api = (
        f'    <g>\n'
        + _hex_prism(756.0, 76.0, 26.0, 15.0, 10.0, surface, lvl1[1], lvl1[2], lvl0[2], eyebrow, 1.15)
        + f'      <rect x="744" y="71" width="5" height="9" rx="1" fill="{eyebrow}"/>\n'
        f'      <rect x="752" y="67" width="5" height="13" rx="1" fill="{accent}"/>\n'
        f'      <rect x="760" y="63" width="5" height="17" rx="1" fill="{cap}"/>\n'
        f'      <text x="756" y="114" text-anchor="middle" class="node-lbl">API · QUEUE</text>\n'
        f'    </g>\n'
    )

    # Satellite 2 (Bottom-Left): RAG / Vector + Relational DB stacked disc cylinder
    sat_rag = (
        f'    <g>\n'
        f'      <ellipse cx="760" cy="212" rx="22" ry="9" fill="{lvl1[2]}" stroke="{accent}" stroke-width="1"/>\n'
        f'      <rect x="738" y="201" width="44" height="11" fill="{lvl1[1]}"/>\n'
        f'      <ellipse cx="760" cy="201" rx="22" ry="9" fill="{lvl2[0]}" stroke="{accent}" stroke-width="1"/>\n'
        f'      <rect x="738" y="190" width="44" height="11" fill="{lvl2[1]}"/>\n'
        f'      <ellipse cx="760" cy="190" rx="22" ry="9" fill="{lvl3[0]}" stroke="{cap}" stroke-width="1.15"/>\n'
        f'      <circle cx="752" cy="190" r="1.8" fill="{core_inner}"/>\n'
        f'      <circle cx="760" cy="190" r="1.8" fill="{core_inner}"/>\n'
        f'      <circle cx="768" cy="190" r="1.8" fill="{core_inner}"/>\n'
        f'      <text x="760" y="236" text-anchor="middle" class="node-lbl">RAG · VECTOR</text>\n'
        f'    </g>\n'
    )

    # Satellite 3 (Right): SEC / Rust & Coldpin Supply-Chain Shield node
    sat_sec = (
        f'    <g>\n'
        + _hex_prism(996.0, 128.0, 27.0, 16.0, 11.0, surface, lvl2[1], lvl1[2], lvl0[2], accent, 1.2)
        + f'      <path d="M996 116L1005 120V127C1005 132.2 1001 135.8 996 137.8C991 135.8 987 132.2 987 127V120L996 116Z" fill="{lvl1[0]}" stroke="{cap}" stroke-width="1.4" stroke-linejoin="round"/>\n'
        f'      <path d="M992.5 127.2L995.2 129.8L1000 124.5" fill="none" stroke="{cap}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>\n'
        f'      <text x="996" y="168" text-anchor="middle" class="node-lbl">RUST · SEC</text>\n'
        f'    </g>\n'
    )

    # Core label pill at bottom of core
    core_badge = (
        f'    <rect x="{cx - 40:.1f}" y="196" width="80" height="19" rx="5" fill="{surface}" stroke="{border}" stroke-width="1"/>\n'
        f'    <text x="{cx:.1f}" y="209" text-anchor="middle" class="core-lbl" fill="{accent}">AGENT CORE</text>\n'
    )

    return (
        orbital_plane
        + traces
        + core_shadow
        + core_base
        + core_prism
        + core_detail
        + sat_api
        + sat_rag
        + sat_sec
        + core_badge
        + _seasonal_motifs(theme_name, pal)
    )


def render_hero_svg(profile: dict[str, Any], theme_name: str, mode: str) -> str:
    """Render dynamic Hero Banner SVG (1080x270) for (theme_name, mode)."""
    pal = get_theme_palette(theme_name, mode)

    eyebrow = xml_escape(profile["role_headline"].upper())
    name = xml_escape(profile["name"])
    sub0 = xml_escape(profile["hero_subtitle_lines"][0])
    sub1 = xml_escape(profile["hero_subtitle_lines"][1])
    meta = xml_escape(f'@{profile["handle"]} · {profile["current_company"]} · {profile["location"]}')

    pill_widths = (154, 158, 152)
    pill_x = 48
    pills_svg: list[str] = []
    for pill_text, pw in zip(profile["hero_pills"], pill_widths):
        pills_svg.append(
            f'    <rect x="{pill_x}" y="172" width="{pw}" height="28" rx="7" fill="{pal["hud_bg"]}" stroke="{pal["hud_border"]}" stroke-width="1"/>\n'
            f'    <line x1="{pill_x + 8}" y1="172.8" x2="{pill_x + pw - 8}" y2="172.8" stroke="{pal["eyebrow"]}" stroke-opacity="0.45" stroke-width="1"/>\n'
            f'    <text x="{pill_x + pw / 2:.1f}" y="190" text-anchor="middle" class="pill">{xml_escape(pill_text)}</text>'
        )
        pill_x += pw + 10

    constellation = _build_constellation(theme_name, mode, pal)

    desc = xml_escape(
        f'{profile["name"]} — {profile["role_headline"]} at {profile["current_company"]}, {profile["location"]}.'
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 270" width="1080" height="270" '
        f'role="img" aria-labelledby="hero-title hero-desc">\n'
        f'  <title id="hero-title">{name} — {xml_escape(profile["role_headline"])}</title>\n'
        f'  <desc id="hero-desc">{desc}</desc>\n'
        f'  <defs>\n'
        f'    <linearGradient id="h-bg" x1="0%" y1="0%" x2="100%" y2="100%">\n'
        f'      <stop offset="0%" stop-color="{pal["bg0"]}"/>\n'
        f'      <stop offset="100%" stop-color="{pal["bg1"]}"/>\n'
        f'    </linearGradient>\n'
        f'    <radialGradient id="h-glow" cx="82%" cy="48%" r="42%">\n'
        f'      <stop offset="0%" stop-color="{pal["glow"]}" stop-opacity="0.18"/>\n'
        f'      <stop offset="100%" stop-color="{pal["bg0"]}" stop-opacity="0"/>\n'
        f'    </radialGradient>\n'
        f'    <pattern id="h-dots" width="24" height="24" patternUnits="userSpaceOnUse">\n'
        f'      <circle cx="2" cy="2" r="0.9" fill="{pal["grid_dot"]}" fill-opacity="0.42"/>\n'
        f'    </pattern>\n'
        f'    <style>\n'
        f'      .eyebrow {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 12px; font-weight: 700; letter-spacing: 1.3px; fill: {pal["eyebrow"]}; }}\n'
        f'      .name {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; font-size: 30px; font-weight: 800; letter-spacing: -0.4px; fill: {pal["title"]}; }}\n'
        f'      .sub {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; font-size: 15.5px; fill: {pal["muted"]}; }}\n'
        f'      .pill {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 12px; font-weight: 600; fill: {pal["hud_val"]}; }}\n'
        f'      .meta {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 12px; fill: {pal["muted"]}; }}\n'
        f'      .node-lbl {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 8.5px; font-weight: 700; letter-spacing: 0.8px; fill: {pal["muted"]}; }}\n'
        f'      .core-lbl {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 9px; font-weight: 700; letter-spacing: 0.9px; }}\n'
        f'    </style>\n'
        f'  </defs>\n'
        f'  <rect x="0.5" y="0.5" width="1079" height="269" rx="14" fill="url(#h-bg)" stroke="{pal["border"]}" stroke-width="1"/>\n'
        f'  <rect x="1" y="1" width="1078" height="268" rx="13.5" fill="url(#h-dots)"/>\n'
        f'  <rect x="1" y="1" width="1078" height="268" rx="13.5" fill="url(#h-glow)"/>\n'
        f'  <rect x="30" y="38" width="3" height="198" rx="1.5" fill="{pal["eyebrow"]}"/>\n'
        f'  <text x="48" y="52" class="eyebrow">{eyebrow}</text>\n'
        f'  <text x="48" y="94" class="name">{name}</text>\n'
        f'  <text x="48" y="126" class="sub">{sub0}</text>\n'
        f'  <text x="48" y="148" class="sub">{sub1}</text>\n'
        f'  <g>\n'
        + "\n".join(pills_svg)
        + f'\n  </g>\n'
        f'  <text x="48" y="236" class="meta">{meta}</text>\n'
        f'  <g>\n'
        + constellation
        + f'  </g>\n'
        f'</svg>\n'
    )
