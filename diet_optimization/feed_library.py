"""Biblioteca de alimentos: composição NASEM + preços + limites de inclusão."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class Feed:
    """Alimento candidato à ração, em base de matéria seca (MS)."""

    rufas_id: int
    name: str
    group: str
    feed_type: str
    dm_pct: float
    cp_pct: float
    ndf_pct: float
    adf_pct: float
    starch_pct: float
    ee_pct: float
    tdn_pct: float
    ca_pct: float
    p_pct: float
    rup_pct: float
    drup_pct: float
    price_brl_kg_dm: float
    min_pct: float
    max_pct: float
    price_source: str
    price_date: str
    price_basis: str
    price_notes: str

    @property
    def is_forage(self) -> bool:
        return self.feed_type.lower().startswith("forage")

    @property
    def is_mineral(self) -> bool:
        return self.feed_type.lower().startswith("mineral")

    @property
    def digestibility_factor(self) -> float:
        """Fator de digestibilidade aparente usado pelo RuFaS para Ca e P."""
        if self.is_forage:
            return 0.30
        if self.is_mineral:
            return 0.95
        return 0.60

    @property
    def ca_abs_kg_per_kg_dm(self) -> float:
        """Ca absorvível em kg por kg de MS."""
        return self.ca_pct / 100.0 * self.digestibility_factor

    @property
    def p_abs_kg_per_kg_dm(self) -> float:
        """P absorvível em kg por kg de MS."""
        return self.p_pct / 100.0 * self.digestibility_factor

    @property
    def rup_dig_kg_per_kg_dm(self) -> float:
        """Proteína não degradável digestível em kg por kg de MS."""
        return self.cp_pct / 100.0 * self.rup_pct / 100.0 * self.drup_pct / 100.0

    @property
    def nel_mcal_per_kg_dm(self) -> float:
        """Energia líquida de lactação aproximada a partir do TDN (NRC 2001).

        NEl (Mcal/kg MS) = 0,0245 * TDN (%) - 0,12.
        """
        return 0.0245 * self.tdn_pct - 0.12

    def price_usd_kg_dm(self, usd_brl: float) -> float:
        return self.price_brl_kg_dm / usd_brl


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "sim", "yes", "y"}


def load_composition(path: str | Path) -> pd.DataFrame:
    composition = pd.read_csv(path)
    required = {
        "rufas_id",
        "Name",
        "feed_type",
        "DM",
        "CP",
        "NDF",
        "ADF",
        "starch",
        "EE",
        "TDN",
        "calcium",
        "phosphorus",
        "RUP",
        "dRUP",
    }
    missing = required.difference(composition.columns)
    if missing:
        raise ValueError(f"Colunas ausentes em {path}: {sorted(missing)}")
    composition = composition.copy()
    composition["rufas_id"] = composition["rufas_id"].astype(int)
    return composition.set_index("rufas_id", drop=False)


def load_prices(path: str | Path) -> pd.DataFrame:
    prices = pd.read_csv(path)
    required = {"rufas_id", "price_brl_kg", "price_basis", "source", "date"}
    missing = required.difference(prices.columns)
    if missing:
        raise ValueError(f"Colunas ausentes em {path}: {sorted(missing)}")
    prices = prices.copy()
    prices["rufas_id"] = prices["rufas_id"].astype(int)
    prices["price_basis"] = prices["price_basis"].str.strip().str.lower()
    if not prices["price_basis"].isin({"as_fed", "dm"}).all():
        raise ValueError("price_basis deve ser 'as_fed' ou 'dm'.")
    return prices.set_index("rufas_id", drop=False)


def load_candidates(path: str | Path) -> pd.DataFrame:
    candidates = pd.read_csv(path)
    required = {"rufas_id", "min_pct", "max_pct", "include", "group"}
    missing = required.difference(candidates.columns)
    if missing:
        raise ValueError(f"Colunas ausentes em {path}: {sorted(missing)}")
    candidates = candidates.copy()
    candidates["rufas_id"] = candidates["rufas_id"].astype(int)
    candidates["include"] = candidates["include"].map(_as_bool)
    if (candidates["min_pct"] < 0).any():
        raise ValueError("min_pct não pode ser negativo.")
    if (candidates["max_pct"] > 100).any():
        raise ValueError("max_pct não pode ser maior que 100.")
    if (candidates["min_pct"] > candidates["max_pct"]).any():
        raise ValueError("min_pct não pode ser maior que max_pct.")
    return candidates.set_index("rufas_id", drop=False)


def load_feeds(config: dict[str, Any]) -> list[Feed]:
    """Carrega e valida a biblioteca de alimentos candidatos."""
    paths = config["paths"]
    composition = load_composition(paths["composition"])
    prices = load_prices(paths["prices"])
    candidates = load_candidates(paths["candidates"])

    selected = candidates[candidates["include"]].copy()
    if selected.empty:
        raise ValueError("Nenhum alimento candidato habilitado.")

    missing_composition = set(selected.index).difference(composition.index)
    missing_prices = set(selected.index).difference(prices.index)
    if missing_composition:
        raise ValueError(f"Alimentos sem composição: {sorted(missing_composition)}")
    if missing_prices:
        raise ValueError(f"Alimentos sem preço: {sorted(missing_prices)}")

    feeds: list[Feed] = []
    for rufas_id, candidate in selected.iterrows():
        row = composition.loc[rufas_id]
        price = prices.loc[rufas_id]
        dm_pct = float(row["DM"])
        price_brl_kg = float(price["price_brl_kg"])
        if price["price_basis"] == "as_fed":
            price_brl_kg_dm = price_brl_kg / (dm_pct / 100.0)
        else:
            price_brl_kg_dm = price_brl_kg

        feed = Feed(
            rufas_id=int(rufas_id),
            name=str(row["Name"]).strip(),
            group=str(candidate["group"]),
            feed_type=str(row["feed_type"]).strip(),
            dm_pct=dm_pct,
            cp_pct=float(row["CP"]),
            ndf_pct=float(row["NDF"]),
            adf_pct=float(row["ADF"]),
            starch_pct=float(row["starch"]),
            ee_pct=float(row["EE"]),
            tdn_pct=float(row["TDN"]),
            ca_pct=float(row["calcium"]),
            p_pct=float(row["phosphorus"]),
            rup_pct=float(row["RUP"]),
            drup_pct=float(row["dRUP"]),
            price_brl_kg_dm=float(price_brl_kg_dm),
            min_pct=float(candidate["min_pct"]),
            max_pct=float(candidate["max_pct"]),
            price_source=str(price["source"]),
            price_date=str(price["date"]),
            price_basis=str(price["price_basis"]),
            price_notes=str(price.get("notes", "")),
        )
        if feed.max_pct <= 0:
            continue
        feeds.append(feed)

    if not feeds:
        raise ValueError("Nenhum alimento com max_pct > 0.")
    return feeds


def feed_by_id(feeds: list[Feed], rufas_id: int) -> Feed:
    for feed in feeds:
        if feed.rufas_id == int(rufas_id):
            return feed
    raise KeyError(f"Alimento {rufas_id} não encontrado na biblioteca.")
