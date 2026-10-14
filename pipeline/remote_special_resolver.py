#!/usr/bin/env python3

import os
import requests
import time


BASE_URL = (
    "https://freelygiveninc.org/"
    "wp-content/uploads/breviary/full_archive/"
    "Special_Days"
)


class RemoteSpecialResolver:

    def __init__(self, retries=1, delay=0, timeout=10):

        self.retries = retries
        self.delay = delay
        self.timeout = timeout

    def resolve(self, day, office):

        if not day.code:
            return None

        candidates = [
            f"psp_{day.code}_{office}.mp3",
            f"loh_{day.code}_{office}.mp3",
        ]

        for filename in candidates:

            url = (
                f"{BASE_URL}/"
                f"{filename}"
            )

            for attempt in range(
                1,
                self.retries + 1
            ):

                try:

                    response = requests.head(
                        url,
                        timeout=self.timeout,
                        allow_redirects=True
                    )

                    if response.status_code == 200:

                        return {
                            "filename": filename,
                            "stem": filename[:-4],
                            "relative_path": (
                                f"Special_Days/{filename}"
                            ),
                            "remote_url": url,
                        }

                except requests.RequestException:
                    pass

                if attempt < self.retries:
                    time.sleep(self.delay)

        return None
