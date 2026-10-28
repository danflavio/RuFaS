"""Carregamento de configuração, dieta basal e cenários."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent
DATA_DIR = PACKAGE_DIR / "data"


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Carrega a configuração principal e resolve caminhos relativos à raiz do RuFaS."""
    config_path = Path(path) if path is not None else DATA_DIR / "config.json"
    config = _read_json(config_path)

    def resolve(value: str) -> str:
        candidate = Path(value)
        if candidate.is_absolute():
            return str(candidate)
        return str((PROJECT_ROOT / candidate).resolve())

    config["_config_path"] = str(config_path)
    config["paths"] = {key: resolve(value) for key, value in config.get("paths", {}).items()}
    config["output_dir"] = resolve(config.get("output_dir", "GO_campo_dourado/otimizacao_dieta"))
    return config


def load_baseline(path: str | Path | None = None) -> dict[str, Any]:
    """Carrega a descrição da dieta basal do RuFaS."""
    baseline_path = Path(path) if path is not None else DATA_DIR / "baseline_diet.json"
    baseline = _read_json(baseline_path)
    baseline["_path"] = str(baseline_path)
    return baseline


def load_scenarios(path: str | Path | None = None) -> dict[str, Any]:
    """Carrega as definições dos cenários de otimização."""
    scenarios_path = Path(path) if path is not None else DATA_DIR / "scenarios.json"
    scenarios = _read_json(scenarios_path)
    scenarios["_path"] = str(scenarios_path)
    return scenarios


def scenario_items(scenarios: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Retorna apenas os cenários válidos (ignora metadados com '_')."""
    return {
        key: value
        for key, value in scenarios.items()
        if not key.startswith("_") and isinstance(value, dict) and "overrides" in value
    }
