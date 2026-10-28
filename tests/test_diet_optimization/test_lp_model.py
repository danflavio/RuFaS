import pytest

from diet_optimization.config import load_config, load_scenarios, scenario_items
from diet_optimization.feed_library import load_feeds
from diet_optimization.lp_model import DietLP
from diet_optimization.requirements import build_requirements
from diet_optimization.tableau import build_tableau


@pytest.fixture(scope="module")
def setup():
    config = load_config()
    feeds = load_feeds(config)
    requirements = build_requirements(config)
    scenarios = scenario_items(load_scenarios())
    scenario = scenarios["iso_energetico"]
    model = DietLP(feeds, requirements, config)
    solution = model.solve_scenario({**scenario, "key": "iso"})
    return model, solution


def test_solution_is_feasible(setup):
    model, solution = setup
    assert solution.status == 0
    assert solution.x_kg_dm.sum() == pytest.approx(solution.dmi_kg, rel=1e-8)
    assert (solution.x_kg_dm >= -1e-9).all()
    supply = solution.nutrient_supply
    assert supply["cp_pct"] >= solution.requirements.cp_min_pct - 1e-6
    assert supply["ndf_pct"] >= solution.requirements.ndf_min_pct - 1e-6
    assert supply["tdn_pct"] >= solution.requirements.tdn_min_pct - 1e-6
    assert supply["ca_abs_g"] >= solution.requirements.ca_abs_g - 1e-6
    assert supply["p_abs_g"] >= solution.requirements.p_abs_g - 1e-6
    assert supply["rup_dig_kg"] >= solution.requirements.rup_min_kg - 1e-6


def test_cost_is_in_expected_range(setup):
    _, solution = setup
    assert 24.0 < solution.cost_brl_cow_day < 30.0


def test_reduced_costs_are_nonnegative(setup):
    _, solution = setup
    for value in solution.reduced_costs.values():
        assert value >= -1e-5


def test_tableau_matches_solution(setup):
    model, solution = setup
    tableau = build_tableau(model.feeds, solution.constraints, solution.x_kg_dm, solution.dmi_kg)
    assert tableau.objective == pytest.approx(solution.cost_brl_cow_day, rel=1e-6)
    assert len(tableau.basis) == len(solution.constraints) + 1
    assert tableau.reduced_costs.min() >= -1e-5
