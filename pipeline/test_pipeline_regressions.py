import json
import contextlib
import io
import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
import xml.etree.ElementTree as ET

from archive import Archive
from generate_rss import build_feed, build_records, parse_filename, parse_office
from recording_resolver import RecordingResolver
from select_audio_v2 import copy_recordings
from liturgical_calendar import get_liturgical_day


class PipelineRegressionTests(unittest.TestCase):
    def test_online_special_recording_is_primary_with_local_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ordinary = {"recordings": []}
            special = {
                "archive_root": str(root / "Special_Days"),
                "recordings": [
                    {"filename": "loh_0603we_oor.mp3",
                     "stem": "loh_0603we_oor",
                     "relative_path": "loh_0603we_oor.mp3", "folders": []},
                    {"filename": "loh_0603we_oor_extra.mp3",
                     "stem": "loh_0603we_oor_extra",
                     "relative_path": "loh_0603we_oor_extra.mp3", "folders": []},
                ],
            }
            ordinary_path = root / "ordinary.json"
            special_path = root / "special.json"
            ordinary_path.write_text(json.dumps(ordinary), encoding="utf-8")
            special_path.write_text(json.dumps(special), encoding="utf-8")
            archive = Archive(str(ordinary_path), str(special_path))

            class RemoteAvailable:
                def resolve(self, *_):
                    return {"filename": "loh_0603we_oor.mp3", "remote_url": "https://example.test/file.mp3"}

            resolver = RecordingResolver(archive)
            resolver.remote_special = RemoteAvailable()
            day = type("Day", (), {
                "season": "Ordinary Time", "code": "0603we",
                "office_of_readings": "proper", "morning_prayer": "weekday",
                "daytime_prayer": "weekday", "evening_prayer": "weekday",
                "night_prayer": "weekday", "weekday": "wednesday",
                "ordinary_week": 10, "psalter_week": 3,
            })()

            result = resolver.resolve_oor(day)
            self.assertEqual(result["remote_url"], "https://example.test/file.mp3")

            class RemoteUnavailable:
                def resolve(self, *_):
                    return None

            resolver.remote_special = RemoteUnavailable()
            result = resolver.resolve_oor(day)
            self.assertEqual([r["filename"] for r in result], ["loh_0603we_oor.mp3"])
            self.assertEqual(
                result[0]["remote_url"],
                "https://freelygiveninc.org/wp-content/uploads/breviary/"
                "full_archive/Special_Days/loh_0603we_oor.mp3",
            )
            self.assertEqual(
                result[0]["full_path"],
                str(root / "Special_Days" / "loh_0603we_oor.mp3"),
            )

    def test_special_code_filename_maps_to_calendar_weekday(self):
        parsed = parse_filename(
            "loh_0603we_oor.mp3",
            target_date=date(2026, 6, 3),
            special_dates={"0603we": "06-03"},
        )
        self.assertEqual(parsed["weekday"], "wednesday")
        self.assertEqual(parsed["office"], "oor")

    def test_second_vespers_recordings_are_included_as_evening_prayer(self):
        for filename, target in (
            ("psp_sunday1a_ep2.mp3", date(2026, 11, 29)),
            ("psp_holyfamily_ep2.mp3", date(2026, 12, 27)),
        ):
            parsed = parse_filename(filename, target_date=target)
            self.assertIsNotNone(parsed, filename)
            self.assertEqual(parsed["office"], "ep", filename)
            self.assertEqual(parsed["weekday"], target.strftime("%A").lower(), filename)
            self.assertEqual(parse_office(filename), "ep", filename)

    def test_missing_local_ordinary_recording_gets_remote_candidate(self):
        class EmptyArchive:
            def find_recording(self, **_kwargs):
                return None

        resolver = RecordingResolver(EmptyArchive())
        day = type("Day", (), {
            "season": "Ordinary Time", "weekday": "tuesday",
            "ordinary_week": 28, "psalter_week": 4,
            "office_of_readings": "weekday",
        })()
        result = resolver.resolve_oor(day)
        self.assertEqual(result["filename"], "psp_tuesday28_oor.mp3")
        self.assertEqual(
            result["remote_url"],
            "https://freelygiveninc.org/wp-content/uploads/breviary/"
            "full_archive/Ordinary%20Time/Tuesday/psp_tuesday28_oor.mp3",
        )

    def test_unresolved_required_office_aborts_before_copying(self):
        with tempfile.TemporaryDirectory() as temp:
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(FileNotFoundError, "oor"):
                    copy_recordings({}, destination_dir=temp)
            self.assertEqual(os.listdir(temp), [])

    def test_current_special_recording_replaces_ordinary_feed_item(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            today = root / "today"
            archive = root / "archive"
            today.mkdir()
            archive.mkdir()
            (today / "loh_0603we_mp.mp3").write_bytes(b"ID3special")
            (archive / "psp_wednesday3o_mp.mp3").write_bytes(b"ID3ordinary")
            (today / "selected_day.json").write_text(
                json.dumps({"date": "2026-06-03", "weekday": "wednesday"}),
                encoding="utf-8",
            )
            special_days = root / "special_days.csv"
            special_days.write_text(
                "date,code,name,rank,season,psalter_week\n"
                "06-03,0603we,Saint Charles Lwanga and Companions,memorial,Ordinary Time,\n",
                encoding="utf-8",
            )

            records = build_records(str(archive), str(today), str(special_days))
            matching = [r for r in records
                        if r["weekday"] == "wednesday" and r["office"] == "mp"]
            self.assertEqual(len(matching), 1)
            self.assertEqual(matching[0]["filename"], "loh_0603we_mp.mp3")

            xml = build_feed(records, now=datetime(2026, 6, 2, 12))
            ET.fromstring(xml)
            self.assertIn(b"Wednesday - Morning Prayer", xml)
            self.assertIn(b"itunes:category", xml)

    def test_seasonal_feed_uses_exact_resolved_archive_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            today = root / "today"
            archive = root / "archive"
            today.mkdir()
            archive.mkdir()
            for filename in (
                "psp_1217_oor.mp3", "psp_1217_mp.mp3",
                "psp_1217_dp.mp3", "psp_1217_ep.mp3",
                "psp_thursday_np.mp3",
            ):
                (today / filename).write_bytes(b"ID3seasonal")
            paths = {
                "oor": ["Advent/Second Half/psp_1217_oor.mp3"],
                "mp": ["Advent/Second Half/psp_1217_mp.mp3"],
                "dp": ["Advent/Second Half/psp_1217_dp.mp3"],
                "ep": ["Advent/Second Half/psp_1217_ep.mp3"],
                "np": ["Advent/Thursday/psp_thursday_np.mp3"],
            }
            (today / "selected_day.json").write_text(json.dumps({
                "date": "2026-12-17", "weekday": "thursday",
                "season": "Advent", "recording_paths": paths,
            }), encoding="utf-8")

            records = build_records(str(archive), str(today), str(root / "none.csv"))
            by_office = {record["office"]: record for record in records}
            self.assertEqual(len(by_office), 5)
            self.assertIn(
                "/Advent/Second%20Half/psp_1217_oor.mp3",
                by_office["oor"]["file_url"],
            )
            self.assertIn(
                "/Advent/Thursday/psp_thursday_np.mp3",
                by_office["np"]["file_url"],
            )

    def test_calendar_recognizes_2026_advent_and_christmas(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        expected = {
            "2026-11-29": "Advent",
            "2026-12-24": "Advent",
            "2026-12-25": "Christmas",
            "2027-01-10": "Christmas",
            "2027-01-11": "Ordinary Time",
        }
        for value, season in expected.items():
            day = datetime.fromisoformat(value).replace(tzinfo=ZoneInfo("Asia/Bangkok"))
            result = get_liturgical_day(day, ordinary_week=34, psalter_week=2)
            self.assertEqual(result.season, season, value)
        holy_family = datetime(2026, 12, 27, tzinfo=ZoneInfo("Asia/Bangkok"))
        result = get_liturgical_day(holy_family, ordinary_week=34, psalter_week=2)
        self.assertEqual(result.code, "holyfamily")

    def test_advent_sunday_ep2_is_a_valid_five_office_feed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            today = root / "today"
            archive = root / "archive"
            today.mkdir()
            archive.mkdir()
            filenames = (
                "psp_sunday1a_oor.mp3", "psp_sunday1a_mp.mp3",
                "psp_sunday1a_dp.mp3", "psp_sunday1a_ep2.mp3",
                "psp_sunday_np.mp3",
            )
            for filename in filenames:
                (today / filename).write_bytes(b"ID3seasonal")
            paths = {office: [f"Advent/Sunday/{filename}"] for office, filename in zip(
                ("oor", "mp", "dp", "ep", "np"), filenames
            )}
            (today / "selected_day.json").write_text(json.dumps({
                "date": "2026-11-29", "weekday": "sunday", "season": "Advent",
                "recording_paths": paths,
            }), encoding="utf-8")

            records = build_records(str(archive), str(today), str(root / "none.csv"))
            self.assertEqual(len(records), 5)
            by_office = {record["office"]: record for record in records}
            self.assertEqual(by_office["ep"]["filename"], "psp_sunday1a_ep2.mp3")
            self.assertIn("/Advent/Sunday/psp_sunday1a_ep2.mp3", by_office["ep"]["file_url"])

    def test_cloud_calendar_contains_2026_special_days(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("Asia/Phnom_Penh")
        teresa = get_liturgical_day(
            datetime(2026, 10, 15, tzinfo=tz), ordinary_week=28, psalter_week=3
        )
        self.assertEqual(teresa.celebration, "Saint Teresa of Avila")
        self.assertEqual(teresa.rank, "memorial")
        self.assertEqual(teresa.code, "1015th")
        self.assertEqual(
            (teresa.office_of_readings, teresa.morning_prayer,
             teresa.daytime_prayer, teresa.evening_prayer, teresa.night_prayer),
            ("proper", "proper", "weekday", "proper", "weekday"),
        )

        advent = get_liturgical_day(
            datetime(2026, 12, 3, tzinfo=tz), ordinary_week=49, psalter_week=2
        )
        self.assertEqual(advent.celebration, "Saint Francis Xavier")
        self.assertEqual(advent.season, "Advent")

        christmas = get_liturgical_day(
            datetime(2026, 12, 25, tzinfo=tz), ordinary_week=49, psalter_week=2
        )
        self.assertEqual(christmas.celebration, "The Nativity of the Lord")
        self.assertEqual(christmas.rank, "solemnity")
        self.assertEqual(christmas.season, "Christmas")

    def test_holy_family_uses_named_proper_recordings(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        day = get_liturgical_day(
            datetime(2026, 12, 27, tzinfo=ZoneInfo("Asia/Bangkok")),
            ordinary_week=34,
            psalter_week=2,
        )
        recordings = RecordingResolver().resolve(day)
        self.assertEqual(recordings["oor"]["filename"], "psp_holyfamily_oor.mp3")
        self.assertEqual(recordings["mp"]["filename"], "psp_holyfamily_mp.mp3")
        self.assertEqual(recordings["ep"]["filename"], "psp_holyfamily_ep2.mp3")


if __name__ == "__main__":
    unittest.main()
