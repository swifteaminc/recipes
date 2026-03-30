#!/usr/local/autopkg/python
"""JetBrains Rider URL Provider."""

from __future__ import absolute_import

import re
import sys
from xml.dom import minidom

from autopkglib import ProcessorError, URLGetter

__all__ = ["RiderURLProvider"]

RIDER_UPDATES_URL = "https://www.jetbrains.com/updates/updates.xml"
RIDER_PRODUCT_NAME = "Rider"
RIDER_DOWNLOAD_URL = "https://download-cdn.jetbrains.com/rider/JetBrains.Rider-%s-aarch64.dmg"
VERSION_RE = re.compile(r"^\d+(?:\.\d+)+$")


class RiderURLProvider(URLGetter):
    """Provides URL and version for the latest stable Apple Silicon Rider build."""

    description = (
        "Provides URL and version for the latest stable Apple Silicon JetBrains Rider release."
    )
    input_variables = {
        "base_url": {
            "required": False,
            "description": "Default is https://www.jetbrains.com/updates/updates.xml",
        }
    }
    output_variables = {
        "url": {"description": "URL to the latest Apple Silicon Rider release"},
        "version": {"description": "Latest stable Rider version"},
    }

    __doc__ = description

    def _fetch_xml(self, version_url):
        try:
            if sys.version_info.major < 3:
                return self.download(version_url)
            return self.download(version_url).decode("utf-8")
        except Exception as err:
            raise ProcessorError("Cannot download %s: %s" % (version_url, err))

    @staticmethod
    def _version_key(version):
        return tuple(int(part) for part in version.split("."))

    def get_rider_version(self, version_url):
        """Retrieve the latest stable Rider version from the JetBrains updates feed."""
        root = minidom.parseString(self._fetch_xml(version_url))
        products = root.childNodes[0].getElementsByTagName("product")

        rider_product = None
        for product in products:
            if (
                product.hasAttribute("name")
                and product.getAttribute("name") == RIDER_PRODUCT_NAME
            ):
                rider_product = product
                break

        if rider_product is None:
            raise ProcessorError("Did not find %s in version XML." % RIDER_PRODUCT_NAME)

        versions = []
        for channel in rider_product.getElementsByTagName("channel"):
            if not (
                channel.hasAttribute("licensing")
                and channel.getAttribute("licensing") == "release"
                and channel.hasAttribute("status")
                and channel.getAttribute("status") == "release"
            ):
                continue

            for build in channel.getElementsByTagName("build"):
                if build.hasAttribute("version"):
                    version = build.getAttribute("version")
                    if VERSION_RE.match(version):
                        versions.append(version)

        if not versions:
            raise ProcessorError("No stable Rider versions found in version XML.")

        return sorted(set(versions), key=self._version_key, reverse=True)[0]

    def main(self):
        version_url = self.env.get("base_url", RIDER_UPDATES_URL)
        version = self.get_rider_version(version_url)

        self.env["version"] = version
        self.env["url"] = RIDER_DOWNLOAD_URL % version

        self.output("Version: %s" % self.env["version"])
        self.output("URL: %s" % self.env["url"])


if __name__ == "__main__":
    processor = RiderURLProvider()
    processor.execute_shell()
