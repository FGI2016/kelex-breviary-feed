#!/usr/bin/env python3

"""
test_select_audio_v2.py

Integration test for the Breviary Resolution Engine.
"""

from datetime import datetime

from liturgical_calendar import get_liturgical_day
from office_resolver import OfficeResolver
from recording_resolver import RecordingResolver


def main():

    print()
    print("Breviary Resolution Engine")
    print("==========================")
    print()

    day = get_liturgical_day(
        datetime(2026, 7, 6),
        ordinary_week=14,
        psalter_week=2
    )

    office_plan = OfficeResolver().resolve(day)

    recording_plan = RecordingResolver().resolve(day)

    print("Liturgical Day")
    print("--------------")
    print(day)
    print()

    print("Office Plan")
    print("-----------")

    for office in (
        "oor",
        "mp",
        "dp",
        "ep",
        "np"
    ):

        print(
            f"{office:>3}: "
            f"{office_plan[office]}"
        )

    print()

    print("Recording Plan")
    print("--------------")

    for office in (
        "oor",
        "mp",
        "dp",
        "ep",
        "np"
    ):

        recordings = recording_plan[office]

        print()

        print(office.upper())

        if not recordings:

            print("  NONE")
            continue

        for recording in recordings:

            print(
                f"  {recording['filename']}"
            )


if __name__ == "__main__":

    main()