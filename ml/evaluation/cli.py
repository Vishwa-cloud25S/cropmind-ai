"""Evaluation report CLI (Phase 4 — docs/05-ml-pipeline §4).

    python -m ml.evaluation.cli report --run-dir runs/<run_id> --device cpu

Auto-discovers everything from the run directory: checkpoint.pt, metrics.json
(training-reported top-1), config.yaml copy (split location). PlantDoc OOD runs
automatically when data/raw/plantdoc/PROVENANCE.json exists; otherwise the report
says NOT_RUN with the exact fetch command — gates are measured, never assumed.
"""

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

from ml.evaluation import core, report, runner
from ml.inference.predictor import Predictor

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO_ROOT / "reports" / "model_evaluation"
PLANTDOC_PROV = REPO_ROOT / "data" / "raw" / "plantdoc" / "PROVENANCE.json"

logger = logging.getLogger("cropmind.ml.evaluation")


def _resolve(path_str: str, base: Path) -> Path:
    path = Path(path_str)
    return path if path.is_absolute() else base / path


def _build_ctx(
    *,
    run_dir: Path,
    predictor: Predictor,
    records_id: list[dict],
    manifest: dict,
    records_ood: list[dict] | None,
    ood_meta: dict | None,
    exemplar_captions: list[dict],
    device: str,
    reproduce: str,
) -> dict:
    classes = predictor.classes
    cm_id = core.confusion_matrix(records_id, classes)
    ind_metrics = core.per_class_metrics(cm_id, classes)
    latency = core.latency_stats([r["latency_ms"] for r in records_id])
    cm_ood = core.confusion_matrix(records_ood, classes) if records_ood is not None else None
    ood_metrics = core.per_class_metrics(cm_ood, classes) if cm_ood is not None else None

    training = json.loads((Path(run_dir) / "metrics.json").read_text(encoding="utf-8"))
    training_top1 = (training.get("test") or {}).get("top1")
    drift = abs(ind_metrics["top1"] - training_top1) if training_top1 is not None else None

    ood_block = None
    if records_ood is not None:
        covered = sorted({r["ground_truth"] for r in records_ood})
        ood_block = {
            "top1": ood_metrics["top1"],
            "images": ood_metrics["images"],
            "coverage": f"{len(covered)}/{len(classes)}",
            "skipped_folders": (ood_meta or {}).get("skipped_folders", {}),
            "per_class": {c: m for c, m in ood_metrics["per_class"].items() if c in covered},
            "bands": core.band_histogram(records_ood),
            "latency": core.latency_stats([r["latency_ms"] for r in records_ood]),
        }
    gates = core.evaluate_gates(
        eval_top1=ind_metrics["top1"],
        training_top1=training_top1,
        latency=latency,
        device=device,
        ood=ood_block,
    )
    if exemplar_captions:
        lines = []
        for cap in exemplar_captions:
            verdict = "WRONG" if cap["ground_truth"] != cap["predicted"] else cap["status"]
            img = f"![orig]({cap['original']})"
            cam = f" ![cam]({cap['gradcam_overlay']})" if cap["gradcam_overlay"] else ""
            lines.append(
                f"{cap['index'] + 1}. GT `{cap['ground_truth']}` → predicted `{cap['predicted']}` "
                f"({cap['confidence'] * 100:.0f}%) — {verdict} {img}{cam}"
            )
        exemplars_note = "\n".join(lines) + "\n\n(Heatmaps are correlation, not proof of lesion location.)"
    else:
        exemplars_note = "No misclassifications and no INCONCLUSIVE samples on this split (recorded honestly)."
    support = core.support_evaluation(ind_metrics["per_class"])
    summary = {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "run_dir": str(run_dir),
        "checkpoint_sha256": (Path(run_dir) / "checkpoint.sha256").read_text(encoding="utf-8").strip(),
        "model_version": predictor.meta.get("model_version"),
        "device": device,
        "dataset": {
            "id": "plantvillage",
            "split": "test",
            "splits_content_sha256": manifest.get("content_sha256"),
            "images": ind_metrics["images"],
        },
        "in_domain": {
            "top1": ind_metrics["top1"],
            "training_reported_top1": training_top1,
            "drift_vs_training": round(drift, 6) if drift is not None else None,
            "per_class": ind_metrics["per_class"],
            "bands": core.band_histogram(records_id),
            "uncertainty_mean": core.uncertainty_mean(records_id),
            "confusions": core.top_confusions(cm_id, classes),
            "latency": latency,
        },
        "ood": ood_block,
        "gates": gates,
        "supported_rule": {"f1_min": core.SUPPORT_F1_MIN, "support_min": core.SUPPORT_MIN},
        "supported_eligible": support["eligible"],
        "watchlist": support["watchlist"],
        "exemplars": exemplar_captions,
    }
    ctx = {
        "generated_utc": summary["generated_utc"],
        "run_dir": str(run_dir),
        "model_version": predictor.meta.get("model_version"),
        "device": device,
        "checkpoint_sha256": summary["checkpoint_sha256"],
        "dataset": summary["dataset"],
        "training_top1": training_top1,
        "classes": classes,
        "in_domain": {
            **ind_metrics,
            "drift": drift or 0.0,
            "bands": summary["in_domain"]["bands"],
            "uncertainty_mean": summary["in_domain"]["uncertainty_mean"],
            "confusions": summary["in_domain"]["confusions"],
            "latency": latency,
        },
        "ood": ood_block,
        "gates": gates,
        "exemplars_note": exemplars_note,
        "reproduce_command": reproduce,
        "summary": summary,
    }
    return ctx


def cmd_report(args) -> int:
    run_dir = Path(args.run_dir).resolve()
    for name in ("checkpoint.pt", "metrics.json", "config.yaml"):
        if not (run_dir / name).exists():
            print(f"run directory missing {name}: {run_dir}", file=sys.stderr)
            return 2
    device = "cpu" if args.device == "cpu" else args.device
    cfg = yaml.safe_load((run_dir / "config.yaml").read_text(encoding="utf-8"))
    splits_dir = _resolve(cfg["data"]["splits_dir"], REPO_ROOT)
    predictor = Predictor(run_dir / "checkpoint.pt", device=device)
    classes = predictor.classes  # canonical order baked into the checkpoint head

    items_id, manifest = runner.in_domain_items(splits_dir)
    records_id = runner.evaluate_items(predictor, items_id, desc="in-domain", limit=args.max_images)

    records_ood, ood_meta = None, None
    ood_cm_path = None
    if not args.no_ood:
        if PLANTDOC_PROV.exists():
            prov = json.loads(PLANTDOC_PROV.read_text(encoding="utf-8"))
            images_root = _resolve(prov["images_root"], PLANTDOC_PROV.parent)
            if images_root.is_absolute() and images_root.exists():
                items_ood, skipped = runner.ood_items(images_root, "plantdoc")
                ood_meta = {"skipped_folders": skipped, "provenance": "data/raw/plantdoc/PROVENANCE.json"}
                records_ood = runner.evaluate_items(predictor, items_ood, desc="ood", limit=args.max_images)
            else:
                logger.warning("plantdoc provenance found but images root missing: %s", images_root)
        else:
            logger.info("plantdoc not present — OOD section will be NOT_RUN (see report)")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    cm_id = core.confusion_matrix(records_id, classes)
    report.render_confusion_png(cm_id, classes, out_dir / "confusion_in_domain.png", "in-domain (rows gt, cols pred)")
    if records_ood is not None:
        cm_ood = core.confusion_matrix(records_ood, classes)
        ood_cm_path = out_dir / "confusion_ood.png"
        report.render_confusion_png(cm_ood, classes, ood_cm_path, "OOD PlantDoc (rows gt, cols pred)")

    picked = runner.select_exemplars(records_id, args.num_exemplars)
    captions = report.materialize_exemplars(predictor, picked, out_dir / "exemplars")

    reproduce = f"python -m ml.evaluation.cli report --run-dir {run_dir.name} --device {device}" + (" --no-ood" if args.no_ood else "")
    ctx = _build_ctx(
        run_dir=run_dir,
        predictor=predictor,
        records_id=records_id,
        manifest=manifest,
        records_ood=records_ood,
        ood_meta=ood_meta,
        exemplar_captions=captions,
        device=device,
        reproduce=reproduce,
    )
    paths = report.write_report(out_dir, ctx)
    print(f"report: {paths['report_md']}")
    for gate in ctx["gates"]:
        print(f"  gate {gate['id']}: {gate['status']} (measured: {gate['measured']})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ml.evaluation.cli", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    rep = sub.add_parser("report", help="generate the full evaluation report for a training run")
    rep.add_argument("--run-dir", type=Path, required=True)
    rep.add_argument("--device", default="cpu", choices=["cpu", "cuda", "auto"],
                     help="evaluation device; M1 latency gate measured on cpu (default)")
    rep.add_argument("--out", type=Path, default=DEFAULT_OUT)
    rep.add_argument("--max-images", type=int, default=None, help="debug cap per split (full split by default)")
    rep.add_argument("--num-exemplars", type=int, default=12)
    rep.add_argument("--no-ood", action="store_true", help="skip PlantDoc out-of-domain even if present")
    rep.set_defaults(func=cmd_report)
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
