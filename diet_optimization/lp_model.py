"""Formulação e resolução do problema de programação linear da dieta."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import OptimizeResult, linprog

from .feed_library import Feed
from .requirements import Requirements, apply_requirement_overrides


@dataclass(frozen=True)
class ConstraintSpec:
    key: str
    label: str
    sense: str  # "min" ou "max"
    unit: str
    report_unit: str
    rhs: float
    row: np.ndarray
    scale: float = 1.0
    report_shadow: bool = True


@dataclass
class DietSolution:
    scenario: str
    feeds: list[Feed]
    requirements: Requirements
    x_kg_dm: np.ndarray
    cost_brl_kg_dm: float
    cost_brl_cow_day: float
    dmi_kg: float
    nutrient_supply: dict[str, float]
    constraints: list[ConstraintSpec]
    marginals: np.ndarray
    shadow_prices: dict[str, float]
    reduced_costs: dict[int, float]
    equality_marginal: float
    solver_message: str
    status: int
    solve_time_s: float

    @property
    def total_pct(self) -> float:
        return float(self.x_kg_dm.sum() / self.dmi_kg * 100.0)

    def diet_table(self) -> pd.DataFrame:
        rows = []
        for feed, kg in zip(self.feeds, self.x_kg_dm):
            pct = kg / self.dmi_kg * 100.0
            rows.append(
                {
                    "rufas_id": feed.rufas_id,
                    "alimento": feed.name,
                    "grupo": feed.group,
                    "kg_ms_dia": kg,
                    "pct_ms": pct,
                    "preco_brl_kg_ms": feed.price_brl_kg_dm,
                    "custo_brl_dia": kg * feed.price_brl_kg_dm,
                    "min_pct": feed.min_pct,
                    "max_pct": feed.max_pct,
                    "custo_reduzido": self.reduced_costs.get(feed.rufas_id, np.nan),
                }
            )
        table = pd.DataFrame(rows).sort_values("pct_ms", ascending=False)
        return table[table["pct_ms"] > 1e-6].reset_index(drop=True)

    def shadow_table(self) -> pd.DataFrame:
        rows = []
        for spec, marginal in zip(self.constraints, self.marginals):
            if not spec.report_shadow:
                continue
            rows.append(
                {
                    "restricao": spec.label,
                    "tipo": "mínimo" if spec.sense == "min" else "máximo",
                    "unidade": spec.report_unit,
                    "preco_sombra_brl_dia": -marginal * spec.scale,
                    "marginal_solver": marginal,
                }
            )
        return pd.DataFrame(rows).sort_values("preco_sombra_brl_dia", ascending=False).reset_index(drop=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "dmi_kg": self.dmi_kg,
            "cost_brl_kg_dm": self.cost_brl_kg_dm,
            "cost_brl_cow_day": self.cost_brl_cow_day,
            "nutrient_supply": self.nutrient_supply,
            "diet": self.diet_table().to_dict(orient="records"),
            "shadow_prices": self.shadow_prices,
            "reduced_costs": self.reduced_costs,
            "equality_marginal": self.equality_marginal,
            "solver_message": self.solver_message,
            "status": self.status,
        }


class DietLP:
    """Modelo de PL de mínimo custo para a vaca em lactação.

    Variáveis de decisão: kg de MS/dia de cada alimento.
    Objetivo: minimizar o custo total da ração (R$/vaca/dia).
    Restrição de igualdade: soma das MS = consumo de MS (DMI).
    Restrições de desigualdade: nutrientes, fibra, minerais e limites de inclusão.
    """

    def __init__(
        self,
        feeds: list[Feed],
        requirements: Requirements,
        config: dict[str, Any] | None = None,
    ) -> None:
        if not feeds:
            raise ValueError("Lista de alimentos vazia.")
        self.feeds = list(feeds)
        self.requirements = requirements
        self.config = config or {}
        self._validate_feasibility_bounds()

    @property
    def n_feeds(self) -> int:
        return len(self.feeds)

    def _validate_feasibility_bounds(self) -> None:
        total_min = sum(f.min_pct for f in self.feeds)
        total_max = sum(f.max_pct for f in self.feeds)
        if total_min > 100.0 + 1e-9:
            raise ValueError(f"Soma dos mínimos ({total_min:.2f}%) excede 100%.")
        if total_max < 100.0 - 1e-9:
            raise ValueError(f"Soma dos máximos ({total_max:.2f}%) é menor que 100%.")

    def _vectors(self) -> dict[str, np.ndarray]:
        def arr(attr: str) -> np.ndarray:
            return np.array([getattr(f, attr) for f in self.feeds], dtype=float)

        return {
            "cp": arr("cp_pct"),
            "ndf": arr("ndf_pct"),
            "adf": arr("adf_pct"),
            "starch": arr("starch_pct"),
            "ee": arr("ee_pct"),
            "tdn": arr("tdn_pct"),
            "ca": arr("ca_pct"),
            "p": arr("p_pct"),
            "ca_abs": arr("ca_abs_kg_per_kg_dm"),
            "p_abs": arr("p_abs_kg_per_kg_dm"),
            "rup_dig": arr("rup_dig_kg_per_kg_dm"),
            "price": arr("price_brl_kg_dm"),
            "min": arr("min_pct"),
            "max": arr("max_pct"),
            "is_forage": np.array([f.is_forage for f in self.feeds], dtype=bool),
        }

    def _build_constraints(
        self,
        vectors: dict[str, np.ndarray],
        requirements: Requirements,
        bound_overrides: dict[int, dict[str, float]] | None = None,
    ) -> list[ConstraintSpec]:
        dmi = requirements.dmi_kg
        bounds = {feed.rufas_id: {"min_pct": feed.min_pct, "max_pct": feed.max_pct} for feed in self.feeds}
        if bound_overrides:
            for feed_id, override in bound_overrides.items():
                feed_id = int(feed_id)
                if feed_id not in bounds:
                    raise KeyError(f"Alimento {feed_id} não está na biblioteca candidata.")
                bounds[feed_id].update(override)

        specs: list[ConstraintSpec] = []

        def add_pct(
            key: str,
            label: str,
            sense: str,
            values: np.ndarray,
            pct: float,
            unit: str = "% da MS",
            report_shadow: bool = True,
        ) -> None:
            if sense == "min":
                specs.append(
                    ConstraintSpec(
                        key=key,
                        label=label,
                        sense="min",
                        unit=unit,
                        report_unit="R$/dia por +1 p.p.",
                        rhs=-pct * dmi,
                        row=-values,
                        scale=dmi,
                        report_shadow=report_shadow,
                    )
                )
            else:
                specs.append(
                    ConstraintSpec(
                        key=key,
                        label=label,
                        sense="max",
                        unit=unit,
                        report_unit="R$/dia por +1 p.p.",
                        rhs=pct * dmi,
                        row=values,
                        scale=dmi,
                        report_shadow=report_shadow,
                    )
                )

        add_pct("ndf_min", "NDF mínimo", "min", vectors["ndf"], requirements.ndf_min_pct)
        add_pct("ndf_max", "NDF máximo", "max", vectors["ndf"], requirements.ndf_max_pct)
        add_pct(
            "forage_ndf_min",
            "NDF de forragem mínimo",
            "min",
            np.where(vectors["is_forage"], vectors["ndf"], 0.0),
            requirements.forage_ndf_min_pct,
        )
        add_pct("cp_min", "Proteína bruta mínima", "min", vectors["cp"], requirements.cp_min_pct)
        add_pct("starch_min", "Amido mínimo", "min", vectors["starch"], requirements.starch_min_pct)
        add_pct("starch_max", "Amido máximo", "max", vectors["starch"], requirements.starch_max_pct)
        add_pct("ee_min", "Extrato etéreo mínimo", "min", vectors["ee"], requirements.ee_min_pct)
        add_pct("ee_max", "Extrato etéreo máximo", "max", vectors["ee"], requirements.ee_max_pct)
        add_pct("tdn_min", "Energia (TDN) mínima", "min", vectors["tdn"], requirements.tdn_min_pct)
        add_pct(
            "ca_total_min",
            "Cálcio total mínimo",
            "min",
            vectors["ca"],
            requirements.ca_total_min_pct,
        )

        specs.append(
            ConstraintSpec(
                key="ca_abs_min",
                label="Cálcio absorvível mínimo",
                sense="min",
                unit="kg Ca/dia",
                report_unit="R$/dia por +1 g",
                rhs=-requirements.ca_abs_g / 1000.0,
                row=-vectors["ca_abs"],
                scale=0.001,
            )
        )
        specs.append(
            ConstraintSpec(
                key="p_abs_min",
                label="Fósforo absorvível mínimo",
                sense="min",
                unit="kg P/dia",
                report_unit="R$/dia por +1 g",
                rhs=-requirements.p_abs_g / 1000.0,
                row=-vectors["p_abs"],
                scale=0.001,
            )
        )
        specs.append(
            ConstraintSpec(
                key="ca_p_min",
                label="Relação Ca:P mínima",
                sense="min",
                unit="razão",
                report_unit="razão",
                rhs=0.0,
                row=requirements.ca_p_min * vectors["p"] - vectors["ca"],
                scale=1.0,
                report_shadow=False,
            )
        )
        specs.append(
            ConstraintSpec(
                key="ca_p_max",
                label="Relação Ca:P máxima",
                sense="max",
                unit="razão",
                report_unit="razão",
                rhs=0.0,
                row=vectors["ca"] - requirements.ca_p_max * vectors["p"],
                scale=1.0,
                report_shadow=False,
            )
        )
        specs.append(
            ConstraintSpec(
                key="rup_min",
                label="Proteína não degradável digestível mínima",
                sense="min",
                unit="kg RUP/dia",
                report_unit="R$/dia por +1 kg",
                rhs=-requirements.rup_min_kg,
                row=-vectors["rup_dig"],
                scale=1.0,
            )
        )

        for idx, feed in enumerate(self.feeds):
            low = bounds[feed.rufas_id]["min_pct"]
            high = bounds[feed.rufas_id]["max_pct"]
            if low > 0:
                row = np.zeros(self.n_feeds)
                row[idx] = -1.0
                specs.append(
                    ConstraintSpec(
                        key=f"min_{feed.rufas_id}",
                        label=f"Inclusão mínima — {feed.name}",
                        sense="min",
                        unit="kg MS/dia",
                        report_unit="R$/dia por +1 kg MS",
                        rhs=-low / 100.0 * dmi,
                        row=row,
                        scale=1.0,
                    )
                )
            if high < 100.0 - 1e-9:
                row = np.zeros(self.n_feeds)
                row[idx] = 1.0
                specs.append(
                    ConstraintSpec(
                        key=f"max_{feed.rufas_id}",
                        label=f"Inclusão máxima — {feed.name}",
                        sense="max",
                        unit="kg MS/dia",
                        report_unit="R$/dia por +1 kg MS",
                        rhs=high / 100.0 * dmi,
                        row=row,
                        scale=1.0,
                    )
                )
        return specs

    def solve(
        self,
        scenario: str = "base",
        requirements: Requirements | None = None,
        price_multipliers: dict[int, float] | None = None,
        price_values: dict[int, float] | None = None,
        bound_overrides: dict[int, dict[str, float]] | None = None,
    ) -> DietSolution:
        """Resolve o PL para um cenário."""
        import time

        start = time.perf_counter()
        req = requirements or self.requirements
        vectors = self._vectors()

        if price_multipliers:
            for feed_id, multiplier in price_multipliers.items():
                idx = self._feed_index(int(feed_id))
                vectors["price"][idx] *= float(multiplier)
        if price_values:
            for feed_id, value in price_values.items():
                idx = self._feed_index(int(feed_id))
                vectors["price"][idx] = float(value)

        constraints = self._build_constraints(vectors, req, bound_overrides)
        A_ub = np.vstack([spec.row for spec in constraints]) if constraints else None
        b_ub = np.array([spec.rhs for spec in constraints], dtype=float) if constraints else None
        A_eq = np.ones((1, self.n_feeds))
        b_eq = np.array([req.dmi_kg])

        result: OptimizeResult = linprog(
            c=vectors["price"],
            A_ub=A_ub,
            b_ub=b_ub,
            A_eq=A_eq,
            b_eq=b_eq,
            bounds=[(0.0, None)] * self.n_feeds,
            method="highs-ds",
        )
        if result.status != 0:
            result = linprog(
                c=vectors["price"],
                A_ub=A_ub,
                b_ub=b_ub,
                A_eq=A_eq,
                b_eq=b_eq,
                bounds=[(0.0, None)] * self.n_feeds,
                method="highs",
            )

        elapsed = time.perf_counter() - start
        if result.status != 0:
            raise RuntimeError(
                f"PL inviável ou sem solução para o cenário '{scenario}': " f"{result.message} (status {result.status})"
            )

        x = np.array(result.x, dtype=float)
        x[np.abs(x) < 1e-9] = 0.0
        cost_kg = float(vectors["price"] @ x)
        cost_day = cost_kg  # x já está em kg MS/dia
        nutrient_supply = self._nutrient_supply(x, vectors, req)

        marginals = np.array(result.ineqlin.marginals, dtype=float)
        equality_marginal = float(result.eqlin.marginals[0])
        reduced = (
            vectors["price"]
            + (A_ub.T @ marginals if A_ub is not None else 0.0)
            + A_eq.T @ np.array([equality_marginal])
        )
        reduced_costs = {feed.rufas_id: float(reduced[idx]) for idx, feed in enumerate(self.feeds)}
        shadow_prices = {
            spec.key: float(-marginals[idx] * spec.scale) for idx, spec in enumerate(constraints) if spec.report_shadow
        }

        return DietSolution(
            scenario=scenario,
            feeds=self.feeds,
            requirements=req,
            x_kg_dm=x,
            cost_brl_kg_dm=cost_kg / req.dmi_kg,
            cost_brl_cow_day=cost_day,
            dmi_kg=req.dmi_kg,
            nutrient_supply=nutrient_supply,
            constraints=constraints,
            marginals=marginals,
            shadow_prices=shadow_prices,
            reduced_costs=reduced_costs,
            equality_marginal=equality_marginal,
            solver_message=str(result.message),
            status=int(result.status),
            solve_time_s=elapsed,
        )

    def _nutrient_supply(
        self,
        x: np.ndarray,
        vectors: dict[str, np.ndarray],
        req: Requirements,
    ) -> dict[str, float]:
        dmi = req.dmi_kg
        return {
            "cp_pct": float(vectors["cp"] @ x / dmi),
            "ndf_pct": float(vectors["ndf"] @ x / dmi),
            "adf_pct": float(vectors["adf"] @ x / dmi),
            "starch_pct": float(vectors["starch"] @ x / dmi),
            "ee_pct": float(vectors["ee"] @ x / dmi),
            "tdn_pct": float(vectors["tdn"] @ x / dmi),
            "ca_total_pct": float(vectors["ca"] @ x / dmi),
            "p_total_pct": float(vectors["p"] @ x / dmi),
            "ca_abs_g": float(vectors["ca_abs"] @ x * 1000.0),
            "p_abs_g": float(vectors["p_abs"] @ x * 1000.0),
            "rup_dig_kg": float(vectors["rup_dig"] @ x),
            "nel_mcal": float(sum(feed.nel_mcal_per_kg_dm * kg for feed, kg in zip(self.feeds, x))),
            "forage_ndf_pct": float(np.where(vectors["is_forage"], vectors["ndf"], 0.0) @ x / dmi),
            "cost_brl_kg_dm": float(vectors["price"] @ x / dmi),
            "cost_brl_cow_day": float(vectors["price"] @ x),
        }

    def _feed_index(self, rufas_id: int) -> int:
        for idx, feed in enumerate(self.feeds):
            if feed.rufas_id == int(rufas_id):
                return idx
        raise KeyError(f"Alimento {rufas_id} não encontrado.")

    def with_bound_overrides(self, bound_overrides: dict[int, dict[str, float]] | None) -> "DietLP":
        if not bound_overrides:
            return self
        normalized = {int(key): value for key, value in bound_overrides.items()}
        feeds = []
        for feed in self.feeds:
            override = normalized.get(feed.rufas_id, {})
            feeds.append(
                replace(
                    feed,
                    min_pct=float(override.get("min_pct", feed.min_pct)),
                    max_pct=float(override.get("max_pct", feed.max_pct)),
                )
            )
        return DietLP(feeds, self.requirements, self.config)

    def solve_scenario(self, scenario: dict[str, Any]) -> DietSolution:
        overrides = scenario.get("overrides", {})
        requirements = apply_requirement_overrides(self.requirements, overrides.get("requirements"))
        bounds = overrides.get("bounds")
        model = self.with_bound_overrides(bounds)
        return model.solve(
            scenario=scenario.get("label", scenario.get("key", "cenário")),
            requirements=requirements,
            price_multipliers=overrides.get("price_multipliers"),
            price_values=overrides.get("price_values"),
        )


def diet_from_percentages(
    feeds: list[Feed],
    percentages: dict[int | str, float],
    dmi_kg: float,
) -> tuple[np.ndarray, float]:
    """Converte percentuais de MS em kg MS/dia e calcula o custo."""
    x = np.zeros(len(feeds))
    for feed_id, pct in percentages.items():
        idx = next((i for i, feed in enumerate(feeds) if feed.rufas_id == int(feed_id)), None)
        if idx is None:
            raise KeyError(f"Alimento {feed_id} não encontrado.")
        x[idx] = float(pct) / 100.0 * dmi_kg
    total = x.sum()
    if abs(total - dmi_kg) > 1e-6 * max(1.0, dmi_kg):
        raise ValueError(f"Percentuais somam {total / dmi_kg * 100:.4f}% da MS, esperado 100%.")
    cost = sum(feed.price_brl_kg_dm * kg for feed, kg in zip(feeds, x))
    return x, cost


def fixed_diet_solution(
    feeds: list[Feed],
    percentages: dict[int | str, float],
    requirements: Requirements,
    name: str,
    scenario: str = "baseline",
) -> DietSolution:
    """Avalia uma dieta fixa (baseline) com a mesma estrutura de saída do PL."""
    x, cost_day = diet_from_percentages(feeds, percentages, requirements.dmi_kg)
    vectors = {
        "cp": np.array([f.cp_pct for f in feeds]),
        "ndf": np.array([f.ndf_pct for f in feeds]),
        "adf": np.array([f.adf_pct for f in feeds]),
        "starch": np.array([f.starch_pct for f in feeds]),
        "ee": np.array([f.ee_pct for f in feeds]),
        "tdn": np.array([f.tdn_pct for f in feeds]),
        "ca": np.array([f.ca_pct for f in feeds]),
        "p": np.array([f.p_pct for f in feeds]),
        "ca_abs": np.array([f.ca_abs_kg_per_kg_dm for f in feeds]),
        "p_abs": np.array([f.p_abs_kg_per_kg_dm for f in feeds]),
        "rup_dig": np.array([f.rup_dig_kg_per_kg_dm for f in feeds]),
        "price": np.array([f.price_brl_kg_dm for f in feeds]),
        "is_forage": np.array([f.is_forage for f in feeds]),
    }
    dmi = requirements.dmi_kg
    nutrient_supply = {
        "cp_pct": float(vectors["cp"] @ x / dmi),
        "ndf_pct": float(vectors["ndf"] @ x / dmi),
        "adf_pct": float(vectors["adf"] @ x / dmi),
        "starch_pct": float(vectors["starch"] @ x / dmi),
        "ee_pct": float(vectors["ee"] @ x / dmi),
        "tdn_pct": float(vectors["tdn"] @ x / dmi),
        "ca_total_pct": float(vectors["ca"] @ x / dmi),
        "p_total_pct": float(vectors["p"] @ x / dmi),
        "ca_abs_g": float(vectors["ca_abs"] @ x * 1000.0),
        "p_abs_g": float(vectors["p_abs"] @ x * 1000.0),
        "rup_dig_kg": float(vectors["rup_dig"] @ x),
        "nel_mcal": float(sum(f.nel_mcal_per_kg_dm * kg for f, kg in zip(feeds, x))),
        "forage_ndf_pct": float(np.where(vectors["is_forage"], vectors["ndf"], 0.0) @ x / dmi),
        "cost_brl_kg_dm": cost_day / dmi,
        "cost_brl_cow_day": cost_day,
    }
    return DietSolution(
        scenario=name,
        feeds=feeds,
        requirements=requirements,
        x_kg_dm=x,
        cost_brl_kg_dm=cost_day / dmi,
        cost_brl_cow_day=cost_day,
        dmi_kg=dmi,
        nutrient_supply=nutrient_supply,
        constraints=[],
        marginals=np.array([]),
        shadow_prices={},
        reduced_costs={feed.rufas_id: np.nan for feed in feeds},
        equality_marginal=np.nan,
        solver_message="dieta fixa",
        status=0,
        solve_time_s=0.0,
    )
