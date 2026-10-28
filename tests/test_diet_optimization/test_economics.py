import pytest

from diet_optimization.config import load_baseline, load_config, load_scenarios, scenario_items
from diet_optimization.economics import compare, economics, mineral_decomposition
from diet_optimization.feed_library import load_feeds
from diet_optimization.lp_model import DietLP, fixed_diet_solution
from diet_optimization.requirements import build_requirements


@pytest.fixture(scope="module")
def setup():
    config = load_config()
    feeds = load_feeds(config)
    requirements = build_requirements(config)
    baseline_data = load_baseline()
    farm = dict(config["farm"])
    farm["milk_kg_cow_day"] = baseline_data["milk_kg_cow_day"]
    baseline = fixed_diet_solution(feeds, baseline_data["rations_pct"], requirements, "baseline")
    model = DietLP(feeds, requirements, config)
    scenario = scenario_items(load_scenarios())["iso_energetico"]
    optimized = model.solve_scenario({**scenario, "key": "iso"})
    return baseline, optimized, farm


def test_baseline_cost(setup):
    baseline, _, _ = setup
    assert baseline.cost_brl_cow_day == pytest.approx(32.17, abs=0.1)


def test_savings_are_positive(setup):
    baseline, optimized, farm = setup
    comparison = compare(baseline, optimized, farm)
    assert comparison["economia_brl_vaca_dia"] > 0
    assert comparison["economia_pct"] > 5
    assert comparison["economia_anual_brl"] > 0


def test_iofc_improves(setup):
    baseline, optimized, farm = setup
    base = economics(baseline, farm)
    opt = economics(optimized, farm)
    assert opt["iofc_brl_vaca_dia"] > base["iofc_brl_vaca_dia"]


def test_mineral_decomposition(setup):
    baseline, optimized, _ = setup
    decomposition = mineral_decomposition(baseline, optimized)
    assert decomposition["economia_total_brl_dia"] > 0
    assert 0 <= decomposition["participacao_mineral_pct"] <= 100
