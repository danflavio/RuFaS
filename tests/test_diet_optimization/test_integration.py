import json

import pytest

from diet_optimization.config import load_config, load_scenarios, scenario_items
from diet_optimization.feed_library import load_feeds
from diet_optimization.integration import write_feed_config
from diet_optimization.lp_model import DietLP
from diet_optimization.requirements import build_requirements


def test_write_feed_config(tmp_path):
    config = load_config()
    feeds = load_feeds(config)
    requirements = build_requirements(config)
    model = DietLP(feeds, requirements, config)
    scenario = scenario_items(load_scenarios())["iso_energetico"]
    solution = model.solve_scenario({**scenario, "key": "iso"})

    output = tmp_path / "feed_otimizado.json"
    write_feed_config(
        config["paths"]["rufas_feed_config"],
        solution,
        output,
        config["farm"]["usd_brl"],
    )
    data = json.loads(output.read_text(encoding="utf-8"))
    ration = next(r for r in data["rations"] if r["animal_combination"] == "lac_cow")
    percentages = [feed["ration_percentage"] for feed in ration["feeds"]]
    assert sum(percentages) == pytest.approx(100.0, abs=1e-4)
    ids_defined = {int(feed["feed_type"]) for feed in data["feeds"]}
    assert {int(feed["feed_type"]) for feed in ration["feeds"]}.issubset(ids_defined)
    assert 154 in ids_defined  # sorgo
