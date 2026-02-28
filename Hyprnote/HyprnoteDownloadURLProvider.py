#!/usr/local/autopkg/python
# -*- coding: utf-8 -*-
"""
HyprnoteDownloadURLProvider
Finds the latest stable Hyprnote (Char) macOS Apple Silicon DMG URL and version
from GitHub releases.
"""

from __future__ import absolute_import

import json
import re
from typing import List

from autopkglib import URLGetter

__all__: List[str] = ["HyprnoteDownloadURLProvider"]


class HyprnoteDownloadURLProvider(URLGetter):
    """Provides URL to the latest stable Hyprnote Apple Silicon DMG."""

    description = __doc__

    input_variables = {
        "release_api_url": {
            "required": False,
            "default": "https://api.github.com/repos/fastrepl/char/releases",
            "description": "GitHub releases API endpoint.",
        },
        "tag_prefix": {
            "required": False,
            "default": "desktop_v",
            "description": "Release tag prefix to match.",
        },
        "asset_name": {
            "required": False,
            "default": "char-macos-aarch64.dmg",
            "description": "Exact release asset name (Apple Silicon DMG).",
        },
    }

    output_variables = {
        "url": {"description": "Direct download URL of the latest stable Hyprnote DMG."},
        "version": {"description": "Version extracted from the stable desktop tag."},
    }

    def main(self):
        release_api_url = self.env.get("release_api_url")
        tag_prefix = self.env.get("tag_prefix", "desktop_v")
        asset_name = self.env.get("asset_name", "char-macos-aarch64.dmg")

        response = self.download(release_api_url)
        if isinstance(response, bytes):
            response = response.decode("utf-8", errors="replace")

        try:
            releases = json.loads(response)
        except Exception as err:
            raise Exception(f"Failed to parse GitHub releases response from {release_api_url}: {err}")

        if not isinstance(releases, list):
            raise Exception(f"Unexpected releases payload from {release_api_url}: {releases}")

        stable_tag_re = re.compile(r"^" + re.escape(tag_prefix) + r"([0-9]+\.[0-9]+\.[0-9]+)$")

        for release in releases:
            if release.get("draft") is True or release.get("prerelease") is True:
                continue

            tag_name = release.get("tag_name") or ""
            match = stable_tag_re.match(tag_name)
            if not match:
                continue

            for asset in release.get("assets", []):
                if asset.get("name") != asset_name:
                    continue
                download_url = asset.get("browser_download_url")
                if not download_url:
                    continue

                self.env["url"] = download_url
                self.env["version"] = match.group(1)
                self.output(f"Found Hyprnote DMG URL: {download_url}")
                self.output(f"Version: {self.env['version']}")
                return

        raise Exception(
            f"Could not find a stable '{tag_prefix}X.Y.Z' release with asset '{asset_name}' in {release_api_url}"
        )


if __name__ == "__main__":
    PROCESSOR = HyprnoteDownloadURLProvider()
    PROCESSOR.execute_shell()
