#!/usr/bin/env python3

"""
Breviary Resolution Engine

select_audio_v2.py

Main application.

Responsibilities

- Determine the target day.
- Build the LiturgicalDay.
- Resolve office types.
- Resolve recordings.
- Copy valid recordings from the local LOTH archive.
- Download invalid or missing recordings from Flywheel.
- Produce breviary_today.

No liturgical decisions belong in this file.
"""

import os
import shutil
import tempfile
import json
import requests
import argparse

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from liturgical_calendar import (
    get_liturgical_day,
    get_ordinary_week,
    get_psalter_week,
)

from office_resolver import OfficeResolver
from recording_resolver import RecordingResolver


###############################################################################
# Configuration
###############################################################################

TZ = ZoneInfo("Asia/Phnom_Penh")

LOTH_ROOT = os.environ.get("BREVIARY_LOTH_ROOT", os.path.expanduser("~/LOTH"))

DESTINATION = os.environ.get("BREVIARY_TODAY_DIR", os.path.expanduser("~/breviary_today"))

REMOTE_BASE_URL = (
    "https://freelygiveninc.org/"
    "wp-content/uploads/breviary/full_archive"
)


###############################################################################
# Utility
###############################################################################

def banner(title):

    print()
    print("=" * 60)
    print(title)
    print("=" * 60)
    print()


def tomorrow():

    now = datetime.now(TZ)

    return (
        now + timedelta(days=1)
    ).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )


def target_day(value=None):
    """Use an explicit ISO date when requested; default to tomorrow."""
    if value is None:
        value = os.environ.get("BREVIARY_TARGET_DATE")
    if value:
        try:
            return datetime.strptime(value, "%Y-%m-%d").replace(
                tzinfo=TZ
            )
        except ValueError as error:
            raise ValueError("Target date must be YYYY-MM-DD") from error
    return tomorrow()


def ensure_destination():

    os.makedirs(
        DESTINATION,
        exist_ok=True
    )


###############################################################################
# Liturgical Day
###############################################################################

def build_liturgical_day(target_date=None):

    target = target_day(target_date)

    ordinary_week = get_ordinary_week(
        target
    )

    psalter_week = get_psalter_week(
        target
    )

    return get_liturgical_day(
        target,
        ordinary_week,
        psalter_week
    )


###############################################################################
# Resolution
###############################################################################

def resolve(target_date=None):

    day = build_liturgical_day(target_date)

    offices = OfficeResolver().resolve(
        day
    )

    recordings = RecordingResolver().resolve(
        day
    )

    return (
        day,
        offices,
        recordings
    )


###############################################################################
# Reporting
###############################################################################

def print_summary(
    day,
    offices,
    recordings
):

    banner(
        "Breviary Resolution Engine"
    )

    print(
        f"Date          : {day.date.date()}"
    )

    print(
        f"Season        : {day.season}"
    )

    print(
        f"Celebration   : {day.celebration}"
    )

    print(
        f"Rank          : {day.rank}"
    )

    print(
        f"Weekday       : {day.weekday}"
    )

    print(
        f"Ordinary Week : {day.ordinary_week}"
    )

    print(
        f"Psalter Week  : {day.psalter_week}"
    )

    print()

    print("Resolved Offices")
    print("----------------")

    for office in (
        "oor",
        "mp",
        "dp",
        "ep",
        "np"
    ):

        print(
            f"{office.upper():3} : "
            f"{offices[office]}"
        )

    print()

    print(
        "Resolved Recordings"
    )

    print(
        "-------------------"
    )

    for office in (
        "oor",
        "mp",
        "dp",
        "ep",
        "np"
    ):

        print()
        print(office.upper())

        if not recordings[office]:

            print(
                "  NONE"
            )

            continue

        office_recordings = recordings[
            office
        ]

        if not isinstance(
            office_recordings,
            list
        ):

            office_recordings = [
                office_recordings
            ]

        for recording in office_recordings:

            print(
                f"  {recording['filename']}"
            )


###############################################################################
# Local Archive
###############################################################################

def find_local_recording(filename):

    matches = []

    for root, directories, files in os.walk(
        LOTH_ROOT
    ):

        if filename in files:

            matches.append(
                os.path.join(
                    root,
                    filename
                )
            )

    if not matches:

        return None

    if len(matches) == 1:

        return matches[0]

    ordinary_time_matches = [
        path
        for path in matches
        if os.path.join(
            "Ordinary Time",
            os.path.basename(
                os.path.dirname(path)
            )
        ) in path
    ]

    if len(ordinary_time_matches) == 1:

        return ordinary_time_matches[0]

    return matches[0]


###############################################################################
# Local File Validation
###############################################################################

def is_valid_mp3(path):

    if not os.path.isfile(path):

        return False

    try:

        with open(
            path,
            "rb"
        ) as infile:

            header = infile.read(3)

    except OSError:

        return False

    if header == b"ID3":

        return True

    if len(header) >= 2:

        if (
            header[0] == 0xFF
            and (header[1] & 0xE0) == 0xE0
        ):

            return True

    return False


###############################################################################
# Remote Recording
###############################################################################

def remote_url_for(recording):

    remote_url = recording.get(
        "remote_url"
    )

    if remote_url:

        return remote_url

    relative_path = recording.get(
        "relative_path"
    )

    if not relative_path:

        return None

    return (
        f"{REMOTE_BASE_URL}/"
        f"{relative_path}"
    )


def download_remote_recording(
    recording,
    destination
):

    remote_url = remote_url_for(
        recording
    )

    if not remote_url:

        return False

    print(
        f"       Downloading: {remote_url}"
    )

    response = requests.get(
        remote_url,
        timeout=60
    )

    response.raise_for_status()

    temporary = (
        f"{destination}.download"
    )

    try:

        with open(
            temporary,
            "wb"
        ) as outfile:

            outfile.write(
                response.content
            )

        if not is_valid_mp3(
            temporary
        ):

            raise ValueError(
                "Remote file is not a valid MP3"
            )

        os.replace(
            temporary,
            destination
        )

    finally:

        if os.path.exists(
            temporary
        ):

            os.remove(
                temporary
            )

    return True


###############################################################################
# Copy / Download Recordings
###############################################################################

def copy_recordings(recordings, destination_dir=DESTINATION):

    banner(
        "Copying Recordings"
    )

    missing = []

    for office in (
        "oor",
        "mp",
        "dp",
        "ep",
        "np"
    ):

        office_recordings = recordings.get(
            office,
            []
        )

        if not office_recordings:

            print(
                f"{office.upper():3} : No recording resolved"
            )

            missing.append(f"{office} (no recording resolved)")

            continue

        if not isinstance(
            office_recordings,
            list
        ):

            office_recordings = [
                office_recordings
            ]

        for recording in office_recordings:

            filename = recording[
                "filename"
            ]

            destination = os.path.join(
                destination_dir,
                filename
            )

            print(
                f"{office.upper():3} : "
                f"{filename}"
            )

            source = recording.get("full_path")
            if not source or not os.path.isfile(source):
                relative_path = recording.get("relative_path")
                if relative_path:
                    expected_local = os.path.join(
                        LOTH_ROOT,
                        *relative_path.split("/"),
                    )
                    if os.path.isfile(expected_local):
                        source = expected_local
                    else:
                        source = None
                else:
                    source = find_local_recording(filename)

            ###################################################################
            # Online archive is authoritative; local files are fallback only.
            ###################################################################

            downloaded = False
            try:
                downloaded = download_remote_recording(
                    recording,
                    destination,
                )
            except (
                requests.exceptions.RequestException,
                ValueError
            ) as error:

                print(
                    f"       REMOTE DOWNLOAD FAILED: "
                    f"{error}"
                )

            if downloaded:
                print("       Downloaded from public archive")
                continue

            if source and is_valid_mp3(source):
                print(f"       Using local fallback: {source}")
                shutil.copyfile(source, destination)
                continue

            missing.append(
                filename
            )

    if missing:

        raise FileNotFoundError(
            "Required recordings are missing or "
            "could not be downloaded: "
            + ", ".join(missing)
        )


###############################################################################
# Finish
###############################################################################

def finish(destination=DESTINATION):

    banner(
        "Breviary Resolution Complete"
    )

    print(
        f"Destination: {destination}"
    )

    print()


###############################################################################
# Main
###############################################################################

def main():

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--date",
        help="Target date in YYYY-MM-DD format (defaults to tomorrow)",
    )
    args = parser.parse_args()

    print()

    print(
        "Starting Breviary Resolution Engine..."
    )

    day, offices, recordings = resolve(args.date)

    print_summary(
        day,
        offices,
        recordings
    )

    parent = os.path.dirname(DESTINATION)
    os.makedirs(parent, exist_ok=True)
    staging = tempfile.mkdtemp(prefix=".breviary_today.", dir=parent)
    try:
        copy_recordings(recordings, destination_dir=staging)

        # Only replace today's published input after every required recording
        # has been copied or downloaded successfully.
        ensure_destination()
        staged_names = set(os.listdir(staging))
        for filename in staged_names:
            os.replace(
                os.path.join(staging, filename),
                os.path.join(DESTINATION, filename),
            )
        for filename in os.listdir(DESTINATION):
            path = os.path.join(DESTINATION, filename)
            if os.path.isfile(path) and filename not in staged_names:
                os.remove(path)

        manifest = {
            "date": day.date.date().isoformat(),
            "weekday": day.weekday,
            "season": day.season,
            "celebration": day.celebration,
            "recordings": sorted(staged_names),
            "recording_paths": {
                office: [
                    item["relative_path"]
                    for item in (value if isinstance(value, list) else [value])
                ]
                for office, value in recordings.items()
                if value
            },
        }
        manifest_path = os.path.join(DESTINATION, "selected_day.json")
        temporary_manifest = manifest_path + ".tmp"
        with open(temporary_manifest, "w", encoding="utf-8") as outfile:
            json.dump(manifest, outfile, indent=2)
        os.replace(temporary_manifest, manifest_path)
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    finish()


if __name__ == "__main__":

    main()
