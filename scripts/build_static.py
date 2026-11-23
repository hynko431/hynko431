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


def _wrap_items(items: list[str], max_chars: int = 76) -> list[str]:
    """Wrap tech stack items across at most two balanced lines."""
    sep = "  ·  "
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


def render_stack_svg(profile: dict[str, Any], mode: str) -> str:
    """Render deterministic 4-tier Tech Stack Architecture SVG (01 -> 04)."""
    pal = get_theme_palette("baseline", mode)
    tiers = profile["tech_stack_tiers"]
    accents = STACK_TIER_ACCENTS[mode]
    card_bg = "#161B22" if mode == "dark" else "#FFFFFF"
    card_stroke = "#30363D" if mode == "dark" else "#D0D7DE"
    pill_bg = "#0D1117" if mode == "dark" else "#F4F7FB"

    row_blocks: list[str] = []
    for i, tier in enumerate(tiers):
        y = 52 + i * 76
        idx = tier["index"]
        accent = accents[idx]
        label = xml_escape(tier["label"])
        wrapped = _wrap_items(tier["items"])

        if len(wrapped) == 1:
            items_svg = (
                f'    <text x="356" y="{y + 37}" class="items">{xml_escape(wrapped[0])}</text>'
            )
        else:
            items_svg = (
                f'    <text x="356" y="{y + 27}" class="items">{xml_escape(wrapped[0])}</text>\n'
                f'    <text x="356" y="{y + 47}" class="items">{xml_escape(wrapped[1])}</text>'
            )

        row_blocks.append(
            f'  <g>\n'
            f'    <rect x="24" y="{y}" width="1072" height="66" rx="10" fill="{card_bg}" stroke="{card_stroke}" stroke-width="1"/>\n'
            f'    <rect x="24" y="{y}" width="5" height="66" rx="2.5" fill="{accent}"/>\n'
            f'    <rect x="44" y="{y + 18}" width="32" height="28" rx="6" fill="{pill_bg}" stroke="{card_stroke}" stroke-width="1"/>\n'
            f'    <text x="60" y="{y + 36}" text-anchor="middle" class="tier-idx" fill="{accent}">{xml_escape(idx)}</text>\n'
            f'    <text x="88" y="{y + 37}" class="tier-label" fill="{accent}">{label}</text>\n'
            f'    <line x1="340" y1="{y + 14}" x2="340" y2="{y + 52}" stroke="{card_stroke}" stroke-width="1"/>\n'
            f'{items_svg}\n'
            f'  </g>'
        )

    desc_summary = "; ".join(f"{t['index']} {t['label']}: {', '.join(t['items'])}" for t in tiers)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 364" width="1120" height="364" '
        f'role="img" aria-labelledby="stack-title stack-desc">\n'
        f'  <title id="stack-title">Tech Stack Architecture — {xml_escape(profile["handle"])}</title>\n'
        f'  <desc id="stack-desc">{xml_escape(desc_summary)}</desc>\n'
        f'  <defs>\n'
        f'    <linearGradient id="st-bg" x1="0%" y1="0%" x2="100%" y2="100%">\n'
        f'      <stop offset="0%" stop-color="{pal["bg0"]}"/>\n'
        f'      <stop offset="100%" stop-color="{pal["bg1"]}"/>\n'
        f'    </linearGradient>\n'
        f'    <style>\n'
        f'      .eyebrow {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 11px; font-weight: 600; letter-spacing: 1.3px; fill: {pal["eyebrow"]}; }}\n'
        f'      .meta {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 11px; fill: {pal["muted"]}; }}\n'
        f'      .tier-idx {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 12px; font-weight: 700; }}\n'
        f'      .tier-label {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; font-size: 14px; font-weight: 700; }}\n'
        f'      .items {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 12.5px; fill: {pal["title"]}; }}\n'
        f'    </style>\n'
        f'  </defs>\n'
        f'  <rect x="0.5" y="0.5" width="1119" height="363" rx="14" fill="url(#st-bg)" stroke="{pal["border"]}" stroke-width="1"/>\n'
        f'  <text x="26" y="33" class="eyebrow">TECH STACK ARCHITECTURE · 01 TO 04</text>\n'
        f'  <text x="1094" y="33" text-anchor="end" class="meta">@{xml_escape(profile["handle"])}</text>\n'
        + "\n".join(row_blocks)
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

    for proj in profile["projects"]:
        slug = proj["slug"]
        icon_pic = _picture(
            f"./assets/icons/{slug}-dark.svg",
            f"./assets/icons/{slug}-light.svg",
            f'{proj["name"]} icon',
            width="48",
            height="48",
        )
        stack_html = " ".join(f"<code>{xml_escape(tech)}</code>" for tech in proj["stack"])
        link_parts = [f'<a href={xml_attr(proj["links"]["code"])}>Code</a>']
        if proj["links"].get("docs"):
            link_parts.append(f'<a href={xml_attr(proj["links"]["docs"])}>Docs</a>')
        if proj["links"].get("live"):
            link_parts.append(f'<a href={xml_attr(proj["links"]["live"])}>Live</a>')
        links_html = " · ".join(link_parts)

        lines.extend(
            [
                "    <tr>",
                f'      <td align="center" width="64">{icon_pic}</td>',
                "      <td>",
                f'        <strong>{xml_escape(proj["name"])}</strong> — <em>{xml_escape(proj["category"])}</em><br/>',
                f'        {xml_escape(proj["summary"])}<br/>',
                f"        {stack_html}<br/>",
                f"        {links_html}",
                "      </td>",
                "    </tr>",
            ]
        )

    other_parts = [
        f'[{op["name"]}]({op["url"]}) *({op["note"]})*' for op in profile["other_projects"]
    ]
    stack_pic = _picture(
        "./assets/stack-3d-dark.svg",
        "./assets/stack-3d-light.svg",
        f"Four-tier Tech Stack Architecture for {handle}",
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
