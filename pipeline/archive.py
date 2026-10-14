#!/usr/bin/env python3

"""
archive.py

Provides access to the Breviary archive indexes.

This module contains no liturgical logic.

It only searches the indexed recordings.
"""

import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_FILE = os.path.join(BASE_DIR, "archive_index.json")
SPECIAL_INDEX_FILE = os.path.join(BASE_DIR, "special_days_index.json")


class Archive:

    def __init__(
        self,
        index_file=INDEX_FILE,
        special_index_file=SPECIAL_INDEX_FILE
    ):

        with open(
            index_file,
            encoding="utf-8"
        ) as infile:

            self.index = json.load(
                infile
            )

        self.recordings = (
            self.index["recordings"]
        )

        if os.path.exists(
            special_index_file
        ):

            with open(
                special_index_file,
                encoding="utf-8"
            ) as infile:

                self.special_index = json.load(
                    infile
                )

            self.special_recordings = (
                self.special_index["recordings"]
            )

            # Older special-day indexes did not include full_path. Rebuild it
            # from the index root and relative path so special recordings are
            # resolved to their exact local archive file.
            special_root = self.special_index.get("archive_root")
            for recording in self.special_recordings:
                if not recording.get("full_path") and special_root:
                    recording["full_path"] = os.path.join(
                        special_root,
                        recording["relative_path"],
                    )

        else:

            self.special_index = {
                "recordings": []
            }

            self.special_recordings = []

    def recording_count(self):

        return len(self.recordings)

    def all_recordings(self):

        return self.recordings

    def contains(
        self,
        filename
    ):

        return (
            self.find_filename(filename)
            is not None
        )

    def find_filename(
        self,
        filename
    ):

        for recording in self.recordings:

            if recording["filename"] == filename:

                return recording

        return None

    def find_recording(
        self,
        *,
        filename=None,
        stem=None,
        season=None,
        folders=None
    ):

        for recording in self.recordings:

            if filename is not None:

                if recording["filename"] != filename:
                    continue

            if stem is not None:

                if recording["stem"] != stem:
                    continue

            current = recording["folders"]

            if season is not None:

                if (
                    not current
                    or current[0] != season
                ):
                    continue

            if folders is not None:

                if current[:len(folders)] != list(folders):
                    continue

            return recording

        return None

    def find_prefix(
        self,
        prefix,
        season=None
    ):

        matches = []

        for recording in self.recordings:

            if not recording["stem"].startswith(prefix):
                continue

            if season is not None:

                folders = recording["folders"]

                if (
                    not folders
                    or folders[0] != season
                ):
                    continue

            matches.append(recording)

        return sorted(
            matches,
            key=lambda r: r["relative_path"]
        )

    def find_special(
        self,
        day,
        office
    ):

        if not day.code:

            return []

        # Prefer the canonical psp_ name, then the legacy loh_ name. Prefix
        # matches can accidentally include similarly named recordings and
        # returning every match can put duplicate offices into today's set.
        for prefix in ("psp", "loh"):
            filename = f"{prefix}_{day.code}_{office}.mp3"
            recording = self.find_special_filename(filename)
            if recording:
                return [recording]

        return []

    def find_special_filename(self, filename):
        for recording in self.special_recordings:
            if recording["filename"] == filename:
                return recording
        return None

    def by_top_folder(
        self,
        folder
    ):

        return [

            r

            for r in self.recordings

            if r["folders"]
            and r["folders"][0] == folder

        ]

    def by_folder(
        self,
        *folders
    ):

        wanted = list(folders)

        return [

            r

            for r in self.recordings

            if r["folders"][:len(wanted)]
            == wanted

        ]

    def filenames(self):

        return sorted(

            r["filename"]

            for r in self.recordings

        )
