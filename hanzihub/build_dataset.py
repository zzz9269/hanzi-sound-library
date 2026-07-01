"""CLI: rebuild the merged reading dataset from all sources.

    python -m hanzihub.build_dataset                 # full rebuild (cached Wiktionary)
    python -m hanzihub.build_dataset --refresh-wiktionary
    python -m hanzihub.build_dataset --no-impute
    python -m hanzihub.build_dataset --no-wiktionary  # offline / sources-only

Writes:
    data/out/readings_long.parquet   (canonical, provenanced)
    data/out/combined_readings.csv   (wide, app-facing)
"""
from __future__ import annotations

import argparse
import sys
import time

from . import merge, paths


def _make_stdio_utf8() -> None:
    """Avoid UnicodeEncodeError when printing CJK paths on a legacy (cp1252)
    Windows console — the build writes its outputs under ``漢字音庫/``."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv: list[str] | None = None) -> None:
    _make_stdio_utf8()
    ap = argparse.ArgumentParser(description="Rebuild the hanzihub reading dataset.")
    ap.add_argument("--no-wiktionary", action="store_true",
                    help="skip the Wiktionary dial-pron layer (offline/sources-only)")
    ap.add_argument("--refresh-wiktionary", action="store_true",
                    help="re-crawl Wiktionary for new/missing characters")
    ap.add_argument("--no-impute", action="store_true",
                    help="skip the ML imputation pass")
    ap.add_argument("--limit-wiktionary", type=int, default=None,
                    help="cap new Wiktionary chars fetched (testing)")
    args = ap.parse_args(argv)

    paths.ensure_dirs()
    t0 = time.time()

    long_df, wide_df = merge.build(
        use_wiktionary=not args.no_wiktionary,
        refresh_wiktionary=args.refresh_wiktionary,
        limit_wiktionary=args.limit_wiktionary,
    )

    # Comparative reconstruction of the Proto-Min node (approximate, *-flagged).
    from . import reconstruct
    long_df = reconstruct.run(long_df)
    wide_df = merge.wide_table(long_df)

    if not args.no_impute:
        try:
            from . import impute
            long_df, wide_df = impute.run(long_df, wide_df)
        except Exception as e:  # imputation is best-effort; never blocks a build
            print(f"[build] imputation skipped ({type(e).__name__}: {e})")

    long_df.to_parquet(paths.READINGS_LONG, index=False)
    wide_df.to_csv(paths.COMBINED_CSV, index=False, encoding="utf-8")

    print(f"[build] wrote {paths.READINGS_LONG}")
    print(f"[build] wrote {paths.COMBINED_CSV}")
    print(f"[build] done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
