from datetime import date
from pathlib import Path

import pytest

from scripts.import_mospi_excel import _select_vintage_candidate


def test_newer_vintage_replaces_older_candidate(tmp_path):
    candidates = {}
    observation_date = date(2026, 6, 1)
    older = tmp_path / "June2026_Annex-IV.xlsx"
    newer = tmp_path / "July2026_Annex-IV.xlsx"

    _select_vintage_candidate(candidates, observation_date, (2026, 6), 100.1, older, "cpi_headline")
    _select_vintage_candidate(candidates, observation_date, (2026, 7), 100.2, newer, "cpi_headline")

    assert candidates[observation_date] == ((2026, 7), 100.2, newer)


def test_identical_same_vintage_duplicate_is_accepted(tmp_path):
    candidates = {}
    observation_date = date(2026, 6, 1)
    first = tmp_path / "June2026_Annex-IV.xlsx"
    duplicate = tmp_path / "copy_June2026_Annex-IV.xlsx"

    _select_vintage_candidate(candidates, observation_date, (2026, 6), 100.1, first, "cpi_headline")
    _select_vintage_candidate(candidates, observation_date, (2026, 6), 100.1, duplicate, "cpi_headline")

    assert candidates[observation_date] == ((2026, 6), 100.1, first)


def test_conflicting_same_vintage_values_are_rejected(tmp_path):
    candidates = {}
    observation_date = date(2026, 6, 1)
    first = tmp_path / "June2026_Annex-IV.xlsx"
    conflict = tmp_path / "copy_June2026_Annex-IV.xlsx"
    _select_vintage_candidate(candidates, observation_date, (2026, 6), 100.1, first, "cpi_headline")

    with pytest.raises(ValueError, match="Conflicting cpi_headline snapshots"):
        _select_vintage_candidate(candidates, observation_date, (2026, 6), 100.2, conflict, "cpi_headline")
