"""Guard for exact ages of anyone under 18 in wording we write.

Applied to titles, places, summaries and source titles — not to an external
source URL, whose slug may repeat the publisher's text.

This guard is necessary but not sufficient for RFC-006 §8.4 (minor-age
wording on public pages). Callers must still review wording by hand.
"""
from __future__ import annotations

import re

# 18 years in days, using the average Gregorian year so week and day counts
# compare cleanly against the 216-month (= 18 year) threshold.
_DAYS_PER_YEAR = 365.25
_UNDER_18_DAYS = 18 * _DAYS_PER_YEAR
_UNDER_18_MONTHS = 18 * 12  # 216; 216 months is 18 years exactly and is allowed

_SMALL = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
_SCALES = {"hundred": 100, "thousand": 1000, "million": 1_000_000}

_ROLE = (
    r"child|children|teen|teens|teenager|teenagers|boy|boys|"
    r"girl|girls|baby|babies|toddler|toddlers|learner|learners|"
    r"pupil|pupils|infant|infants"
)
_PERSON = (
    rf"{_ROLE}|student|students"
)


def parse_word_number(text: str) -> int | None:
    """Parse a whole number written in English words, or None if invalid."""
    parts = [
        p for p in re.split(r"[\s\-]+", (text or "").casefold())
        if p and p not in {"and", "a", "an"}
    ]
    if not parts:
        return None
    total = 0
    current = 0
    seen = False
    for word in parts:
        if word in _SMALL:
            current += _SMALL[word]
            seen = True
        elif word == "hundred":
            current = (current or 1) * 100
            seen = True
        elif word in _SCALES:
            current = (current or 1) * _SCALES[word]
            total += current
            current = 0
            seen = True
        else:
            return None
    if not seen:
        return None
    return total + current


def parse_number(text: str) -> int | None:
    """Parse digits or English words into an int, trying a trailing number run."""
    raw = (text or "").strip().strip(" ,;:()[]")
    if not raw:
        return None
    if re.fullmatch(r"\d{1,7}", raw):
        return int(raw)
    parts = re.split(r"\s+", raw)
    for i in range(len(parts)):
        cand = " ".join(parts[i:])
        if re.fullmatch(r"\d{1,7}", cand):
            return int(cand)
        value = parse_word_number(cand)
        if value is not None:
            return value
    return None


def _under_18(count: int, unit: str) -> bool:
    stem = unit.lower().rstrip("s")
    if stem == "year":
        return count < 18
    if stem == "month":
        return count < _UNDER_18_MONTHS
    if stem == "week":
        return count * 7 < _UNDER_18_DAYS
    if stem == "day":
        return count < _UNDER_18_DAYS
    return False


# Optional "a/an", then digits or an English word-number (hyphens and "and").
_NUM_TOKEN = (
    r"(?:(?:a|an)\s+)?(?:\d{1,7}|(?:[a-z]+(?:[\s\-]+(?:and[\s\-]+)?[a-z]+)*))"
)
_UNIT_OLD_RE = re.compile(
    rf"(?ix)\b(?P<num>{_NUM_TOKEN})\s*[-–]?\s*(?P<unit>years?|months?|weeks?|days?)"
    r"\s*(?:[-–]?\s*old|of\s+age)\b"
)
_AGED_UNIT_RE = re.compile(
    rf"(?ix)\baged\s+(?P<num>{_NUM_TOKEN})\s*(?P<unit>years?|months?|weeks?|days?)\b"
)
_AGE_N_RE = re.compile(
    rf"(?ix)\b(?:age|aged)\s+(?:of\s+)?(?P<num>{_NUM_TOKEN})"
    r"\b(?!\s*[-–]\s*(?:1[8-9]|[2-9]\d))"
)
_YO_RE = re.compile(
    rf"(?ix)\b(?P<num>{_NUM_TOKEN})\s*"
    r"(?:y\s*/\s*o|y\s*\.\s*o\.?|yrs?|yo)\b"
)


def _duration_under_18(text: str) -> bool:
    for rx in (_UNIT_OLD_RE, _AGED_UNIT_RE):
        for match in rx.finditer(text):
            count = parse_number(match.group("num"))
            if count is None:
                continue
            if _under_18(count, match.group("unit")):
                return True
    return False


def _stated_years_under_18(text: str) -> bool:
    """'age 12', 'aged twelve', '12 y/o', '12 y.o.' — years implied, not a duration."""
    for match in _YO_RE.finditer(text):
        count = parse_number(match.group("num"))
        if count is not None and count < 18:
            return True
    for match in _AGE_N_RE.finditer(text):
        # Skip if this 'aged N' is 'aged N months/weeks/days/years' (handled above).
        tail = text[match.end():match.end() + 16].casefold()
        if re.match(r"\s*(years?|months?|weeks?|days?)\b", tail):
            continue
        count = parse_number(match.group("num"))
        if count is not None and count < 18:
            return True
    return False


_ROLE_BRACKET_RE = re.compile(
    rf"(?ix)\b(?:{_ROLE})\s*[\(\[]\s*(?P<num>[^)\]]+?)\s*[\)\]]"
)
_ROLE_APPOSITIVE_RE = re.compile(
    rf"(?ix)\b(?:the|a|an)?\s*(?:{_ROLE})\s*,\s*(?P<num>[^,]+?)\s*,"
)


def _role_number_under_18(text: str) -> bool:
    """Bare under-18 numbers next to child/teen/... wording, or in brackets/apposition."""
    for rx in (_ROLE_BRACKET_RE, _ROLE_APPOSITIVE_RE):
        for match in rx.finditer(text):
            chunk = match.group("num").strip()
            unit_m = re.match(
                r"(?ix)(.+?)\s*(years?|months?|weeks?|days?)\b(.*)$",
                chunk,
            )
            # 'the child, 7 days later,' is not a bare age.
            if unit_m and not re.search(r"(?i)\b(?:old|of\s+age)\b", chunk):
                continue
            count = parse_number(chunk)
            if count is not None and count < 18:
                return True
    return False


_GRADE_RE = re.compile(
    rf"(?ix)"
    rf"\bgrade\s*(?P<g1>[1-9]|1[0-2])\s+(?:{_PERSON})\b"
    rf"|\b(?:{_PERSON})\s+(?:in\s+|of\s+)?grade\s*(?P<g2>[1-9]|1[0-2])\b"
)


def has_person_grade(text: str) -> bool:
    """True if a school grade is tied to a person (learner, pupil, child, ...)."""
    return bool(text and _GRADE_RE.search(text))


def has_minor_age(text: str) -> bool:
    """True if the text states an exact age under 18 years.

    Covers year, month, week and day counts in digits or words, plus a bare
    under-18 number next to child/teen/boy/girl/baby/toddler/learner/pupil
    wording or in an appositive or brackets. A sentence length such as
    '7 years in prison' is not an age and is allowed. Adult ages (18+) pass.
    """
    if not text:
        return False
    if _duration_under_18(text):
        return True
    if _stated_years_under_18(text):
        return True
    if _role_number_under_18(text):
        return True
    return False


def scan_our_wording(label: str, *parts: str) -> list[str]:
    """Scan wording we wrote (not external source URLs) for minor-age issues.

    Necessary but not sufficient for RFC-006 §8.4.
    """
    fails = []
    saw_age = False
    saw_grade = False
    for part in parts:
        if not part:
            continue
        if not saw_age and has_minor_age(part):
            fails.append(f"{label}: exact age of a person under 18")
            saw_age = True
        if not saw_grade and has_person_grade(part):
            fails.append(f"{label}: school grade tied to a person")
            saw_grade = True
        if saw_age and saw_grade:
            break
    return fails
