#!/usr/local/autopkg/python
# -*- coding: utf-8 -*-
"""
SlackPkgURLProvider
Finds the latest Slack macOS arm64 PKG URL and version by scraping Slack's
deployment/help article (which contains direct PKG links).
"""

from __future__ import absolute_import

import re
from typing import List

from autopkglib import URLGetter

__all__: List[str] = ["SlackPkgURLProvider"]


class SlackPkgURLProvider(URLGetter):
    """Provides URL to the latest Slack macOS PKG (arm64)."""

    description = __doc__

    input_variables = {
        "deploy_doc_url": {
            "required": False,
            "default": "https://slack.com/help/articles/360035635174-Deploy-Slack-for-macOS",
            "description": "Slack help article that includes direct PKG download links.",
        },
        "arch": {
            "required": False,
            "default": "arm64",
            "description": "Architecture to match in the Slack PKG URL. Use 'arm64'.",
        },
    }

    output_variables = {
        "url": {"description": "Direct download URL of the latest Slack PKG for the requested arch."},
        "version": {"description": "Slack version extracted from the PKG URL."},
    }

    def main(self):
        deploy_doc_url = self.env.get("deploy_doc_url")
        arch = self.env.get("arch", "arm64")

        html = self.download(deploy_doc_url)
        if isinstance(html, (bytes, bytearray)):
            html = html.decode("utf-8", "ignore")

        # Match e.g.:
        # https://downloads.slack-edge.com/desktop-releases/mac/arm64/4.47.72/Slack-4.47.72-macOS.pkg
        pattern = (
            r"(https://downloads\.slack-edge\.com/desktop-releases/mac/"
            + re.escape(arch)
            + r"/([0-9.]+)/Slack-\2-macOS\.pkg)"
        )

        matches = re.findall(pattern, html)
        if not matches:
            raise Exception(f"Could not find Slack PKG URL for arch={arch} in {deploy_doc_url}")

        # re.findall gives list of tuples: (full_url, version)
        url, version = matches[0]

        self.env["url"] = url
        self.env["version"] = version
        self.output(f"Found Slack PKG URL: {url}")
        self.output(f"Version: {version}")


if __name__ == "__main__":
    PROCESSOR = SlackPkgURLProvider()
    PROCESSOR.execute_shell()
