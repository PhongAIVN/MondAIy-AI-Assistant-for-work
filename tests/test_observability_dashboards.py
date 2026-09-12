"""Contract tĩnh cho narrative Grafana, không cần Grafana chạy để phát hiện drift."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path("observability/grafana/dashboards")
FILES = {
    "overview": ROOT / "p004-overview.json",
    "llm": ROOT / "p004-llm-cost.json",
    "langsmith": ROOT / "p004-langsmith.json",
}
EXPECTED_UIDS = {
    "overview": "p004-production-overview",
    "llm": "p004-llm-cost",
    "langsmith": "p004-langsmith-traces",
}
PROMETHEUS = {"type": "prometheus", "uid": "p004-prometheus"}
GRAFANA_COLOR_MODES = {
    "fixed",
    "shades",
    "thresholds",
    "palette-classic",
    "palette-classic-by-name",
    "continuous-GrYlRd",
    "continuous-RdYlGr",
    "continuous-BlYlRd",
    "continuous-YlRd",
    "continuous-BlPu",
    "continuous-YlBl",
    "continuous-blues",
    "continuous-reds",
    "continuous-greens",
    "continuous-purples",
}


def _dashboard(name: str) -> dict:
    return json.loads(FILES[name].read_text(encoding="utf-8"))


def _panels(dashboard: dict) -> list[dict]:
    def walk(panels: list[dict]) -> list[dict]:
        result: list[dict] = []
        for panel in panels:
            if panel.get("type") == "row":
                result.extend(walk(panel.get("panels") or []))
            else:
                result.append(panel)
        return result

    return walk(dashboard["panels"])


def _expressions(*names: str) -> list[str]:
    return [
        target["expr"]
        for name in names
        for panel in _panels(_dashboard(name))
        for target in panel.get("targets", [])
        if "expr" in target
    ]


def test_dashboard_json_uids_datasources_and_descriptions_are_explicit() -> None:
    dashboards = {name: _dashboard(name) for name in FILES}
    assert {dashboard["uid"] for dashboard in dashboards.values()} == set(EXPECTED_UIDS.values())
    for name in ("overview", "llm"):
        assert dashboards[name]["datasource"] == PROMETHEUS
        for panel in _panels(dashboards[name]):
            assert panel["description"].strip(), panel["title"]
            assert panel.get("datasource") == PROMETHEUS
    for panel in _panels(dashboards["langsmith"]):
        assert panel["description"].strip(), panel["title"]


def test_story_rows_keep_the_presentation_hierarchy() -> None:
    rows = {panel["title"] for name in ("overview", "llm") for panel in _dashboard(name)["panels"] if panel["type"] == "row"}
    assert {
        "Adoption & product outcomes",
        "Conversation quality",
        "Latency & reliability",
        "LLM usage/cost & measurement gaps",
        "Worker health",
        "Data freshness/trust",
    } <= rows


def test_overview_nested_panels_fill_24_columns_without_overlap() -> None:
    dashboard = _dashboard("overview")
    assert dashboard["time"] == {"from": "now-7d", "to": "now"}
    assert dashboard["refresh"] == "5m"
    occupied: list[tuple[int, int, int, int]] = []
    for row in dashboard["panels"]:
        assert row["type"] == "row" and row["collapsed"] is True
        children = row["panels"]
        assert children
        assert all(child["gridPos"]["x"] >= 0 and child["gridPos"]["w"] > 0 for child in children)
        bands: dict[int, list[dict]] = {}
        for child in children:
            bands.setdefault(child["gridPos"]["y"], []).append(child)
        assert all(sum(child["gridPos"]["w"] for child in band) == 24 for band in bands.values())
        for child in children:
            pos = child["gridPos"]
            assert pos["x"] + pos["w"] <= 24
            current = (pos["x"], pos["x"] + pos["w"], pos["y"], pos["y"] + pos["h"])
            assert all(current[1] <= other[0] or other[1] <= current[0] or current[3] <= other[2] or other[3] <= current[2] for other in occupied)
            occupied.append(current)


def test_overview_panel_contract_is_explicit_and_sized_for_scanability() -> None:
    dashboard = _dashboard("overview")
    assert dashboard["uid"] == "p004-production-overview"
    assert dashboard["datasource"] == PROMETHEUS
    stat_titles = {panel["title"] for panel in _panels(dashboard) if panel["type"] == "stat"}
    for panel in _panels(dashboard):
        assert "gridPos" in panel
        assert panel["description"].strip()
        assert panel.get("fieldConfig", {}).get("defaults", {}).get("unit"), panel["title"]
        width = panel["gridPos"]["w"]
        if panel["type"] == "stat":
            assert 4 <= width <= 8, panel["title"]
        elif panel["type"] in {"timeseries", "bargauge"}:
            assert 12 <= width <= 24, panel["title"]
    for panel in _panels(dashboard):
        for target in panel.get("targets", []):
            assert "or vector(0)" not in target.get("expr", "")
    assert stat_titles >= {"Registered users", "Active share · 7d", "Coverage freshness"}


def test_overview_colors_do_not_claim_unsupported_health() -> None:
    raw_counts = {"Registered users"}
    for panel in _panels(_dashboard("overview")):
        defaults = panel.get("fieldConfig", {}).get("defaults", {})
        color = defaults.get("color", {})
        assert color.get("mode") != "value" or color.get("fixedColor") != "red", panel["title"]
        if panel["title"] in raw_counts:
            assert color.get("mode") in GRAFANA_COLOR_MODES, panel["title"]


def test_dashboard_color_modes_are_valid_for_grafana() -> None:
    def colors(value: object) -> list[dict]:
        if isinstance(value, dict):
            found = [value["color"]] if isinstance(value.get("color"), dict) else []
            return found + [item for child in value.values() for item in colors(child)]
        if isinstance(value, list):
            return [item for child in value for item in colors(child)]
        return []

    for name in FILES:
        for color in colors(_dashboard(name)):
            assert color.get("mode") in GRAFANA_COLOR_MODES, (name, color)


def test_ratios_and_freshness_use_the_real_metrics_without_fake_zero() -> None:
    expr = "\n".join(_expressions("overview", "llm"))
    for metric in (
        "p004_product_active_users_7d / p004_product_users_total",
        'p004_product_runs_total{status="succeeded"}',
        "p004_agent_grounding_results_total",
        "p004_agent_guardrail_blocked_turns_total",
        "p004_agent_tool_calls_total",
        "p004_worker_errors_total",
        "p004_worker_ticks_total",
        "p004_worker_processed_total",
        "p004_worker_last_tick_age_seconds",
        "p004_test_coverage_percent",
        "p004_test_coverage_updated_timestamp_seconds",
        "p004_product_rating_last_timestamp_seconds",
        "p004_llm_calls_total",
        "p004_llm_pricing_unknown_total",
    ):
        assert metric in expr
    assert "or vector(0)" not in expr


def test_rates_are_dynamic_tail_aware_and_never_applied_to_snapshot_gauges() -> None:
    expr = _expressions("overview", "llm")
    ranged = [query for query in expr if "rate(" in query or "increase(" in query]
    assert ranged and all("[$__rate_interval]" in query and "[5m]" not in query for query in ranged)
    latency = next(panel for panel in _panels(_dashboard("overview")) if panel["title"] == "HTTP latency · p50 / p90 / p99")
    assert {target["legendFormat"] for target in latency["targets"]} == {"p50", "p90", "p99"}
    assert not any("rate(p004_worker_" in query or "increase(p004_worker_" in query for query in expr)


def test_units_and_privacy_drilldown_are_not_narrative_panels() -> None:
    overview = _panels(_dashboard("overview"))
    units = {panel["title"]: panel["fieldConfig"]["defaults"].get("unit") for panel in overview}
    assert units["Active share · 7d"] == units["HTTP 5xx ratio"] == "percent"
    assert units["HTTP latency · p50 / p90 / p99"] == units["Coverage freshness"] == "s"
    llm_rows = {panel["title"]: panel for panel in _dashboard("llm")["panels"]}
    drilldown = llm_rows["Privacy-safe drilldown"]
    assert drilldown["collapsed"] is True
    assert "user_hash" in "\n".join(target["expr"] for panel in drilldown["panels"] for target in panel["targets"])
    assert all("user_hash" not in "\n".join(target.get("expr", "") for target in panel.get("targets", [])) for panel in llm_rows["LLM usage/cost & measurement gaps"]["panels"])


def test_langsmith_notice_is_static_and_preserves_safe_concurrency() -> None:
    dashboard = _dashboard("langsmith")
    eager = [target for panel in dashboard["panels"] if panel["type"] != "row" for target in panel.get("targets", [])]
    assert len(eager) <= 4
    description = next(panel["description"] for panel in dashboard["panels"] if panel["title"] == "Tổng quan LangSmith trong khoảng thời gian")
    assert "quota" in description and "stale" in description and "start_time" in description
    narrative = [panel for panel in dashboard["panels"] if panel["type"] != "row"]
    sensitive = {"inputs", "outputs", "inputs_preview", "outputs_preview", "messages", "events", "extra", "serialized"}
    for panel in narrative:
        selected = {column["selector"] for target in panel.get("targets", []) for column in target.get("columns", [])}
        if selected & sensitive:
            assert all(
                "$trace_id" in target["url_options"]["data"] or "$run_id" in target["url_options"]["data"]
                for target in panel["targets"]
            )


@pytest.mark.parametrize("name", FILES)
def test_dashboard_file_remains_valid_json(name: str) -> None:
    assert _dashboard(name)["panels"]
