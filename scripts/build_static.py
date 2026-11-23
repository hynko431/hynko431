#!/usr/bin/env python3
"""Offline deterministic static generator and CI drift/SVG/WCAG verifier.

Generates README.md and assets/stack-3d-{dark,light}.svg from profile.json
using Python 3.12 standard library only.
"""

from __future__ import annotations

import argparse
import difflib
import pathlib
import sys
from typing import Any

from scripts.profile_core import (
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

    # Floor shadow under foundation slab (tier 04)
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

    # Vertical architectural spine connectors linking tiers 01..04
    spine_lines = [
        f'  <line x1="{cx:.1f}" y1="{cy_list[0]:.1f}" x2="{cx:.1f}" y2="{cy_list[-1] + slab_h:.1f}" stroke="{pillar_color}" stroke-width="1.2" stroke-dasharray="4 4"/>',
        f'  <line x1="{cx - rx * 0.62:.1f}" y1="{cy_list[0]:.1f}" x2="{cx - rx * 0.62:.1f}" y2="{cy_list[-1]:.1f}" stroke="{pillar_color}" stroke-width="1" stroke-dasharray="3 5" opacity="0.8"/>',
        f'  <line x1="{cx + rx * 0.62:.1f}" y1="{cy_list[0]:.1f}" x2="{cx + rx * 0.62:.1f}" y2="{cy_list[-1]:.1f}" stroke="{pillar_color}" stroke-width="1" stroke-dasharray="3 5" opacity="0.8"/>',
    ]

    # Render 3D isometric slabs bottom-to-top (04 -> 01) for authentic 3D occlusion
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

        # Subtle 3x3 isometric architectural grid lines on top face
        grid_lines: list[str] = []
        for frac in (0.28, 0.56, 0.80):
            # Parallel to top-right edge
            ax = p_top[0] + (p_left[0] - p_top[0]) * frac
            ay = p_top[1] + (p_left[1] - p_top[1]) * frac
            bx = p_right[0] + (p_bottom[0] - p_right[0]) * frac
            by = p_right[1] + (p_bottom[1] - p_right[1]) * frac
            grid_lines.append(
                f'    <line x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}" stroke="{st["grid"]}" stroke-width="0.7" opacity="0.65"/>'
            )
            # Parallel to top-left edge
            cx1 = p_top[0] + (p_right[0] - p_top[0]) * frac
            cy1 = p_top[1] + (p_right[1] - p_top[1]) * frac
            dx1 = p_left[0] + (p_bottom[0] - p_left[0]) * frac
            dy1 = p_left[1] + (p_bottom[1] - p_left[1]) * frac
            grid_lines.append(
                f'    <line x1="{cx1:.1f}" y1="{cy1:.1f}" x2="{dx1:.1f}" y2="{dy1:.1f}" stroke="{st["grid"]}" stroke-width="0.7" opacity="0.65"/>'
            )

        # Compact architectural node markers + centered tier badge on slab face
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

    # Right-side callout cards + precision leader lines aligned 1:1 with slabs 01..04
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
            "<table>",
            "  <tbody>",
        ]
    )

    projects = profile["projects"]
    for row_start in range(0, len(projects), 2):
        pair = projects[row_start : row_start + 2]
        lines.append("    <tr>")
        for proj in pair:
            slug = proj["slug"]
            icon_pic = _picture(
                f"./assets/icons/{slug}-dark.svg",
                f"./assets/icons/{slug}-light.svg",
                f'{proj["name"]} icon',
                width="44",
                height="44",
            )
            stack_html = " ".join(f"<code>{xml_escape(tech)}</code>" for tech in proj["stack"])
            code_url = proj["links"]["code"]
            link_parts = [f'<a href={xml_attr(code_url)}>Code</a>']
            if proj["links"].get("docs"):
                link_parts.append(f'<a href={xml_attr(proj["links"]["docs"])}>Docs</a>')
            if proj["links"].get("live"):
                link_parts.append(f'<a href={xml_attr(proj["links"]["live"])}>Live</a>')
            links_html = " · ".join(link_parts)

            lines.extend(
                [
                    '      <td width="50%" valign="top">',
                    f'        <a href={xml_attr(code_url)}>{icon_pic}</a><br/>',
                    f'        <strong><a href={xml_attr(code_url)}>{xml_escape(proj["name"])}</a></strong><br/>',
                    f'        <em>{xml_escape(proj["category"])}</em><br/><br/>',
                    f'        {xml_escape(proj["summary"])}<br/><br/>',
                    f"        {stack_html}<br/><br/>",
                    f"        {links_html}",
                    "      </td>",
                ]
            )
        if len(pair) == 1:
            lines.append('      <td width="50%" valign="top"></td>')
        lines.append("    </tr>")

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

    lines.extend(
        [
            "  </tbody>",
            "</table>",
            "",
            f'*Also built:* {" · ".join(other_parts)} — [View all repositories →](https://github.com/{handle}?tab=repositories) · [Filter Projects in 3D Explorer →]({explorer}#projects)',
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
            "<details>",
            "<summary>Plain-text stack index (Tiers 01–04)</summary>",
            "",
            "| Tier | Category | Technologies |",
            "| :--- | :--- | :--- |",
        ]
    )

    for tier in profile["tech_stack_tiers"]:
        techs = ", ".join(f"`{t}`" for t in tier["items"])
        lines.append(f'| `{tier["index"]}` | **{tier["label"]}** | {techs} |')

    lines.extend(
        [
            "",
            "</details>",
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


def check_static(repo_root: pathlib.Path, profile: dict[str, Any], dynamic_assets_base: str) -> list[str]:
    """Run zero-drift, WCAG AA, and static SVG/XML checks without writing files."""
    errors: list[str] = []
    errors.extend(validate_all_palettes_wcag())

    expected_files: dict[pathlib.Path, str] = {
        repo_root / "README.md": render_readme(profile, dynamic_assets_base),
        repo_root / "assets" / "stack-3d-dark.svg": render_stack_svg(profile, "dark"),
        repo_root / "assets" / "stack-3d-light.svg": render_stack_svg(profile, "light"),
    }
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
    ]
    for rel in svg_rel_paths:
        p = repo_root / rel
        if not p.exists():
            errors.append(f"Missing static SVG: {rel}")
            continue
        errors.extend(validate_svg_document(p.read_text(encoding="utf-8"), rel))

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or verify static Layer 1 README and stack SVGs.")
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
        print("OK: zero drift, WCAG AA pass, and all 22 static SVGs valid.")
        return 0

    wcag_errors = validate_all_palettes_wcag()
    if wcag_errors:
        for err in wcag_errors:
            print(err, file=sys.stderr)
        return 1

    readme = render_readme(profile, base)
    stack_dark = render_stack_svg(profile, "dark")
    stack_light = render_stack_svg(profile, "light")

    for name, svg in (("stack-3d-dark.svg", stack_dark), ("stack-3d-light.svg", stack_light)):
        svg_errors = validate_svg_document(svg, name)
        if svg_errors:
            for err in svg_errors:
                print(err, file=sys.stderr)
            return 1

    write_text_lf(repo_root / "README.md", readme)
    write_text_lf(repo_root / "assets" / "stack-3d-dark.svg", stack_dark)
    write_text_lf(repo_root / "assets" / "stack-3d-light.svg", stack_light)
    print(f"Wrote README.md ({len(readme)} bytes) and assets/stack-3d-{{dark,light}}.svg")
    return 0


if __name__ == "__main__":
    sys.exit(main())
