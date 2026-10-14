from dataclasses import dataclass
from datetime import datetime, timedelta
import csv
import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SPECIAL_DAYS_FILE = os.path.join(BASE_DIR, "special_days.csv")
SPECIAL_DAYS_V2_FILE = os.path.join(BASE_DIR, "special_days_v2.csv")
LITURGICAL_WEEKS_FILE = os.path.join(BASE_DIR, "liturgical_weeks.csv")


@dataclass
class LiturgicalDay:
    date: datetime

    season: str
    celebration: str
    rank: str

    code: str | None

    ordinary_week: int
    psalter_week: int

    weekday: str

    office_of_readings: str
    morning_prayer: str
    daytime_prayer: str
    evening_prayer: str
    night_prayer: str


def get_special_day(month_day):

    if not os.path.exists(
        SPECIAL_DAYS_FILE
    ):
        return None

    with open(
        SPECIAL_DAYS_FILE,
        newline="",
        encoding="utf-8"
    ) as csvfile:

        reader = csv.DictReader(
            csvfile
        )

        for row in reader:

            if row["date"] == month_day:
                return row

    return None


def _advent_start(year):
    """Return the First Sunday of Advent (fourth Sunday before Christmas)."""
    christmas = datetime(year, 12, 25)
    sunday_before = christmas - timedelta(days=(christmas.weekday() + 1) % 7)
    return sunday_before - timedelta(days=21)


def _season_for_date(target_date):
    current = target_date.date()
    advent_start = _advent_start(target_date.year).date()
    if advent_start <= current < datetime(target_date.year, 12, 25).date():
        return "Advent"
    if current >= datetime(target_date.year, 12, 25).date():
        return "Christmas"
    previous_advent = _advent_start(target_date.year - 1).date()
    epiphany = datetime(target_date.year, 1, 6).date()
    baptism = epiphany + timedelta(days=(6 - epiphany.weekday()) % 7 or 7)
    if previous_advent <= current <= baptism:
        return "Christmas"
    return "Ordinary Time"


def get_seasonal_special_day(target_date):
    """Read the detailed 2026 proper calendar where its weekday code matches."""
    if target_date.year != 2026 or not os.path.exists(SPECIAL_DAYS_V2_FILE):
        return None
    month_day = target_date.strftime("%m-%d")
    weekday_code = target_date.strftime("%a").lower()[:2]
    with open(SPECIAL_DAYS_V2_FILE, newline="", encoding="utf-8") as csvfile:
        for row in csv.DictReader(csvfile):
            if row.get("date") == month_day:
                code = row.get("code", "")
                # The table contains year-specific weekday suffixes. Ignore
                # stale entries if the year is changed or the table is wrong.
                suffix = code[-2:] if code else ""
                if suffix in {"mo", "tu", "we", "th", "fr", "sa", "su"} and suffix != weekday_code:
                    return None
                return row
    return None


def _holy_family_date(year):
    christmas = datetime(year, 12, 25)
    sunday_after = christmas + timedelta(days=(6 - christmas.weekday()) % 7 or 7)
    # If Christmas itself is Sunday, the Sunday of the octave is January 1;
    # the feast is kept on December 30 instead.
    if christmas.weekday() == 6 or sunday_after.month == 1 and sunday_after.day == 1:
        return datetime(year, 12, 30).date()
    return sunday_after.date()


def get_week_record(target_date):

    target = target_date.date()

    latest = None

    with open(
        LITURGICAL_WEEKS_FILE,
        newline="",
        encoding="utf-8"
    ) as csvfile:

        reader = csv.DictReader(
            csvfile
        )

        for row in reader:

            row_date = datetime.strptime(
                row["date"],
                "%Y-%m-%d"
            ).date()

            if row_date <= target:

                latest = row

            else:

                break

    if latest is None:

        raise ValueError(
            f"No liturgical week for {target}"
        )

    return latest


def get_ordinary_week(target_date):

    return int(
        get_week_record(
            target_date
        )["ordinary_week"]
    )


def get_psalter_week(target_date):

    value = get_week_record(
        target_date
    )["psalter_week"]

    return int(
        str(value).replace(
            "o",
            ""
        )
    )


def _weekday_name(date):

    return date.strftime(
        "%A"
    ).lower()


def get_liturgical_day(
    target_date,
    ordinary_week,
    psalter_week
):

    ordinary_week = int(
        ordinary_week
    )

    psalter_week = int(
        psalter_week
    )

    weekday = _weekday_name(
        target_date
    )

    season = _season_for_date(target_date)
    celebration = "Feria"
    rank = "weekday"
    code = None

    office_of_readings = "weekday"
    morning_prayer = "weekday"
    daytime_prayer = "weekday"
    evening_prayer = "weekday"
    night_prayer = "weekday"

    month_day = target_date.strftime(
        "%m-%d"
    )

    special = get_seasonal_special_day(target_date) or get_special_day(month_day)
    if target_date.date() == _holy_family_date(target_date.year):
        special = {
            "name": "The Holy Family of Jesus, Mary and Joseph",
            "code": "holyfamily",
            "rank": "feast",
            "season": "Christmas",
            "oor": "proper", "mp": "proper", "dp": "proper",
            "ep": "proper", "np": "weekday",
        }

    if special:

        celebration = (
            special.get("name")
            or celebration
        )

        code = (
            special.get("code")
            or None
        )

        rank = (
            special.get("rank")
            or rank
        ).lower()

        season = (
            special.get("season")
            or season
        )

        if special.get(
            "psalter_week"
        ):

            psalter_week = int(
                str(
                    special[
                        "psalter_week"
                    ]
                ).replace(
                    "o",
                    ""
                )
            )

        if any(special.get(key) for key in ("oor", "mp", "dp", "ep", "np")):
            office_of_readings = special.get("oor") or "weekday"
            morning_prayer = special.get("mp") or "weekday"
            daytime_prayer = special.get("dp") or "weekday"
            evening_prayer = special.get("ep") or "weekday"
            night_prayer = special.get("np") or "weekday"

        elif rank == "memorial":

            office_of_readings = "proper"
            morning_prayer = "proper"
            evening_prayer = "proper"

        elif rank == "feast":

            office_of_readings = "proper"
            morning_prayer = "proper"
            daytime_prayer = "proper"
            evening_prayer = "proper"

        elif rank == "solemnity":

            office_of_readings = "proper"
            morning_prayer = "proper"
            daytime_prayer = "proper"
            evening_prayer = "proper"
            night_prayer = "proper"

    return LiturgicalDay(
        date=target_date,
        season=season,
        celebration=celebration,
        rank=rank,
        code=code,
        ordinary_week=ordinary_week,
        psalter_week=psalter_week,
        weekday=weekday,
        office_of_readings=office_of_readings,
        morning_prayer=morning_prayer,
        daytime_prayer=daytime_prayer,
        evening_prayer=evening_prayer,
        night_prayer=night_prayer,
    )
