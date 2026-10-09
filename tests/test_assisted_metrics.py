from nirs_cas.assisted_oracle import _metrics, _classes


def test_null_abstention_is_not_correct_first_error():
    predictions = [
        {"id": "a", "verdict": "indeterminate", "first_error_step": None},
        {"id": "b", "verdict": "incorrect", "first_error_step": "s2"},
        {"id": "c", "verdict": "indeterminate", "first_error_step": None},
    ]
    labels = {
        "a": {"verdict": "correct", "first_error_step": None},
        "b": {"verdict": "incorrect", "first_error_step": "s2"},
        "c": {"verdict": "incorrect", "first_error_step": "s3"},
    }
    metrics = _metrics(predictions, labels, [False, False, False])
    assert metrics["verified_solution_coverage"] == 0
    assert metrics["verdict_coverage"] == 1 / 3
    assert metrics["first_error_accuracy"] == 1 / 2
    assert metrics["first_error_accuracy_all"] == 1 / 3
    assert metrics["indeterminate_count"] == 2


def test_class_metrics_keep_task_and_solution_coverage_separate():
    predictions = [
        {
            "verdict": "indeterminate",
            "problem": {
                "context_check": {"status": "valid"},
                "fallback_reasons": ["unsupported edge"],
            },
        },
        {"verdict": "correct", "problem": {"context_check": {"status": "unsupported"}}},
    ]
    classes = _classes(predictions, ["equation", "equation"], [False, True])["equation"]
    assert classes["verified_solution_coverage"] == 1 / 2
    assert classes["task_aware_coverage"] == 1 / 2
    assert classes["indeterminate_reasons"] == {"unsupported edge": 1}
