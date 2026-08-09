"""Evaluation report artifacts: REPORT.md, summary.json, confusion-matrix PNGs, exemplars.

No matplotlib dependency — the matrix is drawn with Pillow (already a dependency).
"""

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from ml.data.winpath import windows_safe
from ml.inference.predictor import Predictor


def render_confusion_png(cm: np.ndarray, classes: list[str], out_path: Path, title: str) -> Path:
    """Draw the matrix with row/col INDEX labels; REPORT.md carries the full-name legend."""
    n = len(classes)
    cell = 30
    margin = 26
    size = margin + n * cell + 4
    img = Image.new("RGB", (size, size), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    vmax = max(int(cm.max()), 1)
    for i in range(n):
        row_total = max(int(cm[i].sum()), 1)
        for j in range(n):
            value = int(cm[i, j])
            x0, y0 = margin + j * cell, margin + i * cell
            if value == 0:
                fill = (245, 245, 245)
            elif i == j:
                shade = int(220 - 120 * (value / row_total))
                fill = (shade, 235, shade)
            else:
                shade = int(240 - 160 * (value / vmax))
                fill = (240, max(shade, 40), max(shade, 40))
            draw.rectangle([x0, y0, x0 + cell - 2, y0 + cell - 2], fill=fill, outline=(200, 200, 200))
            if value:
                text = str(value)
                bbox = draw.textbbox((0, 0), text, font=font)
                draw.text((x0 + (cell - 2 - bbox[2]) / 2, y0 + (cell - 2 - bbox[3]) / 2), text, fill="black", font=font)
    for k in range(n):
        draw.text((2, margin + k * cell + 8), str(k), fill="black", font=font)
        draw.text((margin + k * cell + 8, 2), str(k), fill="black", font=font)
    draw.text((margin, margin + n * cell + 2), title, fill="black", font=font)
    out_path = Path(out_path)
    img.save(out_path)
    return out_path


def materialize_exemplars(predictor: Predictor, picked: list[dict], ex_dir: Path) -> list[dict]:
    """Re-predict selected images WITH Grad-CAM artifacts; copy thumbnails + captions."""
    ex_dir = Path(ex_dir)
    ex_dir.mkdir(parents=True, exist_ok=True)
    # Idempotent re-runs (Gate C re-runs the eval on the same output dir): drop this
    # run's artifact set first. Windows rename refuses existing targets (WinError 183),
    # and stale exemplars from an older run must never mix into this run's report.
    for stale in ex_dir.glob("*.png"):
        stale.unlink()
    (ex_dir / "captions.json").unlink(missing_ok=True)
    captions = []
    for k, rec in enumerate(picked):
        pred = predictor.predict(rec["path"], explain_dir=ex_dir, top_k=3)
        overlay_src = Path(pred["gradcam_overlay"]) if pred["gradcam_overlay"] else None
        overlay_name = None
        if overlay_src and overlay_src.exists():
            overlay_name = f"{k:02d}-gradcam.png"
            overlay_src.replace(ex_dir / overlay_name)  # os.replace: overwrite-safe Windows+POSIX
        orig = Image.open(windows_safe(rec["path"])).convert("RGB")  # no-op on short/POSIX paths
        orig.thumbnail((416, 416))
        orig_name = f"{k:02d}-orig.png"
        orig.save(ex_dir / orig_name)
        captions.append({
            "index": k,
            "original": f"exemplars/{orig_name}",
            "gradcam_overlay": f"exemplars/{overlay_name}" if overlay_name else None,
            "ground_truth": rec["ground_truth"],
            "predicted": rec["predicted"],
            "confidence": rec["confidence"],
            "status": rec["status"],
            "source_path": rec["path"],
        })
    (ex_dir / "captions.json").write_text(json.dumps(captions, indent=2) + "\n", encoding="utf-8")
    return captions


def _gates_table(gates: list[dict]) -> str:
    lines = ["| Gate | Requirement | Measured | Status |", "|---|---|---|---|"]
    for g in gates:
        measured = "—" if g["measured"] is None else g["measured"]
        lines.append(f"| {g['id']} | {g['requirement']} | {measured} | **{g['status']}** |")
    return "\n".join(lines)


def _per_class_table(per_class: dict, caption: str) -> str:
    lines = [f"#### {caption}", "", "| Class | Precision | Recall | F1 | Support |", "|---|---|---|---|---|"]
    for name in sorted(per_class):
        m = per_class[name]
        lines.append(f"| {name} | {m['precision']:.4f} | {m['recall']:.4f} | {m['f1']:.4f} | {m['support']} |")
    return "\n".join(lines)


def _bands_table(bands: dict) -> str:
    lines = ["| Band | Count | Share |", "|---|---|---|"]
    for band, row in bands.items():
        lines.append(f"| {band} | {row['count']} | {row['share'] * 100:.1f}% |")
    return "\n".join(lines)


def _index_legend(classes: list[str]) -> str:
    return ", ".join(f"{i}={name}" for i, name in enumerate(classes))


def _confusions_block(confusions: list[dict]) -> str:
    if not confusions:
        return "No misclassifications on this split (recorded, not hidden)."
    rows = "\n".join(f"| {c['actual']} | {c['predicted']} | {c['count']} |" for c in confusions)
    return "| Actual | Predicted | Count |\n|---|---|---|\n" + rows


def write_report(out_dir: Path, ctx: dict) -> dict:
    """Assemble REPORT.md + summary.json (+ exemplar captions already on disk)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ind = ctx["in_domain"]
    ood = ctx["ood"]
    gates = ctx["gates"]
    classes = ctx["classes"]

    sections = [
        "# CropMind AI — Model Evaluation Report",
        "",
        (
            f"**Generated:** {ctx['generated_utc']} (UTC) · **Run:** `{ctx['run_dir']}` · "
            f"**Model version:** {ctx['model_version']} · **Device:** {ctx['device']}"
        ),
        (
            f"**Checkpoint sha256:** `{ctx['checkpoint_sha256']}`  \n"
            f"**Held-out dataset:** {ctx['dataset']['id']} test split · "
            f"content sha256 `{ctx['dataset']['splits_content_sha256']}`"
        ),
        "",
        (
            "> This report is generated code-side from measured inference only. Nothing here is a "
            "field-performance claim: in-domain numbers come from clean PlantVillage imagery; the "
            "out-of-domain PlantDoc result is the honest signal for real-world expectations."
        ),
        "",
        "## M1 gates (docs/01 §6) — measured",
        "",
        _gates_table(gates),
        "",
        "## In-domain — held-out PlantVillage test split",
        "",
        f"Top-1 **{ind['top1']:.4f}** over {ind['images']} images"
        + (f" (training-reported {ctx['training_top1']:.4f}, drift {ind['drift']:.4f})" if ctx.get("training_top1") else "")
        + f". Mean uncertainty (normalized entropy): {ind['uncertainty_mean']}.",
        "",
        "![confusion matrix](confusion_in_domain.png)",
        "",
        f"*Matrix uses index labels — legend: {_index_legend(classes)}*",
        "",
        "#### Most frequent confusions",
        "",
        _confusions_block(ind["confusions"]),
        "",
        _per_class_table(ind["per_class"], "Per-class precision / recall / F1 / support (in-domain)"),
        "",
        "#### Confidence bands on the test split (product behaviour under current thresholds)",
        "",
        _bands_table(ind["bands"]),
        "",
        "#### Latency (classification path)",
        "",
        (
            "| count | mean | p50 | p95 | max | device |\n|---|---|---|---|---|---|\n"
            f"| {ind['latency']['count']} | {ind['latency']['mean_ms']} ms | {ind['latency']['p50_ms']} ms | "
            f"{ind['latency']['p95_ms']} ms | {ind['latency']['max_ms']} ms | {ctx['device']} |"
        ),
        "",
    ]
    if ood is None:
        sections += [
            "## Out-of-domain — PlantDoc",
            "",
            "**NOT RUN in this environment.** The honesty metric requires the PlantDoc raw tree. Fetch + verify, then re-run this report:",
            "",
            "```",
            "python -m ml.data.cli pipeline --dataset plantdoc --accept-license",
            "```",
            "",
        ]
    else:
        sections += [
            "## Out-of-domain — PlantDoc (field imagery; honesty metric, never tuned on)",
            "",
            (
                f"Top-1 **{ood['top1']:.4f}** over {ood['images']} images · coverage {ood['coverage']} of the "
                f"21-class taxonomy · unmapped folders recorded: {ood['skipped_folders']}."
            ),
            "Expect this to be far below the in-domain number — that gap is the domain shift, published deliberately.",
            "",
            "![ood confusion matrix](confusion_ood.png)",
            "",
            f"*Matrix uses index labels — legend: {_index_legend(classes)}*",
            "",
            _per_class_table(ood["per_class"], "Per-class metrics (OOD, covered classes only)"),
            "",
        ]
    sections += [
        "## Exemplars (worst errors + inconclusive, with Grad-CAM)",
        "",
        ctx["exemplars_note"],
        "",
        "## Methodology & reproduction",
        "",
        "```",
        ctx["reproduce_command"],
        "```",
        "",
        (
            "Pipeline: deterministic split files + the shipped `Predictor` contract per image; Grad-CAM only for "
            "exemplars (latency gate measures the classification path). Sources: `ml/evaluation/` (git-visible)."
        ),
        "",
        "## Caveats (must travel with any number above)",
        "",
        "- In-domain performance on clean lab-style imagery is NOT field performance; the OOD block is the honest signal.",
        "- Below the LOW band the product answers INCONCLUSIVE — by design; the band histogram shows how often that fires.",
        "- Severity values elsewhere in the app are a labelled visual proxy; no severity ground truth exists.",
        "- No chemical product or dosage guidance is provided anywhere. Decision support only.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(sections) + "\n", encoding="utf-8")
    (out_dir / "summary.json").write_text(json.dumps(ctx["summary"], indent=2) + "\n", encoding="utf-8")
    return {"report_md": str(out_dir / "REPORT.md"), "summary_json": str(out_dir / "summary.json")}
