#!/usr/bin/env python3
"""Build the daily Breviary feed in a clean runner without local audio archives."""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta
from email.utils import format_datetime
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "pipeline"
TZ = ZoneInfo("Asia/Phnom_Penh")
OFFICES = ("oor", "mp", "dp", "ep", "np")
DAY_ORDER = {name: i for i, name in enumerate(
    ("sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday")
)}


def build(target_date: str | None) -> int:
    target = datetime.strptime(target_date, "%Y-%m-%d").date() if target_date else (
        datetime.now(TZ).date() + timedelta(days=1)
    )
    with tempfile.TemporaryDirectory(prefix="breviary-cloud-") as temp:
        temp_path = Path(temp)
        today_dir = temp_path / "today"
        archive_dir = temp_path / "archive"
        archive_dir.mkdir()
        output_file = temp_path / "generated.xml"
        env = os.environ.copy()
        env.update({
            "BREVIARY_TODAY_DIR": str(today_dir),
            "BREVIARY_LOTH_ROOT": str(temp_path / "no-local-archive"),
            "BREVIARY_ARCHIVE_DIR": str(archive_dir),
            "BREVIARY_OUTPUT_FILE": str(output_file),
            "BREVIARY_SPECIAL_DAYS_FILE": str(PIPELINE / "special_days.csv"),
            "PYTHONDONTWRITEBYTECODE": "1",
        })
        subprocess.run(
            [sys.executable, str(PIPELINE / "select_audio_v2.py"), "--date", target.isoformat()],
            cwd=ROOT, env=env, check=True,
        )
        manifest = json.loads((today_dir / "selected_day.json").read_text(encoding="utf-8"))
        if manifest.get("date") != target.isoformat():
            raise RuntimeError(f"Selector returned {manifest.get('date')} for {target}")
        found = {path.name for path in today_dir.glob("*.mp3")}
        if len(found) != len(OFFICES):
            raise RuntimeError(f"Expected five office recordings; found {sorted(found)}")
        for name in OFFICES:
            if not any(name in filename for filename in found):
                raise RuntimeError(f"Missing required office recording: {name}")

        # Build only today's five items. The rolling history comes from index.xml;
        # audio files for old episodes are never downloaded or stored in Actions.
        sys.path.insert(0, str(PIPELINE))
        import generate_rss
        records = generate_rss.build_records(
            audio_dir=str(archive_dir),
            today_dir=str(today_dir),
            special_days_file=str(PIPELINE / "special_days.csv"),
        )
        if len(records) != len(OFFICES) or {r["office"] for r in records} != set(OFFICES):
            raise RuntimeError("Feed builder did not resolve exactly one recording for each office")
        current_root = ET.fromstring(generate_rss.build_feed(records))
        source_root = ET.parse(ROOT / "index.xml").getroot()
        channel = source_root.find("channel")
        current_channel = current_root.find("channel")
        if channel is None or current_channel is None:
            raise RuntimeError("Input or generated RSS has no channel")
        for item in list(channel.findall("item")):
            title = item.findtext("title", "")
            if title.startswith(target.strftime("%A") + " - "):
                channel.remove(item)
        for item in current_channel.findall("item"):
            channel.append(item)
        old_build = channel.find("lastBuildDate")
        new_build = current_channel.findtext("lastBuildDate")
        if old_build is not None:
            old_build.text = new_build
        else:
            ET.SubElement(channel, "lastBuildDate").text = new_build

        items = channel.findall("item")
        if len(items) != 35:
            raise RuntimeError(f"Expected 35 rolling feed items, got {len(items)}")
        def item_key(item):
            title = item.findtext("title", "")
            weekday = title.split(" - ", 1)[0].lower()
            office = title.rsplit(" - ", 1)[-1].lower()
            return DAY_ORDER.get(weekday, 7), OFFICES.index(office) if office in OFFICES else 9
        for item in items:
            channel.remove(item)
        for item in sorted(items, key=item_key):
            channel.append(item)
        ET.register_namespace("itunes", "http://www.itunes.com/dtds/podcast-1.0.dtd")
        document = ET.tostring(source_root, encoding="utf-8", xml_declaration=True)
        ET.fromstring(document)
        temporary_output = ROOT / "index.xml.tmp"
        temporary_output.write_bytes(document)
        temporary_output.replace(ROOT / "index.xml")
        print(f"Built {target.isoformat()} ({manifest.get('season')}; {len(items)} feed items)")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", help="Target date in YYYY-MM-DD; default is tomorrow in Asia/Phnom_Penh")
    args = parser.parse_args()
    raise SystemExit(build(args.date))
