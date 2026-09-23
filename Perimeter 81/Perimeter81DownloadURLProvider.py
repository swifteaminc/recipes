#!/usr/local/autopkg/python
# -*- coding: utf-8 -*-
"""
Perimeter81DownloadURLProvider
Finds the newest public Check Point SASE / Harmony SASE macOS package URL.
"""

from __future__ import absolute_import

import re
import urllib.error
import urllib.request
from typing import List

from autopkglib import URLGetter

__all__: List[str] = ["Perimeter81DownloadURLProvider"]


class Perimeter81DownloadURLProvider(URLGetter):
    """Provides the newest macOS package URL that is available on the CDN."""

    description = __doc__

    input_variables = {
        "release_notes_url": {
            "required": False,
            "default": (
                "https://sc1.checkpoint.com/documents/Infinity_Portal/WebAdminGuides/EN/"
                "SASE-Admin-Guide/SASE_Security/Topics/macos/macos_agent_release_notes.html"
            ),
            "description": "Check Point SASE macOS release notes URL.",
        },
        "cdn_base_url": {
            "required": False,
            "default": "https://static.perimeter81.com/agents/mac",
            "description": "Base URL for public macOS package downloads.",
        },
        "candidate_limit": {
            "required": False,
            "default": "20",
            "description": "Maximum release-note versions to probe before failing.",
        },
    }

    output_variables = {
        "url": {"description": "Direct download URL for the selected package."},
        "download_filename": {"description": "Selected package filename."},
        "full_version": {"description": "Full 4-part package version."},
        "version": {"description": "3-part application version."},
        "build": {"description": "Build number from the 4-part version."},
        "app_name": {"description": "Installed application bundle name without .app."},
        "pkg_component_name": {"description": "Unpacked component package name without _unsigned.pkg."},
    }

    def _ordered_versions(self, html):
        versions = []

        current_match = re.search(
            r"<h1[^>]*>\s*macOS\s*</h1>.*?<h2[^>]*>\s*([0-9]+(?:\.[0-9]+){3})\s*</h2>",
            html,
            re.IGNORECASE | re.DOTALL,
        )
        if current_match:
            versions.append(current_match.group(1))

        macos_link_re = re.compile(
            r'href="[^"]*/SASE_Security/Topics/macos/[^"]*"[^>]*>\s*([0-9]+(?:\.[0-9]+){3})\s*</a>',
            re.IGNORECASE | re.DOTALL,
        )
        for version in macos_link_re.findall(html):
            if version not in versions:
                versions.append(version)

        return versions

    def _candidate_filenames(self, full_version):
        major_version = int(full_version.split(".", 1)[0])
        if major_version >= 13:
            return [
                f"CheckPointSASE_{full_version}.pkg",
                f"Harmony_SASE_{full_version}.pkg",
            ]
        return [
            f"Harmony_SASE_{full_version}.pkg",
            f"CheckPointSASE_{full_version}.pkg",
        ]

    def _cdn_url_exists(self, url):
        request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "AutoPkg"})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return 200 <= response.status < 400
        except urllib.error.HTTPError as err:
            self.output(f"Skipping unavailable package URL ({err.code}): {url}")
        except urllib.error.URLError as err:
            self.output(f"Skipping unavailable package URL ({err.reason}): {url}")
        return False

    def main(self):
        release_notes_url = self.env.get("release_notes_url")
        cdn_base_url = self.env.get("cdn_base_url", "").rstrip("/")
        candidate_limit = int(self.env.get("candidate_limit", "20"))

        response = self.download(release_notes_url)
        if isinstance(response, bytes):
            response = response.decode("utf-8", errors="replace")

        versions = self._ordered_versions(response)
        if not versions:
            raise Exception(f"Could not find macOS release versions in {release_notes_url}")

        for full_version in versions[:candidate_limit]:
            for filename in self._candidate_filenames(full_version):
                url = f"{cdn_base_url}/{filename}"
                if not self._cdn_url_exists(url):
                    continue

                version_parts = full_version.split(".")
                app_name = "Check Point SASE" if filename.startswith("CheckPointSASE_") else "Harmony SASE"

                self.env["url"] = url
                self.env["download_filename"] = filename
                self.env["full_version"] = full_version
                self.env["version"] = ".".join(version_parts[:3])
                self.env["build"] = version_parts[3]
                self.env["app_name"] = app_name
                self.env["pkg_component_name"] = app_name

                self.output(f"Found package URL: {url}")
                self.output(f"Version: {full_version}")
                return

        raise Exception(
            f"Could not find an available macOS package on {cdn_base_url} "
            f"from the first {candidate_limit} versions in {release_notes_url}"
        )


if __name__ == "__main__":
    PROCESSOR = Perimeter81DownloadURLProvider()
    PROCESSOR.execute_shell()
