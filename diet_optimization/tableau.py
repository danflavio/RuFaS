"""Reconstrução didática do quadro final do simplex e faixas de sensibilidade."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .feed_library import Feed
from .lp_model import ConstraintSpec


class TableauError(RuntimeError):
    pass


@dataclass
class TableauResult:
    tableau: pd.DataFrame
    basis: list[str]
    reduced_costs: pd.Series
    duals: pd.Series
    objective: float
    rhs_ranges: pd.DataFrame
    coefficient_ranges: pd.DataFrame


def _constraint_rhs_scale(spec: ConstraintSpec, dmi: float) -> float:
    if spec.unit == "% da MS":
        return 1.0 / dmi
    if spec.unit in {"kg Ca/dia", "kg P/dia"}:
        return 1000.0
    return 1.0


def _select_basis(matrix: np.ndarray, values: np.ndarray, n_basic: int) -> list[int]:  # noqa: C901
    """Seleciona uma base viável a partir das colunas com maior valor absoluto."""
    candidates = sorted(range(len(values)), key=lambda idx: -abs(values[idx]))
    basis: list[int] = []

    def rank(cols: list[int]) -> int:
        if not cols:
            return 0
        return int(np.linalg.matrix_rank(matrix[:, cols]))

    for idx in candidates:
        if len(basis) >= n_basic:
            break
        trial = basis + [idx]
        if rank(trial) > len(basis):
            basis.append(idx)
    for idx in range(matrix.shape[1]):
        if len(basis) >= n_basic:
            break
        if idx in basis:
            continue
        trial = basis + [idx]
        if rank(trial) > len(basis):
            basis.append(idx)
    if len(basis) != n_basic:
        raise TableauError("Não foi possível completar a base do simplex.")
    return basis


def build_tableau(  # noqa: C901
    feeds: list[Feed],
    constraints: list[ConstraintSpec],
    x_kg_dm: np.ndarray,
    dmi_kg: float,
) -> TableauResult:
    """Monta o quadro final do simplex a partir da base ótima.

    A formulação padrão é:
        min c'x
        s.a. A_ub x <= b_ub
             A_eq x  = b_eq
             x >= 0

    As folgas das desigualdades e a variável artificial da igualdade entram
    como colunas. O quadro final é B^-1 A e B^-1 b, com a linha de custo
    reduzido no rodapé.
    """
    n = len(feeds)
    m_ineq = len(constraints)
    if m_ineq == 0:
        raise TableauError("Sem restrições de desigualdade para montar o quadro.")

    A_ub = np.vstack([spec.row for spec in constraints])
    b_ub = np.array([spec.rhs for spec in constraints], dtype=float)
    A_eq = np.ones((1, n))
    b_eq = np.array([dmi_kg], dtype=float)
    c = np.array([feed.price_brl_kg_dm for feed in feeds], dtype=float)

    m_eq = 1
    m = m_ineq + m_eq
    A_all = np.zeros((m, n + m_ineq + m_eq))
    A_all[:m_ineq, :n] = A_ub
    A_all[:m_ineq, n : n + m_ineq] = np.eye(m_ineq)
    A_all[m_ineq:, :n] = A_eq
    A_all[m_ineq:, n + m_ineq :] = np.eye(m_eq)
    b_all = np.concatenate([b_ub, b_eq])
    c_all = np.concatenate([c, np.zeros(m_ineq + m_eq)])

    slack = b_ub - A_ub @ x_kg_dm
    artificial = b_eq - A_eq @ x_kg_dm
    values = np.concatenate([x_kg_dm, slack, artificial])
    names = [f"x_{feed.rufas_id}_{feed.name}" for feed in feeds] + [f"s_{spec.key}" for spec in constraints] + ["a_dmi"]

    basis_idx = _select_basis(A_all, values, m)
    B = A_all[:, basis_idx]
    if abs(np.linalg.det(B)) < 1e-12:
        raise TableauError("Base singular.")
    B_inv = np.linalg.inv(B)
    tableau = B_inv @ A_all
    rhs = B_inv @ b_all
    c_B = c_all[basis_idx]
    reduced = c_all - c_B @ tableau
    objective = float(c_B @ rhs)

    if np.min(rhs) < -1e-6:
        raise TableauError(f"Base infactível: RHS mínimo {np.min(rhs):.3e}.")
    if np.min(reduced[:n]) < -1e-5:
        raise TableauError(f"Custo reduzido negativo: {np.min(reduced[:n]):.3e}.")
    if abs(objective - float(c @ x_kg_dm)) > 1e-4:
        raise TableauError(f"Objetivo do quadro ({objective:.6f}) difere do PL ({float(c @ x_kg_dm):.6f}).")

    columns = names + ["RHS"]
    data = np.column_stack([tableau, rhs])
    rows = [names[idx] for idx in basis_idx]
    df = pd.DataFrame(data, index=rows, columns=columns)
    df.loc["custo_reduzido"] = np.concatenate([reduced, [objective]])

    # Faixas de RHS mantendo a mesma base.
    range_rows = []
    basic_values = rhs
    for row_idx, spec in enumerate(constraints):
        if not spec.report_shadow:
            continue
        direction = B_inv[:, row_idx]
        lower = -np.inf
        upper = np.inf
        for value, component in zip(basic_values, direction):
            if component > 1e-12:
                lower = max(lower, -value / component)
            elif component < -1e-12:
                upper = min(upper, -value / component)
        b_low = spec.rhs + lower
        b_high = spec.rhs + upper
        scale = _constraint_rhs_scale(spec, dmi_kg)
        if spec.sense == "min":
            natural_low = -b_high * scale
            natural_high = -b_low * scale
        else:
            natural_low = b_low * scale
            natural_high = b_high * scale
        range_rows.append(
            {
                "restricao": spec.label,
                "unidade": spec.report_unit.replace("R$/dia por +1 ", ""),
                "valor_atual": (-spec.rhs if spec.sense == "min" else spec.rhs) * scale,
                "minimo": natural_low,
                "maximo": natural_high,
                "preco_sombra_brl_dia": float(reduced[n + row_idx] * spec.scale),
                "folga_atual": float(slack[row_idx] * scale),
            }
        )
    ranges = pd.DataFrame(range_rows)

    # Faixas de preço que preservam a base (para alimentos básicos e não básicos).
    coefficient_rows = []
    nonbasic = [idx for idx in range(n) if idx not in basis_idx]
    for feed_idx, feed in enumerate(feeds):
        if feed_idx in basis_idx:
            # Faixa de preço para variável básica: r_l(Δ) >= 0 para todo não básico l.
            row_pos = basis_idx.index(feed_idx)
            lower = -np.inf
            upper = np.inf
            feasible = True
            for col in nonbasic:
                coefficient = tableau[row_pos, col]
                rhs_reduced = reduced[col]
                if abs(coefficient) < 1e-12:
                    if rhs_reduced < -1e-9:
                        feasible = False
                        break
                    continue
                bound = rhs_reduced / coefficient
                if coefficient > 0:
                    upper = min(upper, bound)
                else:
                    lower = max(lower, bound)
            if feasible:
                coefficient_rows.append(
                    {
                        "rufas_id": feed.rufas_id,
                        "alimento": feed.name,
                        "preco_atual": feed.price_brl_kg_dm,
                        "preco_min": feed.price_brl_kg_dm + lower,
                        "preco_max": feed.price_brl_kg_dm + upper,
                        "status": "básico",
                        "preco_entrada": np.nan,
                    }
                )
        else:
            rc = float(reduced[feed_idx])
            coefficient_rows.append(
                {
                    "rufas_id": feed.rufas_id,
                    "alimento": feed.name,
                    "preco_atual": feed.price_brl_kg_dm,
                    "preco_min": feed.price_brl_kg_dm - rc,
                    "preco_max": np.inf,
                    "status": "não básico",
                    "preco_entrada": feed.price_brl_kg_dm - rc,
                }
            )
    coeff_df = pd.DataFrame(coefficient_rows)

    return TableauResult(
        tableau=df,
        basis=rows,
        reduced_costs=pd.Series(reduced[:n], index=[f.rufas_id for f in feeds]),
        duals=pd.Series(reduced[n : n + m_ineq], index=[s.key for s in constraints]),
        objective=objective,
        rhs_ranges=ranges,
        coefficient_ranges=coeff_df,
    )
