from diet_optimization.config import load_config, load_scenarios, scenario_items
from diet_optimization.feed_library import load_feeds
from diet_optimization.lp_model import DietLP
from diet_optimization.requirements import build_requirements
from diet_optimization.sensitivity import break_even_table, one_at_a_time_prices


def test_oat_and_break_even():
    config = load_config()
    feeds = load_feeds(config)
    requirements = build_requirements(config)
    model = DietLP(feeds, requirements, config)
    scenario = scenario_items(load_scenarios())["iso_energetico"]
    solution = model.solve_scenario({**scenario, "key": "iso"})

    oat = one_at_a_time_prices(model, solution, [51, 44, 167], pct=10)
    assert len(oat) == 3
    assert oat["amplitude_brl_dia"].notna().all()

    break_even = break_even_table(model, solution)
    assert not break_even.empty
    assert {"preco_atual", "preco_entrada", "status"}.issubset(break_even.columns)
    assert (break_even["preco_atual"] > 0).all()
