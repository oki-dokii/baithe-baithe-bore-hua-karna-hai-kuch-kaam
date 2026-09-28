"""Offline synthetic-only training rehearsal for the v1 mud-loss window contract.

The output is never loaded by the API and is never an operational model.
"""

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

from pydantic import ValidationError

from nwis.prediction import DatasetManifest, FEATURES, Window, audit

DEMO_BLOCKERS = {"synthetic_only_not_real_validation", "domain_review_required"}
STATE = "trained_on_synthetic_demo_only"


class TrainingRefused(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def sigmoid(value: float) -> float:
    if value >= 0:
        inverse = math.exp(-min(value, 700))
        return 1 / (1 + inverse)
    exponential = math.exp(max(value, -700))
    return exponential / (1 + exponential)


def rows(manifest: DatasetManifest, split: str) -> list[Window]:
    return [window for window in manifest.windows if window.split == split]


def matrix(windows: list[Window]) -> tuple[list[list[float]], list[int]]:
    return [[window.features[name] for name in FEATURES] for window in windows], [
        window.label for window in windows
    ]


def standardizer(values: list[list[float]]) -> tuple[list[float], list[float]]:
    size = len(values)
    means = [sum(row[column] for row in values) / size for column in range(len(FEATURES))]
    scales = [
        max(math.sqrt(sum((row[column] - means[column]) ** 2 for row in values) / size), 1e-9)
        for column in range(len(FEATURES))
    ]
    return means, scales


def transformed(values: list[list[float]], means: list[float], scales: list[float]):
    return [
        [(value - means[column]) / scales[column] for column, value in enumerate(row)]
        for row in values
    ]


def fit_logistic(values: list[list[float]], labels: list[int]) -> tuple[list[float], float]:
    """Deterministic, small-data logistic software baseline; no external estimator state."""
    rate = sum(labels) / len(labels)
    if rate <= 0 or rate >= 1:
        raise TrainingRefused("train_has_one_class")
    weights = [0.0] * len(FEATURES)
    intercept = math.log(rate / (1 - rate))
    for _ in range(1200):
        probabilities = [
            sigmoid(intercept + sum(weight * value for weight, value in zip(weights, row)))
            for row in values
        ]
        errors = [probability - label for probability, label in zip(probabilities, labels)]
        intercept -= 0.05 * sum(errors) / len(labels)
        weights = [
            weight
            - 0.05
            * (
                sum(error * row[column] for error, row in zip(errors, values)) / len(labels)
                + 0.02 * weight
            )
            for column, weight in enumerate(weights)
        ]
    return weights, intercept


def predict(values: list[list[float]], weights: list[float], intercept: float) -> list[float]:
    return [
        sigmoid(intercept + sum(weight * value for weight, value in zip(weights, row)))
        for row in values
    ]


def roc_auc(labels: list[int], scores: list[float]) -> float:
    positives = sum(labels)
    negatives = len(labels) - positives
    if not positives or not negatives:
        raise TrainingRefused("evaluation_has_one_class")
    ranked = sorted(zip(scores, labels), key=lambda item: item[0])
    positive_rank_sum = 0.0
    rank = 1
    index = 0
    while index < len(ranked):
        end = index + 1
        while end < len(ranked) and ranked[end][0] == ranked[index][0]:
            end += 1
        average_rank = (rank + rank + end - index - 1) / 2
        positive_rank_sum += average_rank * sum(label for _, label in ranked[index:end])
        rank += end - index
        index = end
    return (positive_rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def average_precision(labels: list[int], scores: list[float]) -> float:
    positives = sum(labels)
    if not positives:
        raise TrainingRefused("evaluation_has_no_positives")
    ordered = sorted(zip(scores, labels), key=lambda item: item[0], reverse=True)
    found = 0
    total = 0.0
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][0] == ordered[index][0]:
            end += 1
        group_positives = sum(label for _, label in ordered[index:end])
        found += group_positives
        total += group_positives * found / end
        index = end
    return total / positives


def brier(labels: list[int], scores: list[float]) -> float:
    return sum((score - label) ** 2 for label, score in zip(labels, scores)) / len(labels)


def confusion(labels: list[int], scores: list[float], threshold: float) -> dict:
    counts = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    for label, score in zip(labels, scores):
        predicted = score >= threshold
        counts[("t" if predicted == bool(label) else "f") + ("p" if predicted else "n")] += 1
    precision = counts["tp"] / (counts["tp"] + counts["fp"]) if counts["tp"] + counts["fp"] else 0
    recall = counts["tp"] / (counts["tp"] + counts["fn"]) if counts["tp"] + counts["fn"] else 0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
    return {**counts, "precision": precision, "recall": recall, "f1": f1}


def choose_threshold(labels: list[int], scores: list[float]) -> float:
    candidates = sorted(set(scores) | {0.5})
    return max(
        candidates, key=lambda threshold: (confusion(labels, scores, threshold)["f1"], threshold)
    )


def reliability_bins(labels: list[int], scores: list[float], bins: int = 5) -> list[dict]:
    """Descriptive quantile bins. They do not calibrate the fitted model."""
    ordered = sorted(zip(scores, labels))
    result = []
    for number in range(min(bins, len(labels))):
        start = number * len(labels) // min(bins, len(labels))
        end = (number + 1) * len(labels) // min(bins, len(labels))
        group = ordered[start:end]
        if group:
            result.append(
                {
                    "n": len(group),
                    "mean_score": sum(s for s, _ in group) / len(group),
                    "event_fraction": sum(y for _, y in group) / len(group),
                }
            )
    return result


def split_digest(windows: list[Window]) -> str:
    ids = "\n".join(sorted(window.sample_id for window in windows))
    return hashlib.sha256(ids.encode()).hexdigest()


def train(manifest: DatasetManifest) -> tuple[dict, dict]:
    report = audit(manifest)
    if manifest.kind != "synthetic":
        raise TrainingRefused("real_training_not_authorized")
    unexpected = set(report["blockers"]) - DEMO_BLOCKERS
    if unexpected:
        raise TrainingRefused("manifest_fails_software_structure_gate")
    return fit_baseline(manifest, report, state=STATE, training_authorized=False)


def fit_baseline(
    manifest: DatasetManifest, report: dict, *, state: str,
    training_authorized: bool, approval_id: str | None = None,
) -> tuple[dict, dict]:
    """Shared deterministic evaluator; caller must enforce its own data-use gate."""
    partitions = {name: rows(manifest, name) for name in ("train", "validation", "test")}
    x_train, y_train = matrix(partitions["train"])
    means, scales = standardizer(x_train)
    weights, intercept = fit_logistic(transformed(x_train, means, scales), y_train)
    x_validation, y_validation = matrix(partitions["validation"])
    validation_scores = predict(transformed(x_validation, means, scales), weights, intercept)
    threshold = choose_threshold(y_validation, validation_scores)
    x_test, y_test = matrix(partitions["test"])
    test_scores = predict(transformed(x_test, means, scales), weights, intercept)
    prevalence = sum(y_train) / len(y_train)
    baseline = [prevalence] * len(y_test)
    artifact = {
        "schema_version": "mud-loss-logistic-experiment-v1" if approval_id else "mud-loss-logistic-demo-v1",
        "state": state,
        "algorithm": "standardized_l2_logistic_batch_gradient_descent",
        "fit_parameters": {"iterations": 1200, "learning_rate": 0.05, "l2": 0.02},
        "feature_schema": "mud-loss-features-v1",
        "features": list(FEATURES),
        "means": means,
        "scales": scales,
        "weights": weights,
        "intercept": intercept,
        "threshold": threshold,
        "manifest_sha256": report["manifest_sha256"],
        "source_sha256": manifest.source_sha256,
        "approval_id": approval_id,
        "split_sample_id_sha256": {name: split_digest(items) for name, items in partitions.items()},
    }
    card = {
        "state": state,
        "model_family": "logistic_software_baseline",
        "hazard": "mud_loss",
        "horizon_m": 100,
        "source_kind": manifest.kind,
        "manifest_sha256": report["manifest_sha256"],
        "training_authorized": training_authorized,
        "operationally_validated": False,
        "deployed": False,
        "calibrated": False,
        "audit_blockers": report["blockers"],
        "partitions": report["partitions"],
        "threshold_selected_on": "validation_f1_then_fewer_alerts",
        "validation": {
            "brier": brier(y_validation, validation_scores),
            "reliability_bins": reliability_bins(y_validation, validation_scores),
        },
        "test": {
            "model_roc_auc": roc_auc(y_test, test_scores),
            "prevalence_roc_auc": roc_auc(y_test, baseline),
            "model_average_precision": average_precision(y_test, test_scores),
            "prevalence_average_precision": average_precision(y_test, baseline),
            "model_brier": brier(y_test, test_scores),
            "prevalence_brier": brier(y_test, baseline),
            "confusion_at_validation_threshold": confusion(y_test, test_scores, threshold),
            "reliability_bins": reliability_bins(y_test, test_scores),
        },
        "limitations": [
            ("Offline approved-source experiment, not an OIL field validation" if approval_id
             else "Owned synthetic software test, not a real drilling validation"),
            "Tiny windows and repeated samples cannot establish event-level lead time or field alert burden",
            "Reliability bins diagnose scores but do not calibrate them",
            "No trained artifact is loaded by /risk/current or /prediction/readiness",
        ],
    }
    return artifact, card


def demo_manifest() -> DatasetManifest:
    """Deterministic toy data with physical-well-disjoint partitions."""
    windows = []
    for split_index, split in enumerate(("train", "validation", "test")):
        for well_index in range(4):
            well = f"owned-synthetic-{split}-{well_index}"
            for positive in (False, True):
                anchor_md = 1000 if positive else 1300
                jitter = 0.2 * well_index + 0.1 * split_index
                windows.append(
                    Window(
                        sample_id=f"{well}-{'positive' if positive else 'negative'}",
                        physical_well_id=well,
                        wellbore_id=f"{well}-main",
                        split=split,
                        anchor_md_m=anchor_md,
                        feature_end_md_m=anchor_md,
                        observed_through_md_m=anchor_md + 100,
                        next_loss_md_m=anchor_md + 50 if positive else None,
                        label_reviewed=True,
                        label_source="owned_synthetic_software_fixture",
                        features={
                            "rop_m_per_h": 8 + jitter + (2 if positive else 0),
                            "wob_kn": 35 + jitter + (5 if positive else 0),
                            "rpm": 90 + jitter,
                            "torque_kn_m": 7 + jitter + (3 if positive else 0),
                            "flow_in_l_per_min": 1000 + 10 * jitter,
                            "mud_density_kg_per_m3": 1200 + 2 * jitter,
                        },
                    )
                )
    return DatasetManifest(
        schema_version="mud-loss-windows-v1",
        kind="synthetic",
        source_reference="owned deterministic synthetic software fixture",
        source_sha256=hashlib.sha256(b"nwis-owned-synthetic-ml-demo-v1").hexdigest(),
        permission_reference="owned synthetic fixture",
        domain_reviewed=False,
        windows=windows,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline synthetic-only ML software rehearsal")
    parser.add_argument("manifest", type=Path, nargs="?", help="Prepared Window manifest")
    parser.add_argument(
        "--demo", action="store_true", help="Use owned deterministic synthetic windows"
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="Explicit local directory for demo artifact and model card",
    )
    args = parser.parse_args()
    if args.demo == (args.manifest is not None):
        parser.error("Provide exactly one of a manifest path or --demo")
    try:
        manifest = (
            demo_manifest()
            if args.demo
            else DatasetManifest.model_validate_json(args.manifest.read_text())
        )
        artifact, card = train(manifest)
    except (TrainingRefused, ValidationError) as exc:
        code = exc.code if isinstance(exc, TrainingRefused) else "manifest_schema_invalid"
        print(json.dumps({"error_code": code, "training_authorized": False}), file=sys.stderr)
        raise SystemExit(2) from None
    outputs = [args.out_dir / "synthetic-model.json", args.out_dir / "synthetic-model-card.json"]
    if args.demo:
        outputs.append(args.out_dir / "synthetic-manifest.json")
    if any(path.exists() for path in outputs):
        print(
            json.dumps({"error_code": "output_exists", "training_authorized": False}),
            file=sys.stderr,
        )
        raise SystemExit(2)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    if args.demo:
        (args.out_dir / "synthetic-manifest.json").write_text(manifest.model_dump_json(indent=2))
    (args.out_dir / "synthetic-model.json").write_text(json.dumps(artifact, indent=2))
    (args.out_dir / "synthetic-model-card.json").write_text(json.dumps(card, indent=2))
    print(
        json.dumps(
            {
                "state": STATE,
                "partitions": card["partitions"],
                "training_authorized": False,
                "deployed": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
