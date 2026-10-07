import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import tempfile
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock


class TestProfiler:
    def test_profile_dataset_creates_json(self, tmp_path, monkeypatch):
        monkeypatch.setattr("agents.profiler.PROFILES_DIR", tmp_path)
        monkeypatch.setattr("agents.profiler.LLM_PROVIDER", "github")

        # Create a test CSV
        csv_path = tmp_path / "test.csv"
        df = pd.DataFrame({"id": [1, 2, 3], "name": ["a", "b", "c"], "value": [10.0, 20.0, None]})
        df.to_csv(csv_path, index=False)

        # Mock LLM call
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"semantic_meanings": {"test": {"id": "unique identifier"}}, "join_keys": [], "quality_notes": ["ok"]}'
        mock_llm.invoke.return_value = mock_response
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"messages": [mock_response]}

        with patch("agents.profiler._make_llm", return_value=mock_llm), patch("agents.profiler.create_agent", return_value=mock_agent):
            from agents.profiler import profile_dataset
            result = profile_dataset(str(csv_path), "test-run", "Profile this dataset")

        assert Path(result).exists()
        with open(result) as f:
            profile = json.load(f)
        assert "datasets" in profile
        assert "test" in profile["datasets"]
        assert profile["datasets"]["test"]["shape"]["rows"] == 3
        assert profile["datasets"]["test"]["shape"]["columns"] == 3

    def test_profile_multiple_datasets(self, tmp_path, monkeypatch):
        monkeypatch.setattr("agents.profiler.PROFILES_DIR", tmp_path)
        monkeypatch.setattr("agents.profiler.LLM_PROVIDER", "github")

        # Create test CSVs
        csv1 = tmp_path / "sales.csv"
        csv2 = tmp_path / "products.csv"
        pd.DataFrame({"product_id": [1, 2], "revenue": [100, 200]}).to_csv(csv1, index=False)
        pd.DataFrame({"product_id": [1, 2], "name": ["A", "B"]}).to_csv(csv2, index=False)

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '```json\n{"semantic_meanings": {}, "join_keys": [{"left_dataset": "sales", "left_column": "product_id", "right_dataset": "products", "right_column": "product_id", "confidence": "high"}], "quality_notes": ["ok"]}\n```'
        mock_llm.invoke.return_value = mock_response
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"messages": [mock_response]}

        with patch("agents.profiler._make_llm", return_value=mock_llm), patch("agents.profiler.create_agent", return_value=mock_agent):
            from agents.profiler import profile_multiple_datasets
            result = profile_multiple_datasets(
                [str(csv1), str(csv2)],
                "test-run",
                "Profile these datasets and identify join keys",
            )

        assert Path(result).exists()
        with open(result) as f:
            profile = json.load(f)
        assert len(profile["datasets"]) == 2
