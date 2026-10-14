#!/usr/bin/env python3

"""
test_recording_resolver.py

Tests the Ordinary Time weekday implementation of
RecordingResolver.
"""

from datetime import datetime

from liturgical_calendar import get_liturgical_day
from recording_resolver import RecordingResolver


def print_office(name, recordings):

    print(f"\n{name.upper()}")

    if not recordings:

        print("  No recordings found.")
        return

    for recording in recordings:

        print(f"  {recording['filename']}")


def main():

    day = get_liturgical_day(
        datetime(2026, 7, 6),
        ordinary_week=14,
        psalter_week=2
    )

    resolver = RecordingResolver()

    plan = resolver.resolve(day)

    print()
    print("Recording Resolver Test")
    print("=======================")

    print(f"Date          : {day.date.date()}")
    print(f"Season        : {day.season}")
    print(f"Rank          : {day.rank}")
    print(f"Weekday       : {day.weekday}")
    print(f"Ordinary Week : {day.ordinary_week}")
    print(f"Psalter Week  : {day.psalter_week}")

    for office in (
        "oor",
        "mp",
        "dp",
        "ep",
        "np"
    ):

        print_office(
            office,
            plan[office]
        )


if __name__ == "__main__":

    main()