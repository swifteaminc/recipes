#!/usr/local/autopkg/python
# -*- coding: utf-8 -*-
"""
SlackPkgURLProvider
Finds the latest Slack macOS PKG URL and version using Slack's
desktop.latestRelease API.
"""

from __future__ import absolute_import

import json
import re
from typing import List
from urllib.parse import urlencode

from autopkglib import URLGetter

__all__: List[str] = ["SlackPkgURLProvider"]


class SlackPkgURLProvider(URLGetter):
    """Provides URL to the latest Slack macOS PKG."""

    description = __doc__

    input_variables = {
        "release_api_url": {
            "required": False,
            "default": "https://slack.com/api/desktop.latestRelease",
            "description": "Slack latest release API endpoint.",
        },
        "arch": {
            "required": False,
            "default": "arm64",
            "description": "Architecture to request. Use 'arm64'.",
        },
        "variant": {
            "required": False,
            "default": "pkg",
            "description": "Slack installer variant to request.",
        },
    }

    output_variables = {
        "url": {"description": "Direct download URL of the latest Slack PKG for the requested arch."},
        "version": {"description": "Slack version extracted from the PKG URL."},
    }

    def main(self):
        release_api_url = self.env.get("release_api_url")
        arch = self.env.get("arch", "arm64")
        variant = self.env.get("variant", "pkg")
        if arch != "arm64":
            raise Exception(f"Unsupported arch '{arch}'. This recipe is locked to arm64.")

        params = urlencode({"redirect": "0", "variant": variant, "arch": arch})
        separator = "&" if "?" in release_api_url else "?"
        query_url = f"{release_api_url}{separator}{params}"

        response = self.download(query_url)
        if isinstance(response, bytes):
            response = response.decode("utf-8", errors="replace")

        try:
            payload = json.loads(response)
        except Exception as err:
            raise Exception(f"Failed to parse Slack latest-release response from {query_url}: {err}")

        if not payload.get("ok"):
            raise Exception(f"Slack latest-release API returned failure payload: {payload}")

        url = (payload.get("download_url") or "").replace("\\/", "/")
        version = payload.get("version")
        if not url or not version:
            raise Exception(f"Slack latest-release API did not return url/version: {payload}")

        # Validate expected URL shape to catch upstream API changes early.
        pattern = (
            r"^https://downloads\.slack-edge\.com/desktop-releases/mac/"
            + re.escape(arch)
            + r"/([0-9.]+)/Slack-\1-macOS\.pkg$"
        )
        match = re.match(pattern, url)
        if not match:
            raise Exception(f"Unexpected Slack download URL format from API: {url}")

        self.env["url"] = url
        self.env["version"] = match.group(1)
        self.output(f"Found Slack PKG URL: {url}")
        self.output(f"Version: {self.env['version']}")


if __name__ == "__main__":
    PROCESSOR = SlackPkgURLProvider()
    PROCESSOR.execute_shell()
