"""CLI do módulo de otimização da dieta."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from .config import load_baseline, load_config, load_scenarios, scenario_items
from .economics import compare, economics, mineral_decomposition
from .feed_library import load_feeds
from .integration import generate_integration_files, run_rufas_task
from .lp_model import DietLP, fixed_diet_solution
from .report import generate_report
from .requirements import apply_requirement_overrides, build_requirements
from .sensitivity import (
    break_even_table,
    one_at_a_time_prices,
    pairwise_break_even,
    pairwise_scenarios,
    sobol_feed_cost,
    sobol_iofc,
)
from .tableau import build_tableau
from .validation import summarize_validation

FEED_IDS_SENSITIVITY = [51, 44, 167, 58, 169, 154, 36, 193, 112, 60]
PAIRWISE_FEEDS = [(44, 154), (167, 60), (167, 169), (51, 110), (167, 112), (36, 193)]


def _model_for_scenario(
    base_model: DietLP,
    scenario: dict[str, Any],
) -> DietLP:
    overrides = scenario.get("overrides", {})
    requirements = apply_requirement_overrides(base_model.requirements, overrides.get("requirements"))
    return DietLP(
        base_model.with_bound_overrides(overrides.get("bounds")).feeds,
        requirements,
        base_model.config,
    )


def _scenario_row(
    key: str,
    label: str,
    solution,
    baseline_solution,
    farm: dict[str, Any],
) -> dict[str, Any]:
    econ = economics(solution, farm)
    base_econ = economics(baseline_solution, farm)
    return {
        "cenario": key,
        "label": label,
        "custo_brl_vaca_dia": econ["custo_racao_brl_vaca_dia"],
        "custo_brl_kg_ms": econ["custo_racao_brl_kg_ms"],
        "custo_brl_kg_leite": econ["custo_racao_brl_kg_leite"],
        "economia_vs_basal_pct": (
            (base_econ["custo_racao_brl_vaca_dia"] - econ["custo_racao_brl_vaca_dia"])
            / base_econ["custo_racao_brl_vaca_dia"]
            * 100.0
        ),
        "iofc_brl_vaca_dia": econ["iofc_brl_vaca_dia"],
        "iofc_delta_pct": (
            (econ["iofc_brl_vaca_dia"] - base_econ["iofc_brl_vaca_dia"]) / base_econ["iofc_brl_vaca_dia"] * 100.0
        ),
        "custo_anual_brl": econ["custo_racao_anual_brl"],
        "economia_anual_brl": (base_econ["custo_racao_anual_brl"] - econ["custo_racao_anual_brl"]),
        "tdn_pct": solution.nutrient_supply["tdn_pct"],
        "cp_pct": solution.nutrient_supply["cp_pct"],
        "ndf_pct": solution.nutrient_supply["ndf_pct"],
    }


def run_analysis(
    output_dir: str | Path | None = None,
    fast: bool = False,
    sobol_n: int | None = None,
    seed: int = 44,
    run_rufas: bool = False,
) -> dict[str, Any]:
    config = load_config()
    if output_dir is not None:
        config["output_dir"] = str(Path(output_dir).resolve())
    output_dir = Path(config["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    feeds = load_feeds(config)
    requirements = build_requirements(config)
    baseline_data = load_baseline()
    farm = dict(config["farm"])
    farm["milk_kg_cow_day"] = float(baseline_data["milk_kg_cow_day"])
    scenarios = scenario_items(load_scenarios())

    base_model = DietLP(feeds, requirements, config)
    baseline_solution = fixed_diet_solution(feeds, baseline_data["rations_pct"], requirements, "Basal (RuFaS)")

    solutions: dict[str, Any] = {}
    models: dict[str, DietLP] = {}
    for key, scenario in scenarios.items():
        model = _model_for_scenario(base_model, scenario)
        models[key] = model
        solutions[key] = model.solve(scenario=scenario.get("label", key))

    comparisons = {key: compare(baseline_solution, solution, farm) for key, solution in solutions.items()}

    scenario_rows = [
        _scenario_row(key, scenario.get("label", key), solutions[key], baseline_solution, farm)
        for key, scenario in scenarios.items()
    ]
    scenario_df = pd.DataFrame(scenario_rows)
    baseline_row = _scenario_row("baseline", "Basal (RuFaS)", baseline_solution, baseline_solution, farm)
    scenario_with_baseline = pd.concat([pd.DataFrame([baseline_row]), scenario_df], ignore_index=True)

    iso_key = "iso_energetico"
    iso_solution = solutions[iso_key]
    iso_model = models[iso_key]
    tableau = build_tableau(iso_model.feeds, iso_solution.constraints, iso_solution.x_kg_dm, iso_solution.dmi_kg)
    break_even = break_even_table(iso_model, iso_solution)
    pair_be = pairwise_break_even(iso_model, iso_solution, PAIRWISE_FEEDS)

    n_sobol = sobol_n or (128 if fast else int(config["sensitivity"]["sobol_n"]))
    oat = one_at_a_time_prices(
        iso_model, iso_solution, FEED_IDS_SENSITIVITY, pct=float(config["sensitivity"]["price_shock_pct"])
    )
    sobol_cost, _, _ = sobol_feed_cost(
        iso_model,
        iso_solution,
        FEED_IDS_SENSITIVITY,
        n=n_sobol,
        seed=int(config["sensitivity"]["sobol_seed"]),
        price_pct=30.0,
    )
    sobol_margin, _, _ = sobol_iofc(
        iso_model,
        iso_solution,
        farm,
        FEED_IDS_SENSITIVITY,
        n=n_sobol,
        seed=int(config["sensitivity"]["sobol_seed"]),
        price_pct=30.0,
        milk_pct=20.0,
    )
    n_pairwise = 64 if fast else 256
    comparisons_pairwise = [(iso_key, key) for key in scenarios if key != iso_key]
    pairwise = pairwise_scenarios(
        base_model,
        scenarios,
        farm,
        baseline_solution,
        n_samples=n_pairwise,
        seed=seed,
        comparisons=comparisons_pairwise,
    )

    validation_summary, validation_tests = summarize_validation(Path("output/CSVs"))

    results: dict[str, Any] = {
        "config": config,
        "baseline": baseline_solution,
        "scenarios": solutions,
        "scenario_meta": scenarios,
        "solutions": solutions,
        "comparisons": comparisons,
        "scenario_table": scenario_df,
        "scenario_table_with_baseline": scenario_with_baseline,
        "tableau": tableau,
        "break_even": break_even,
        "pairwise_break_even": pair_be,
        "oat": oat,
        "sobol_cost": sobol_cost,
        "sobol_iofc": sobol_margin,
        "pairwise": pairwise,
        "validation_summary": validation_summary,
        "validation_tests": validation_tests,
        "n_sobol": n_sobol,
        "n_pairwise": n_pairwise,
        "mineral_decomp": mineral_decomposition(baseline_solution, iso_solution),
        "economics_baseline": economics(baseline_solution, farm),
        "economics_iso": economics(iso_solution, farm),
    }

    report_path = generate_report(results, output_dir)
    integration_paths = generate_integration_files(config, iso_solution, output_dir, seed=seed)

    if run_rufas:
        print("Executando validação no RuFaS...")
        exit_code = run_rufas_task(integration_paths["task_manager"], Path(__file__).resolve().parents[1])
        if exit_code != 0:
            print(f"Aviso: RuFaS terminou com código {exit_code}.")
        validation_summary, validation_tests = summarize_validation(Path("output/CSVs"))
        results["validation_summary"] = validation_summary
        results["validation_tests"] = validation_tests
        report_path = generate_report(results, output_dir)

    serializable = {
        "baseline": {
            "cost_brl_cow_day": baseline_solution.cost_brl_cow_day,
            "nutrient_supply": baseline_solution.nutrient_supply,
            "diet": baseline_solution.diet_table().to_dict(orient="records"),
        },
        "scenarios": {
            key: {
                "label": scenarios[key].get("label", key),
                "cost_brl_cow_day": solution.cost_brl_cow_day,
                "nutrient_supply": solution.nutrient_supply,
                "diet": solution.diet_table().to_dict(orient="records"),
                "comparison_vs_baseline": comparisons[key],
            }
            for key, solution in solutions.items()
        },
        "comparisons": comparisons,
        "scenario_table": scenario_with_baseline.to_dict(orient="records"),
        "mineral_decomp": results["mineral_decomp"],
        "break_even": break_even.to_dict(orient="records"),
        "pairwise_break_even": pair_be.to_dict(orient="records"),
        "oat": oat.to_dict(orient="records"),
        "sobol_cost": sobol_cost.to_dict(orient="records"),
        "sobol_iofc": sobol_margin.to_dict(orient="records"),
        "pairwise": pairwise.to_dict(orient="records"),
        "validation_summary": validation_summary.to_dict(orient="records"),
        "validation_tests": validation_tests.to_dict(orient="records"),
        "integration": {key: str(value) for key, value in integration_paths.items()},
        "report": str(report_path),
    }
    with (output_dir / "resultados.json").open("w", encoding="utf-8") as handle:
        json.dump(serializable, handle, indent=2, ensure_ascii=False, default=str)

    return {
        "report_path": report_path,
        "integration_paths": integration_paths,
        "results": serializable,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Otimização da dieta integrada ao RuFaS")
    parser.add_argument("--output-dir", type=str, default=None, help="Diretório de saída")
    parser.add_argument("--fast", action="store_true", help="Sobol e testes pareados reduzidos")
    parser.add_argument("--sobol-n", type=int, default=None, help="Número de amostras Sobol")
    parser.add_argument("--seed", type=int, default=44, help="Seed dos testes pareados e da validação")
    parser.add_argument("--run-rufas", action="store_true", help="Executar validação no RuFaS")
    args = parser.parse_args()

    output = run_analysis(
        output_dir=args.output_dir,
        fast=args.fast,
        sobol_n=args.sobol_n,
        seed=args.seed,
        run_rufas=args.run_rufas,
    )
    print(f"Relatório: {output['report_path']}")
    print(f"HTML: {Path(output['report_path']).with_suffix('.html')}")
    pdf_path = Path(output["report_path"]).with_suffix(".pdf")
    if pdf_path.exists():
        print(f"PDF: {pdf_path}")
    for key, path in output["integration_paths"].items():
        print(f"{key}: {path}")
    print("\nResumo:")
    for row in output["results"]["scenario_table"]:
        print(
            f"  {row['label']}: R$ {row['custo_brl_vaca_dia']:.2f}/vaca/dia "
            f"({row['economia_vs_basal_pct']:+.1f}% vs basal)"
        )


if __name__ == "__main__":
    main()
