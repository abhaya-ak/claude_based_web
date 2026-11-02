import json
from pathlib import Path

from apps.reports.management.commands.seed_playbooks import load_hotlines_data


class TestHotlinesLoader:
    """
    Tests for D135:
    - hotlines.json entries require name, number, source_url, verified_on.
    - Loader refuses entries without source_url and verified_on.
    - Nepal entries stay empty.
    """

    def test_loader_refuses_entries_without_source_url(self, tmp_path):
        data = {
            "MY": [
                {
                    "name": "Invalid Hotline",
                    "number": "997",
                    "verified_on": "2026-10-01",
                    # missing source_url
                }
            ]
        }
        hotlines_file = tmp_path / "hotlines.json"
        hotlines_file.write_text(json.dumps(data), encoding="utf-8")

        loaded = load_hotlines_data(tmp_path)
        assert loaded.get("MY") == []

    def test_loader_refuses_entries_without_verified_on(self, tmp_path):
        data = {
            "MY": [
                {
                    "name": "Invalid Hotline",
                    "number": "997",
                    "source_url": "https://example.com/hotline",
                    # missing verified_on
                }
            ]
        }
        hotlines_file = tmp_path / "hotlines.json"
        hotlines_file.write_text(json.dumps(data), encoding="utf-8")

        loaded = load_hotlines_data(tmp_path)
        assert loaded.get("MY") == []

    def test_loader_accepts_valid_entries(self, tmp_path):
        data = {
            "MY": [
                {
                    "name": "Valid Hotline",
                    "number": "997",
                    "source_url": "https://example.com/hotline",
                    "verified_on": "2026-10-01",
                }
            ],
            "NP": [],
        }
        hotlines_file = tmp_path / "hotlines.json"
        hotlines_file.write_text(json.dumps(data), encoding="utf-8")

        loaded = load_hotlines_data(tmp_path)
        assert len(loaded.get("MY", [])) == 1
        entry = loaded["MY"][0]
        assert entry["name"] == "Valid Hotline"
        assert entry["number"] == "997"
        assert entry["source_url"] == "https://example.com/hotline"
        assert entry["verified_on"] == "2026-10-01"
        assert loaded.get("NP") == []

    def test_loader_handles_missing_file_gracefully(self, tmp_path):
        loaded = load_hotlines_data(tmp_path)
        assert loaded == {}

    def test_nepal_entries_stay_empty_in_actual_hotlines_file(self):
        data_dir = Path(__file__).resolve().parent.parent / "data"
        loaded = load_hotlines_data(data_dir)
        # Per D135: Nepal entries stay empty until owner supplies them
        assert loaded.get("NP", []) == []
