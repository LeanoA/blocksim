"""Unit and integration tests for the BlockSim CLI (`blocksim.cli`)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from blocksim.cli import main


def _write_simple_model(tmp_path: Path) -> Path:
    """Write a minimal valid Constant -> Gain -> Scope model JSON file."""
    payload = {
        "schema_version": "1.0.0",
        "model": {
            "name": "CLI Gain Model",
            "blocks": [
                {"id": "src", "type": "ConstantSource", "params": {"value": 3.0}},
                {"id": "gain", "type": "Gain", "params": {"k": 4.0}},
                {"id": "scope", "type": "Scope", "params": {}},
            ],
            "connections": [
                {
                    "source_block": "src",
                    "source_port": "out",
                    "target_block": "gain",
                    "target_port": "in",
                },
                {
                    "source_block": "gain",
                    "source_port": "out",
                    "target_block": "scope",
                    "target_port": "in",
                },
            ],
            "simulation_config": {
                "solver": "rk4",
                "t_start": 0.0,
                "t_end": 0.1,
                "dt": 0.05,
            },
        },
    }
    model_file = tmp_path / "gain_model.json"
    model_file.write_text(json.dumps(payload), encoding="utf-8")
    return model_file


class TestBlocksCommand:
    def test_blocks_text_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = main(["blocks"])
        captured = capsys.readouterr()
        assert code == 0
        assert "Registered blocks" in captured.out
        assert "ConstantSource" in captured.out
        assert "Integrator" in captured.out

    def test_blocks_json_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = main(["blocks", "--json"])
        captured = capsys.readouterr()
        assert code == 0
        data = json.loads(captured.out)
        types = {b["type"] for b in data["blocks"]}
        assert {"ConstantSource", "Gain", "Integrator", "Resistor"} <= types


class TestValidateCommand:
    def test_validate_valid_model(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = _write_simple_model(tmp_path)
        code = main(["validate", str(path), "--json"])
        captured = capsys.readouterr()
        assert code == 0
        data = json.loads(captured.out)
        assert data["valid"] is True

    def test_validate_invalid_model_returns_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        bad_file = tmp_path / "bad.json"
        bad_file.write_text(
            json.dumps(
                {
                    "name": "Broken",
                    "blocks": [{"id": "b1", "type": "UnknownBlock", "params": {}}],
                    "connections": [],
                }
            ),
            encoding="utf-8",
        )
        code = main(["validate", str(bad_file)])
        captured = capsys.readouterr()
        assert code == 1
        assert "INVALID" in captured.out

    def test_validate_missing_file_returns_2(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = main(["validate", str(tmp_path / "missing.json"), "--json"])
        captured = capsys.readouterr()
        assert code == 2
        data = json.loads(captured.out)
        assert data["valid"] is False


class TestInspectAndRunCommands:
    def test_inspect_json(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = _write_simple_model(tmp_path)
        code = main(["inspect", str(path), "--json"])
        captured = capsys.readouterr()
        assert code == 0
        data = json.loads(captured.out)
        assert data["block_count"] == 3
        assert data["connection_count"] == 2
        assert data["execution_order"] == ["src", "gain", "scope"]

    def test_run_simulation_and_export_output(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = _write_simple_model(tmp_path)
        out_file = tmp_path / "out.json"
        code = main(
            [
                "run",
                str(path),
                "--solver",
                "euler",
                "--t-end",
                "0.05",
                "--dt",
                "0.025",
                "--output",
                str(out_file),
                "--json",
            ]
        )
        captured = capsys.readouterr()
        assert code == 0
        summary = json.loads(captured.out)
        assert summary["solver"] == "euler"
        assert summary["final_signals"]["gain.out"] == pytest.approx(12.0)
        assert out_file.exists()
        saved = json.loads(out_file.read_text(encoding="utf-8"))
        assert "signals" in saved
        assert saved["signals"]["gain.out"][-1] == pytest.approx(12.0)
