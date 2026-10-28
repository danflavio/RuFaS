"""Leitura e sumarização das validações de dieta executadas no RuFaS."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from scipy.stats import wilcoxon

# Prefixo -> (cenário, seed). A seed 44 foi a primeira execução, sem sufixo.
RUN_MAP: dict[str, tuple[str, int]] = {
    "GO_validacao_baseline": ("baseline", 44),
    "GO_validacao_baseline_s45": ("baseline", 45),
    "GO_validacao_baseline_s46": ("baseline", 46),
    "GO_validacao_iso": ("iso_energetico", 44),
    "GO_validacao_iso_s45": ("iso_energetico", 45),
    "GO_validacao_iso_s46": ("iso_energetico", 46),
    "GO_validacao_nasem_novo": ("nasem", 44),
}


def _read_run(path: Path) -> pd.DataFrame | None:
    prefix = path.name.split("_saved_variables")[0]
    if prefix not in RUN_MAP:
        return None
    cols = pd.read_csv(path, nrows=0).columns.tolist()
    wanted: dict[str, str] = {}
    for col in cols:
        if "report_herd_statistics_data.daily_milk_production" in col:
            wanted["milk"] = col
        elif "report_herd_statistics_data.milking_cow_num" in col:
            wanted["milking"] = col
        elif "ration_per_animal_for_LAC_COW_PEN_3.dry_matter_intake_total" in col:
            wanted["dmi"] = col
        elif "enteric_methane_emission_for_LAC_COW_PEN_3" in col:
            wanted["ch4"] = col
        elif "RufasTime.simulation_day" in col:
            wanted["sim"] = col
    if len(wanted) < 5:
        return None
    df = pd.read_csv(path, usecols=list(wanted.values())).rename(columns={value: key for key, value in wanted.items()})
    df = df.dropna(subset=["sim"])
    if df.empty:
        return None
    return df


def summarize_validation(csv_dir: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Lê os CSVs de validação e devolve (resumo_por_execucao, teste_pareado)."""
    csv_dir = Path(csv_dir)
    rows = []
    daily_by_seed: dict[tuple[str, int], pd.DataFrame] = {}
    for path in sorted(csv_dir.glob("GO_validacao_*_saved_variables*.csv")):
        prefix = path.name.split("_saved_variables")[0]
        if prefix not in RUN_MAP:
            continue
        scenario, seed = RUN_MAP[prefix]
        df = _read_run(path)
        if df is None:
            continue
        daily_by_seed[(scenario, seed)] = df
        milk = float(df["milk"].mean())
        cows = float(df["milking"].mean())
        dmi = float(df["dmi"].mean())
        ch4 = float(df["ch4"].mean())
        rows.append(
            {
                "cenario": scenario,
                "seed": seed,
                "leite_kg_dia": milk,
                "vacas_em_lactacao": cows,
                "leite_kg_vaca_dia": milk / cows,
                "cms_kg_vaca_dia": dmi,
                "metano_kg_dia": ch4 / 1000.0,
                "metano_g_kg_leite": ch4 / milk,
                "dias": len(df),
            }
        )
    summary = pd.DataFrame(rows).sort_values(["cenario", "seed"]).reset_index(drop=True)

    # Teste pareado por seed entre baseline e iso_energetico.
    pairs = []
    seeds = sorted(set(summary.loc[summary["cenario"] == "baseline", "seed"]))
    for seed in seeds:
        base = summary[(summary["cenario"] == "baseline") & (summary["seed"] == seed)]
        iso = summary[(summary["cenario"] == "iso_energetico") & (summary["seed"] == seed)]
        if base.empty or iso.empty:
            continue
        pairs.append(
            {
                "seed": seed,
                "delta_leite_kg_dia": float(iso["leite_kg_dia"].iloc[0] - base["leite_kg_dia"].iloc[0]),
                "delta_leite_pct": float((iso["leite_kg_dia"].iloc[0] / base["leite_kg_dia"].iloc[0] - 1) * 100),
                "delta_cms_kg_dia": float(iso["cms_kg_vaca_dia"].iloc[0] - base["cms_kg_vaca_dia"].iloc[0]),
                "delta_metano_pct": float((iso["metano_kg_dia"].iloc[0] / base["metano_kg_dia"].iloc[0] - 1) * 100),
                "delta_intensidade_pct": float(
                    (iso["metano_g_kg_leite"].iloc[0] / base["metano_g_kg_leite"].iloc[0] - 1) * 100
                ),
            }
        )
    pairwise = pd.DataFrame(pairs)
    if len(pairwise) >= 2:
        test_rows = []
        for metric in ["delta_leite_kg_dia", "delta_cms_kg_dia", "delta_metano_pct", "delta_intensidade_pct"]:
            values = pairwise[metric].to_numpy()
            try:
                _, p_value = wilcoxon(values)
            except ValueError:
                p_value = 1.0
            test_rows.append(
                {
                    "metrica": metric,
                    "media": float(values.mean()),
                    "desvio_padrao": float(values.std(ddof=1)),
                    "n_seeds": len(values),
                    "p_valor_wilcoxon": float(p_value),
                }
            )
        tests = pd.DataFrame(test_rows)
    else:
        tests = pd.DataFrame()
    return summary, tests


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Resumo das validações de dieta no RuFaS")
    parser.add_argument("--csv-dir", default="output/CSVs", help="Diretório dos CSVs do RuFaS")
    parser.add_argument("--output-dir", default="GO_campo_dourado/otimizacao_dieta")
    args = parser.parse_args()
    summary, tests = summarize_validation(args.csv_dir)
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output / "validacao_resumo.csv", index=False, encoding="utf-8-sig")
    if not tests.empty:
        tests.to_csv(output / "validacao_testes.csv", index=False, encoding="utf-8-sig")
    print(summary.to_string(index=False))
    if not tests.empty:
        print()
        print(tests.to_string(index=False))


if __name__ == "__main__":
    main()
