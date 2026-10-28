import pytest

from diet_optimization.config import load_baseline, load_config, load_scenarios, scenario_items
from diet_optimization.feed_library import load_feeds
from diet_optimization.requirements import build_requirements


@pytest.fixture(scope="module")
def config():
    return load_config()


@pytest.fixture(scope="module")
def feeds(config):
    return load_feeds(config)


@pytest.fixture(scope="module")
def requirements(config):
    return build_requirements(config)


@pytest.fixture(scope="module")
def baseline():
    return load_baseline()


@pytest.fixture(scope="module")
def scenarios():
    return scenario_items(load_scenarios())


def test_feed_library_has_candidates(feeds):
    assert len(feeds) >= 15
    assert all(feed.price_brl_kg_dm > 0 for feed in feeds)
    assert all(0 <= feed.min_pct <= feed.max_pct <= 100 for feed in feeds)


def test_requirement_values(requirements):
    assert requirements.dmi_kg == pytest.approx(25.3, rel=1e-6)
    assert requirements.nel_mcal > 40
    assert requirements.cp_min_pct == pytest.approx(17.5, rel=1e-6)
    assert 70 < requirements.tdn_min_pct < 80


def test_baseline_sums_to_100(baseline):
    assert sum(baseline["rations_pct"].values()) == pytest.approx(100.0)


def test_scenarios_are_well_formed(scenarios):
    assert "iso_energetico" in scenarios
    assert "nasem" in scenarios
    for scenario in scenarios.values():
        assert "overrides" in scenario
