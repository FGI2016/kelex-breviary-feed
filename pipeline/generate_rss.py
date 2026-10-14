#!/usr/bin/env python3
"""Build the Breviary RSS feed from the selected day and rolling archive."""

import csv
import json
import os
import xml.etree.ElementTree as ET
from datetime import date, datetime
from email.utils import format_datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo

BASE_URL = "https://freelygiveninc.org/wp-content/uploads/breviary/archive"
FULL_ARCHIVE_BASE_URL = (
    "https://freelygiveninc.org/wp-content/uploads/breviary/full_archive"
)
AUDIO_DIR = os.environ.get("BREVIARY_ARCHIVE_DIR", os.path.expanduser("~/breviary_archive"))
TODAY_DIR = os.environ.get("BREVIARY_TODAY_DIR", os.path.expanduser("~/breviary_today"))
OUTPUT_FILE = os.environ.get("BREVIARY_OUTPUT_FILE", os.path.expanduser("~/breviary/kelex_breviary.xml"))
SPECIAL_DAYS_FILE = os.environ.get("BREVIARY_SPECIAL_DAYS_FILE", os.path.join(os.path.dirname(__file__), "special_days.csv"))
TZ = ZoneInfo("Asia/Phnom_Penh")

TITLE_MAP = {
    "oor": "Office of Readings",
    "mp": "Morning Prayer",
    "dp": "Daytime Prayer",
    "ep": "Evening Prayer",
    "np": "Night Prayer",
}
OFFICE_ORDER = {office: i for i, office in enumerate(TITLE_MAP, 1)}
DAY_ORDER = {
    "sunday": 0, "monday": 1, "tuesday": 2, "wednesday": 3,
    "thursday": 4, "friday": 5, "saturday": 6,
}
DAY_NAME = {day: day.title() for day in DAY_ORDER}


def load_special_dates(path=SPECIAL_DAYS_FILE):
    """Return proper-code to month/day mappings from the liturgical table."""
    if not os.path.isfile(path):
        return {}
    with open(path, newline="", encoding="utf-8") as infile:
        return {
            row["code"]: row["date"]
            for row in csv.DictReader(infile)
            if row.get("code") and row.get("date")
        }


def parse_filename(filename, *, recording_timestamp=None, target_date=None,
                   special_dates=None):
    """Parse an office recording; special codes use their calendar date."""
    if not filename.endswith(".mp3"):
        return None
    parts = filename[:-4].split("_")
    if len(parts) < 3:
        return None
    office_token = parts[-1].lower()
    # The archive marks second Vespers with ep2; the podcast feed still has one
    # Evening Prayer slot, so include that recording as the day's EP item.
    office = "ep" if office_token == "ep2" else office_token
    if office not in OFFICE_ORDER:
        return None

    token = parts[1].lower()
    weekday = next((day for day in DAY_ORDER if token.startswith(day)), None)
    if weekday is None and target_date is not None:
        weekday = target_date.strftime("%A").lower()
    if weekday is None:
        special_dates = special_dates or {}
        month_day = special_dates.get(token)
        if month_day:
            if target_date:
                year = target_date.year
            elif recording_timestamp is not None:
                year = datetime.fromtimestamp(recording_timestamp, TZ).year
            else:
                year = datetime.now(TZ).year
            try:
                month, day_number = map(int, month_day.split("-"))
                weekday = date(year, month, day_number).strftime("%A").lower()
            except ValueError:
                return None
    if weekday is None:
        return None
    return {"weekday": weekday, "office": office, "filename": filename}


def parse_office(filename):
    if not filename.endswith(".mp3"):
        return None
    office = filename[:-4].split("_")[-1].lower()
    if office == "ep2":
        return "ep"
    return office if office in OFFICE_ORDER else None


def read_target_date(today_dir=TODAY_DIR):
    manifest = os.path.join(today_dir, "selected_day.json")
    if not os.path.isfile(manifest):
        return None
    try:
        with open(manifest, encoding="utf-8") as infile:
            return date.fromisoformat(json.load(infile)["date"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def read_target_manifest(today_dir=TODAY_DIR):
    manifest = os.path.join(today_dir, "selected_day.json")
    try:
        with open(manifest, encoding="utf-8") as infile:
            return json.load(infile)
    except (OSError, ValueError, TypeError):
        return {}


def find_today_recordings(today_dir=TODAY_DIR, *, target_date=None,
                          special_dates=None):
    if not os.path.isdir(today_dir):
        return []
    records = []
    for filename in os.listdir(today_dir):
        path = os.path.join(today_dir, filename)
        if not os.path.isfile(path):
            continue
        info = parse_filename(
            filename,
            recording_timestamp=os.path.getmtime(path),
            target_date=target_date,
            special_dates=special_dates,
        )
        if info:
            info.update(file_path=path, file_size=os.path.getsize(path),
                        mtime=os.path.getmtime(path))
            records.append(info)
    return sorted(records, key=lambda r: OFFICE_ORDER[r["office"]])


def find_archive_recordings(audio_dir=AUDIO_DIR, *, special_dates=None):
    if not os.path.isdir(audio_dir):
        return []
    latest = {}
    for filename in os.listdir(audio_dir):
        path = os.path.join(audio_dir, filename)
        if not os.path.isfile(path):
            continue
        mtime = os.path.getmtime(path)
        info = parse_filename(
            filename, recording_timestamp=mtime, special_dates=special_dates
        )
        if not info:
            continue
        info.update(file_path=path, file_size=os.path.getsize(path), mtime=mtime)
        key = (info["weekday"], info["office"])
        if key not in latest or mtime > latest[key]["mtime"]:
            latest[key] = info
    return list(latest.values())


def build_records(audio_dir=AUDIO_DIR, today_dir=TODAY_DIR,
                  special_days_file=SPECIAL_DAYS_FILE):
    special_dates = load_special_dates(special_days_file)
    manifest = read_target_manifest(today_dir)
    target_date = read_target_date(today_dir)
    current = find_today_recordings(
        today_dir, target_date=target_date, special_dates=special_dates
    )
    season = manifest.get("season")
    recording_paths = manifest.get("recording_paths", {})
    for record in current:
        paths = recording_paths.get(record["office"], [])
        if paths:
            relative_path = paths.pop(0)
        else:
            token = record["filename"][:-4].split("_")[1].lower()
            is_special = token in special_dates
            if is_special:
                relative_path = f"Special_Days/{record['filename']}"
            else:
                relative_path = (
                    f"{season}/{record['weekday'].title()}/"
                    f"{record['filename']}"
                )
        record["file_url"] = (
            f"{FULL_ARCHIVE_BASE_URL}/"
            f"{quote(relative_path, safe='/')}"
        )
    current_keys = {(r["weekday"], r["office"]) for r in current}
    previous = find_archive_recordings(audio_dir, special_dates=special_dates)
    records = [r for r in previous
               if (r["weekday"], r["office"]) not in current_keys]
    records.extend(current)
    records.sort(key=lambda r: (DAY_ORDER[r["weekday"]], OFFICE_ORDER[r["office"]]))
    return records


def build_feed(records, *, now=None):
    now = now or datetime.now(ZoneInfo("UTC"))
    itunes = "http://www.itunes.com/dtds/podcast-1.0.dtd"
    ET.register_namespace("itunes", itunes)
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Daily Audio Files"
    ET.SubElement(channel, "link").text = "https://freelygiveninc.org"
    ET.SubElement(channel, "language").text = "en-us"
    ET.SubElement(channel, "description").text = "Daily audio for prayer throughout the day."
    ET.SubElement(channel, f"{{{itunes}}}author").text = "Daily Audio Files"
    ET.SubElement(channel, f"{{{itunes}}}summary").text = "Daily audio for prayer throughout the day."
    ET.SubElement(channel, f"{{{itunes}}}explicit").text = "false"
    ET.SubElement(channel, f"{{{itunes}}}category", {"text": "Religion & Spirituality"})
    ET.SubElement(channel, f"{{{itunes}}}image", {
        "href": "https://freelygiveninc.org/wp-content/uploads/breviary/artwork.jpg"
    })
    ET.SubElement(channel, "lastBuildDate").text = format_datetime(now)

    for record in records:
        url = record.get("file_url") or f"{BASE_URL}/{record['filename']}"
        item = ET.SubElement(channel, "item")
        title = f"{DAY_NAME[record['weekday']]} - {TITLE_MAP[record['office']]}"
        ET.SubElement(item, "title").text = title
        ET.SubElement(item, "enclosure", {
            "url": url, "length": str(record["file_size"]), "type": "audio/mpeg"
        })
        ET.SubElement(item, "guid").text = url
        stamp = datetime.fromtimestamp(record["mtime"], ZoneInfo("UTC"))
        ET.SubElement(item, "pubDate").text = format_datetime(stamp)

    return ET.tostring(rss, encoding="utf-8", xml_declaration=True)


def generate(output_file=OUTPUT_FILE, audio_dir=AUDIO_DIR, today_dir=TODAY_DIR,
             special_days_file=SPECIAL_DAYS_FILE):
    records = build_records(audio_dir, today_dir, special_days_file)
    document = build_feed(records)
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    temporary = output_file + ".tmp"
    with open(temporary, "wb") as outfile:
        outfile.write(document)
    os.replace(temporary, output_file)
    print(f"RSS written to {output_file} ({len(records)} items)")
    return records


if __name__ == "__main__":
    generate()
