"""Geração dos arquivos de integração para rodar a dieta ótima no RuFaS."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from .lp_model import DietSolution


def _load(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write(path: str | Path, data: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def _round_percentages(percentages: dict[int, float]) -> dict[int, float]:
    rounded = {int(feed_id): round(float(pct), 4) for feed_id, pct in percentages.items() if pct > 1e-6}
    total = sum(rounded.values())
    if abs(total - 100.0) > 1e-6:
        # Ajusta o maior componente para fechar 100%.
        largest = max(rounded, key=rounded.get)
        rounded[largest] = round(rounded[largest] + (100.0 - total), 4)
    return {feed_id: pct for feed_id, pct in rounded.items() if pct > 1e-6}


def write_feed_config(
    base_feed_path: str | Path,
    solution: DietSolution,
    output_path: str | Path,
    usd_brl: float,
    animal_combination: str = "lac_cow",
) -> Path:
    """Escreve uma cópia do feed.json do RuFaS com a ração otimizada."""
    feed_config = copy.deepcopy(_load(base_feed_path))
    existing = {int(feed["feed_type"]): feed for feed in feed_config["feeds"]}

    percentages: dict[int, float] = {}
    for feed, kg in zip(solution.feeds, solution.x_kg_dm):
        pct = kg / solution.dmi_kg * 100.0
        if pct <= 1e-6:
            continue
        percentages[feed.rufas_id] = pct
        price_usd = round(feed.price_usd_kg_dm(usd_brl), 4)
        if feed.rufas_id not in existing:
            # RuFaS usa US$/kg de MS.
            existing[feed.rufas_id] = {
                "feed_type": feed.rufas_id,
                "purchased_feed_cost": price_usd,
                "buffer": 0.15,
                "runtime_purchase_allowance": 1000.0,
                "advance_purchase_allowance": 1000000.0,
                "planning_cycle_allowance": 1000.0,
            }
        else:
            # Mantém o custo do RuFaS alinhado à tabela de preços usada no PL.
            existing[feed.rufas_id]["purchased_feed_cost"] = price_usd
    feed_config["feeds"] = sorted(existing.values(), key=lambda item: int(item["feed_type"]))
    rounded = _round_percentages(percentages)

    found = False
    for ration in feed_config.get("rations", []):
        if ration.get("animal_combination") == animal_combination:
            ration["feeds"] = [
                {"feed_type": int(feed_id), "ration_percentage": pct} for feed_id, pct in rounded.items()
            ]
            found = True
            break
    if not found:
        raise ValueError(f"Ração para '{animal_combination}' não encontrada no feed config.")

    _write(output_path, feed_config)
    return Path(output_path)


def write_config(
    base_config_path: str | Path,
    output_path: str | Path,
    simulation_type: str = "animals_only",
    start_date: str = "2015:1",
    end_date: str = "2015:365",
) -> Path:
    config = copy.deepcopy(_load(base_config_path))
    config["simulation_type"] = simulation_type
    config["start_date"] = start_date
    config["end_date"] = end_date
    _write(output_path, config)
    return Path(output_path)


def write_farm_metadata(
    base_metadata_path: str | Path,
    output_path: str | Path,
    feed_path: str,
    config_path: str,
) -> Path:
    metadata = copy.deepcopy(_load(base_metadata_path))
    metadata["files"]["feed"]["path"] = feed_path
    metadata["files"]["config"]["path"] = config_path
    _write(output_path, metadata)
    return Path(output_path)


def write_tasks(
    output_dir: str | Path,
    farm_metadata_path: str,
    output_prefix: str = "GO_dieta_otimizada",
    seed: int = 44,
) -> tuple[Path, Path]:
    output_dir = Path(output_dir)
    tasks = {
        "parallel_workers": 1,
        "export_input_data_to_csv": False,
        "input_data_csv_export_path": "output/CSVs",
        "tasks": [
            {
                "task_type": "SIMULATION_SINGLE_RUN",
                "metadata_file_path": farm_metadata_path,
                "output_prefix": output_prefix,
                "log_verbosity": "errors",
                "random_seeds": [seed],
            }
        ],
    }
    tasks_path = output_dir / "_otimizacao_tasks.json"
    _write(tasks_path, tasks)
    task_manager = {
        "files": {
            "tasks": {
                "title": "Task manager data",
                "description": "Validação da dieta otimizada",
                "path": str(tasks_path).replace("\\", "/"),
                "type": "json",
                "properties": "tasks_properties",
            }
        }
    }
    tm_path = output_dir / "_otimizacao_task_manager_metadata.json"
    _write(tm_path, task_manager)
    return tasks_path, tm_path


def generate_integration_files(
    config: dict[str, Any],
    solution: DietSolution,
    output_dir: str | Path,
    seed: int = 44,
) -> dict[str, Path]:
    """Gera feed, config, metadata e tasks de validação."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = config["paths"]
    usd_brl = float(config["farm"]["usd_brl"])

    feed_path = output_dir / "feed_otimizado.json"
    write_feed_config(paths["rufas_feed_config"], solution, feed_path, usd_brl)

    config_path = output_dir / "config_otimizado.json"
    write_config(
        paths["rufas_config"],
        config_path,
        simulation_type="animals_only",
        start_date="2015:1",
        end_date="2015:365",
    )

    metadata_path = output_dir / "farm_metadata_otimizado.json"
    write_farm_metadata(
        paths["rufas_farm_metadata"],
        metadata_path,
        feed_path=str(feed_path).replace("\\", "/"),
        config_path=str(config_path).replace("\\", "/"),
    )

    output_prefix = "GO_validacao_iso" if seed == 44 else f"GO_validacao_iso_s{seed}"
    tasks_path, tm_path = write_tasks(
        output_dir,
        farm_metadata_path=str(metadata_path).replace("\\", "/"),
        output_prefix=output_prefix,
        seed=seed,
    )
    return {
        "feed": feed_path,
        "config": config_path,
        "farm_metadata": metadata_path,
        "tasks": tasks_path,
        "task_manager": tm_path,
    }


def run_rufas_task(task_manager_path: str | Path, project_root: str | Path) -> int:
    """Executa o RuFaS com o wrapper gerado e devolve o código de saída."""
    command = [
        sys.executable,
        "main.py",
        "-p",
        str(task_manager_path),
        "-v",
        "errors",
    ]
    completed = subprocess.run(command, cwd=str(project_root), check=False)
    return int(completed.returncode)
