"""Avaliação econômica da dieta e comparação de cenários."""

from __future__ import annotations

from typing import Any, Iterable

import pandas as pd

from .lp_model import DietSolution


def milk_revenue_brl_cow_day(farm: dict[str, Any], milk_kg: float | None = None) -> float:
    milk_kg = float(milk_kg if milk_kg is not None else farm["milk_kg_cow_day"])
    liters = milk_kg / float(farm["milk_density_kg_l"])
    return liters * float(farm["milk_price_brl_l"])


def economics(solution: DietSolution, farm: dict[str, Any]) -> dict[str, float]:
    """Indicadores econômicos por vaca/dia e por ano."""
    milk_kg = float(farm["milk_kg_cow_day"])
    cows = float(farm["lactating_cows"])
    days = float(farm["days_per_year"])
    feed_cost = solution.cost_brl_cow_day
    revenue = milk_revenue_brl_cow_day(farm, milk_kg)
    iofc = revenue - feed_cost
    return {
        "custo_racao_brl_vaca_dia": feed_cost,
        "custo_racao_brl_kg_ms": solution.cost_brl_kg_dm,
        "custo_racao_brl_kg_leite": feed_cost / milk_kg,
        "receita_leite_brl_vaca_dia": revenue,
        "iofc_brl_vaca_dia": iofc,
        "iofc_brl_kg_leite": iofc / milk_kg,
        "custo_racao_pct_receita": feed_cost / revenue * 100.0,
        "custo_racao_anual_brl": feed_cost * cows * days,
        "iofc_anual_brl": iofc * cows * days,
    }


def compare(
    baseline: DietSolution,
    optimized: DietSolution,
    farm: dict[str, Any],
) -> dict[str, float]:
    """Compara a dieta otimizada com a basal."""
    base = economics(baseline, farm)
    opt = economics(optimized, farm)
    cows = float(farm["lactating_cows"])
    days = float(farm["days_per_year"])
    delta_day = opt["custo_racao_brl_vaca_dia"] - base["custo_racao_brl_vaca_dia"]
    return {
        "custo_basal_brl_vaca_dia": base["custo_racao_brl_vaca_dia"],
        "custo_otimizado_brl_vaca_dia": opt["custo_racao_brl_vaca_dia"],
        "economia_brl_vaca_dia": -delta_day,
        "economia_pct": -delta_day / base["custo_racao_brl_vaca_dia"] * 100.0,
        "economia_anual_brl": -delta_day * cows * days,
        "custo_basal_brl_kg_leite": base["custo_racao_brl_kg_leite"],
        "custo_otimizado_brl_kg_leite": opt["custo_racao_brl_kg_leite"],
        "iofc_basal_brl_vaca_dia": base["iofc_brl_vaca_dia"],
        "iofc_otimizado_brl_vaca_dia": opt["iofc_brl_vaca_dia"],
        "iofc_delta_brl_vaca_dia": opt["iofc_brl_vaca_dia"] - base["iofc_brl_vaca_dia"],
        "iofc_delta_pct": ((opt["iofc_brl_vaca_dia"] - base["iofc_brl_vaca_dia"]) / base["iofc_brl_vaca_dia"] * 100.0),
        "custo_racao_pct_receita_basal": base["custo_racao_pct_receita"],
        "custo_racao_pct_receita_otimizado": opt["custo_racao_pct_receita"],
    }


def scenario_table(
    scenarios: dict[str, DietSolution],
    baseline: DietSolution,
    farm: dict[str, Any],
) -> pd.DataFrame:
    rows = []
    base_econ = economics(baseline, farm)
    for key, solution in scenarios.items():
        econ = economics(solution, farm)
        rows.append(
            {
                "cenario": key,
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
                    (econ["iofc_brl_vaca_dia"] - base_econ["iofc_brl_vaca_dia"])
                    / base_econ["iofc_brl_vaca_dia"]
                    * 100.0
                ),
                "custo_anual_brl": econ["custo_racao_anual_brl"],
                "economia_anual_brl": (base_econ["custo_racao_anual_brl"] - econ["custo_racao_anual_brl"]),
            }
        )
    return pd.DataFrame(rows)


def feed_line_costs(solution: DietSolution, feed_ids: Iterable[int]) -> float:
    ids = {int(feed_id) for feed_id in feed_ids}
    return float(
        sum(kg * feed.price_brl_kg_dm for feed, kg in zip(solution.feeds, solution.x_kg_dm) if feed.rufas_id in ids)
    )


def mineral_decomposition(baseline: DietSolution, optimized: DietSolution) -> dict[str, float]:
    """Separa o efeito da troca de fontes minerais do restante da reformulação."""
    mineral_ids = {234, 301, 230, 231, 232, 258, 260}
    base_mineral = feed_line_costs(baseline, mineral_ids)
    opt_mineral = feed_line_costs(optimized, mineral_ids)
    total_saving = baseline.cost_brl_cow_day - optimized.cost_brl_cow_day
    mineral_saving = base_mineral - opt_mineral
    return {
        "custo_mineral_basal_brl_dia": base_mineral,
        "custo_mineral_otimizado_brl_dia": opt_mineral,
        "economia_mineral_brl_dia": mineral_saving,
        "economia_total_brl_dia": total_saving,
        "participacao_mineral_pct": (mineral_saving / total_saving * 100.0 if abs(total_saving) > 1e-12 else 0.0),
        "economia_reformulacao_brl_dia": total_saving - mineral_saving,
    }
