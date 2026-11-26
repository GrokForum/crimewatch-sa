"""Mutation tests for pipeline/minor_guard.py.

Uses one synthetic public-catalog fixture with no real names. The guard is
necessary but not sufficient for RFC-006 §8.4.
"""
from __future__ import annotations

import copy

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
