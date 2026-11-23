#!/usr/bin/env python3
"""Best-effort non-fatal post-deploy Camo cache purger.

Queries GitHub's official README HTML render API to discover signed
camo.githubusercontent.com URLs across both <source srcset> and <img src>
and issues HTTP PURGE requests. Always exits 0 on network or purge errors.
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser

USER_AGENT = "hynko431-profile-builder/2.0"
CAMO_PREFIX = "https://camo.githubusercontent.com/"


class _CamoUrlExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []
        self._seen: set[str] = set()

    def _add(self, candidate: str) -> None:
        url = candidate.strip()
        if url.startswith(CAMO_PREFIX) and url not in self._seen:
            self._seen.add(url)
            self.urls.append(url)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {k.lower(): (v or "") for k, v in attrs}
        if tag.lower() == "img" and "src" in attr_map:
            self._add(attr_map["src"])
        if "srcset" in attr_map:
            for part in attr_map["srcset"].split(","):
                tokens = part.strip().split()
                if tokens:
                    self._add(tokens[0])


def extract_camo_urls(html_text: str) -> list[str]:
    """Extract deduplicated Camo URLs from rendered README HTML."""
    parser = _CamoUrlExtractor()
    parser.feed(html_text)
    parser.close()
    return parser.urls


def purge_repo_camo(repo: str, token: str = "") -> list[tuple[str, int | str]]:
    """Fetch rendered README HTML via GitHub REST API and send HTTP PURGE to each Camo URL."""
    api_url = f"https://api.github.com/repos/{repo}/readme"
    headers = {
        "Accept": "application/vnd.github.html+json",
        "User-Agent": USER_AGENT,
    }
    if token.strip():
        headers["Authorization"] = f"Bearer {token.strip()}"

    req = urllib.request.Request(api_url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        html_text = resp.read().decode("utf-8", errors="ignore")

    results: list[tuple[str, int | str]] = []
    for url in extract_camo_urls(html_text):
        purge_req = urllib.request.Request(url, method="PURGE", headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(purge_req, timeout=10) as p_resp:
                results.append((url, p_resp.status))
        except urllib.error.HTTPError as exc:
            results.append((url, exc.code))
        except (urllib.error.URLError, TimeoutError) as exc:
            results.append((url, str(exc)))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Best-effort Camo PURGE for GitHub README images.")
    parser.add_argument("--repo", default="hynko431/hynko431", help="owner/repo")
    args = parser.parse_args(argv)

    token = os.environ.get("GITHUB_TOKEN", "")
    try:
        results = purge_repo_camo(args.repo, token=token)
        for url, status in results:
            print(f"PURGE {status} {url}")
        print(f"Camo purge complete ({len(results)} unique URLs).")
    except Exception as exc:  # noqa: BLE001 — intentionally non-fatal
        print(f"Warning: Camo purge skipped due to error: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
