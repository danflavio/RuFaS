"""Requisitos nutricionais da vaca em lactação (NASEM + restrições práticas)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from RUFAS.biophysical.animal.data_types.animal_types import AnimalType
from RUFAS.biophysical.animal.nutrients.nasem_requirements_calculator import (
    NASEMRequirementsCalculator,
)


@dataclass(frozen=True)
class NasemRequirements:
    maintenance_energy_mcal: float
    growth_energy_mcal: float
    pregnancy_energy_mcal: float
    lactation_energy_mcal: float
    activity_energy_mcal: float
    metabolizable_protein_g: float
    calcium_g: float
    phosphorus_g: float
    dry_matter_kg: float

    @property
    def net_energy_mcal(self) -> float:
        return (
            self.maintenance_energy_mcal
            + self.growth_energy_mcal
            + self.pregnancy_energy_mcal
            + self.lactation_energy_mcal
            + self.activity_energy_mcal
        )


@dataclass(frozen=True)
class Requirements:
    """Restrições nutricionais usadas no problema de programação linear."""

    dmi_kg: float
    nel_mcal: float
    mp_g: float
    ca_abs_g: float
    p_abs_g: float
    cp_min_pct: float
    tdn_min_pct: float
    ndf_min_pct: float
    ndf_max_pct: float
    forage_ndf_min_pct: float
    starch_min_pct: float
    starch_max_pct: float
    ee_min_pct: float
    ee_max_pct: float
    ca_total_min_pct: float
    ca_p_min: float
    ca_p_max: float
    rup_min_kg: float
    nasem: NasemRequirements

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["nasem"]["net_energy_mcal"] = self.nasem.net_energy_mcal
        return data


def compute_nasem_requirements(cow: dict[str, Any]) -> NasemRequirements:
    """Chama o calculador NASEM do próprio RuFaS."""
    animal_type = AnimalType[cow.get("animal_type", "LAC_COW")]
    result = NASEMRequirementsCalculator.calculate_requirements(
        body_weight=float(cow["body_weight_kg"]),
        mature_body_weight=float(cow["mature_body_weight_kg"]),
        day_of_pregnancy=cow.get("day_of_pregnancy"),
        body_condition_score_5=float(cow["body_condition_score_5"]),
        days_in_milk=int(cow["days_in_milk"]),
        average_daily_gain_heifer=float(cow["average_daily_gain_heifer_g"]),
        animal_type=animal_type,
        parity=int(cow["parity"]),
        calving_interval=int(cow["calving_interval_days"]),
        milk_fat=float(cow["milk_fat_pct"]),
        milk_true_protein=float(cow["milk_true_protein_pct"]),
        milk_lactose=float(cow["milk_lactose_pct"]),
        milk_production=float(cow["milk_production_kg"]),
        housing=str(cow["housing"]),
        distance=float(cow["distance_m"]),
        lactating=bool(cow["lactating"]),
        ndf_percentage=float(cow["ndf_percentage"]),
        process_based_phosphorus_requirement=float(
            cow.get("process_based_phosphorus_requirement", 0.0)
        ),
    )
    return NasemRequirements(
        maintenance_energy_mcal=result.maintenance_energy,
        growth_energy_mcal=result.growth_energy,
        pregnancy_energy_mcal=result.pregnancy_energy,
        lactation_energy_mcal=result.lactation_energy,
        activity_energy_mcal=result.activity_energy,
        metabolizable_protein_g=result.metabolizable_protein,
        calcium_g=result.calcium,
        phosphorus_g=result.phosphorus,
        dry_matter_kg=result.dry_matter,
    )


def tdn_min_pct_from_energy(nel_mcal: float, dmi_kg: float) -> float:
    """Converte a exigência de NEl em TDN mínimo (% da MS).

    Usa a relação inversa de NRC (2001): NEl = 0,0245 * TDN - 0,12.
    """
    if dmi_kg <= 0:
        raise ValueError("DMI deve ser positiva.")
    nel_density = nel_mcal / dmi_kg
    return (nel_density + 0.12) / 0.0245


def build_requirements(config: dict[str, Any]) -> Requirements:
    """Combina a exigência NASEM com as restrições práticas de formulação."""
    cow = config["cow"]
    practical = config["requirements"]
    nasem = compute_nasem_requirements(cow)

    dmi = float(practical.get("dmi_kg") or nasem.dry_matter_kg)
    cp_from_mp = (
        nasem.metabolizable_protein_g
        / float(practical["cp_mp_conversion"])
        / dmi
        * 100.0
        * float(practical["cp_safety_factor"])
    )
    cp_min = max(float(practical["cp_min_pct"]), cp_from_mp)
    tdn_override = practical.get("tdn_min_pct")
    tdn_min = (
        float(tdn_override)
        if tdn_override is not None
        else tdn_min_pct_from_energy(nasem.net_energy_mcal, dmi)
    )

    return Requirements(
        dmi_kg=dmi,
        nel_mcal=nasem.net_energy_mcal,
        mp_g=nasem.metabolizable_protein_g,
        ca_abs_g=nasem.calcium_g,
        p_abs_g=nasem.phosphorus_g,
        cp_min_pct=cp_min,
        tdn_min_pct=tdn_min,
        ndf_min_pct=float(practical["ndf_min_pct"]),
        ndf_max_pct=float(practical["ndf_max_pct"]),
        forage_ndf_min_pct=float(practical["forage_ndf_min_pct"]),
        starch_min_pct=float(practical["starch_min_pct"]),
        starch_max_pct=float(practical["starch_max_pct"]),
        ee_min_pct=float(practical["ee_min_pct"]),
        ee_max_pct=float(practical["ee_max_pct"]),
        ca_total_min_pct=float(practical["ca_total_min_pct"]),
        ca_p_min=float(practical["ca_p_min"]),
        ca_p_max=float(practical["ca_p_max"]),
        rup_min_kg=float(practical["rup_min_kg"]),
        nasem=nasem,
    )


def apply_requirement_overrides(
    requirements: Requirements, overrides: dict[str, Any] | None
) -> Requirements:
    """Aplica overrides de cenário sem alterar o objeto original."""
    if not overrides:
        return requirements
    data = asdict(requirements)
    nasem_data = data.pop("nasem")
    for key, value in overrides.items():
        if key not in data:
            raise KeyError(f"Override de requisito desconhecido: {key}")
        if key == "tdn_min_pct" and value is None:
            value = tdn_min_pct_from_energy(requirements.nel_mcal, requirements.dmi_kg)
        data[key] = float(value)
    nasem = NasemRequirements(**nasem_data)
    return Requirements(**data, nasem=nasem)
