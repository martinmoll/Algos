from datetime import UTC, datetime

from nordpower.publication import assumed_knowledge_time, load_rules


def test_default_rule_for_day_ahead_prices_is_1300_local_on_the_day_before():
    # delivery 16 Jan 2024 12:00 local (11:00 UTC); 13:00 CET on 15 Jan = 12:00 UTC
    kt = assumed_knowledge_time("da_price", datetime(2024, 1, 16, 11, tzinfo=UTC))
    assert kt == datetime(2024, 1, 15, 12, tzinfo=UTC)


def test_the_rule_comes_from_the_config_file(tmp_path):
    cfg = tmp_path / "rules.toml"
    cfg.write_text(
        '[da_price]\nrule = "local_time_on_day_before_delivery"\nlocal_time = "14:15"\n'
        'reviewed = "test"\n',
        encoding="utf-8",
    )
    kt = assumed_knowledge_time(
        "da_price", datetime(2024, 7, 16, 10, tzinfo=UTC), rules=load_rules(cfg)
    )
    assert kt == datetime(2024, 7, 15, 12, 15, tzinfo=UTC)  # 14:15 CEST


def test_every_rule_in_the_config_records_its_review():
    for dataset, rule in load_rules().items():
        assert rule.get("reviewed"), f"{dataset} rule has no review note"
