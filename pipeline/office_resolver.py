#!/usr/bin/env python3

"""
office_resolver.py

Determines the liturgical source for each office.

This module contains liturgical reasoning.

It does NOT know anything about filenames,
directories, downloads, or WordPress.

Its only job is to answer:

    "Where does this office come from?"
"""


class OfficeResolver:

    def resolve(
        self,
        liturgical_day
    ):

        explicit = {
            "oor": getattr(liturgical_day, "office_of_readings", None),
            "mp": getattr(liturgical_day, "morning_prayer", None),
            "dp": getattr(liturgical_day, "daytime_prayer", None),
            "ep": getattr(liturgical_day, "evening_prayer", None),
            "np": getattr(liturgical_day, "night_prayer", None),
        }
        if all(value in ("proper", "weekday") for value in explicit.values()):
            return explicit

        rank = (
            liturgical_day.rank
            .lower()
        )

        if rank == "weekday":

            return self._resolve_weekday(
                liturgical_day
            )

        if rank == "memorial":

            return self._resolve_memorial(
                liturgical_day
            )

        if rank == "feast":

            return self._resolve_feast(
                liturgical_day
            )

        if rank == "solemnity":

            return self._resolve_solemnity(
                liturgical_day
            )

        raise ValueError(
            f"Unknown rank: {rank}"
        )

    def _resolve_weekday(
        self,
        liturgical_day
    ):

        return {

            "oor": "weekday",
            "mp": "weekday",
            "dp": "weekday",
            "ep": "weekday",
            "np": "weekday",
        }

    def _resolve_memorial(
        self,
        liturgical_day
    ):

        return {

            "oor": "proper",
            "mp": "proper",
            "dp": "weekday",
            "ep": "proper",
            "np": "weekday",
        }

    def _resolve_feast(
        self,
        liturgical_day
    ):

        return {

            "oor": "weekday",
            "mp": "weekday",
            "dp": "proper",
            "ep": "weekday",
            "np": "weekday",
        }

    def _resolve_solemnity(
        self,
        liturgical_day
    ):

        return {

            "oor": "proper",
            "mp": "proper",
            "dp": "proper",
            "ep": "proper",
            "np": "proper",
        }
