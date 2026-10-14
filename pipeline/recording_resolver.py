#!/usr/bin/env python3

"""
Breviary Resolution Engine

Module:
recording_resolver.py

Resolve archive recordings from a LiturgicalDay.

Proper recordings are resolved from the local indexed archive first. The
remote archive is only a fallback when the local copy is unavailable.
"""

from archive import Archive
from remote_special_resolver import RemoteSpecialResolver
from urllib.parse import quote
from datetime import date, timedelta


REMOTE_ARCHIVE_BASE = (
    "https://freelygiveninc.org/"
    "wp-content/uploads/breviary/full_archive"
)


def _first_sunday_of_advent(year):
    christmas = date(year, 12, 25)
    sunday_before = christmas - timedelta(
        days=(christmas.weekday() + 1) % 7
    )
    return sunday_before - timedelta(days=21)


class RecordingResolver:

    def __init__(self, archive=None):

        self.archive = archive or Archive()
        self.remote_special = RemoteSpecialResolver()

    def resolve(self, day):
        return {
            "oor": self.resolve_oor(day),
            "mp": self.resolve_mp(day),
            "dp": self.resolve_dp(day),
            "ep": self.resolve_ep(day),
            "np": self.resolve_np(day),
        }

    def _season(self, day):

        return day.season

    def _proper(self, day, office):

        if day.season in ("Advent", "Christmas"):
            target = day.date.date() if hasattr(day.date, "date") else day.date
            mmdd = target.strftime("%m%d")
            code = getattr(day, "code", None)
            exact = []
            if code == "holyfamily":
                exact.append(f"psp_holyfamily_{office}")
                if office == "ep":
                    exact.insert(0, "psp_holyfamily_ep2")
            if day.season == "Advent" and target.month == 12 and target.day >= 17:
                exact.append(f"psp_{mmdd}_{office}")
            if day.season == "Christmas" and target.month == 12 and target.day >= 25:
                exact.append(f"psp_{mmdd}_{office}")
            if day.season == "Christmas" and target.month == 1 and target.day == 1:
                exact.append(f"psp_{mmdd}_{office}")
            if code:
                exact.extend((f"psp_{code}_{office}", f"loh_{code}_{office}"))
            exact.append(f"psp_{mmdd}_{office}")
            indexed = {r["stem"]: r for r in self.archive.all_recordings()
                       if r.get("folders", [None])[0] == day.season}
            for stem in exact:
                if stem in indexed:
                    result = dict(indexed[stem])
                    result["remote_url"] = (
                        f"{REMOTE_ARCHIVE_BASE}/"
                        f"{quote(result['relative_path'], safe='/')}"
                    )
                    return result
            return None

        if not day.code:
            return None

        # The public Full Archive is authoritative; the local index is a
        # fallback for offline recovery.
        remote = self.remote_special.resolve(day, office)
        if remote:
            return remote

        special = self.archive.find_special(day, office)
        if special:
            for recording in special:
                relative_path = recording.get("relative_path", recording["filename"])
                if not relative_path.startswith("Special_Days/"):
                    relative_path = f"Special_Days/{relative_path}"
                recording["remote_url"] = (
                    f"{REMOTE_ARCHIVE_BASE}/"
                    f"{quote(relative_path, safe='/')}"
                )
            return special

        # Final fallback: ordinary archive lookup.
        recording = self.archive.find_prefix(
            f"psp_{day.code}_{office}"
        )

        if recording:
            return recording

        return None

    def _ordinary_week_stem(
        self,
        weekday,
        week,
        office
    ):

        if week <= 7:

            return (
                f"psp_{weekday}"
                f"{week}o_{office}"
            )

        return (
            f"psp_{weekday}"
            f"{week}_{office}"
        )

    def _ordinary_recording(self, day, stem):
        if day.season in ("Advent", "Christmas"):
            office = stem.rsplit("_", 1)[-1]
            return self._seasonal_recording(day, office)

        filename = f"{stem}.mp3"
        local = self.archive.find_recording(
            filename=filename,
            season=self._season(day),
        )
        if local:
            relative_path = local["relative_path"]
            local["remote_url"] = (
                f"{REMOTE_ARCHIVE_BASE}/"
                f"{quote(relative_path, safe='/')}"
            )
            return [local]

        relative_path = (
            f"{day.season}/{day.weekday.title()}/{filename}"
        )
        return {
            "filename": filename,
            "stem": stem,
            "relative_path": relative_path,
            "folders": [day.season, day.weekday.title()],
            "remote_url": (
                f"{REMOTE_ARCHIVE_BASE}/"
                f"{quote(relative_path, safe='/')}"
            ),
        }

    def _seasonal_recording(self, day, office):
        """Resolve a seasonal recording only when that exact file is indexed."""
        target = day.date.date() if hasattr(day.date, "date") else day.date
        weekday = day.weekday
        month_day = target.strftime("%m%d")
        code = getattr(day, "code", None)
        records = self.archive.all_recordings()
        by_stem = {}
        for record in records:
            if record.get("folders", [None])[0] == day.season:
                by_stem.setdefault(record["stem"], []).append(record)

        candidates = []
        if day.season == "Advent":
            # The second half of Advent is recorded by calendar date.
            if target.month == 12 and target.day >= 17:
                candidates.extend([f"psp_{month_day}_{office}"])
            if code:
                candidates.extend([f"psp_{code}_{office}", f"loh_{code}_{office}"])
            candidates.append(f"psp_{month_day}_{office}")
            week = min(4, max(1, ((target - _first_sunday_of_advent(target.year)).days // 7) + 1))
            candidates.append(f"psp_{weekday}{week}a_{office}")
            if weekday == "sunday" and office == "ep":
                candidates.insert(0, f"psp_sunday{week}a_ep2")
            candidates.append(f"psp_{weekday}3_{office}")
            # NP is weekday-based throughout the season.
            if office == "np":
                candidates.append(f"psp_{weekday}_np")

        elif day.season == "Christmas":
            if target.month == 12 and target.day == 25:
                candidates.insert(0, f"psp_1225_{office}")
            if target.month == 12 and 26 <= target.day <= 31:
                candidates.insert(0, f"psp_{month_day}_{office}")
            if target.month == 1 and target.day == 1:
                candidates.insert(0, f"psp_0101_{office}")
            if code:
                candidates.extend([f"psp_{code}_{office}", f"loh_{code}_{office}"])
            if target.month == 12 and target.day <= 31:
                candidates.append(f"psp_{weekday}be_{office}")
            else:
                candidates.append(f"psp_{weekday}ep_{office}")
                if weekday == "sunday":
                    candidates.insert(-1, f"psp_epiphany_{office}2" if office == "ep" else f"psp_epiphany_{office}")
            if target.month == 1 and target.day == 10 and weekday == "sunday":
                candidates.insert(0, f"psp_epiphany_{office}2" if office == "ep" else f"psp_epiphany_{office}")
            if office == "np":
                candidates.append(f"psp_{weekday}_np")

        for stem in candidates:
            choices = by_stem.get(stem, [])
            record = next((r for r in choices if not any(
                folder.lower() in {
                    "monday", "tuesday", "wednesday", "thursday",
                    "friday", "saturday", "sunday",
                } and folder.lower() != weekday
                for folder in r.get("folders", [])
            )), None)
            if record is None and day.season == "Advent" and target.month == 12 and target.day == 24:
                record = next((r for r in records if r["stem"] == stem and
                               r.get("relative_path", "").startswith("Christmas/")), None)
            if record:
                result = dict(record)
                result["remote_url"] = (
                    f"{REMOTE_ARCHIVE_BASE}/"
                    f"{quote(result['relative_path'], safe='/')}"
                )
                return result
        if day.season == "Christmas" and office == "dp":
            psalter = ((day.psalter_week - 1) % 4) + 1
            fallback = f"psp_{weekday}{psalter}o_dp"
            record = next((r for r in records if r["stem"] == fallback and
                           r.get("relative_path", "").startswith("Ordinary Time/")), None)
            if record:
                result = dict(record)
                result["remote_url"] = (
                    f"{REMOTE_ARCHIVE_BASE}/"
                    f"{quote(result['relative_path'], safe='/')}"
                )
                return result
        raise FileNotFoundError(
            f"No indexed {day.season} recording for {target} {office}; "
            f"tried: {', '.join(candidates)}"
        )

    def resolve_oor(self, day):

        if day.office_of_readings == "proper":

            recording = self._proper(
                day,
                "oor"
            )

            if recording:
                return recording

        stem = self._ordinary_week_stem(
            day.weekday,
            day.ordinary_week,
            "oor"
        )

        return self._ordinary_recording(day, stem)

    def resolve_mp(self, day):

        if day.morning_prayer == "proper":

            recording = self._proper(
                day,
                "mp"
            )

            if recording:
                return recording

        if day.weekday == "sunday":

            stem = self._ordinary_week_stem(
                "sunday",
                day.ordinary_week,
                "mp"
            )

        else:

            psalter = (
                (day.psalter_week - 1) % 4
            ) + 1

            stem = (
                f"psp_{day.weekday}"
                f"{psalter}o_mp"
            )

        return self._ordinary_recording(day, stem)

    def resolve_dp(self, day):

        if day.daytime_prayer == "proper":

            recording = self._proper(
                day,
                "dp"
            )

            if recording:
                return recording

        if day.weekday == "sunday":

            stem = self._ordinary_week_stem(
                "sunday",
                day.ordinary_week,
                "dp"
            )

        else:

            psalter = (
                (day.psalter_week - 1) % 4
            ) + 1

            stem = (
                f"psp_{day.weekday}"
                f"{psalter}o_dp"
            )

        return self._ordinary_recording(day, stem)

    def resolve_ep(self, day):

        if day.evening_prayer == "proper":

            recording = self._proper(
                day,
                "ep"
            )

            if recording:
                return recording

        if day.weekday in (
            "saturday",
            "sunday"
        ):

            stem = self._ordinary_week_stem(
                day.weekday,
                day.ordinary_week,
                "ep"
            )

        else:

            psalter = (
                (day.psalter_week - 1) % 4
            ) + 1

            stem = (
                f"psp_{day.weekday}"
                f"{psalter}o_ep"
            )

        return self._ordinary_recording(day, stem)

    def resolve_np(self, day):

        if day.night_prayer == "proper":

            recording = self._proper(
                day,
                "np"
            )

            if recording:
                return recording if isinstance(recording, list) else [recording]

        if day.season in ("Advent", "Christmas"):
            return [self._seasonal_recording(day, "np")]

        recording = self.archive.find_recording(
            filename=f"psp_{day.weekday}_np.mp3",
            season=self._season(day),
            folders=(
                day.season,
                day.weekday.capitalize()
            )
        )

        if recording is None:
            recording = self._ordinary_recording(
                day,
                f"psp_{day.weekday}_np",
            )

        return [recording]
