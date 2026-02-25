#!/usr/local/autopkg/python

from __future__ import absolute_import

import re
import subprocess

from autopkglib import Processor, ProcessorError

__all__ = ["ConductorDownloadURLProvider"]


class ConductorDownloadURLProvider(Processor):
    description = (
        "Finds the current Conductor CDN DMG URL by parsing conductor.build and "
        "its Next.js chunks."
    )
    input_variables = {
        "homepage_url": {
            "required": False,
            "default": "https://www.conductor.build/",
            "description": "Conductor homepage URL.",
        },
        "arch": {
            "required": False,
            "default": "aarch64",
            "description": "Architecture suffix in URL (aarch64 or x86_64).",
        },
    }
    output_variables = {
        "download_url": {
            "description": "Resolved Conductor DMG download URL.",
        },
    }

    @staticmethod
    def _fetch_text(url):
        try:
            result = subprocess.run(
                ["curl", "-fsSL", "--max-time", "30", url],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as err:
            raise ProcessorError(
                "curl failed for %s: %s"
                % (url, err.stderr.decode("utf-8", "ignore").strip())
            )
        return result.stdout.decode("utf-8", "ignore")

    @staticmethod
    def _find_direct_url(text, arch):
        pattern = re.compile(
            r"https://cdn\.crabnebula\.app/download/melty/conductor/latest/platform/dmg-"
            + re.escape(arch)
        )
        match = pattern.search(text)
        return match.group(0) if match else None

    @staticmethod
    def _find_escaped_url(text, arch):
        pattern = re.compile(
            r"https:\\/\\/cdn\.crabnebula\.app\\/download\\/melty\\/conductor\\/latest\\/platform\\/dmg-"
            + re.escape(arch)
        )
        match = pattern.search(text)
        if not match:
            return None
        return match.group(0).replace("\\/", "/")

    def main(self):
        homepage_url = self.env["homepage_url"]
        arch = self.env["arch"]

        homepage = self._fetch_text(homepage_url)

        found = self._find_direct_url(homepage, arch)
        if not found:
            found = self._find_escaped_url(homepage, arch)
        if found:
            self.output("Resolved Conductor download URL from homepage.")
            self.env["download_url"] = found
            return

        chunk_paths = re.findall(r"/_next/static/chunks/[A-Za-z0-9._-]+\.js", homepage)
        seen = set()
        for chunk_path in chunk_paths:
            if chunk_path in seen:
                continue
            seen.add(chunk_path)
            chunk_url = "https://www.conductor.build%s" % chunk_path
            try:
                chunk = self._fetch_text(chunk_url)
            except Exception:
                continue

            found = self._find_direct_url(chunk, arch)
            if not found:
                found = self._find_escaped_url(chunk, arch)
            if found:
                self.output("Resolved Conductor download URL from %s" % chunk_path)
                self.env["download_url"] = found
                return

        raise ProcessorError(
            "Could not find Conductor download URL for arch=%s from %s"
            % (arch, homepage_url)
        )


if __name__ == "__main__":
    PROCESSOR = ConductorDownloadURLProvider()
    PROCESSOR.execute_shell()
