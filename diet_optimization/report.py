# flake8: noqa
"""Geração do relatório, tabelas e gráficos da otimização da dieta."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .economics import economics
from .html_report import write_html_report, write_pdf_report
from .lp_model import DietSolution
from .tableau import TableauResult

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 9.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.22,
        "grid.linestyle": "--",
        "figure.dpi": 150,
        "savefig.dpi": 150,
    }
)

COLORS = {
    "baseline": "#7f8c8d",
    "iso": "#1f8a70",
    "nasem": "#2c6fbb",
    "intermediario": "#e6a23c",
    "com_milho": "#c0392b",
    "com_linhaca": "#8e44ad",
    "sem_sorgo": "#d35400",
    "max_economia": "#16a085",
    "accent": "#e67e22",
    "grid": "#bdc3c7",
}


def brl(value: float, decimals: int = 2) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "—"
    if value == np.inf:
        return "∞"
    if value == -np.inf:
        return "−∞"
    text = f"{value:,.{decimals}f}"
    return "R$ " + text.replace(",", "X").replace(".", ",").replace("X", ".")


def num(value: float, decimals: int = 2) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "—"
    if value == np.inf:
        return "∞"
    if value == -np.inf:
        return "−∞"
    return f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(value: float, decimals: int = 1, signed: bool = False) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "—"
    if value == np.inf:
        return "∞"
    if value == -np.inf:
        return "−∞"
    sign = "+" if signed and value > 0 else ""
    return f"{sign}{value:.{decimals}f}%".replace(".", ",")


def md_table(
    df: pd.DataFrame,
    columns: list[str],
    headers: list[str],
    formatters: list[Any] | None = None,
) -> str:
    formatters = formatters or [str] * len(columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for _, row in df.iterrows():
        cells = []
        for column, fmt in zip(columns, formatters):
            value = row.get(column, "")
            text = fmt(value) if callable(fmt) else str(value)
            cells.append(str(text).replace("|", "/"))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return np.nan


def _diet_frame(solution: DietSolution, label: str) -> pd.DataFrame:
    table = solution.diet_table().copy()
    table["cenario"] = label
    return table


def _scenario_color(key: str) -> str:
    mapping = {
        "baseline": COLORS["baseline"],
        "iso_energetico": COLORS["iso"],
        "nasem": COLORS["nasem"],
        "intermediario": COLORS["intermediario"],
        "com_milho_15": COLORS["com_milho"],
        "com_linhaca_5": COLORS["com_linhaca"],
        "sem_sorgo": COLORS["sem_sorgo"],
        "max_economia": COLORS["max_economia"],
    }
    return mapping.get(key, "#34495e")


def plot_diet_comparison(baseline: DietSolution, optimized: DietSolution, path: Path) -> None:
    base = baseline.diet_table()
    opt = optimized.diet_table()
    names = list(dict.fromkeys(list(base["alimento"]) + list(opt["alimento"])))
    base_map = dict(zip(base["alimento"], base["pct_ms"]))
    opt_map = dict(zip(opt["alimento"], opt["pct_ms"]))
    order = sorted(names, key=lambda name: -max(base_map.get(name, 0), opt_map.get(name, 0)))
    top = order[:9]
    other = order[9:]

    def values(mapping: dict[str, float]) -> list[float]:
        vals = [mapping.get(name, 0.0) for name in top]
        vals.append(sum(mapping.get(name, 0.0) for name in other))
        return vals

    labels = top + (["Outros"] if other else [])
    base_vals = values(base_map)
    opt_vals = values(opt_map)
    palette = plt.cm.tab20(np.linspace(0, 1, len(labels)))

    fig, ax = plt.subplots(figsize=(9.5, 4.6))
    left_base = 0.0
    left_opt = 0.0
    for idx, label in enumerate(labels):
        ax.barh([1], [base_vals[idx]], left=left_base, color=palette[idx], edgecolor="white", height=0.55)
        ax.barh([0], [opt_vals[idx]], left=left_opt, color=palette[idx], edgecolor="white", height=0.55)
        left_base += base_vals[idx]
        left_opt += opt_vals[idx]
    ax.set_yticks([0, 1], ["Otimizada", "Basal"])
    ax.set_xlabel("% da matéria seca")
    ax.set_xlim(0, 100)
    ax.set_title("Composição da dieta — basal vs. otimizada (iso-energética)")
    handles = [plt.Rectangle((0, 0), 1, 1, color=palette[idx]) for idx in range(len(labels))]
    ax.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.18),
        ncol=3,
        frameon=False,
        fontsize=7.5,
    )
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def plot_cost_comparison(scenario_table: pd.DataFrame, path: Path) -> None:
    table = scenario_table.copy()
    table = table.sort_values("custo_brl_vaca_dia", ascending=True)
    colors = [_scenario_color(key) for key in table["cenario"]]
    fig, ax = plt.subplots(figsize=(8.8, 4.6))
    bars = ax.barh(table["label"], table["custo_brl_vaca_dia"], color=colors, edgecolor="white")
    for bar, value in zip(bars, table["custo_brl_vaca_dia"]):
        ax.text(value + 0.15, bar.get_y() + bar.get_height() / 2, brl(value), va="center", fontsize=8)
    ax.set_xlabel("R$/vaca em lactação/dia")
    ax.set_title("Custo da ração por vaca em lactação")
    ax.set_xlim(0, table["custo_brl_vaca_dia"].max() * 1.18)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def plot_frontier(scenario_table: pd.DataFrame, path: Path) -> None:
    offsets = {
        "baseline": (7, 5),
        "iso_energetico": (7, -12),
        "com_milho_15": (7, -4),
        "sem_sorgo": (7, 8),
        "com_linhaca_5": (7, 20),
        "intermediario": (7, 5),
        "nasem": (7, 5),
        "max_economia": (7, 5),
    }
    short_labels = {
        "baseline": "Basal",
        "iso_energetico": "Iso-energética",
        "nasem": "NASEM",
        "intermediario": "Intermediário",
        "com_milho_15": "Com 15% milho",
        "com_linhaca_5": "Com 5% linhaça",
        "sem_sorgo": "Sem sorgo",
        "max_economia": "Máx. economia",
    }
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    for _, row in scenario_table.iterrows():
        ax.scatter(
            row["tdn_pct"],
            row["custo_brl_vaca_dia"],
            s=90,
            color=_scenario_color(row["cenario"]),
            edgecolor="white",
            zorder=3,
        )
        ax.annotate(
            short_labels.get(row["cenario"], row["label"]),
            (row["tdn_pct"], row["custo_brl_vaca_dia"]),
            textcoords="offset points",
            xytext=offsets.get(row["cenario"], (7, 5)),
            fontsize=7.5,
        )
    ax.set_xlabel("TDN da dieta (% da MS)")
    ax.set_ylabel("Custo (R$/vaca/dia)")
    ax.set_title("Fronteira custo × densidade energética")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def plot_tornado(oat: pd.DataFrame, path: Path, top_n: int = 8) -> None:
    table = oat.dropna(subset=["delta_menos_pct", "delta_mais_pct"]).head(top_n).iloc[::-1]
    fig, ax = plt.subplots(figsize=(8.4, 4.4))
    y = np.arange(len(table))
    ax.barh(y, table["delta_menos_pct"], color="#c0392b", alpha=0.85, label="Preço −20%")
    ax.barh(y, table["delta_mais_pct"], color="#1f8a70", alpha=0.85, label="Preço +20%")
    ax.set_yticks(y, table["alimento"])
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Variação do custo da ração (%)")
    ax.set_title("Sensibilidade local do custo a ±20% no preço de cada alimento")
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def plot_sobol(df: pd.DataFrame, path: Path, title: str, name_column: str = "alimento") -> None:
    table = df.head(10).iloc[::-1]
    y = np.arange(len(table))
    fig, ax = plt.subplots(figsize=(8.4, 4.4))
    ax.barh(y + 0.18, table["ST"], height=0.34, color="#2c6fbb", label="ST (total)")
    ax.barh(y - 0.18, table["S1"].clip(lower=0), height=0.34, color="#1f8a70", label="S1 (primeira ordem)")
    ax.set_yticks(y, table[name_column])
    ax.set_xlabel("Índice de Sobol")
    ax.set_title(title)
    ax.legend(frameon=False, loc="lower right")
    ax.set_xlim(0, max(0.1, float(table["ST"].max()) * 1.15))
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def plot_break_even(break_even: pd.DataFrame, path: Path, top_n: int = 10) -> None:
    table = break_even.dropna(subset=["preco_entrada"]).sort_values("reducao_necessaria_pct").head(top_n)
    if table.empty:
        return
    fig, ax = plt.subplots(figsize=(8.4, 4.4))
    y = np.arange(len(table))
    ax.scatter(table["preco_atual"], y, color="#7f8c8d", label="Preço atual", zorder=3)
    ax.scatter(table["preco_entrada"], y, color="#c0392b", label="Preço de entrada", zorder=3)
    for idx, row in enumerate(table.itertuples()):
        ax.plot([row.preco_atual, row.preco_entrada], [idx, idx], color="#bdc3c7", linewidth=2, zorder=1)
        ax.text(
            min(row.preco_atual, row.preco_entrada) - 0.04,
            idx,
            pct(row.reducao_necessaria_pct, 1, signed=True),
            va="center",
            ha="right",
            fontsize=7.5,
            color="#c0392b",
        )
    ax.set_yticks(y, table["alimento"])
    ax.set_xlabel("R$/kg de MS")
    ax.set_title("Preço de indiferença dos alimentos fora da dieta ótima")
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def plot_validation(summary: pd.DataFrame, path: Path) -> None:
    if summary.empty:
        return
    metrics = [
        ("leite_kg_vaca_dia", "Leite (kg/vaca/dia)", None),
        ("cms_kg_vaca_dia", "CMS (kg MS/vaca/dia)", None),
        ("metano_g_kg_leite", "CH₄ (g/kg leite)", None),
        ("metano_kg_dia", "CH₄ entérico (kg/dia)", None),
    ]
    scenarios = list(summary["cenario"].unique())
    labels = {
        "baseline": "Basal",
        "iso_energetico": "Iso-energética",
        "nasem": "NASEM",
    }
    fig, axes = plt.subplots(2, 2, figsize=(9.2, 5.6))
    for ax, (metric, title, _) in zip(axes.ravel(), metrics):
        data = [summary.loc[summary["cenario"] == scenario, metric].to_numpy() for scenario in scenarios]
        positions = np.arange(len(scenarios))
        means = [np.nanmean(values) for values in data]
        errors = [np.nanstd(values, ddof=1) if len(values) > 1 else 0 for values in data]
        ax.bar(
            positions,
            means,
            yerr=errors,
            capsize=3,
            color=[_scenario_color(s) for s in scenarios],
            edgecolor="white",
        )
        ax.set_xticks(positions, [labels.get(s, s) for s in scenarios])
        ax.set_title(title, fontsize=9)
    fig.suptitle("Validação no RuFaS — 1 ano (basal/iso: seeds 44–46; NASEM: seed 44)", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def save_tables(results: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    baseline = results["baseline"]
    scenarios = results["scenarios"]

    frames = {
        "dieta_basal.csv": _diet_frame(baseline, "baseline"),
        "dieta_iso.csv": _diet_frame(scenarios["iso_energetico"], "iso_energetico"),
        "dieta_nasem.csv": _diet_frame(scenarios["nasem"], "nasem"),
        "cenarios.csv": results["scenario_table"],
        "sensibilidade_oat.csv": results["oat"],
        "sobol_custo.csv": results["sobol_cost"],
        "sobol_iofc.csv": results["sobol_iofc"],
        "break_even.csv": results["break_even"],
        "pairwise_break_even.csv": results["pairwise_break_even"],
        "pairwise_cenarios.csv": results["pairwise"],
        "quadro_simplex.csv": results["tableau"].tableau.rename_axis("variavel_basica").reset_index(),
        "faixas_rhs.csv": results["tableau"].rhs_ranges,
        "faixas_preco.csv": results["tableau"].coefficient_ranges,
    }
    if not results["validation_summary"].empty:
        frames["validacao_resumo.csv"] = results["validation_summary"]
    if not results["validation_tests"].empty:
        frames["validacao_testes.csv"] = results["validation_tests"]
    for name, frame in frames.items():
        path = output_dir / name
        frame.to_csv(path, index=False, encoding="utf-8-sig")
        paths[name] = path
    return paths


def _scenario_labels(results: dict[str, Any]) -> dict[str, str]:
    labels = {"baseline": "Basal (RuFaS)"}
    meta = results.get("scenario_meta", {})
    for key in results["scenarios"]:
        labels[key] = meta.get(key, {}).get("label", key)
    return labels


def _section_resumo(results: dict[str, Any]) -> str:
    baseline = results["baseline"]
    iso = results["scenarios"]["iso_energetico"]
    nasem = results["scenarios"]["nasem"]
    comp_iso = results["comparisons"]["iso_energetico"]
    comp_nasem = results["comparisons"]["nasem"]
    mineral = results["mineral_decomp"]
    validation = results["validation_summary"]

    validation_text = ""
    if not validation.empty:
        iso_rows = validation[validation["cenario"] == "iso_energetico"]
        base_rows = validation[validation["cenario"] == "baseline"]
        if not iso_rows.empty and not base_rows.empty:
            milk_base = base_rows["leite_kg_dia"].mean()
            milk_iso = iso_rows["leite_kg_dia"].mean()
            dmi_base = base_rows["cms_kg_vaca_dia"].mean()
            dmi_iso = iso_rows["cms_kg_vaca_dia"].mean()
            ch4_base = base_rows["metano_g_kg_leite"].mean()
            ch4_iso = iso_rows["metano_g_kg_leite"].mean()
            validation_text = (
                f"Na validação de 1 ano no RuFaS (seeds 44–46), a produção de leite do lote "
                f"ficou em {num(milk_iso, 0)} kg/dia com a dieta otimizada contra "
                f"{num(milk_base, 0)} kg/dia da basal; o CMS caiu {pct(abs((dmi_iso / dmi_base - 1) * 100), 1)} "
                f"e a intensidade de metano entérico caiu {pct(abs((ch4_iso / ch4_base - 1) * 100), 1)}."
            )
    return f"""## 1. Resumo executivo

Este trabalho desenvolve um módulo de **programação linear (PL)** acoplado aos arquivos de entrada e saída do **RuFaS** para formular a dieta da vaca em lactação da Fazenda Campo Dourado (GO) ao **mínimo custo**, com avaliação do efeito econômico, análise de sensibilidade local e global (Sobol) e validação biológica no simulador.

**Resultado principal.** A dieta iso-energética (mesmo aporte de energia, proteína e fibra da dieta basal) custa **{brl(iso.cost_brl_cow_day)}/vaca/dia**, contra **{brl(baseline.cost_brl_cow_day)}/vaca/dia** da dieta basal avaliada com os mesmos preços de GO. Isso representa economia de **{brl(comp_iso['economia_brl_vaca_dia'])}/vaca/dia ({pct(comp_iso['economia_pct'])})** e **{brl(comp_iso['economia_anual_brl'])}/ano** para as {num(results['config']['farm']['lactating_cows'], 2)} vacas em lactação. A margem sobre o custo da ração (IOFC) sobe {pct(comp_iso['iofc_delta_pct'])}.

**Dieta recomendada (iso-energética):** {', '.join(f"{row['alimento']} {pct(row['pct_ms'])}" for _, row in iso.diet_table().head(5).iterrows())}, completando com minerais e ureia. A formulação substitui parte do milho e do farelo de soja por **sorgo, glúten de milho e farelo de algodão**, além de trocar a mistura mineral de 3% por calcário + mistura mineral em nível menor.

**Custo de segurança nutricional.** Se a fazenda quiser corrigir o déficit teórico de energia da dieta basal e atender à exigência NASEM (TDN 76,99% da MS), o custo sobe para **{brl(nasem.cost_brl_cow_day)}/vaca/dia** — ainda {pct(comp_nasem['economia_pct'])} abaixo da basal, mas com economia muito menor. O cenário iso-energético é o de maior retorno econômico; o cenário NASEM é o mais conservador.

**Decomposição da economia.** Cerca de **{pct(mineral['participacao_mineral_pct'])}** da economia vêm da substituição de fontes minerais caras (3% de mistura mineral) por calcário e por fósforo de alimentos como farelo de algodão e glúten de milho; os outros **{pct(100 - mineral['participacao_mineral_pct'])}** vêm da reformulação dos demais ingredientes. Esse ponto é importante: parte do ganho é correção de uma fórmula mineral possivelmente superdimensionada no cenário basal, não só “troca de milho por sorgo”. A decomposição é contábil: parte do fósforo foi transferida para farelo de algodão e glúten de milho, cujo custo aparece nas outras linhas; o ganho líquido é a diferença total.

**Sensibilidade.** O custo da ração é dominado pelo preço da **silagem de milho** (ST ≈ {num(results['sobol_cost'].iloc[0]['ST'], 2)}), seguido por **farelo de soja** (ST ≈ {num(results['sobol_cost'].iloc[1]['ST'], 2)}) e **sorgo** (ST ≈ {num(results['sobol_cost'].iloc[2]['ST'], 2)}). Na margem (IOFC), o **preço do leite** domina (ST ≈ {num(results['sobol_iofc'].iloc[0]['ST'], 2)}); os preços dos alimentos têm efeito pequeno. O milho grão só entra na dieta se cair cerca de **{pct(abs(results['break_even'].loc[results['break_even']['rufas_id'] == 44, 'reducao_necessaria_pct'].iloc[0]) if (results['break_even']['rufas_id'] == 44).any() else 0)}**; o farelo de linhaça, se cair cerca de **{pct(abs(results['break_even'].loc[results['break_even']['rufas_id'] == 112, 'reducao_necessaria_pct'].iloc[0]) if (results['break_even']['rufas_id'] == 112).any() else 0)}**.

{validation_text}

> **Leitura crítica:** o módulo é uma aproximação linear do modelo NASEM. Ele não substitui o RuFaS; serve para explorar o espaço de formulação, gerar hipóteses e orientar negociação de preços. A decisão final deve ser validada com o simulador completo (`full_farm`), com a dieta real da fazenda e com acompanhamento de consumo, leite, escore corporal e saúde ruminal.
"""


def _section_contexto(results: dict[str, Any]) -> str:
    farm = results["config"]["farm"]
    return f"""## 2. Contexto e problema

O RuFaS é um simulador *whole-farm* de fazendas leiteiras. O cenário `GO_campo_dourado` representa uma fazenda de 100 vacas Holstein em Goiás, com 88,6 vacas em lactação em média, produção de 41,3 kg de leite/vaca/dia e consumo de 25,3 kg de MS/vaca/dia. A dieta basal do RuFaS é definida no arquivo `feed.json` e inclui silagem de milho, silagem de leguminosa, milho grão, farelo de soja, caroço de algodão e mistura mineral.

O problema de pesquisa operacional é:

> Dado um lote de vacas com exigências nutricionais conhecidas, um conjunto de alimentos com composição e preço, e limites práticos de inclusão, qual mistura de alimentos atende às exigências ao **menor custo**? Como o custo e a composição ótima reagem a mudanças de preço? A dieta ótima mantém a produção quando simulada no RuFaS?

O escopo é a **ração da vaca em lactação** (pen `LAC_COW_PEN_3`), não o rebanho total. Bezerras, novilhas e vacas secas têm outras dietas e não são otimizadas aqui. O custo é o da ração no cocho, sem armazenamento, perdas, mistura, mão de obra ou capital.

**Dados de preço.** Preços de milho, soja e leite vêm do CEPEA (27/10/2026 para grãos; leite GO de ago/2026). Farelo de soja em Anápolis/GO vem da Agrolink (27/10/2026). Subprodutos sem indicador público usam cotação regional ou estimativa declarada. O câmbio usado para converter os preços do RuFaS é R$ {num(farm['usd_brl'], 2)}/US$ (Notícias Agrícolas, 27/10/2026).

**Hipótese central.** A dieta basal foi formulada com preços e ingredientes do exemplo do RuFaS (Nordeste dos EUA). Ao reavaliar a mesma dieta com preços de Goiás e permitir outros ingredientes, existe espaço para reduzir custo sem piorar o aporte nutricional.
"""


def _section_metodo(results: dict[str, Any]) -> str:
    req = results["baseline"].requirements
    return f"""## 3. Dados e método

### 3.1 Exigências nutricionais

As exigências foram calculadas com o próprio calculador NASEM do RuFaS para uma vaca de 650 kg, 150 dias em lactação, 41,3 kg de leite/dia, 4,0% de gordura e 3,2% de proteína:

| Indicador | Valor |
|---|---:|
| Consumo de MS (DMI) | {num(req.dmi_kg)} kg/dia |
| Energia líquida de lactação (NEl) | {num(req.nel_mcal)} Mcal/dia |
| Proteína metabolizável (PM) | {num(req.mp_g, 0)} g/dia |
| Cálcio absorvível | {num(req.ca_abs_g, 1)} g/dia |
| Fósforo absorvível | {num(req.p_abs_g, 1)} g/dia |
| TDN mínimo equivalente | {num(req.tdn_min_pct)}% da MS |

Além das exigências NASEM, foram impostas restrições práticas de formulação: NDF entre {num(req.ndf_min_pct)}% e {num(req.ndf_max_pct)}%, NDF de forragem ≥ {num(req.forage_ndf_min_pct)}%, amido entre {num(req.starch_min_pct)}% e {num(req.starch_max_pct)}%, extrato etéreo entre {num(req.ee_min_pct)}% e {num(req.ee_max_pct)}%, proteína bruta ≥ {num(req.cp_min_pct)}%, RUP digestível ≥ {num(req.rup_min_kg)} kg/dia, cálcio total ≥ {num(req.ca_total_min_pct)}% e relação Ca:P entre {num(req.ca_p_min)} e {num(req.ca_p_max)}. O cálcio e o fósforo absorvíveis usam os fatores de digestibilidade do RuFaS (0,30 para forragem, 0,60 para concentrado e 0,95 para mineral).

### 3.2 Formulação do problema de programação linear

Variáveis de decisão: $x_i$ = kg de MS/dia do alimento $i$ (19 alimentos candidatos).

```
minimizar   Σ c_i x_i
sujeito a   Σ x_i = 25,3                     (consumo de MS)
            Σ a_ij x_i ≥ b_j                 (nutrientes mínimos)
            Σ a_ij x_i ≤ b_j                 (limites máximos)
            l_i ≤ x_i ≤ u_i                  (inclusão mínima e máxima)
```

O problema tem 19 variáveis e 37 restrições de desigualdade, além da igualdade de MS. Foi resolvido com `scipy.optimize.linprog`, método **dual simplex** (HiGHS). O quadro final do simplex foi reconstruído a partir da base ótima para leitura econômica (custos reduzidos e preços sombra).

### 3.3 Dieta basal e cenários

A dieta basal é a ração `lac_cow` do `feed.json` do RuFaS, com 30% de silagem de milho, 18% de silagem de leguminosa, 24% de milho, 16% de farelo de soja, 9% de caroço de algodão e 3% de mistura mineral. Ela foi avaliada com a mesma tabela de preços da otimização, para separar efeito de formulação de efeito de preço.

Cenários:
- **Iso-energético (recomendado):** TDN mínimo igual ao da dieta basal (72,12% da MS), mantendo energia, proteína e fibra.
- **NASEM:** TDN mínimo de 76,99% da MS, corrigindo o déficit teórico de energia; NDF mínimo de 27,5% e Ca:P mínimo de 1,2 para acomodar a alta densidade energética.
- **Intermediário:** TDN de 74,0%.
- **Com milho 15%:** força pelo menos 15% de milho grão.
- **Com linhaça 5%:** força 5% de farelo de linhaça.
- **Sem sorgo:** simula indisponibilidade de sorgo.
- **Máxima economia:** remove a exigência de RUP e reduz a proteína bruta para 17,0%.

### 3.4 Análise de sensibilidade

- **Local:** preço sombra de cada restrição, custo reduzido de cada alimento, faixas de RHS que preservam a base ótima e preço de indiferença dos alimentos.
- **Global (Sobol):** 10 preços de alimentos variando ±30% e preço do leite ±20%; índices de primeira ordem (S1) e total (ST), com {results['n_sobol']} amostras e *bootstrap* de 100 reamostragens.
- **Testes pareados:** os mesmos choques de preço são aplicados a todos os cenários; as diferenças são comparadas com Wilcoxon e IC bootstrap de 95%.
- **Pairwise de ingredientes:** para pares como milho × sorgo, calcula-se o preço de indiferença do segundo ingrediente.

### 3.5 Validação no RuFaS

A dieta iso-energética foi convertida em `feed_otimizado.json` e simulada no RuFaS em modo `animals_only`, 1 ano (2015), seeds 44, 45 e 46. A basal foi simulada nas mesmas seeds; a NASEM, na seed 44. Foram comparados leite, consumo de MS, metano entérico e intensidade de metano. O modo `animals_only` isola o efeito nutricional; não inclui dejetos, solo, culturas nem custos completos da fazenda.
"""


def _section_resultados(results: dict[str, Any]) -> str:
    baseline = results["baseline"]
    iso = results["scenarios"]["iso_energetico"]
    nasem = results["scenarios"]["nasem"]
    labels = _scenario_labels(results)

    diet_base = baseline.diet_table()
    diet_iso = iso.diet_table()

    diet_table = md_table(
        diet_iso,
        ["alimento", "pct_ms", "kg_ms_dia", "preco_brl_kg_ms", "custo_brl_dia"],
        ["Alimento", "% MS", "kg MS/dia", "R$/kg MS", "R$/dia"],
        [str, lambda v: pct(v), lambda v: num(v, 2), lambda v: brl(v), lambda v: brl(v)],
    )
    base_table = md_table(
        diet_base,
        ["alimento", "pct_ms", "kg_ms_dia", "preco_brl_kg_ms", "custo_brl_dia"],
        ["Alimento", "% MS", "kg MS/dia", "R$/kg MS", "R$/dia"],
        [str, lambda v: pct(v), lambda v: num(v, 2), lambda v: brl(v), lambda v: brl(v)],
    )

    nutrients = pd.DataFrame(
        [
            {
                "indicador": "Proteína bruta (% MS)",
                "basal": baseline.nutrient_supply["cp_pct"],
                "iso": iso.nutrient_supply["cp_pct"],
                "nasem": nasem.nutrient_supply["cp_pct"],
                "requisito": num(iso.requirements.cp_min_pct),
            },
            {
                "indicador": "NDF (% MS)",
                "basal": baseline.nutrient_supply["ndf_pct"],
                "iso": iso.nutrient_supply["ndf_pct"],
                "nasem": nasem.nutrient_supply["ndf_pct"],
                "requisito": f"{num(iso.requirements.ndf_min_pct)} (iso) / {num(nasem.requirements.ndf_min_pct)} (NASEM) – {num(iso.requirements.ndf_max_pct)}",
            },
            {
                "indicador": "Amido (% MS)",
                "basal": baseline.nutrient_supply["starch_pct"],
                "iso": iso.nutrient_supply["starch_pct"],
                "nasem": nasem.nutrient_supply["starch_pct"],
                "requisito": f"{num(iso.requirements.starch_min_pct)}–{num(iso.requirements.starch_max_pct)}",
            },
            {
                "indicador": "Extrato etéreo (% MS)",
                "basal": baseline.nutrient_supply["ee_pct"],
                "iso": iso.nutrient_supply["ee_pct"],
                "nasem": nasem.nutrient_supply["ee_pct"],
                "requisito": f"{num(iso.requirements.ee_min_pct)}–{num(iso.requirements.ee_max_pct)}",
            },
            {
                "indicador": "TDN (% MS)",
                "basal": baseline.nutrient_supply["tdn_pct"],
                "iso": iso.nutrient_supply["tdn_pct"],
                "nasem": nasem.nutrient_supply["tdn_pct"],
                "requisito": f"{num(iso.requirements.tdn_min_pct)} (iso) / {num(nasem.requirements.tdn_min_pct)} (NASEM)",
            },
            {
                "indicador": "NEl (Mcal/dia)",
                "basal": baseline.nutrient_supply["nel_mcal"],
                "iso": iso.nutrient_supply["nel_mcal"],
                "nasem": nasem.nutrient_supply["nel_mcal"],
                "requisito": f"{num(baseline.nutrient_supply['nel_mcal'])} (iso = basal) / {num(nasem.requirements.nel_mcal)} (NASEM)",
            },
            {
                "indicador": "RUP digestível (kg/dia)",
                "basal": baseline.nutrient_supply["rup_dig_kg"],
                "iso": iso.nutrient_supply["rup_dig_kg"],
                "nasem": nasem.nutrient_supply["rup_dig_kg"],
                "requisito": num(iso.requirements.rup_min_kg),
            },
            {
                "indicador": "Ca absorvível (g/dia)",
                "basal": baseline.nutrient_supply["ca_abs_g"],
                "iso": iso.nutrient_supply["ca_abs_g"],
                "nasem": nasem.nutrient_supply["ca_abs_g"],
                "requisito": num(iso.requirements.ca_abs_g),
            },
            {
                "indicador": "P absorvível (g/dia)",
                "basal": baseline.nutrient_supply["p_abs_g"],
                "iso": iso.nutrient_supply["p_abs_g"],
                "nasem": nasem.nutrient_supply["p_abs_g"],
                "requisito": num(iso.requirements.p_abs_g),
            },
        ]
    )
    nutrient_table = md_table(
        nutrients,
        ["indicador", "basal", "iso", "nasem", "requisito"],
        ["Indicador", "Basal", "Iso-energética", "NASEM", "Requisito"],
        [str, lambda v: num(v, 2), lambda v: num(v, 2), lambda v: num(v, 2), str],
    )

    comp_iso = results["comparisons"]["iso_energetico"]
    comp_nasem = results["comparisons"]["nasem"]
    econ = pd.DataFrame(
        [
            {
                "indicador": "Custo da ração (R$/vaca/dia)",
                "basal": brl(comp_iso["custo_basal_brl_vaca_dia"]),
                "iso": brl(comp_iso["custo_otimizado_brl_vaca_dia"]),
                "nasem": brl(comp_nasem["custo_otimizado_brl_vaca_dia"]),
            },
            {
                "indicador": "Custo por kg de leite (R$/kg)",
                "basal": brl(comp_iso["custo_basal_brl_kg_leite"], 3),
                "iso": brl(comp_iso["custo_otimizado_brl_kg_leite"], 3),
                "nasem": brl(comp_nasem["custo_otimizado_brl_kg_leite"], 3),
            },
            {
                "indicador": "IOFC (R$/vaca/dia)",
                "basal": brl(comp_iso["iofc_basal_brl_vaca_dia"]),
                "iso": brl(comp_iso["iofc_otimizado_brl_vaca_dia"]),
                "nasem": brl(comp_nasem["iofc_otimizado_brl_vaca_dia"]),
            },
            {
                "indicador": "Custo da ração (% da receita)",
                "basal": pct(comp_iso["custo_racao_pct_receita_basal"]),
                "iso": pct(comp_iso["custo_racao_pct_receita_otimizado"]),
                "nasem": pct(comp_nasem["custo_racao_pct_receita_otimizado"]),
            },
            {
                "indicador": "Economia anual (R$)",
                "basal": "—",
                "iso": brl(comp_iso["economia_anual_brl"], 0),
                "nasem": brl(comp_nasem["economia_anual_brl"], 0),
            },
        ]
    )
    econ_table = md_table(
        econ,
        ["indicador", "basal", "iso", "nasem"],
        ["Indicador", "Basal", "Iso-energética", "NASEM"],
        [str, str, str, str],
    )

    scenario_table = results["scenario_table_with_baseline"].copy()
    scenario_md = md_table(
        scenario_table,
        [
            "label",
            "custo_brl_vaca_dia",
            "custo_brl_kg_leite",
            "economia_vs_basal_pct",
            "iofc_brl_vaca_dia",
            "economia_anual_brl",
        ],
        ["Cenário", "R$/vaca/dia", "R$/kg leite", "Economia vs. basal", "IOFC (R$/vaca/dia)", "Economia anual (R$)"],
        [str, lambda v: brl(v), lambda v: brl(v), lambda v: pct(v, 1, True), lambda v: brl(v), lambda v: brl(v, 0)],
    )

    validation_md = ""
    if not results["validation_summary"].empty:
        val = results["validation_summary"].copy()
        val["cenario"] = val["cenario"].map(labels).fillna(val["cenario"])
        validation_md = (
            "### 4.5 Validação biológica no RuFaS\n\n"
            + md_table(
                val,
                [
                    "cenario",
                    "seed",
                    "leite_kg_dia",
                    "vacas_em_lactacao",
                    "leite_kg_vaca_dia",
                    "cms_kg_vaca_dia",
                    "metano_kg_dia",
                    "metano_g_kg_leite",
                ],
                [
                    "Cenário",
                    "Seed",
                    "Leite (kg/dia)",
                    "Vacas",
                    "Leite/vaca (kg/dia)",
                    "CMS (kg/vaca/dia)",
                    "CH₄ (kg/dia)",
                    "CH₄ (g/kg leite)",
                ],
                [
                    str,
                    lambda v: str(int(v)),
                    lambda v: num(v, 0),
                    lambda v: num(v, 2),
                    lambda v: num(v, 2),
                    lambda v: num(v, 2),
                    lambda v: num(v, 2),
                    lambda v: num(v, 2),
                ],
            )
            + "\n\nA validação é exploratória: 1 ano, sem repetição de curto prazo. Basal e iso-energética foram simuladas com 3 seeds; a NASEM, com 1 seed (44). Os efeitos de metano da iso são consistentes em sinal e magnitude, mas o teste de Wilcoxon com 3 seeds tem baixo poder estatístico (p = 0,25). O leite ficou estável; o CMS caiu levemente; o metano entérico por kg de leite caiu cerca de 9%.\n\n![Validação no RuFaS](fig_validacao.png)\n"
        )

    return f"""## 4. Resultados

### 4.1 Dieta ótima

A dieta iso-energética de mínimo custo é:

{diet_table}

A dieta basal, para comparação, é:

{base_table}

Observações:
- A otimização **não usa milho grão** no cenário iso-energético: o sorgo e o glúten de milho entregam TDN e proteína a custo menor por unidade de energia. O milho só entra se seu preço cair (ver seção 5).
- O farelo de soja cai de 16% para cerca de 9%; parte da proteína é suprida por farelo de algodão, glúten de milho e ureia.
- A mistura mineral cai de 3% para 0,5%, com 1,2% de calcário. O fósforo é suprido por farelo de algodão e glúten de milho, que são fontes mais baratas por unidade de P.
- A dieta usa 0,4% de ureia, dentro do limite de 0,6% da MS. Ureia é uma fonte de nitrogênio não proteico; seu uso exige adaptação gradual e mistura uniforme.

### 4.2 Adequação nutricional

{nutrient_table}

A dieta iso-energética atende às restrições impostas. O TDN é igual ao da basal (72,12%), o que é coerente com a hipótese de manter a produção. A dieta NASEM eleva o TDN para 76,99%, mas custa mais. O cálcio absorvível da basal é cerca de 147 g/dia, muito acima dos 66,8 g/dia exigidos; a dieta otimizada mantém cerca de 144 g/dia, porque o mínimo de cálcio total (0,60%) e a relação Ca:P mínima (1,5) impedem uma redução maior. Se o objetivo fosse reduzir o excesso de cálcio, seria necessário relaxar essas restrições e buscar outra fonte de fósforo; o ganho econômico e ambiental não foi incluído nesta análise.

### 4.3 Efeito econômico

{econ_table}

O custo da ração da vaca em lactação cai de **{brl(comp_iso['custo_basal_brl_vaca_dia'])}** para **{brl(comp_iso['custo_otimizado_brl_vaca_dia'])}/dia**, uma economia de **{pct(comp_iso['economia_pct'])}**. Para 88,6 vacas, isso equivale a **{brl(comp_iso['economia_anual_brl'])}/ano**. A margem sobre o custo da ração sobe de {brl(comp_iso['iofc_basal_brl_vaca_dia'])} para {brl(comp_iso['iofc_otimizado_brl_vaca_dia'])}/vaca/dia (+{pct(comp_iso['iofc_delta_pct'])}). O custo da ração como proporção da receita cai de {pct(comp_iso['custo_racao_pct_receita_basal'])} para {pct(comp_iso['custo_racao_pct_receita_otimizado'])}.

### 4.4 Comparação de cenários

{scenario_md}

O cenário de **máxima economia** chega a {brl(results['scenarios']['max_economia'].cost_brl_cow_day)}/vaca/dia, mas remove a exigência de RUP e reduz a proteína bruta; é um limite superior teórico, não uma recomendação direta. O cenário **com milho 15%** custa {brl(results['scenarios']['com_milho_15'].cost_brl_cow_day)}/vaca/dia ({pct((results['scenarios']['com_milho_15'].cost_brl_cow_day / iso.cost_brl_cow_day - 1) * 100, 1, True)} vs. iso), mostrando o custo de manter o milho por razões operacionais. O cenário **com linhaça 5%** custa {brl(results['scenarios']['com_linhaca_5'].cost_brl_cow_day)}/vaca/dia; o prêmio sobre a iso é de {brl(results['scenarios']['com_linhaca_5'].cost_brl_cow_day - iso.cost_brl_cow_day)}/vaca/dia.

{validation_md}

![Composição da dieta](fig_dieta.png)

![Custo por cenário](fig_custo.png)

![Fronteira custo × energia](fig_fronteira.png)
"""


def _section_sensibilidade(results: dict[str, Any]) -> str:
    tableau: TableauResult = results["tableau"]
    shadow = tableau.rhs_ranges.copy()
    shadow = shadow[shadow["folga_atual"].abs() < 1e-6].copy()
    shadow = shadow.sort_values("preco_sombra_brl_dia", ascending=False)
    shadow_table = md_table(
        shadow,
        ["restricao", "valor_atual", "minimo", "maximo", "preco_sombra_brl_dia", "unidade"],
        ["Restrição ativa", "Valor atual", "Mínimo", "Máximo", "Preço sombra (R$/dia)", "Unidade"],
        [
            str,
            lambda v: num(v, 2),
            lambda v: num(0.0 if abs(v) < 1e-9 else max(v, 0), 2),
            lambda v: num(v, 2),
            lambda v: brl(v, 3),
            str,
        ],
    )

    break_even = results["break_even"].copy()
    nonbasic = break_even[break_even["status"] == "não básico"].copy()
    nonbasic = nonbasic.sort_values("reducao_necessaria_pct")
    be_table = md_table(
        nonbasic,
        ["alimento", "preco_atual", "preco_entrada", "reducao_necessaria_pct"],
        ["Alimento", "Preço atual (R$/kg MS)", "Preço de entrada (R$/kg MS)", "Redução necessária"],
        [str, lambda v: brl(v), lambda v: brl(v), lambda v: pct(v, 1, True)],
    )

    basic = break_even[break_even["status"] == "básico"].copy()
    basic = basic.sort_values("aumento_suportado_pct")
    basic_table = md_table(
        basic,
        ["alimento", "preco_atual", "preco_max", "aumento_suportado_pct"],
        ["Alimento na dieta", "Preço atual (R$/kg MS)", "Preço de saída (R$/kg MS)", "Aumento suportado"],
        [str, lambda v: brl(v), lambda v: brl(v), lambda v: pct(v, 1, True)],
    )

    pair_be = results["pairwise_break_even"].copy()
    pair_table = md_table(
        pair_be,
        ["alimento_A", "alimento_B", "preco_B_atual_brl_kg_ms", "preco_B_indiferenca_brl_kg_ms", "variacao_B_pct"],
        [
            "Alimento A",
            "Alimento B",
            "Preço atual de B (R$/kg MS)",
            "Preço de indiferença de B (R$/kg MS)",
            "Variação de B",
        ],
        [str, str, lambda v: brl(v), lambda v: brl(v), lambda v: pct(v, 1, True)],
    )

    oat = results["oat"]
    oat_table = md_table(
        oat.head(10),
        ["alimento", "delta_menos_pct", "delta_mais_pct", "amplitude_brl_dia"],
        ["Alimento", "Custo −20%", "Custo +20%", "Amplitude (R$/dia)"],
        [str, lambda v: pct(v, 1, True), lambda v: pct(v, 1, True), lambda v: brl(v)],
    )

    sobol_cost = results["sobol_cost"]
    sobol_cost_table = md_table(
        sobol_cost.head(10),
        ["alimento", "S1", "S1_conf", "ST", "ST_conf"],
        ["Alimento", "S1", "IC 95%", "ST", "IC 95%"],
        [str, lambda v: num(v, 3), lambda v: num(v, 3), lambda v: num(v, 3), lambda v: num(v, 3)],
    )
    sobol_iofc = results["sobol_iofc"]
    sobol_iofc_table = md_table(
        sobol_iofc.head(10),
        ["variavel", "S1", "S1_conf", "ST", "ST_conf"],
        ["Variável", "S1", "IC 95%", "ST", "IC 95%"],
        [str, lambda v: num(v, 3), lambda v: num(v, 3), lambda v: num(v, 3), lambda v: num(v, 3)],
    )

    pairwise = results["pairwise"].copy()
    if not pairwise.empty:
        labels = _scenario_labels(results)
        pairwise["cenario_A"] = pairwise["cenario_A"].map(labels).fillna(pairwise["cenario_A"])
        pairwise["cenario_B"] = pairwise["cenario_B"].map(labels).fillna(pairwise["cenario_B"])
    pairwise_table = md_table(
        pairwise,
        [
            "cenario_A",
            "cenario_B",
            "delta_medio_brl_dia",
            "delta_pct_medio",
            "ic95_inf_brl_dia",
            "ic95_sup_brl_dia",
            "p_valor_wilcoxon",
        ],
        ["Cenário A", "Cenário B", "Δ médio (R$/dia)", "Δ (%)", "IC 95% inf.", "IC 95% sup.", "p (Wilcoxon)"],
        [
            str,
            str,
            lambda v: brl(v),
            lambda v: pct(v, 1, True),
            lambda v: brl(v),
            lambda v: brl(v),
            lambda v: num(v, 4),
        ],
    )

    return f"""## 5. Análise de sensibilidade

### 5.1 Preços sombra e quadro final do simplex

O quadro final do simplex mostra quais restrições estão ativas e quanto custaria apertá-las ou relaxá-las. A tabela abaixo traz as restrições com folga zero; o preço sombra é o acréscimo de custo (R$/vaca/dia) para **aumentar em uma unidade** a exigência (ou o valor de **relaxar** o limite, no caso de restrições de máximo).

{shadow_table}

Leitura de negócio:
- **Energia (TDN):** cada ponto percentual adicional de TDN custa cerca de {brl(shadow.loc[shadow['restricao'].str.contains('Energia'), 'preco_sombra_brl_dia'].iloc[0] if (shadow['restricao'].str.contains('Energia')).any() else 0, 3)}/vaca/dia. Isso mostra o custo de buscar uma dieta mais energética.
- **Proteína bruta:** cada ponto percentual adicional custa cerca de {brl(shadow.loc[shadow['restricao'].str.contains('Proteína bruta'), 'preco_sombra_brl_dia'].iloc[0] if (shadow['restricao'].str.contains('Proteína bruta')).any() else 0, 3)}/vaca/dia.
- **RUP:** cada kg adicional de RUP digestível custa cerca de {brl(shadow.loc[shadow['restricao'].str.contains('não degradável'), 'preco_sombra_brl_dia'].iloc[0] if (shadow['restricao'].str.contains('não degradável')).any() else 0, 3)}/vaca/dia; é a restrição mais cara da formulação.
- **Mistura mineral:** o mínimo de 0,5% custa cerca de {brl(shadow.loc[shadow['restricao'].str.contains('Mineral', case=False), 'preco_sombra_brl_dia'].iloc[0] if (shadow['restricao'].str.contains('Mineral', case=False)).any() else 0, 3)}/vaca/dia por kg adicional de MS. Isso reforça que a mistura mineral é um item de alto custo unitário.

As faixas de RHS mostram até onde a base ótima não muda. Por exemplo, a exigência de TDN pode cair de {num(shadow.loc[shadow['restricao'].str.contains('Energia'), 'valor_atual'].iloc[0], 2) if (shadow['restricao'].str.contains('Energia')).any() else '—'}% até {num(shadow.loc[shadow['restricao'].str.contains('Energia'), 'minimo'].iloc[0], 2) if (shadow['restricao'].str.contains('Energia')).any() else '—'}% sem trocar a base; acima disso, a composição muda.

### 5.2 Preço de indiferença dos alimentos

A tabela abaixo mostra quanto cada alimento **fora da dieta** precisaria cair para entrar na solução ótima:

{be_table}

E quanto cada alimento **na dieta** pode subir antes de ser substituído:

{basic_table}

O caso do **milho** é o mais didático: aos preços de 27/10/2026 (R$ 64,87/saca), ele não entra. O preço de indiferença é cerca de **{brl(break_even.loc[break_even['rufas_id'] == 44, 'preco_entrada'].iloc[0]) if (break_even['rufas_id'] == 44).any() else '—'}/kg MS**, equivalente a uma queda de **{pct(abs(break_even.loc[break_even['rufas_id'] == 44, 'reducao_necessaria_pct'].iloc[0]), 1) if (break_even['rufas_id'] == 44).any() else '—'}** (cerca de R$ 56/saca). A **linhaça** só entra se cair **{pct(abs(break_even.loc[break_even['rufas_id'] == 112, 'reducao_necessaria_pct'].iloc[0]), 1) if (break_even['rufas_id'] == 112).any() else '—'}**, para cerca de {brl(break_even.loc[break_even['rufas_id'] == 112, 'preco_entrada'].iloc[0]) if (break_even['rufas_id'] == 112).any() else '—'}/kg MS. O preço de referência é o Indicador CEPEA Campinas; para uma fazenda em Goiás, o preço posto na fazenda pode ser diferente. O critério prático é: **se o milho posto estiver abaixo de ~R$ 56/saca, ele passa a competir**; acima disso, o sorgo tende a dominar.

### 5.3 Comparações pareadas de ingredientes

{pair_table}

Exemplo: o sorgo pode subir cerca de **{pct(pair_be.loc[pair_be['alimento_B'].str.contains('Sorgo'), 'variacao_B_pct'].iloc[0], 1, True) if (pair_be['alimento_B'].str.contains('Sorgo')).any() else '—'}** antes de o milho assumir seu espaço. O farelo de algodão pode subir cerca de **{pct(pair_be.loc[pair_be['alimento_B'].str.contains('Farelo de algodão'), 'variacao_B_pct'].iloc[0], 1, True) if (pair_be['alimento_B'].str.contains('Farelo de algodão')).any() else '—'}** antes de o farelo de soja voltar. O farelo de linhaça precisaria cair **{pct(abs(pair_be.loc[pair_be['alimento_B'].str.contains('Farelo de linhaça'), 'variacao_B_pct'].iloc[0]), 1) if (pair_be['alimento_B'].str.contains('Farelo de linhaça')).any() else '—'}** para competir com o farelo de soja.

### 5.4 Sensibilidade local (tornado)

{oat_table}

A silagem de milho é o item de maior impacto: ±20% no seu preço move o custo da ração em cerca de ±5,7%. Sorgo e farelo de soja vêm em seguida. A linhaça tem impacto praticamente nulo porque não está na dieta.

![Tornado](fig_tornado.png)

### 5.5 Sensibilidade global (Sobol)

**Custo da ração.** Índices de Sobol para os 10 preços de alimentos variando ±30%:

{sobol_cost_table}

**Margem sobre o custo da ração (IOFC).** Inclui o preço do leite variando ±20%:

{sobol_iofc_table}

Interpretação:
- No custo, a **silagem de milho** é o fator dominante (ST ≈ {num(sobol_cost.iloc[0]['ST'], 2)}), seguida de **farelo de soja** (ST ≈ {num(sobol_cost.iloc[1]['ST'], 2)}) e **sorgo** (ST ≈ {num(sobol_cost.iloc[2]['ST'], 2)}). A linhaça tem ST ≈ {num(sobol_cost.loc[sobol_cost['alimento'].str.contains('Flaxseed'), 'ST'].iloc[0] if (sobol_cost['alimento'].str.contains('Flaxseed')).any() else 0, 4)}, praticamente zero.
- No IOFC, o **preço do leite** explica cerca de {pct(sobol_iofc.iloc[0]['ST'] * 100)} da variância; os preços dos alimentos somam pouco. A mensagem de gestão é clara: **negociar leite e manter a produção** importa mais do que perseguir o último centavo na ração; a ração é alavanca de custo, mas o preço do leite é a alavanca de receita.

![Sobol custo](fig_sobol_custo.png)

![Sobol IOFC](fig_sobol_iofc.png)

### 5.6 Testes pareados de cenários

{pairwise_table}

Todos os cenários foram resolvidos sobre a mesma amostra de {results['n_pairwise']} choques de preço (±20%), o que controla o efeito comum de mercado. As diferenças são estatisticamente significativas. O cenário iso-energético é mais barato que o NASEM, o intermediário, o com milho, o com linhaça e o sem sorgo; o cenário de máxima economia é ainda mais barato, mas com risco nutricional.

![Preço de indiferença](fig_break_even.png)
"""


def _section_integracao(results: dict[str, Any]) -> str:
    validation = results["validation_summary"]
    validation_text = ""
    if not validation.empty:
        base = validation[validation["cenario"] == "baseline"]
        iso = validation[validation["cenario"] == "iso_energetico"]
        if not base.empty and not iso.empty:
            validation_text = (
                f"**Validação realizada.** A dieta iso-energética foi simulada em 1 ano com seeds 44, 45 e 46. "
                f"O leite ficou em média em {num(iso['leite_kg_dia'].mean(), 0)} kg/dia contra "
                f"{num(base['leite_kg_dia'].mean(), 0)} kg/dia da basal "
                f"({pct((iso['leite_kg_dia'].mean() / base['leite_kg_dia'].mean() - 1) * 100, 1, True)}); "
                f"o CMS por vaca caiu {pct(abs((iso['cms_kg_vaca_dia'].mean() / base['cms_kg_vaca_dia'].mean() - 1) * 100), 1)} "
                f"e a intensidade de metano entérico caiu "
                f"{pct(abs((iso['metano_g_kg_leite'].mean() / base['metano_g_kg_leite'].mean() - 1) * 100), 1)}. "
                f"A dieta NASEM (mais energética) também manteve o leite e reduziu levemente a intensidade de metano "
                f"(-1,6% vs. basal no seed 44), mas custa cerca de R$ 5,53/vaca/dia mais que a iso-energética. "
                f"O trade-off principal é econômico, não ambiental."
            )
    return f"""## 6. Integração com o RuFaS

O módulo gera os seguintes arquivos para rodar a dieta no RuFaS:

| Arquivo | Uso |
|---|---|
| `feed_otimizado.json` | Cópia do `feed.json` com a ração `lac_cow` substituída pela dieta ótima e os novos alimentos adicionados ao bloco `feeds`. |
| `config_otimizado.json` | Configuração de validação (`animals_only`, 1 ano) ou de simulação completa. |
| `farm_metadata_otimizado.json` | Metadata da fazenda apontando para o feed e a config otimizados. |
| `_otimizacao_tasks.json` | Task de execução com seed e prefixo de saída. |
| `_otimizacao_task_manager_metadata.json` | Wrapper para rodar com `main.py -p`. |
| `dieta_iso.csv`, `dieta_nasem.csv`, `quadro_simplex.csv` | Tabelas de apoio. |

Comando de validação (1 ano, `animals_only`):

```powershell
.\\.venv\\Scripts\\python.exe main.py -p .\\GO_campo_dourado\\otimizacao_dieta\\_otimizacao_task_manager_metadata.json -v errors
```

Para simulação completa de 5 anos (`full_farm`), troque `config_otimizado.json` pelo `config.json` original e ajuste `simulation_type` para `full_farm`. O CSV de saída pode passar de 500 MB.

{validation_text}

**Ressalva importante.** O RuFaS usa uma curva de lactação e um otimizador não linear internos. A dieta do módulo é imposta como ração definida pelo usuário (`user_input`), e o RuFaS verifica se ela atende às exigências. Se não atender, o modelo pode reduzir a produção. Nesta validação, o leite ficou estável, o que é um bom sinal, mas não prova que a dieta funcionará em qualquer fazenda.
"""


def _section_limitacoes(results: dict[str, Any]) -> str:
    return """## 7. Limitações e riscos

1. **Linearização.** O modelo NASEM é não linear: a energia metabolizável depende do consumo, do amido, do metano e do nitrogênio; a proteína metabolizável depende das frações de nitrogênio e da digestibilidade. O PL usa TDN, PB e RUP digestível como proxies lineares. A validação no RuFaS é a ponte entre a aproximação e o modelo completo.
2. **Preços.** Os preços são uma fotografia de 27/10/2026. Subprodutos como sorgo, glúten de milho, farelo de algodão e linhaça usam cotação regional ou estimativa; a incerteza é maior que a do milho e da soja. O preço do leite é de ago/2026 e varia por qualidade, volume e contrato.
3. **Mistura mineral.** A dieta basal usa 3% de mistura mineral, o que pode não refletir a prática da fazenda. Cerca de 61% da economia vem da troca dessa fonte mineral; se a fazenda já usa uma mistura mais barata ou parcialmente produzida na fazenda, a economia será menor. O cenário “basal ajustado” (1% mineral + 1% calcário) custa R$ 29,52/vaca/dia, mas fica deficiente em P absorvível; não é um comparativo válido sem uma fonte de fósforo.
4. **Escopo.** O custo é o da ração da vaca em lactação. Não inclui bezerras, novilhas, vacas secas, armazenamento, perdas, mistura, mão de obra, energia, capital ou custos fixos.
5. **Validação.** A validação é de 1 ano; basal e iso-energética com 3 seeds e a NASEM com 1 seed, em modo `animals_only`. O rebanho é sintético e o clima/solo são aproximações. Não houve acompanhamento de escore corporal, saúde ruminal, consumo individual ou qualidade do leite.
6. **Metano.** A dieta iso-energética reduziu o metano entérico por kg de leite na validação, mas o efeito no CO₂e total da fazenda depende de dejetos, solo, culturas e emissões de ração comprada. O modo `full_farm` é necessário para uma conclusão ambiental.
7. **Ureia.** A dieta usa 0,4% de ureia. Ureia mal misturada ou em excesso pode causar toxicidade; a adaptação deve ser gradual e acompanhada por nutricionista.
8. **Câmbio e inflação.** A conversão para US$ usa R$ 5,35/US$. Variações cambiais mudam a comparação com o RuFaS, mas não a otimização em reais.
"""


def _section_conclusoes(results: dict[str, Any]) -> str:
    iso = results["scenarios"]["iso_energetico"]
    comp = results["comparisons"]["iso_energetico"]
    return f"""## 8. Conclusões e recomendações

1. **A dieta iso-energética é a recomendação econômica.** Ela mantém o aporte de energia, proteína e fibra da dieta basal, custa {brl(iso.cost_brl_cow_day)}/vaca/dia contra {brl(comp['custo_basal_brl_vaca_dia'])}/vaca/dia da basal ({pct(comp['economia_pct'])} de economia) e foi validada no RuFaS com leite estável. Para 88,6 vacas, a economia potencial é de {brl(comp['economia_anual_brl'])}/ano.
2. **A dieta NASEM é a opção conservadora.** Atende à exigência formal de energia (TDN 76,99%) e custa {brl(results['scenarios']['nasem'].cost_brl_cow_day)}/vaca/dia, ainda {pct(results['comparisons']['nasem']['economia_pct'])} abaixo da basal. É indicada se a fazenda prefere segurança nutricional a economia máxima.
3. **O milho não é competitivo aos preços atuais.** Ele só entra se cair cerca de 13% (para ~R$ 56/saca). O sorgo é a principal fonte de energia da dieta ótima, seguido de glúten de milho. A fazenda deve monitorar a relação de preços milho/sorgo e contratar sorgo com antecedência.
4. **A linhaça não se paga pelo valor nutricional.** Ela só entra se cair cerca de 34%. Se a fazenda quiser leite com apelo funcional (ômega-3), o prêmio é de cerca de {brl(results['scenarios']['com_linhaca_5'].cost_brl_cow_day - iso.cost_brl_cow_day)}/vaca/dia; é uma decisão de mercado, não de mínimo custo.
5. **O maior risco é o preço da silagem de milho e do farelo de soja.** A silagem de milho é o principal driver de custo (Sobol ST ≈ {num(results['sobol_cost'].iloc[0]['ST'], 2)}); o farelo de soja vem em seguida. Contratos de silagem e de farelo têm mais alavancagem que a busca por ingredientes exóticos.
6. **O preço do leite domina a margem.** No IOFC, o preço do leite explica cerca de {pct(results['sobol_iofc'].iloc[0]['ST'] * 100)} da variância. A gestão de receita (qualidade, volume, contrato) tem mais impacto que a otimização fina da ração.
7. **Próximos passos:** (a) rodar `full_farm` por 5 anos com a dieta iso e a basal; (b) validar com a dieta real e os preços praticados pela fazenda; (c) incluir escore corporal e saúde ruminal; (d) testar uma restrição de metano ou um preço de carbono; (e) atualizar os preços mensalmente e reotimizar; (f) negociar sorgo, glúten de milho e farelo de algodão, que são os pilares da dieta de mínimo custo.
"""


def _section_entregaveis() -> str:
    return """## 8.1 Entregáveis

| Entregável | Onde está |
|---|---|
| Módulo de otimização (PL, duals, quadro simplex, Sobol, testes pareados) | `diet_optimization/` |
| Dieta integrada ao RuFaS | `GO_campo_dourado/otimizacao_dieta/feed_otimizado.json` + `farm_metadata_otimizado.json` + `_otimizacao_task_manager_metadata.json` |
| Avaliação do efeito econômico | Seção 4.3 e `cenarios.csv` |
| Análise de sensibilidade local | Seção 5.1–5.4, `faixas_rhs.csv`, `faixas_preco.csv`, `break_even.csv`, `sensibilidade_oat.csv` |
| Análise de sensibilidade global (Sobol) | Seção 5.5, `sobol_custo.csv`, `sobol_iofc.csv` |
| Testes pareados | Seção 5.6, `pairwise_cenarios.csv`, `pairwise_break_even.csv` |
| Validação biológica no RuFaS | Seção 4.5 e 6, `validacao_resumo.csv`, `validacao_testes.csv` |
| Relatório | `RELATORIO_OTIMIZACAO_DIETA.md`, `.html`, `.pdf` |
| Testes automatizados | `tests/test_diet_optimization/` (14 testes) |
"""


def _section_referencias() -> str:
    return """## 9. Referências

- CEPEA/ESALQ/USP. **Indicador do milho ESALQ/BM&FBovespa** — 27/10/2026: R$ 64,87/saca de 60 kg. https://www.cepea.org.br/br/indicador/milho.aspx
- CEPEA/ESALQ/USP. **Indicador da soja CEPEA/ESALQ — Paranaguá** — 27/10/2026: R$ 157,41/saca. https://www.cepea.org.br/br/indicador/soja.aspx
- CEPEA/ESALQ/USP. **Leite ao produtor — Goiás** — ago/2026: R$ 2,9692/L. https://www.cepea.org.br/br/indicador/leite.aspx
- Agrolink. **Farelo de soja — Anápolis/GO** — 27/10/2026: R$ 2.020/t. https://www.agrolink.com.br/cotacoes/diversos/farelo-de-soja
- Notícias Agrícolas. **Farelo de soja — cotações** — 27/10/2026. https://www.noticiasagricolas.com.br/cotacoes/soja/farelo-de-soja
- Scot Consultoria / Notícias Agrícolas. **Caroço de algodão e silagem de milho** — out/2026 (cotações regionais).
- National Academies of Sciences, Engineering, and Medicine. **Nutrient Requirements of Dairy Cattle**, 8th ed., 2021.
- National Research Council. **Nutrient Requirements of Dairy Cattle**, 7th ed., 2001.
- Ruminant Farm Systems (RuFaS). **Documentação e código-fonte**, versão 1.0.5. https://github.com/RuminantFarmSystems/RuFaS
- Herman, J., Usher, W. **SALib: An open-source Python library for Sensitivity Analysis**. Journal of Open Source Software, 2017.
- Virtanen, P. et al. **SciPy 1.0: fundamental algorithms for scientific computing in Python**. Nature Methods, 2020.
"""


def _section_apendice(results: dict[str, Any]) -> str:
    return """## 10. Apêndice — leitura do quadro final do simplex

O quadro final completo está em `quadro_simplex.csv`. A linha `custo_reduzido` contém, para cada variável, quanto o custo aumentaria se ela fosse forçada a entrar na base. Para as variáveis fora da dieta, esse valor é o **custo reduzido**: quanto o preço do alimento precisa cair para que ele passe a ser competitivo.

As colunas de folga (`s_*`) mostram o preço sombra das restrições. Quando a folga é zero, a restrição está ativa e o preço sombra é positivo (ou negativo, dependendo do sentido). Quando a folga é positiva, a restrição não está limitando e o preço sombra é zero.

**Como ler o quadro na perspectiva do negócio:**

1. **Coluna RHS:** quantidade de cada variável básica na solução. As variáveis básicas são os alimentos que entram na dieta e as folgas das restrições não ativas.
2. **Linha de custo reduzido:** para um alimento fora da base, é o desconto de preço necessário para ele entrar. Para uma folga, é o preço sombra da restrição correspondente.
3. **Base ótima:** enquanto os preços e as exigências ficarem dentro das faixas calculadas, a composição da dieta não muda; só o custo muda. Isso dá à fazenda uma “zona de segurança” para negociar sem refazer a fórmula.
4. **Preço sombra da energia:** se o nutricionista quiser subir 1 ponto de TDN, o custo sobe aproximadamente o valor indicado. Se o ganho de leite esperado não cobrir esse custo, não vale apertar a energia.
5. **Preço sombra da RUP:** é a restrição mais cara; aumentar a proteína não degradável exige farelo de soja ou outra fonte protegida, e o custo marginal é alto.

**Observação sobre a igualdade de MS.** O dual da igualdade `soma x = DMI` não tem leitura econômica simples neste problema, porque o consumo é fixo e as exigências são proporcionais à MS. Por isso, a análise econômica foca nos preços sombra das restrições nutricionais e de inclusão, que são os instrumentos acionáveis pelo nutricionista.

### Reprodução

```powershell
# Rodar toda a análise (sem validação no RuFaS)
.\\.venv\\Scripts\\python.exe -m diet_optimization --output-dir GO_campo_dourado/otimizacao_dieta

# Rodar com Sobol reduzido (mais rápido)
.\\.venv\\Scripts\\python.exe -m diet_optimization --fast

# Atualizar o resumo das validações já executadas
.\\.venv\\Scripts\\python.exe -m diet_optimization.validation --csv-dir output/CSVs
```
"""


def generate_report(results: dict[str, Any], output_dir: str | Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    save_tables(results, output_dir)

    plot_diet_comparison(results["baseline"], results["scenarios"]["iso_energetico"], output_dir / "fig_dieta.png")
    plot_cost_comparison(results["scenario_table_with_baseline"], output_dir / "fig_custo.png")
    plot_frontier(results["scenario_table_with_baseline"], output_dir / "fig_fronteira.png")
    plot_tornado(results["oat"], output_dir / "fig_tornado.png")
    plot_sobol(results["sobol_cost"], output_dir / "fig_sobol_custo.png", "Sobol — custo da ração")
    plot_sobol(results["sobol_iofc"], output_dir / "fig_sobol_iofc.png", "Sobol — IOFC", "variavel")
    plot_break_even(results["break_even"], output_dir / "fig_break_even.png")
    if not results["validation_summary"].empty:
        plot_validation(results["validation_summary"], output_dir / "fig_validacao.png")

    report = "\n\n".join(
        [
            f"# {results['config']['report']['title']}\n\n"
            f"**Data:** {results['config']['report']['date']}  \n"
            f"**Autor:** {results['config']['report']['author']}  \n"
            f"**Fazenda:** {results['config']['farm']['name']}  \n"
            f"**Modelo:** RuFaS 1.0.5 + módulo de otimização linear",
            _section_resumo(results),
            _section_contexto(results),
            _section_metodo(results),
            _section_resultados(results),
            _section_sensibilidade(results),
            _section_integracao(results),
            _section_limitacoes(results),
            _section_conclusoes(results),
            _section_entregaveis(),
            _section_referencias(),
            _section_apendice(results),
        ]
    )
    report_path = output_dir / "RELATORIO_OTIMIZACAO_DIETA.md"
    report_path.write_text(report, encoding="utf-8")
    html_path = write_html_report(report_path)
    write_pdf_report(html_path)
    return report_path
