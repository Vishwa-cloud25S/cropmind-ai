"""Dataset pipeline CLI.

    python -m ml.data.cli download --dataset plantvillage --accept-license
    python -m ml.data.cli split    --dataset plantvillage
    python -m ml.data.cli verify   --dataset plantvillage
    python -m ml.data.cli stats    --dataset plantvillage
    python -m ml.data.cli pipeline --dataset plantvillage --accept-license

Data lands under data/ (gitignored). Reports land under reports/datasets/.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from ml.data import download, registry, split, stats, verify

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW = REPO_ROOT / "data" / "raw"
DEFAULT_SPLITS = REPO_ROOT / "data" / "splits"
DEFAULT_REPORTS = REPO_ROOT / "reports" / "datasets"

logger = logging.getLogger("cropmind.ml.cli")


def _images_root_for(dataset: str, raw_dir: Path, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    prov_path = raw_dir / dataset / "PROVENANCE.json"
    if prov_path.exists():
        prov = json.loads(prov_path.read_text(encoding="utf-8"))
        return raw_dir / dataset / prov["images_root"]
    # no provenance (e.g. hand-placed data): locate by class folders
    return download.find_images_root(Path(raw_dir) / dataset, dataset)


def cmd_download(args) -> int:
    root = download.download_dataset(args.dataset, args.raw_dir, accept_license=args.accept_license)
    print(f"images root: {root}")
    return 0


def _split_dir(args) -> Path:
    return args.splits_dir / args.dataset / args.split_version


def cmd_split(args) -> int:
    images_root = _images_root_for(args.dataset, args.raw_dir, args.images_root)
    ratios = tuple(p / 100 for p in (args.train, args.val, args.test))
    manifest = split.split_dataset(images_root, _split_dir(args), args.dataset, seed=args.seed, ratios=ratios, version=args.split_version)
    totals = {name: manifest["splits"][name]["count"] for name in ("train", "val", "test")}
    print(f"split {args.split_version} (seed {args.seed}): {totals} -> {_split_dir(args)}")
    return 0


def cmd_verify(args) -> int:
    problems = verify.verify_provenance(args.raw_dir / args.dataset / "PROVENANCE.json")
    split_dir = _split_dir(args)
    if split_dir.exists():
        problems += verify.verify_splits(split_dir)
    if problems:
        print("VERIFICATION FAILED:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("verification OK: provenance complete, splits intact, no leakage")
    return 0


def cmd_stats(args) -> int:
    summary = stats.generate_stats(_split_dir(args), args.reports_dir)
    print(json.dumps(summary, indent=2))
    return 0


def cmd_pipeline(args) -> int:
    return max(cmd_download(args), cmd_split(args), cmd_verify(args), cmd_stats(args))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ml.data.cli", description=__doc__)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--dataset", choices=sorted(registry.REGISTRY), required=True)
    common.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW)
    common.add_argument("--splits-dir", type=Path, default=DEFAULT_SPLITS)
    common.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS)
    sub = parser.add_subparsers(dest="command", required=True)

    for name, fn in (("download", cmd_download), ("split", cmd_split), ("verify", cmd_verify), ("stats", cmd_stats), ("pipeline", cmd_pipeline)):
        sp = sub.add_parser(name, parents=[common])
        if name in ("download", "pipeline"):
            sp.add_argument("--accept-license", action="store_true", help="confirm you reviewed the dataset license (page URL is printed otherwise)")
        if name in ("split", "pipeline"):
            sp.add_argument("--images-root", default=None)
            sp.add_argument("--seed", type=int, default=42)
            sp.add_argument("--train", type=int, default=70)
            sp.add_argument("--val", type=int, default=15)
            sp.add_argument("--test", type=int, default=15)
            sp.add_argument("--split-version", default="v1")
        elif name in ("verify", "stats"):
            sp.add_argument("--split-version", default="v1")
        sp.set_defaults(func=fn)
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (download.LicenseNotAcceptedError, download.DownloadError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
