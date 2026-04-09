#!/usr/local/autopkg/python
from __future__ import absolute_import

import json
from autopkglib import ProcessorError, URLGetter

__all__ = ["NessusDownloadURLProvider"]


class NessusDownloadURLProvider(URLGetter):
    """Provide the latest Tenable Nessus macOS DMG URL and version."""

    description = __doc__
    input_variables = {
        "downloads_api_url": {
            "required": False,
            "default": "https://www.tenable.com/downloads/api/v2/pages/nessus",
            "description": "Tenable Nessus downloads API endpoint.",
        }
    }
    output_variables = {
        "url": {"description": "Direct URL to the latest Nessus macOS DMG."},
        "version": {"description": "Latest Nessus macOS version."},
    }

    def main(self):
        downloads_api_url = self.env.get("downloads_api_url")
        response = self.download(downloads_api_url, text=True)

        try:
            payload = json.loads(response)
        except Exception as err:
            raise ProcessorError(
                "Failed to parse Nessus downloads API response from %s: %s"
                % (downloads_api_url, err)
            )

        latest = payload.get("releases", {}).get("latest", {})
        if not isinstance(latest, dict):
            raise ProcessorError(
                "Unexpected latest releases payload from %s" % downloads_api_url
            )

        for release_name, files in latest.items():
            if not isinstance(files, list):
                continue
            for item in files:
                if item.get("os") != "macOS":
                    continue
                if not str(item.get("file", "")).endswith(".dmg"):
                    continue

                file_url = item.get("file_url")
                version = item.get("version")
                if not file_url or not version:
                    continue

                self.env["url"] = file_url
                self.env["version"] = version
                self.output("Release: %s" % release_name)
                self.output("Version: %s" % version)
                self.output("URL: %s" % file_url)
                return

        raise ProcessorError(
            "Could not find a latest Nessus macOS DMG in %s" % downloads_api_url
        )


if __name__ == "__main__":
    processor = NessusDownloadURLProvider()
    processor.execute_shell()
