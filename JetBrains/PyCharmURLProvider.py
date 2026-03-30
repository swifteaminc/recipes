#!/usr/local/autopkg/python
from __future__ import absolute_import

import re
import sys
from xml.dom import minidom

from autopkglib import ProcessorError, URLGetter

__all__ = ["PyCharmURLProvider"]

PYCHARM_UPDATES_URL = "https://www.jetbrains.com/updates/updates.xml"
PYCHARM_PRODUCT_NAME = "PyCharm"
PYCHARM_DOWNLOAD_URL = "https://download-cdn.jetbrains.com/python/pycharm-%s-aarch64.dmg"
VERSION_RE = re.compile(r"^\d+(?:\.\d+)+$")


class PyCharmURLProvider(URLGetter):
    """Provide URL for the latest stable Apple Silicon PyCharm build."""

    description = "Provides URL and version for the latest stable Apple Silicon PyCharm release."
    input_variables = {
        "base_url": {
            "required": False,
            "description": "Default is https://www.jetbrains.com/updates/updates.xml",
        },
    }
    output_variables = {
        "url": {"description": "URL to the latest Apple Silicon PyCharm release"},
        "version": {"description": "Latest stable PyCharm version"},
    }

    __doc__ = description

    def _fetch_xml(self, version_url):
        """Fetch update feed XML."""
        try:
            if sys.version_info.major < 3:
                return self.download(version_url)
            return self.download(version_url).decode("utf-8")
        except Exception as err:
            raise ProcessorError("Cannot download %s: %s" % (version_url, err))

    @staticmethod
    def _version_key(version):
        """Sort versions numerically, not lexicographically."""
        return tuple(int(part) for part in version.split("."))

    def get_pycharm_version(self, pycharm_version_url):
        """Retrieve version number from XML."""
        root = minidom.parseString(self._fetch_xml(pycharm_version_url))
        products = root.childNodes[0].getElementsByTagName("product")

        pycharm_product = None
        for product in products:
            if (
                product.hasAttribute("name")
                and product.getAttribute("name") == PYCHARM_PRODUCT_NAME
            ):
                pycharm_product = product
                break

        if pycharm_product is None:
            raise ProcessorError("Did not find %s in version XML." % PYCHARM_PRODUCT_NAME)

        versions = []
        for channel in pycharm_product.getElementsByTagName("channel"):
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
            raise ProcessorError("No stable PyCharm versions found in version XML.")

        return sorted(set(versions), key=self._version_key, reverse=True)[0]

    def main(self):
        """Main function."""
        version_url = self.env.get("base_url", PYCHARM_UPDATES_URL)
        version = self.get_pycharm_version(version_url)

        self.env["version"] = version
        download_url = PYCHARM_DOWNLOAD_URL % version
        self.env["url"] = download_url

        self.output("Version: %s" % self.env["version"])
        self.output("URL: %s" % self.env["url"])


if __name__ == "__main__":
    processor = PyCharmURLProvider()
    processor.execute_shell()
