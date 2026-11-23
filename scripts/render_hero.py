"""Dynamic Hero Banner SVG renderer (Python 3.12 stdlib only).

Renders viewBox="0 0 1080 270" dark/light banners with seasonal geometric
accents confined to the right-column isometric beacon when theme != baseline.
"""

from __future__ import annotations

from typing import Any

from scripts.profile_core import get_theme_palette, xml_escape


def _seasonal_motifs(theme_name: str, pal: dict[str, Any]) -> str:
    """Render bounded geometric seasonal motifs inside x=720..1032, y=24..254."""
    if theme_name == "baseline":
        return ""
    eyebrow = pal["eyebrow"]
    accent = pal["accent"]
    cap = pal["peak_cap"]

    if theme_name == "new_year":
        return (
            f'    <g opacity="0.72" stroke-width="1.4" stroke-linecap="round">\n'
            f'      <path d="M758 46V60M751 53H765" stroke="{eyebrow}"/>\n'
            f'      <path d="M994 42V58M986 50H1002" stroke="{accent}"/>\n'
            f'      <path d="M1014 102V112M1009 107H1019" stroke="{cap}"/>\n'
            f'      <circle cx="776" cy="84" r="2.2" fill="{cap}"/>\n'
            f'      <circle cx="968" cy="76" r="2" fill="{eyebrow}"/>\n'
            f'    </g>\n'
        )
    if theme_name == "diwali":
        return (
            f'    <g opacity="0.75" stroke-width="1.3" stroke-linejoin="round">\n'
            f'      <polygon points="756,52 762,62 756,70 750,62" fill="{eyebrow}" stroke="{cap}"/>\n'
            f'      <polygon points="996,46 1002,56 996,64 990,56" fill="{accent}" stroke="{cap}"/>\n'
            f'      <polygon points="1010,132 1015,140 1010,147 1005,140" fill="{eyebrow}" stroke="{cap}"/>\n'
            f'    </g>\n'
        )
    if theme_name == "halloween":
        return (
            f'    <g opacity="0.72" fill="none" stroke-width="1.4" stroke-linecap="round">\n'
            f'      <path d="M998 44A14 14 0 1 0 1010 64A10.5 10.5 0 1 1 998 44Z" fill="{eyebrow}" stroke="{eyebrow}"/>\n'
            f'      <polyline points="746,66 766,54 786,62" stroke="{accent}" stroke-dasharray="2.5 3"/>\n'
            f'      <circle cx="746" cy="66" r="2.2" fill="{accent}"/>\n'
            f'      <circle cx="766" cy="54" r="2.2" fill="{eyebrow}"/>\n'
            f'      <circle cx="786" cy="62" r="2.2" fill="{accent}"/>\n'
            f'    </g>\n'
        )
    if theme_name == "christmas":
        return (
            f'    <g opacity="0.74" stroke-width="1.4" stroke-linejoin="round">\n'
            f'      <polygon points="758,42 768,62 748,62" fill="none" stroke="{eyebrow}"/>\n'
            f'      <polygon points="996,40 1007,62 985,62" fill="none" stroke="{eyebrow}"/>\n'
            f'      <polygon points="1012,118 1020,134 1004,134" fill="none" stroke="{accent}"/>\n'
            f'      <circle cx="758" cy="40" r="2.2" fill="{accent}"/>\n'
            f'      <circle cx="996" cy="38" r="2.2" fill="{accent}"/>\n'
            f'    </g>\n'
        )
    return ""


def _iso_slab(cx: float, cy: float, rx: float, ry: float, h: float, top_c: str, left_c: str, right_c: str, stroke_c: str) -> str:
    p_top = f"{cx:.1f},{cy - ry:.1f} {cx + rx:.1f},{cy:.1f} {cx:.1f},{cy + ry:.1f} {cx - rx:.1f},{cy:.1f}"
    p_left = f"{cx - rx:.1f},{cy:.1f} {cx:.1f},{cy + ry:.1f} {cx:.1f},{cy + ry + h:.1f} {cx - rx:.1f},{cy + h:.1f}"
    p_right = f"{cx:.1f},{cy + ry:.1f} {cx + rx:.1f},{cy:.1f} {cx + rx:.1f},{cy + h:.1f} {cx:.1f},{cy + ry + h:.1f}"
    return (
        f'    <polygon points="{p_left}" fill="{left_c}" stroke="{stroke_c}" stroke-width="0.9" stroke-linejoin="round"/>\n'
        f'    <polygon points="{p_right}" fill="{right_c}" stroke="{stroke_c}" stroke-width="0.9" stroke-linejoin="round"/>\n'
        f'    <polygon points="{p_top}" fill="{top_c}" stroke="{stroke_c}" stroke-width="0.9" stroke-linejoin="round"/>\n'
    )


def render_hero_svg(profile: dict[str, Any], theme_name: str, mode: str) -> str:
    """Render dynamic Hero Banner SVG (1080x270) for (theme_name, mode)."""
    pal = get_theme_palette(theme_name, mode)
    lvl1 = pal["levels"]["1"]
    lvl2 = pal["levels"]["2"]
    lvl3 = pal["levels"]["3"]
    lvl4 = pal["levels"]["4"]

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

    # Right column isometric 3-tier beacon strictly inside x=720..1032, y=24..254
    cx = 876.0
    beacon = (
        f'    <polygon points="750.0,196.0 876.0,144.0 1002.0,196.0 876.0,252.0" fill="{pal["shadow_color"]}" opacity="{pal["shadow_opacity_outer"]}"/>\n'
        + _iso_slab(cx, 192.0, 118.0, 46.0, 12.0, pal["plinth_top"], pal["plinth_left"], pal["plinth_right"], pal["plinth_stroke"])
        + _iso_slab(cx, 152.0, 86.0, 34.0, 11.0, lvl1[0], lvl1[1], lvl1[2], lvl1[3])
        + _iso_slab(cx, 114.0, 64.0, 25.0, 10.0, lvl2[0], lvl2[1], lvl2[2], lvl2[3])
        + _iso_slab(cx, 78.0, 44.0, 17.0, 9.0, lvl3[0], lvl3[1], lvl3[2], lvl3[3])
        + _iso_slab(cx, 50.0, 18.0, 8.0, 16.0, lvl4[0], lvl4[1], lvl4[2], lvl4[3])
        + f'    <line x1="{cx:.1f}" y1="152.0" x2="{cx:.1f}" y2="66.0" stroke="{pal["accent"]}" stroke-width="1.0" stroke-dasharray="3 4" opacity="0.55"/>\n'
        + _seasonal_motifs(theme_name, pal)
    )

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
        f'    <radialGradient id="h-glow" cx="80%" cy="46%" r="44%">\n'
        f'      <stop offset="0%" stop-color="{pal["glow"]}" stop-opacity="0.16"/>\n'
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
        + beacon
        + f'  </g>\n'
        f'</svg>\n'
    )
