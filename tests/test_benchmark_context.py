from tmf620.benchmark import build_context_report


def test_context_benchmark_projection_saves_tokens():
    report = build_context_report()

    totals = report["projection_totals"]
    assert totals["saved_tokens"] > 0
    assert totals["projected_tokens"] < totals["full_tokens"]

    for case in report["projection_cases"]:
        assert case["savings"]["tokens"] > 0
        assert case["projected"]["tokens"] < case["full"]["tokens"]


def test_context_benchmark_discovery_progression_is_incremental():
    report = build_context_report()
    discovery = report["discovery_progression"]

    assert discovery["compact_catalog"]["tokens"] > 0
    assert (
        discovery["catalog_plus_group"]["tokens"]
        > discovery["compact_catalog"]["tokens"]
    )
    assert (
        discovery["catalog_plus_group_plus_leaf"]["tokens"]
        > discovery["catalog_plus_group"]["tokens"]
    )


def test_context_benchmark_error_recovery_has_targeted_help_cost():
    report = build_context_report()
    recovery = report["error_recovery"]

    assert recovery["missing_required_argument_error"]["tokens"] > 0
    assert recovery["targeted_help_after_error"]["tokens"] > 0
    assert recovery["combined_tokens"] == (
        recovery["missing_required_argument_error"]["tokens"]
        + recovery["targeted_help_after_error"]["tokens"]
    )


def test_context_benchmark_reports_resource_path_mode():
    report = build_context_report()
    resource_path_mode = report["resource_path_mode"]

    assert resource_path_mode["catalog_entries"] > 0
    assert resource_path_mode["sample_group_help"]["tokens"] > 0
    assert resource_path_mode["sample_leaf_help"]["tokens"] > 0
