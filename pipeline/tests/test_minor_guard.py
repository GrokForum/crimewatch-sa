"""Mutation tests for pipeline/minor_guard.py.

Uses one synthetic public-catalog fixture with no real names. The guard is
necessary but not sufficient for RFC-006 §8.4.
"""
from __future__ import annotations

import copy
import re

import pytest

import minor_guard

# One synthetic catalog-like fixture. No real people, towns or outlets.
SYNTHETIC = {
    "date": "2026-01-15",
    "summary": (
        "No new official or news item with a fetched source was added "
        "on this lean morning run."
    ),
    "item": {
        "id": "2026-01-15-sample",
        "title": "An arrest after a reported attack",
        "place": "a town in the province",
        "summary": (
            "A farmer and his wife were attacked. An 18-year-old man was "
            "arrested. The deceased and the suspects are not named here."
        ),
        "source_title": "Official post",
    },
}


def _parts(fixture: dict) -> tuple[str, ...]:
    item = fixture["item"]
    return (
        fixture["summary"],
        item["title"],
        item["place"],
        item["summary"],
        item["source_title"],
    )


def _scan(fixture: dict) -> list[str]:
    return minor_guard.scan_our_wording(fixture["item"]["id"], *_parts(fixture))


def _mutate_item(suffix: str) -> dict:
    fixture = copy.deepcopy(SYNTHETIC)
    fixture["item"]["summary"] += " " + suffix
    return fixture


def _mutate_day(suffix: str) -> dict:
    fixture = copy.deepcopy(SYNTHETIC)
    fixture["summary"] += " " + suffix
    return fixture


def test_module_notes_rfc006_scope():
    assert "necessary but not sufficient for RFC-006 §8.4" in (minor_guard.__doc__ or "")


def test_synthetic_fixture_is_clean():
    assert _scan(SYNTHETIC) == []
    for part in _parts(SYNTHETIC):
        assert not minor_guard.has_minor_age(part)
        assert not minor_guard.has_person_grade(part)


@pytest.mark.parametrize("words, value", [
    ("twenty-four", 24),
    ("two hundred and fifteen", 215),
    ("two hundred and sixteen", 216),
    ("eighteen", 18),
    ("forty", 40),
    ("a hundred", 100),
    ("one hundred and fifteen", 115),
    ("nine hundred and thirty-nine", 939),
    ("six thousand five hundred and seventy-five", 6575),
])
def test_word_number_parser(words, value):
    assert minor_guard.parse_word_number(words) == value
    assert minor_guard.parse_number(words) == value
    assert minor_guard.parse_number(str(value)) == value


@pytest.mark.parametrize("phrase", [
    "A 17-year-old boy was wounded.",
    "A two-year-old girl was wounded.",
    "age 12",
    "12 y/o",
    "12 y.o.",
    "a 24-month-old infant",
    "aged 24 months",
    "215 months old",
    "eighteen-month-old",
    "an eighteen-month-old infant",
    "two hundred and fifteen months old",
    "a two-hundred-and-fifteen-month-old infant",
    "one hundred and fifteen months old",
    "child (15)",
    "teen (15)",
    "the child, 7,",
    "the boy, 12,",
    "a girl (16)",
    "the toddler, 2,",
    "learner (14)",
    "the pupil, 11,",
    "the baby, 6,",
    "three weeks old",
    "a 10-week-old baby",
    "seven days old",
    "aged forty weeks",
    "nine hundred and thirty-nine weeks old",
    "age of 12",
    "fifteen years of age",
    "A boy aged nine was wounded.",
    "age twelve was reported.",
    "a boy of 9",
    "a child of 15",
    "a girl of nine",
    "a minor of 16",
    "a teen of 14",
    "7-yo",
    "7-yr-old",
    "a 7-yo child",
    "a 7-yr-old child",
    "a daughter of 7",
    "a son of 8",
    "a grandchild of 6",
    "a grandson of 9",
    "a granddaughter of 10",
    "a nephew of 11",
    "a niece of 12",
    "an infant of 18 months",
    "a child of 18 months",
    "The girl, 14 was",
    "The child was 7",
])
def test_minor_age_mutation_is_refused(phrase):
    fixture = _mutate_item(phrase)
    fails = _scan(fixture)
    assert any("exact age of a person under 18" in f for f in fails), (phrase, fails)
    assert minor_guard.has_minor_age(fixture["item"]["summary"])


def test_day_summary_minor_age_mutation_is_refused():
    fixture = _mutate_day("A child (15) was named in the summary.")
    fails = _scan(fixture)
    assert any("exact age of a person under 18" in f for f in fails), fails


@pytest.mark.parametrize("phrase", [
    "age 18",
    "18 y/o",
    "18 y.o.",
    "216 months old",
    "two hundred and sixteen months old",
    "An 18-year-old man was arrested.",
    "A 48-year-old man was arrested.",
    "He was sentenced to 7 years in prison.",
    "the child, 18,",
    "teen (18)",
    "the child, 7 days later, was found",
    "A 21-year-old learner was arrested.",
    "nine hundred and forty weeks old",
    "six thousand five hundred and seventy-five days old",
    "a group of 9",
    "a child of the community",
    "children of 15 families",
    "a boy of 18",
    "twenty-one-year-old",
    "a mother of 3",
    "father of 2",
    "sentenced to 18 months",
    "The child was 18",
    "The child was 7 days later",
    "7 years in prison",
])
def test_adult_age_and_sentence_length_are_allowed(phrase):
    fixture = _mutate_item(phrase)
    fails = _scan(fixture)
    assert not any("exact age of a person under 18" in f for f in fails), (phrase, fails)
    assert not minor_guard.has_minor_age(phrase)


@pytest.mark.parametrize("phrase", [
    "A Grade 12 learner was arrested.",
    "a grade 10 pupil",
    "the learner in grade 11",
    "Grade 7 learner",
    "a grade 8 boy",
    "the pupil of grade 3",
    "Gr 7 pupil",
    "Gr. 7 pupil",
    "gr7 learner",
    "grade-7 learner",
    "Grade-7 learner",
    "gr-7 pupil",
    "grade–7 learner",
])
def test_grade_tied_to_person_is_refused(phrase):
    fixture = _mutate_item(phrase)
    fails = _scan(fixture)
    assert any("school grade tied to a person" in f for f in fails), (phrase, fails)
    assert minor_guard.has_person_grade(phrase)


@pytest.mark.parametrize("phrase", [
    "A 21-year-old learner was arrested.",
    "Grade 12 results were released.",
    "the grade of the offence",
    "The larger group of 7 pupils gathered.",
    "Mr. Grant, a pupil, spoke.",
    "GR 12 results were released.",
    "Gr.7",
    "GR 12 results",
])
def test_untied_grade_or_adult_learner_is_allowed(phrase):
    fixture = _mutate_item(phrase)
    fails = _scan(fixture)
    assert not any("school grade tied to a person" in f for f in fails), (phrase, fails)
    assert not minor_guard.has_person_grade(phrase)


def test_scan_reports_age_and_grade_together():
    fixture = _mutate_item("A Grade 12 learner, child (15), was wounded.")
    fails = _scan(fixture)
    assert any("exact age of a person under 18" in f for f in fails), fails
    assert any("school grade tied to a person" in f for f in fails), fails


@pytest.mark.parametrize("phrase", [
    "A boy aged nine was wounded.",
    "age twelve was reported.",
])
def test_mid_sentence_word_age_is_refused(phrase):
    """Word ages must be captured even when more sentence text follows."""
    fixture = _mutate_item(phrase)
    fails = _scan(fixture)
    assert any("exact age of a person under 18" in f for f in fails), (phrase, fails)
    assert minor_guard.has_minor_age(phrase)


@pytest.mark.parametrize("phrase", [
    "a boy of 9",
    "a child of 15",
    "a girl of nine",
    "a minor of 16",
    "a teen of 14",
    "a learner of 12",
    "a pupil of 11",
    "a baby of 2",
    "a toddler of 3",
    "an infant of 1",
])
def test_role_of_n_under_18_is_refused(phrase):
    fixture = _mutate_item(phrase)
    fails = _scan(fixture)
    assert any("exact age of a person under 18" in f for f in fails), (phrase, fails)
    assert minor_guard.has_minor_age(phrase)


@pytest.mark.parametrize("phrase", [
    "a group of 9",
    "a child of the community",
    "children of 15 families",
    "a boy of 18",
])
def test_role_of_n_negatives_are_allowed(phrase):
    fixture = _mutate_item(phrase)
    fails = _scan(fixture)
    assert not any("exact age of a person under 18" in f for f in fails), (phrase, fails)
    assert not minor_guard.has_minor_age(phrase)


@pytest.mark.parametrize("phrase", [
    "Gr 7 pupil",
    "Gr. 7 pupil",
    "gr7 learner",
])
def test_grade_abbreviation_tied_to_person_is_refused(phrase):
    fixture = _mutate_item(phrase)
    fails = _scan(fixture)
    assert any("school grade tied to a person" in f for f in fails), (phrase, fails)
    assert minor_guard.has_person_grade(phrase)


@pytest.mark.parametrize("phrase", [
    "The larger group of 7 pupils gathered.",
    "Mr. Grant, a pupil, spoke.",
    "GR 12 results were released.",
])
def test_gr_as_a_different_word_is_allowed(phrase):
    fixture = _mutate_item(phrase)
    fails = _scan(fixture)
    assert not any("school grade tied to a person" in f for f in fails), (phrase, fails)
    assert not minor_guard.has_person_grade(phrase)


# --- Item and day-summary tests for each new branch ---

@pytest.mark.parametrize("phrase", [
    "7-yo",
    "7-yr-old",
    "a 7-yo child",
    "a 7-yr-old child",
])
def test_yo_and_yr_old_are_refused_in_item_and_day(phrase):
    item = _mutate_item(phrase)
    day = _mutate_day(phrase)
    for fixture in (item, day):
        fails = _scan(fixture)
        assert any("exact age of a person under 18" in f for f in fails), (phrase, fails)
    assert minor_guard.has_minor_age(phrase)


@pytest.mark.parametrize("phrase", [
    "a daughter of 7",
    "a son of 8",
    "a grandchild of 6",
    "a grandson of 9",
    "a granddaughter of 10",
    "a nephew of 11",
    "a niece of 12",
])
def test_kin_of_n_is_refused_in_item_and_day(phrase):
    item = _mutate_item(phrase)
    day = _mutate_day(phrase)
    for fixture in (item, day):
        fails = _scan(fixture)
        assert any("exact age of a person under 18" in f for f in fails), (phrase, fails)
    assert minor_guard.has_minor_age(phrase)


@pytest.mark.parametrize("phrase", [
    "a mother of 3",
    "father of 2",
])
def test_parent_of_n_is_allowed_in_item_and_day(phrase):
    item = _mutate_item(phrase)
    day = _mutate_day(phrase)
    for fixture in (item, day):
        fails = _scan(fixture)
        assert not any("exact age of a person under 18" in f for f in fails), (phrase, fails)
    assert not minor_guard.has_minor_age(phrase)


@pytest.mark.parametrize("phrase", [
    "an infant of 18 months",
    "a child of 18 months",
])
def test_role_of_n_with_month_unit_is_refused_in_item_and_day(phrase):
    item = _mutate_item(phrase)
    day = _mutate_day(phrase)
    for fixture in (item, day):
        fails = _scan(fixture)
        assert any("exact age of a person under 18" in f for f in fails), (phrase, fails)
    assert minor_guard.has_minor_age(phrase)


def test_sentenced_to_18_months_is_allowed_in_item_and_day():
    phrase = "sentenced to 18 months"
    item = _mutate_item(phrase)
    day = _mutate_day(phrase)
    for fixture in (item, day):
        fails = _scan(fixture)
        assert not any("exact age of a person under 18" in f for f in fails), fails
    assert not minor_guard.has_minor_age(phrase)


@pytest.mark.parametrize("phrase", [
    "The girl, 14 was",
    "The child was 7",
])
def test_unclosed_appositive_and_role_was_n_are_refused_in_item_and_day(phrase):
    item = _mutate_item(phrase)
    day = _mutate_day(phrase)
    for fixture in (item, day):
        fails = _scan(fixture)
        assert any("exact age of a person under 18" in f for f in fails), (phrase, fails)
    assert minor_guard.has_minor_age(phrase)


@pytest.mark.parametrize("phrase", [
    "grade-7 learner",
    "Grade-7 learner",
    "gr-7 pupil",
    "grade–7 learner",
])
def test_hyphenated_grade_is_refused_mutation(phrase):
    fixture = _mutate_item(phrase)
    fails = _scan(fixture)
    assert any("school grade tied to a person" in f for f in fails), (phrase, fails)
    assert minor_guard.has_person_grade(phrase)
    day = _mutate_day(phrase)
    assert any("school grade tied to a person" in f for f in _scan(day)), phrase


# --- Separator fuzz: every existing refused/allowed phrase, each separator ---

_SEP_RUN_BETWEEN = re.compile(
    r"(?<=[A-Za-z0-9])[\s .‐‑‒–—−-]+(?=[A-Za-z0-9])"
)

SEPARATOR_VARIANTS = [
    " ",
    "-",
    "‐",
    "‑",
    "‒",
    "–",
    "—",
    "−",
    " ",
    ".",
]


def _with_separator(phrase: str, sep: str) -> str:
    return _SEP_RUN_BETWEEN.sub(sep, phrase)


def _is_refused(text: str) -> bool:
    return minor_guard.has_minor_age(text) or minor_guard.has_person_grade(text)


# The existing refused phrases (age and grade) used across this module, plus
# the separator-gap forms this round is meant to close.
FUZZ_REFUSED = (
    "A 17-year-old boy was wounded.",
    "A two-year-old girl was wounded.",
    "age 12",
    "12 y/o",
    "12 y.o.",
    "a 24-month-old infant",
    "aged 24 months",
    "215 months old",
    "eighteen-month-old",
    "an eighteen-month-old infant",
    "two hundred and fifteen months old",
    "a two-hundred-and-fifteen-month-old infant",
    "one hundred and fifteen months old",
    "child (15)",
    "teen (15)",
    "the child, 7,",
    "the boy, 12,",
    "a girl (16)",
    "the toddler, 2,",
    "learner (14)",
    "the pupil, 11,",
    "the baby, 6,",
    "three weeks old",
    "a 10-week-old baby",
    "seven days old",
    "aged forty weeks",
    "nine hundred and thirty-nine weeks old",
    "age of 12",
    "fifteen years of age",
    "A boy aged nine was wounded.",
    "age twelve was reported.",
    "a boy of 9",
    "a child of 15",
    "a girl of nine",
    "a minor of 16",
    "a teen of 14",
    "7-yo",
    "7-yr-old",
    "a daughter of 7",
    "a son of 8",
    "an infant of 18 months",
    "The girl, 14 was",
    "The child was 7",
    "A Grade 12 learner was arrested.",
    "a grade 10 pupil",
    "the learner in grade 11",
    "Grade 7 learner",
    "a grade 8 boy",
    "the pupil of grade 3",
    "Gr 7 pupil",
    "Gr. 7 pupil",
    "gr7 learner",
    "grade-7 learner",
    "Grade-7 learner",
    "gr-7 pupil",
    "grade–7 learner",
)

# Named allowed phrases from Reviewer A, plus the existing allowance set.
FUZZ_ALLOWED = (
    "Gr.7",
    "twenty-one-year-old",
    "GR 12 results",
    "a group of 9",
    "7 years in prison",
    "community hub",
    "age 18",
    "18 y/o",
    "18 y.o.",
    "216 months old",
    "two hundred and sixteen months old",
    "An 18-year-old man was arrested.",
    "A 48-year-old man was arrested.",
    "He was sentenced to 7 years in prison.",
    "the child, 18,",
    "teen (18)",
    "the child, 7 days later, was found",
    "A 21-year-old learner was arrested.",
    "nine hundred and forty weeks old",
    "six thousand five hundred and seventy-five days old",
    "a child of the community",
    "children of 15 families",
    "a boy of 18",
    "a mother of 3",
    "father of 2",
    "sentenced to 18 months",
    "Grade 12 results were released.",
    "the grade of the offence",
    "The larger group of 7 pupils gathered.",
    "Mr. Grant, a pupil, spoke.",
    "GR 12 results were released.",
    "the hub of the community",
)


@pytest.mark.parametrize("phrase", FUZZ_REFUSED)
@pytest.mark.parametrize("sep", SEPARATOR_VARIANTS, ids=lambda s: ascii(s))
def test_separator_fuzz_refuses_existing_phrases(phrase, sep):
    fuzzed = _with_separator(phrase, sep)
    assert _is_refused(fuzzed), (phrase, ascii(sep), fuzzed)


@pytest.mark.parametrize("phrase", FUZZ_ALLOWED)
@pytest.mark.parametrize("sep", SEPARATOR_VARIANTS, ids=lambda s: ascii(s))
def test_separator_fuzz_allows_existing_phrases(phrase, sep):
    fuzzed = _with_separator(phrase, sep)
    assert not _is_refused(fuzzed), (phrase, ascii(sep), fuzzed)


def test_separator_fuzz_mutation_on_synthetic_fixture():
    """One mutation check: a hyphen / en-dash grade and a 7-yo age on the fixture."""
    for phrase in ("grade-7 learner", "grade–7 learner", "7-yo", "a daughter of 7"):
        fixture = _mutate_item(phrase)
        fails = _scan(fixture)
        assert fails, phrase
        for sep in SEPARATOR_VARIANTS:
            fuzzed = _with_separator(phrase, sep)
            mutated = _mutate_item(fuzzed)
            assert _scan(mutated), (phrase, ascii(sep), fuzzed)
