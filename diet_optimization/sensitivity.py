"""Análise de sensibilidade local e global (Sobol) e testes pareados."""

from __future__ import annotations

import warnings
from typing import Any, Iterable

import numpy as np
import pandas as pd
from SALib.analyze import sobol as sobol_analyze
from SALib.sample import sobol as sobol_sample
from scipy.stats import wilcoxon

from .economics import economics
from .feed_library import feed_by_id
from .lp_model import DietLP, DietSolution
from .tableau import build_tableau


def one_at_a_time_prices(
    model: DietLP,
    solution: DietSolution,
    feed_ids: Iterable[int],
    pct: float = 20.0,
) -> pd.DataFrame:
    """Sensibilidade local: varia o preço de um alimento por vez."""
    rows = []
    base_cost = solution.cost_brl_cow_day
    scenario_model = DietLP(solution.feeds, solution.requirements, model.config)
    for feed_id in feed_ids:
        feed = feed_by_id(solution.feeds, int(feed_id))
        row = {
            "rufas_id": feed.rufas_id,
            "alimento": feed.name,
            "preco_base": feed.price_brl_kg_dm,
            "custo_base_brl_dia": base_cost,
        }
        for label, multiplier in [("menos", 1 - pct / 100.0), ("mais", 1 + pct / 100.0)]:
            try:
                solved = scenario_model.solve(
                    scenario=f"oat_{label}_{feed.rufas_id}",
                    price_multipliers={feed.rufas_id: multiplier},
                )
                row[f"custo_{label}_brl_dia"] = solved.cost_brl_cow_day
                row[f"delta_{label}_brl_dia"] = solved.cost_brl_cow_day - base_cost
                row[f"delta_{label}_pct"] = (solved.cost_brl_cow_day / base_cost - 1) * 100
            except RuntimeError:
                row[f"custo_{label}_brl_dia"] = np.nan
                row[f"delta_{label}_brl_dia"] = np.nan
                row[f"delta_{label}_pct"] = np.nan
        row["amplitude_brl_dia"] = abs(row.get("custo_mais_brl_dia", np.nan) - row.get("custo_menos_brl_dia", np.nan))
        rows.append(row)
    return pd.DataFrame(rows).sort_values("amplitude_brl_dia", ascending=False).reset_index(drop=True)


def _solve_with_multipliers(
    model: DietLP,
    multipliers: dict[int, float],
) -> float | None:
    try:
        return model.solve(price_multipliers=multipliers).cost_brl_cow_day
    except RuntimeError:
        return None


def sobol_feed_cost(
    model: DietLP,
    base_solution: DietSolution,
    feed_ids: Iterable[int],
    n: int = 512,
    seed: int = 42,
    price_pct: float = 30.0,
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """Sobol global sobre o custo da ração em função dos preços dos alimentos."""
    feed_ids = [int(f) for f in feed_ids]
    names = [feed_by_id(model.feeds, f).name for f in feed_ids]
    problem = {
        "num_vars": len(feed_ids),
        "names": names,
        "bounds": [[1 - price_pct / 100.0, 1 + price_pct / 100.0] for _ in feed_ids],
    }
    X = sobol_sample.sample(problem, n, calc_second_order=False, seed=seed)
    Y = np.full(X.shape[0], np.nan)
    base_cost = base_solution.cost_brl_cow_day
    scenario_model = DietLP(base_solution.feeds, base_solution.requirements, model.config)
    for idx, row in enumerate(X):
        multipliers = {feed_id: float(value) for feed_id, value in zip(feed_ids, row)}
        value = _solve_with_multipliers(scenario_model, multipliers)
        Y[idx] = value if value is not None else base_cost * 1.5
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        Si = sobol_analyze.analyze(
            problem,
            Y,
            calc_second_order=False,
            seed=seed,
            num_resamples=100,
            conf_level=0.95,
        )
    table = pd.DataFrame(
        {
            "rufas_id": feed_ids,
            "alimento": names,
            "S1": Si["S1"],
            "S1_conf": Si["S1_conf"],
            "ST": Si["ST"],
            "ST_conf": Si["ST_conf"],
        }
    ).sort_values("ST", ascending=False)
    return table.reset_index(drop=True), X, Y


def sobol_iofc(
    model: DietLP,
    base_solution: DietSolution,
    farm: dict[str, Any],
    feed_ids: Iterable[int],
    n: int = 512,
    seed: int = 42,
    price_pct: float = 30.0,
    milk_pct: float = 20.0,
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """Sobol global sobre a margem sobre o custo da ração (IOFC)."""
    feed_ids = [int(f) for f in feed_ids]
    names = [feed_by_id(model.feeds, f).name for f in feed_ids] + ["Preço do leite"]
    bounds = [[1 - price_pct / 100.0, 1 + price_pct / 100.0] for _ in feed_ids]
    bounds.append([1 - milk_pct / 100.0, 1 + milk_pct / 100.0])
    problem = {"num_vars": len(names), "names": names, "bounds": bounds}
    X = sobol_sample.sample(problem, n, calc_second_order=False, seed=seed)
    Y = np.full(X.shape[0], np.nan)
    base_iofc = economics(base_solution, farm)["iofc_brl_vaca_dia"]
    milk_price = float(farm["milk_price_brl_l"])
    scenario_model = DietLP(base_solution.feeds, base_solution.requirements, model.config)
    for idx, row in enumerate(X):
        multipliers = {feed_id: float(value) for feed_id, value in zip(feed_ids, row[:-1])}
        milk_factor = float(row[-1])
        try:
            solution = scenario_model.solve(price_multipliers=multipliers)
        except RuntimeError:
            Y[idx] = base_iofc * 0.5
            continue
        farm_shift = dict(farm)
        farm_shift["milk_price_brl_l"] = milk_price * milk_factor
        Y[idx] = economics(solution, farm_shift)["iofc_brl_vaca_dia"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        Si = sobol_analyze.analyze(
            problem,
            Y,
            calc_second_order=False,
            seed=seed,
            num_resamples=100,
            conf_level=0.95,
        )
    table = pd.DataFrame(
        {
            "variavel": names,
            "S1": Si["S1"],
            "S1_conf": Si["S1_conf"],
            "ST": Si["ST"],
            "ST_conf": Si["ST_conf"],
        }
    ).sort_values("ST", ascending=False)
    return table.reset_index(drop=True), X, Y


def break_even_table(
    model: DietLP,
    solution: DietSolution,
    feed_ids: Iterable[int] | None = None,
) -> pd.DataFrame:
    """Preço de entrada/saída de cada alimento mantendo a base ótima."""
    tableau = build_tableau(model.feeds, solution.constraints, solution.x_kg_dm, solution.dmi_kg)
    table = tableau.coefficient_ranges.copy()
    table["reducao_necessaria_pct"] = np.where(
        table["status"] == "não básico",
        (table["preco_entrada"] / table["preco_atual"] - 1) * 100.0,
        np.nan,
    )
    table["aumento_suportado_pct"] = np.where(
        table["status"] == "básico",
        (table["preco_max"] / table["preco_atual"] - 1) * 100.0,
        np.nan,
    )
    if feed_ids is not None:
        ids = {int(f) for f in feed_ids}
        table = table[table["rufas_id"].isin(ids)]
    return table.sort_values(["status", "preco_entrada"], ascending=[True, True]).reset_index(drop=True)


def pairwise_break_even(
    model: DietLP,
    solution: DietSolution,
    pairs: Iterable[tuple[int, int]],
) -> pd.DataFrame:
    """Compara pares de alimentos pelo preço de indiferença do segundo."""
    break_even = break_even_table(model, solution)
    rows = []
    for first, second in pairs:
        feed_a = feed_by_id(model.feeds, int(first))
        feed_b = feed_by_id(model.feeds, int(second))
        record = break_even[break_even["rufas_id"] == int(second)]
        if record.empty:
            continue
        record = record.iloc[0]
        price_entry = record["preco_entrada"]
        if pd.isna(price_entry):
            # Se o segundo já está na dieta, usa o limite superior de preço.
            price_entry = record["preco_max"]
        rows.append(
            {
                "alimento_A": feed_a.name,
                "preco_A_brl_kg_ms": feed_a.price_brl_kg_dm,
                "alimento_B": feed_b.name,
                "preco_B_atual_brl_kg_ms": feed_b.price_brl_kg_dm,
                "preco_B_indiferenca_brl_kg_ms": price_entry,
                "variacao_B_pct": (price_entry / feed_b.price_brl_kg_dm - 1) * 100.0,
                "relacao_B_A": price_entry / feed_a.price_brl_kg_dm,
                "B_na_dieta": feed_b.rufas_id
                in set(solution.feeds[i].rufas_id for i in np.where(solution.x_kg_dm > 1e-6)[0]),
            }
        )
    return pd.DataFrame(rows)


def _paired_ci(differences: np.ndarray, resamples: int, seed: int) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    means = np.array([rng.choice(differences, size=len(differences), replace=True).mean() for _ in range(resamples)])
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def pairwise_scenarios(  # noqa: C901
    model: DietLP,
    scenarios: dict[str, dict[str, Any]],
    farm: dict[str, Any],
    baseline_solution: DietSolution,
    n_samples: int = 256,
    price_pct: float = 20.0,
    seed: int = 42,
    comparisons: Iterable[tuple[str, str]] | None = None,
) -> pd.DataFrame:
    """Teste pareado de cenários sob a mesma amostra de preços.

    Para cada amostra de preços (choque uniforme de ±price_pct nos alimentos
    candidatos), resolve todos os cenários. As diferenças são pareadas por
    amostra, o que controla o efeito comum dos preços.
    """
    rng = np.random.default_rng(seed)
    feed_ids = [feed.rufas_id for feed in model.feeds]
    samples = rng.uniform(1 - price_pct / 100.0, 1 + price_pct / 100.0, size=(n_samples, len(feed_ids)))
    costs: dict[str, list[float]] = {key: [] for key in scenarios}
    solved_scenarios: dict[str, DietSolution] = {}
    for key, scenario in scenarios.items():
        solved_scenarios[key] = model.solve_scenario({**scenario, "key": key})
    for row in samples:
        multipliers = {feed_id: float(value) for feed_id, value in zip(feed_ids, row)}
        for key, scenario in scenarios.items():
            requirements = None
            overrides = scenario.get("overrides", {})
            if overrides.get("requirements"):
                from .requirements import apply_requirement_overrides

                requirements = apply_requirement_overrides(model.requirements, overrides["requirements"])
            bounds = overrides.get("bounds")
            scenario_model = model.with_bound_overrides(bounds)
            try:
                solution = scenario_model.solve(
                    scenario=key,
                    requirements=requirements,
                    price_multipliers=multipliers,
                )
                costs[key].append(solution.cost_brl_cow_day)
            except RuntimeError:
                costs[key].append(np.nan)

    if comparisons is None:
        keys = list(scenarios)
        comparisons = [(keys[0], key) for key in keys[1:]]
    rows = []
    for first, second in comparisons:
        a = np.array(costs[first], dtype=float)
        b = np.array(costs[second], dtype=float)
        mask = np.isfinite(a) & np.isfinite(b)
        diff = b[mask] - a[mask]
        if len(diff) < 10:
            continue
        try:
            _, p_value = wilcoxon(diff)
        except ValueError:
            p_value = 1.0
        ci_low, ci_high = _paired_ci(diff, resamples=2000, seed=seed)
        rows.append(
            {
                "cenario_A": first,
                "cenario_B": second,
                "delta_medio_brl_dia": float(diff.mean()),
                "delta_pct_medio": float(diff.mean() / a[mask].mean() * 100.0),
                "ic95_inf_brl_dia": ci_low,
                "ic95_sup_brl_dia": ci_high,
                "p_valor_wilcoxon": float(p_value),
                "significativo_5pct": bool(p_value < 0.05),
                "n_amostras": int(mask.sum()),
            }
        )
    return pd.DataFrame(rows)


def key_feed_ids(model: DietLP, max_feeds: int = 10) -> list[int]:
    """Seleciona os alimentos com maior participação no custo da dieta ótima."""
    solution = model.solve()
    contributions = [(feed.rufas_id, kg * feed.price_brl_kg_dm) for feed, kg in zip(solution.feeds, solution.x_kg_dm)]
    contributions.sort(key=lambda item: item[1], reverse=True)
    return [feed_id for feed_id, _ in contributions[:max_feeds]]
