"""Shared Python 3.12 standard-library core for hynko431 profile generation.

Provides manifest validation, fixed-offset IST seasonal theme resolution,
complete 5x2 WCAG AA color palettes, XML escaping, SVG/XML validation,
and deterministic LF file writing.
"""

from __future__ import annotations

import copy
import datetime as dt
import json
import pathlib
import re
import xml.etree.ElementTree as ET
from typing import Any
from xml.sax.saxutils import escape as _sax_escape
from xml.sax.saxutils import quoteattr as _sax_quoteattr

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

DIWALI_DATES: dict[int, dt.date] = {
    2026: dt.date(2026, 11, 8),
    2027: dt.date(2027, 10, 29),
    2028: dt.date(2028, 10, 17),
    2029: dt.date(2029, 11, 5),
    2030: dt.date(2030, 10, 26),
    2031: dt.date(2031, 11, 14),
    2032: dt.date(2032, 11, 2),
    2033: dt.date(2033, 10, 22),
    2034: dt.date(2034, 11, 10),
    2035: dt.date(2035, 10, 30),
}

THEME_NAMES: tuple[str, ...] = ("baseline", "new_year", "diwali", "halloween", "christmas")
MODES: tuple[str, ...] = ("dark", "light")
WCAG_FG_KEYS: tuple[str, ...] = ("eyebrow", "title", "muted", "hud_val", "accent")
WCAG_BG_KEYS: tuple[str, ...] = ("bg0", "bg1", "hud_bg")

STACK_TIER_ACCENTS: dict[str, dict[str, str]] = {
    "dark": {
        "01": "#58A6FF",
        "02": "#A5B4FC",
        "03": "#34D399",
        "04": "#FBBF24",
    },
    "light": {
        "01": "#0969DA",
        "02": "#4F46E5",
        "03": "#047857",
        "04": "#B45309",
    },
}

PROJECT_CARD_ACCENTS: dict[str, dict[str, str]] = {
    "dark": {
        "coldpin": "#58A6FF",
        "sentinel": "#FBBF24",
        "cutaway": "#A5B4FC",
        "helix": "#34D399",
        "autopilot": "#38BDF8",
        "medical": "#F472B6",
    },
    "light": {
        "coldpin": "#0969DA",
        "sentinel": "#B45309",
        "cutaway": "#4F46E5",
        "helix": "#047857",
        "autopilot": "#0369A1",
        "medical": "#BE185D",
    },
}

_BASE_TOKENS: dict[str, dict[str, Any]] = {
    "dark": {
        "bg0": "#0D1117",
        "bg1": "#111827",
        "hud_bg": "#161B22",
        "border": "#30363D",
        "grid_dot": "#30363D",
        "hud_border": "#30363D",
        "title": "#F0F6FC",
        "hud_val": "#F0F6FC",
        "muted": "#8B949E",
        "axis_text": "#8B949E",
        "plinth_top": "#131A26",
        "plinth_left": "#0C111A",
        "plinth_right": "#090D14",
        "plinth_stroke": "#263244",
        "shadow_color": "#000000",
        "shadow_opacity_inner": 0.22,
        "shadow_opacity_outer": 0.12,
    },
    "light": {
        "bg0": "#FFFFFF",
        "bg1": "#F4F7FB",
        "hud_bg": "#FFFFFF",
        "border": "#D0D7DE",
        "grid_dot": "#D0D7DE",
        "hud_border": "#D0D7DE",
        "title": "#1F2328",
        "hud_val": "#1F2328",
        "muted": "#57606A",
        "axis_text": "#57606A",
        "plinth_top": "#EEF3FA",
        "plinth_left": "#DCE5F2",
        "plinth_right": "#CBD7E8",
        "plinth_stroke": "#C6D3E5",
        "shadow_color": "#0F172A",
        "shadow_opacity_inner": 0.07,
        "shadow_opacity_outer": 0.04,
    },
}

_THEME_OVERRIDES: dict[str, dict[str, dict[str, Any]]] = {
    "baseline": {
        "dark": {
            "eyebrow": "#58A6FF",
            "accent": "#38BDF8",
            "glow": "#58A6FF",
            "peak_cap": "#A5F3FC",
            "levels": {
                "0": ["#182130", "#111824", "#0C111A", "#243044"],
                "1": ["#1F4B7A", "#15365A", "#0E2540", "#326BA6"],
                "2": ["#2D74C4", "#1F5698", "#153D6E", "#4D94E4"],
                "3": ["#58A6FF", "#3480DC", "#215EA8", "#8CC4FF"],
                "4": ["#5CE1FF", "#2EB4E6", "#1885B5", "#B5F3FF"],
            },
        },
        "light": {
            "eyebrow": "#0969DA",
            "accent": "#0369A1",
            "glow": "#0969DA",
            "peak_cap": "#38BDF8",
            "levels": {
                "0": ["#E2E8F0", "#CBD5E1", "#B8C4D4", "#F1F5F9"],
                "1": ["#93C5FD", "#60A5FA", "#3B82F6", "#BFDBFE"],
                "2": ["#3B82F6", "#2563EB", "#1D4ED8", "#60A5FA"],
                "3": ["#0969DA", "#0550AE", "#033D8B", "#38BDF8"],
                "4": ["#0284C7", "#0369A1", "#075985", "#7DD3FC"],
            },
        },
    },
    "new_year": {
        "dark": {
            "eyebrow": "#FBBF24",
            "accent": "#60A5FA",
            "glow": "#FBBF24",
            "peak_cap": "#FDE68A",
            "levels": {
                "0": ["#182130", "#111824", "#0C111A", "#243044"],
                "1": ["#1E3A5F", "#152A47", "#0E1D33", "#2F5485"],
                "2": ["#2563EB", "#1D4ED8", "#1E40AF", "#60A5FA"],
                "3": ["#60A5FA", "#3B82F6", "#2563EB", "#93C5FD"],
                "4": ["#FBBF24", "#D97706", "#B45309", "#FDE68A"],
            },
        },
        "light": {
            "eyebrow": "#92400E",
            "accent": "#1D4ED8",
            "glow": "#D97706",
            "peak_cap": "#F59E0B",
            "levels": {
                "0": ["#E2E8F0", "#CBD5E1", "#B8C4D4", "#F1F5F9"],
                "1": ["#BFDBFE", "#93C5FD", "#60A5FA", "#DBEAFE"],
                "2": ["#3B82F6", "#2563EB", "#1D4ED8", "#60A5FA"],
                "3": ["#1D4ED8", "#1E40AF", "#1E3A8A", "#3B82F6"],
                "4": ["#D97706", "#B45309", "#92400E", "#FBBF24"],
            },
        },
    },
    "diwali": {
        "dark": {
            "eyebrow": "#F59E0B",
            "accent": "#FBBF24",
            "glow": "#F59E0B",
            "peak_cap": "#FEF08A",
            "levels": {
                "0": ["#1F1B18", "#161311", "#100E0C", "#2E2823"],
                "1": ["#5C3414", "#45250D", "#331A08", "#7C471B"],
                "2": ["#B45309", "#92400E", "#78350F", "#D97706"],
                "3": ["#F59E0B", "#D97706", "#B45309", "#FBBF24"],
                "4": ["#FDE047", "#EAB308", "#CA8A04", "#FEF9C3"],
            },
        },
        "light": {
            "eyebrow": "#9A3412",
            "accent": "#B45309",
            "glow": "#D97706",
            "peak_cap": "#F59E0B",
            "levels": {
                "0": ["#E7E5E4", "#D6D3D1", "#C2BEB9", "#F5F5F4"],
                "1": ["#FDE68A", "#FCD34D", "#FBBF24", "#FEF3C7"],
                "2": ["#F59E0B", "#D97706", "#B45309", "#FBBF24"],
                "3": ["#C2410C", "#9A3412", "#7C2D12", "#EA580C"],
                "4": ["#9A3412", "#7C2D12", "#601F0C", "#EA580C"],
            },
        },
    },
    "halloween": {
        "dark": {
            "eyebrow": "#FB923C",
            "accent": "#C084FC",
            "glow": "#A855F7",
            "peak_cap": "#FED7AA",
            "levels": {
                "0": ["#1C1926", "#14121D", "#0E0C14", "#2B263B"],
                "1": ["#4C1D95", "#3B0764", "#2E1065", "#6D28D9"],
                "2": ["#7E22CE", "#6B21A8", "#581C87", "#A855F7"],
                "3": ["#C084FC", "#9333EA", "#7E22CE", "#D8B4FE"],
                "4": ["#FB923C", "#EA580C", "#C2410C", "#FED7AA"],
            },
        },
        "light": {
            "eyebrow": "#9A3412",
            "accent": "#6D28D9",
            "glow": "#7C3AED",
            "peak_cap": "#F97316",
            "levels": {
                "0": ["#E5E7EB", "#D1D5DB", "#B8C0CC", "#F3F4F6"],
                "1": ["#DDD6FE", "#C4B5FD", "#A78BFA", "#EDE9FE"],
                "2": ["#8B5CF6", "#7C3AED", "#6D28D9", "#A78BFA"],
                "3": ["#6D28D9", "#5B21B6", "#4C1D95", "#8B5CF6"],
                "4": ["#EA580C", "#C2410C", "#9A3412", "#FB923C"],
            },
        },
    },
    "christmas": {
        "dark": {
            "eyebrow": "#34D399",
            "accent": "#F87171",
            "glow": "#10B981",
            "peak_cap": "#FECACA",
            "levels": {
                "0": ["#15201C", "#0F1815", "#0A110F", "#22332D"],
                "1": ["#065F46", "#064E3B", "#022C22", "#047857"],
                "2": ["#059669", "#047857", "#065F46", "#10B981"],
                "3": ["#34D399", "#10B981", "#059669", "#6EE7B7"],
                "4": ["#F87171", "#DC2626", "#B91C1C", "#FECACA"],
            },
        },
        "light": {
            "eyebrow": "#047857",
            "accent": "#B91C1C",
            "glow": "#059669",
            "peak_cap": "#EF4444",
            "levels": {
                "0": ["#E2E8F0", "#CBD5E1", "#B8C4D4", "#F1F5F9"],
                "1": ["#A7F3D0", "#6EE7B7", "#34D399", "#D1FAE5"],
                "2": ["#10B981", "#059669", "#047857", "#34D399"],
                "3": ["#047857", "#065F46", "#064E3B", "#10B981"],
                "4": ["#DC2626", "#B91C1C", "#991B1B", "#F87171"],
            },
        },
    },
}

_REPO_SLUG_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_XML_ENTITIES: dict[str, str] = {'"': "&quot;", "'": "&apos;"}


def xml_escape(text: str) -> str:
    """Escape &, <, >, \", and ' to XML entities."""
    return _sax_escape(str(text), _XML_ENTITIES)


def xml_attr(text: str) -> str:
    """Escape &, <, >, \", and ' and wrap in double quotes for XML attributes."""
    return _sax_quoteattr(str(text), _XML_ENTITIES)


def resolve_active_theme(today_ist: dt.date) -> str:
    """Resolve active seasonal theme for an IST date.

    Precedence: diwali > new_year > christmas > halloween > baseline.
    """
    diwali = DIWALI_DATES.get(today_ist.year)
    if diwali is not None and (diwali - dt.timedelta(days=1)) <= today_ist <= (diwali + dt.timedelta(days=1)):
        return "diwali"

    md = (today_ist.month, today_ist.day)
    if md in ((12, 31), (1, 1), (1, 2)):
        return "new_year"
    if md in ((12, 24), (12, 25), (12, 26)):
        return "christmas"
    if md in ((10, 30), (10, 31)):
        return "halloween"
    return "baseline"


def get_theme_palette(theme_name: str, mode: str) -> dict[str, Any]:
    """Return merged base + override color tokens for (theme_name, mode)."""
    if theme_name not in _THEME_OVERRIDES:
        raise ValueError(f"Unknown theme_name: {theme_name!r}")
    if mode not in _BASE_TOKENS:
        raise ValueError(f"Unknown mode: {mode!r}")
    merged = copy.deepcopy(_BASE_TOKENS[mode])
    merged.update(copy.deepcopy(_THEME_OVERRIDES[theme_name][mode]))
    return merged


def _require_non_empty_str(obj: Any, field_path: str) -> str:
    if not isinstance(obj, str) or not obj.strip():
        raise ValueError(f"Expected non-empty string for {field_path}")
    return obj


def _require_url(url: Any, field_path: str, *, allow_mailto: bool = False, allow_rel_assets: bool = False) -> str:
    val = _require_non_empty_str(url, field_path)
    if allow_rel_assets and val == "./assets":
        return val
    if val.startswith("https://"):
        return val
    if allow_mailto and val.startswith("mailto:"):
        return val
    raise ValueError(f"Disallowed URL scheme for {field_path}: {val!r}")


def load_profile(path: pathlib.Path) -> dict[str, Any]:
    """Load and validate profile.json fail-closed, raising ValueError on invalid schema."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("profile.json root must be a JSON object")
    if raw.get("schema_version") != 1:
        raise ValueError(f"Unsupported schema_version: {raw.get('schema_version')!r}")

    for key in ("handle", "name", "role_headline", "location", "current_company", "summary"):
        _require_non_empty_str(raw.get(key), key)

    subtitle_lines = raw.get("hero_subtitle_lines")
    if not isinstance(subtitle_lines, list) or len(subtitle_lines) != 2:
        raise ValueError("hero_subtitle_lines must be a 2-element list")
    for idx, line in enumerate(subtitle_lines):
        s = _require_non_empty_str(line, f"hero_subtitle_lines[{idx}]")
        if len(s) > 64:
            raise ValueError(f"hero_subtitle_lines[{idx}] exceeds 64 chars ({len(s)})")

    pills = raw.get("hero_pills")
    if not isinstance(pills, list) or len(pills) != 3:
        raise ValueError("hero_pills must be a 3-element list")
    for idx, pill in enumerate(pills):
        _require_non_empty_str(pill, f"hero_pills[{idx}]")

    _require_url(raw.get("explorer_url"), "explorer_url")
    _require_url(raw.get("dynamic_assets_base"), "dynamic_assets_base", allow_rel_assets=True)

    contacts = raw.get("contact")
    if not isinstance(contacts, list) or not contacts:
        raise ValueError("contact must be a non-empty list")
    for idx, item in enumerate(contacts):
        if not isinstance(item, dict):
            raise ValueError(f"contact[{idx}] must be an object")
        for k in ("id", "label", "alt"):
            _require_non_empty_str(item.get(k), f"contact[{idx}].{k}")
        _require_url(item.get("url"), f"contact[{idx}].url", allow_mailto=True)

    experience = raw.get("experience")
    if not isinstance(experience, list) or not experience:
        raise ValueError("experience must be a non-empty list")
    for idx, exp in enumerate(experience):
        if not isinstance(exp, dict):
            raise ValueError(f"experience[{idx}] must be an object")
        _require_non_empty_str(exp.get("company"), f"experience[{idx}].company")
        _require_non_empty_str(exp.get("location"), f"experience[{idx}].location")
        roles = exp.get("roles")
        if not isinstance(roles, list) or not roles:
            raise ValueError(f"experience[{idx}].roles must be a non-empty list")
        for r_idx, role in enumerate(roles):
            if not isinstance(role, dict):
                raise ValueError(f"experience[{idx}].roles[{r_idx}] must be an object")
            for k in ("title", "employment_type", "period"):
                _require_non_empty_str(role.get(k), f"experience[{idx}].roles[{r_idx}].{k}")
            highlights = role.get("highlights")
            if not isinstance(highlights, list) or not highlights:
                raise ValueError(f"experience[{idx}].roles[{r_idx}].highlights must be non-empty")
            for h_idx, h in enumerate(highlights):
                _require_non_empty_str(h, f"experience[{idx}].roles[{r_idx}].highlights[{h_idx}]")

    edu = raw.get("education")
    if not isinstance(edu, dict):
        raise ValueError("education must be an object")
    for k in ("institution", "degree", "period"):
        _require_non_empty_str(edu.get(k), f"education.{k}")

    tiers = raw.get("tech_stack_tiers")
    if not isinstance(tiers, list) or not tiers:
        raise ValueError("tech_stack_tiers must be a non-empty list")
    valid_tier_ids: set[str] = set()
    for idx, tier in enumerate(tiers):
        if not isinstance(tier, dict):
            raise ValueError(f"tech_stack_tiers[{idx}] must be an object")
        tid = _require_non_empty_str(tier.get("id"), f"tech_stack_tiers[{idx}].id")
        _require_non_empty_str(tier.get("index"), f"tech_stack_tiers[{idx}].index")
        _require_non_empty_str(tier.get("label"), f"tech_stack_tiers[{idx}].label")
        items = tier.get("items")
        if not isinstance(items, list) or not items:
            raise ValueError(f"tech_stack_tiers[{idx}].items must be non-empty")
        for i_idx, itm in enumerate(items):
            _require_non_empty_str(itm, f"tech_stack_tiers[{idx}].items[{i_idx}]")
        valid_tier_ids.add(tid)

    projects = raw.get("projects")
    if not isinstance(projects, list) or not projects:
        raise ValueError("projects must be a non-empty list")
    for idx, proj in enumerate(projects):
        if not isinstance(proj, dict):
            raise ValueError(f"projects[{idx}] must be an object")
        for k in ("slug", "name", "category", "summary"):
            _require_non_empty_str(proj.get(k), f"projects[{idx}].{k}")
        repo = _require_non_empty_str(proj.get("repo"), f"projects[{idx}].repo")
        if not _REPO_SLUG_RE.match(repo):
            raise ValueError(f"Invalid repo slug for projects[{idx}].repo: {repo!r}")
        stack = proj.get("stack")
        if not isinstance(stack, list) or not stack:
            raise ValueError(f"projects[{idx}].stack must be non-empty")
        for s_idx, tech in enumerate(stack):
            _require_non_empty_str(tech, f"projects[{idx}].stack[{s_idx}]")
        tier_ids = proj.get("tier_ids")
        if not isinstance(tier_ids, list) or not tier_ids:
            raise ValueError(f"projects[{idx}].tier_ids must be non-empty")
        for tid in tier_ids:
            if tid not in valid_tier_ids:
                raise ValueError(f"Unknown tier_id {tid!r} in projects[{idx}].tier_ids")
        links = proj.get("links")
        if not isinstance(links, dict):
            raise ValueError(f"projects[{idx}].links must be an object")
        _require_url(links.get("code"), f"projects[{idx}].links.code")
        for opt_key in ("docs", "live"):
            val = links.get(opt_key)
            if val is not None:
                _require_url(val, f"projects[{idx}].links.{opt_key}")

    other_projects = raw.get("other_projects")
    if not isinstance(other_projects, list):
        raise ValueError("other_projects must be a list")
    for idx, op in enumerate(other_projects):
        if not isinstance(op, dict):
            raise ValueError(f"other_projects[{idx}] must be an object")
        _require_non_empty_str(op.get("name"), f"other_projects[{idx}].name")
        _require_non_empty_str(op.get("note"), f"other_projects[{idx}].note")
        _require_url(op.get("url"), f"other_projects[{idx}].url")

    return raw


def relative_luminance(hex_color: str) -> float:
    """Compute WCAG 2.1 relative luminance for a #RRGGBB hex color."""
    hx = hex_color.lstrip("#")
    if len(hx) != 6:
        raise ValueError(f"Expected 6-digit hex color, got {hex_color!r}")
    r, g, b = (int(hx[i : i + 2], 16) / 255.0 for i in (0, 2, 4))

    def _lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast_ratio(fg: str, bg: str) -> float:
    """Compute WCAG 2.1 contrast ratio between two #RRGGBB hex colors."""
    l1, l2 = sorted((relative_luminance(fg), relative_luminance(bg)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def validate_all_palettes_wcag() -> list[str]:
    """Validate WCAG AA (>= 4.5:1) across all 5x2 theme palettes and stack tier accents."""
    errors: list[str] = []
    for theme_name in THEME_NAMES:
        for mode in MODES:
            pal = get_theme_palette(theme_name, mode)
            for fg_key in WCAG_FG_KEYS:
                fg = pal[fg_key]
                for bg_key in WCAG_BG_KEYS:
                    bg = pal[bg_key]
                    ratio = contrast_ratio(fg, bg)
                    if ratio < 4.5:
                        errors.append(
                            f"WCAG AA fail: {theme_name}/{mode} {fg_key} ({fg}) on {bg_key} ({bg}) = {ratio:.2f}:1 < 4.5:1"
                        )
    stack_card_bg = {"dark": "#161B22", "light": "#FFFFFF"}
    for mode, tiers in STACK_TIER_ACCENTS.items():
        bg = stack_card_bg[mode]
        for idx, fg in tiers.items():
            ratio = contrast_ratio(fg, bg)
            if ratio < 4.5:
                errors.append(
                    f"WCAG AA fail: stack-3d/{mode} tier {idx} ({fg}) on {bg} = {ratio:.2f}:1 < 4.5:1"
                )
    for mode, cards in PROJECT_CARD_ACCENTS.items():
        bg = stack_card_bg[mode]
        for slug, fg in cards.items():
            ratio = contrast_ratio(fg, bg)
            if ratio < 4.5:
                errors.append(
                    f"WCAG AA fail: card/{mode} {slug} ({fg}) on {bg} = {ratio:.2f}:1 < 4.5:1"
                )
    return errors


def validate_svg_document(svg_text: str, name: str) -> list[str]:
    """Validate XML well-formedness, SVG 1.1 safety constraints, and accessibility tags."""
    errors: list[str] = []
    if "rgba(" in svg_text:
        errors.append(f"{name}: contains non-SVG-1.1 'rgba(' attribute")
    if "<feGaussianBlur" in svg_text:
        errors.append(f"{name}: contains prohibited '<feGaussianBlur' filter")

    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as exc:
        errors.append(f"{name}: XML parse error: {exc}")
        return errors

    local_tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag
    if local_tag != "svg":
        errors.append(f"{name}: root element is <{local_tag}>, expected <svg>")
    if not root.attrib.get("viewBox"):
        errors.append(f"{name}: missing viewBox attribute on <svg>")
    if root.attrib.get("role") != "img":
        errors.append(f"{name}: missing role=\"img\" on <svg>")

    title_el = next((el for el in root.iter() if (el.tag.split("}")[-1]) == "title"), None)
    desc_el = next((el for el in root.iter() if (el.tag.split("}")[-1]) == "desc"), None)
    if title_el is None or not (title_el.text and title_el.text.strip()):
        errors.append(f"{name}: missing non-empty <title> element")
    if desc_el is None or not (desc_el.text and desc_el.text.strip()):
        errors.append(f"{name}: missing non-empty <desc> element")

    return errors


def write_text_lf(path: pathlib.Path, content: str) -> None:
    """Write UTF-8 text deterministically using LF line endings."""
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(normalized)
