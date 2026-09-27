# Synthetic mud-loss training rehearsal

This is an **offline software exercise**, not a validated drilling-risk model. Run from `backend`:

```sh
.venv/bin/python -m nwis.train_mud_loss --demo --out-dir ../data/processed/mud-loss-demo-v1
```

Use a new output directory each time; the command refuses to overwrite an existing artifact. It saves the owned deterministic `DatasetManifest`, a JSON logistic model, and a model card. The training command accepts only `kind: synthetic` and only when `prediction.audit()` finds no blockers beyond `synthetic_only_not_real_validation` and `domain_review_required`. Real/public/private manifests are explicitly refused even if their structural checks pass, because the audit never grants training authorization. All physical wells and sidetracks remain in one split.

The pipeline standardizes each feature using **training** windows only, fits a deterministic L2-regularized logistic classifier on training wells, chooses a threshold from **validation** F1 (preferring fewer alerts on a tie), and evaluates once on untouched test wells. The training prevalence is the computed constant baseline. The card reports ROC-AUC, average precision, Brier score, threshold confusion counts, and descriptive reliability bins for test and baseline where applicable. Reliability bins diagnose score behavior; they do **not** calibrate probabilities. The saved model is not loaded by the API, so `/risk/current` remains `model_not_available`.

The built-in fixture has 12 synthetic physical wells and 24 synthetic windows. Its separable feature pattern and tiny sample are intentionally suitable only for exercising code paths. High scores here would be meaningless as drilling-performance evidence; the card says `trained_on_synthetic_demo_only`, `calibrated: false`, `deployed: false`, `training_authorized: false`, and `operationally_validated: false`. No private or public drilling data is bundled or sent to a model provider.

For a real experiment, first implement and independently verify a permitted source-specific importer for telemetry, mud density and reviewer-adjudicated loss onset/negative coverage. Freeze a well-grouped split and adequacy criteria, then design a separate training authorization process rather than relabeling data or bypassing `prediction.audit()`. Field calibration, event-level lead distance, alert burden and transfer to OIL wells remain unmeasured.
