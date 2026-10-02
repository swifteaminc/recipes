#!/usr/local/autopkg/python
# -*- coding: utf-8 -*-
"""
Perimeter81DownloadURLProvider
Finds the newest public Check Point SASE / Harmony SASE macOS package URL.
"""

from __future__ import absolute_import

import re
import subprocess
from typing import List

from autopkglib import URLGetter

__all__: List[str] = ["Perimeter81DownloadURLProvider"]

# Installed .app name (also the unpacked component package name) for each
# package filename prefix, keyed by the prefix lowercased with separators removed.
APP_NAMES_BY_PREFIX = {
    "checkpointsase": "Check Point SASE",
    "harmonysase": "Harmony SASE",
}


class Perimeter81DownloadURLProvider(URLGetter):
    """Provides the newest macOS package URL that is available on the CDN."""

    description = __doc__

    input_variables = {
        "downloads_page_url": {
            "required": False,
            "default": (
                "https://sc1.checkpoint.com/documents/Infinity_Portal/WebAdminGuides/EN/"
                "SASE-Admin-Guide/SASE_Security/Topics/download/introduction_to_the_downloads_page.html"
            ),
            "description": "Check Point SASE Downloads page, which links the current macOS package.",
        },
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

    def _read(self, url):
        response = self.download(url)
        if isinstance(response, bytes):
            response = response.decode("utf-8", errors="replace")
        return response

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

    def _downloads_page_package(self, html, cdn_base_url):
        match = re.search(
            r'href="(' + re.escape(cdn_base_url) + r'/([^"/]+_([0-9]+(?:\.[0-9]+){3})\.pkg))"',
            html,
        )
        if not match:
            return None
        return match.group(1), match.group(2), match.group(3)

    def _candidate_filenames(self, full_version):
        major_version = int(full_version.split(".", 1)[0])
        if major_version >= 13:
            return [
                f"CheckPoint_SASE_{full_version}.pkg",
                f"CheckPointSASE_{full_version}.pkg",
                f"Harmony_SASE_{full_version}.pkg",
            ]
        return [
            f"Harmony_SASE_{full_version}.pkg",
            f"CheckPointSASE_{full_version}.pkg",
        ]

    def _app_name_for(self, filename):
        # Guessing here would be worse than failing: the munki recipe builds the
        # installs check from app_name, so a wrong name points Munki at an app
        # that never exists and it reinstalls on every run.
        key = re.sub(r"[^a-z]", "", filename.rsplit("_", 1)[0].lower())
        if key not in APP_NAMES_BY_PREFIX:
            raise Exception(
                f"Unrecognized package name {filename}: add its installed app name to APP_NAMES_BY_PREFIX"
            )
        return APP_NAMES_BY_PREFIX[key]

    def _cdn_url_exists(self, url):
        # Python's own ssl module doesn't fetch missing intermediates via AIA,
        # so a urllib HEAD request can fail with CERTIFICATE_VERIFY_FAILED
        # against a CloudFront edge that (transiently) serves an incomplete
        # chain. curl builds the chain correctly and is what the rest of
        # AutoPkg's downloads already rely on, so use it here too.
        cmd = [
            "curl", "--silent", "--show-error", "--head", "--fail",
            "--location", "--max-time", "20", "--retry", "2", "--retry-delay", "2",
            "--user-agent", "AutoPkg",
            url,
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=30)
            return True
        except subprocess.CalledProcessError as err:
            stderr = err.stderr.decode("utf-8", errors="replace").strip()
            self.output(f"Skipping unavailable package URL ({stderr or 'curl exit ' + str(err.returncode)}): {url}")
        except subprocess.TimeoutExpired:
            self.output(f"Skipping unavailable package URL (timeout): {url}")
        return False

    def _select(self, url, filename, full_version):
        app_name = self._app_name_for(filename)
        version_parts = full_version.split(".")

        self.env["url"] = url
        self.env["download_filename"] = filename
        self.env["full_version"] = full_version
        self.env["version"] = ".".join(version_parts[:3])
        self.env["build"] = version_parts[3]
        self.env["app_name"] = app_name
        self.env["pkg_component_name"] = app_name

        self.output(f"Found package URL: {url}")
        self.output(f"Version: {full_version}")

    def main(self):
        downloads_page_url = self.env.get("downloads_page_url")
        release_notes_url = self.env.get("release_notes_url")
        cdn_base_url = self.env.get("cdn_base_url", "").rstrip("/")
        candidate_limit = int(self.env.get("candidate_limit", "20"))

        # The Downloads page links the current package by its real filename, so
        # it survives Check Point renaming the file (13.x moved from
        # CheckPointSASE_ to CheckPoint_SASE_, which broke the filename guessing
        # below). The release notes are only a fallback for when that page is
        # unreachable or stops linking a live package.
        found = None
        try:
            found = self._downloads_page_package(self._read(downloads_page_url), cdn_base_url)
        except Exception as err:
            self.output(f"Could not read the Downloads page ({err})")
        if found and self._cdn_url_exists(found[0]):
            self._select(*found)
            return
        self.output("No live macOS package linked from the Downloads page; falling back to release notes")

        versions = self._ordered_versions(self._read(release_notes_url))
        if not versions:
            raise Exception(f"Could not find macOS release versions in {release_notes_url}")

        for full_version in versions[:candidate_limit]:
            for filename in self._candidate_filenames(full_version):
                url = f"{cdn_base_url}/{filename}"
                if self._cdn_url_exists(url):
                    self._select(url, filename, full_version)
                    return

        raise Exception(
            f"Could not find an available macOS package on {cdn_base_url} "
            f"from the first {candidate_limit} versions in {release_notes_url}"
        )


if __name__ == "__main__":
    PROCESSOR = Perimeter81DownloadURLProvider()
    PROCESSOR.execute_shell()
