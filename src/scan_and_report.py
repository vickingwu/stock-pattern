"""
scan_and_report.py
==================

Scan one or more ticker symbols for chart patterns using Yahoo Finance data
and produce an HTML report.

Designed to be driven by GitHub Actions (workflow_dispatch), but it also runs
locally. All configuration comes from environment variables.

Output:
  - Writes scan_report.html (uploaded by the workflow as a downloadable artifact)
  - Writes a Markdown summary to the GitHub Actions run page ($GITHUB_STEP_SUMMARY)
  - Prints results to stdout

No email, no secrets required.

Environment variables
----------------------
  SYMBOLS       Comma/space/newline separated tickers, e.g. "AAPL, MSFT NVDA"
  PATTERN       Pattern key (default: all). One of the keys in FN_DICT or a
                group: all, bull, bear, bull_harm, bear_harm.
  TIMEFRAME     daily | weekly | monthly (default: daily)
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Tuple

import utils
from loaders.YFinanceLoader import YFinanceLoader

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("scan_and_report")

DIR = Path(__file__).parent

# Same mapping used by init.py
FN_DICT: Dict[str, Callable] = {
    "flagu": utils.find_bullish_flag,
    "flagd": utils.find_bearish_flag,
    "vcpu": utils.find_bullish_vcp,
    "dbot": utils.find_double_bottom,
    "hnsu": utils.find_reverse_hns,
    "vcpd": utils.find_bearish_vcp,
    "dtop": utils.find_double_top,
    "hnsd": utils.find_hns,
    "trng": utils.find_triangles,
    "uptl": utils.find_uptrend_line,
    "dntl": utils.find_downtrend_line,
    "abcdu": utils.find_bullish_abcd,
    "abcdd": utils.find_bearish_abcd,
    "batu": utils.find_bullish_bat,
    "batd": utils.find_bearish_bat,
    "gartu": utils.find_bullish_gartley,
    "gartd": utils.find_bearish_gartley,
    "crabu": utils.find_bullish_crab,
    "crabd": utils.find_bearish_crab,
    "bflyu": utils.find_bullish_butterfly,
    "bflyd": utils.find_bearish_butterfly,
}

GROUPS = {
    "all": ("vcpu", "hnsu", "dbot", "flagu", "vcpd", "hnsd", "dtop", "flagd"),
    "bull": ("vcpu", "hnsu", "dbot", "flagu"),
    "bear": ("vcpd", "hnsd", "dtop", "flagd"),
    "bull_harm": ("abcdu", "batu", "gartu", "crabu", "bflyu"),
    "bear_harm": ("abcdd", "batd", "gartd", "crabd", "bflyd"),
}


def parse_symbols(raw: str) -> List[str]:
    """Split a free-form list of symbols on commas, spaces and newlines."""
    if not raw:
        return []

    for sep in (",", "\n", "\t", ";"):
        raw = raw.replace(sep, " ")

    seen = []
    for token in raw.split(" "):
        token = token.strip().upper()
        if token and token not in seen:
            seen.append(token)
    return seen


def resolve_functions(pattern: str) -> Tuple[str, Tuple[Callable, ...]]:
    pattern = (pattern or "all").strip().lower()

    if pattern in GROUPS:
        return pattern, tuple(FN_DICT[k] for k in GROUPS[pattern])

    if pattern in FN_DICT:
        return pattern, (FN_DICT[pattern],)

    valid = ", ".join(list(GROUPS.keys()) + list(FN_DICT.keys()))
    raise SystemExit(f"Unknown PATTERN '{pattern}'. Valid values: {valid}")


def scan_symbol(sym: str, fns: Tuple[Callable, ...], loader, config: dict,
                bars_left: int = 6, bars_right: int = 6) -> Tuple[bool, List[dict]]:
    """Detect patterns for a single symbol. Mirrors init.py:scan_pattern.

    Returns (had_data, results). had_data is False when the loader returned no
    usable OHLC data for the symbol, so the caller can report it separately.
    """
    results: List[dict] = []

    df = loader.get(sym)

    if df is None or df.empty:
        return False, results

    pivots = utils.get_max_min(df, barsLeft=bars_left, barsRight=bars_right,
                               pivot_type="both")

    if not len(pivots):
        return True, results

    for fn in fns:
        try:
            result = fn(sym, df, pivots, config)
        except Exception as e:
            logger.warning(f"{sym}: error running {fn.__name__} - {e!r}")
            continue

        if result:
            results.append(utils.make_serializable(result))

    return True, results


def build_html(all_patterns: List[dict], scanned: List[str], no_data: List[str],
               pattern: str, timeframe: str) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    rows = ""
    if all_patterns:
        for p in all_patterns:
            rows += (
                f"<tr><td>{p.get('sym', '')}</td><td>{p.get('pattern', '')}</td>"
                f"<td>{p.get('start', '')}</td><td>{p.get('end', '')}</td></tr>"
            )
    else:
        rows = '<tr><td colspan="4">No patterns detected.</td></tr>'

    no_data_html = ""
    if no_data:
        no_data_html = "<p><b>No data / skipped:</b> " + ", ".join(no_data) + "</p>"

    return f"""\
<html><body style="font-family:Arial,sans-serif;color:#222">
<h2>Stock-Pattern scan report</h2>
<p><b>Pattern:</b> {pattern.upper()} &nbsp; <b>Timeframe:</b> {timeframe} &nbsp;
<b>Generated:</b> {now}</p>
<p><b>Symbols scanned ({len(scanned)}):</b> {", ".join(scanned) if scanned else "-"}</p>
{no_data_html}
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse">
<thead style="background:#f0f0f0">
<tr><th>Symbol</th><th>Pattern</th><th>Start</th><th>End</th></tr>
</thead>
<tbody>{rows}</tbody>
</table>
<p style="color:#888;font-size:12px;margin-top:20px">
Generated by stock-pattern (BennyThadikaran) via GitHub Actions.
Not financial advice. Patterns are detected prior to breakout and must be
validated manually.
</p>
</body></html>"""


def build_markdown(all_patterns: List[dict], scanned: List[str], no_data: List[str],
                   pattern: str, timeframe: str) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "## Stock-Pattern scan report",
        "",
        f"- **Pattern:** {pattern.upper()}",
        f"- **Timeframe:** {timeframe}",
        f"- **Generated:** {now}",
        f"- **Symbols scanned ({len(scanned)}):** {', '.join(scanned) if scanned else '-'}",
    ]

    if no_data:
        lines.append(f"- **No data / skipped:** {', '.join(no_data)}")

    lines += ["", "| Symbol | Pattern | Start | End |", "|---|---|---|---|"]

    if all_patterns:
        for p in all_patterns:
            lines.append(
                f"| {p.get('sym', '')} | {p.get('pattern', '')} | "
                f"{p.get('start', '')} | {p.get('end', '')} |"
            )
    else:
        lines.append("| _No patterns detected_ | | | |")

    lines += ["", "_Not financial advice. Validate patterns manually._"]
    return "\n".join(lines)


def write_job_summary(markdown: str):
    """Append the report to the GitHub Actions run page, if available."""
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(markdown + "\n")
        logger.info("Report written to GitHub Actions job summary")


def main():
    symbols = parse_symbols(os.environ.get("SYMBOLS", ""))
    timeframe = os.environ.get("TIMEFRAME", "daily").strip().lower() or "daily"
    pattern_input = os.environ.get("PATTERN", "all")

    if not symbols:
        raise SystemExit("No SYMBOLS provided. Set the SYMBOLS environment variable.")

    if timeframe not in YFinanceLoader.timeframes:
        valid = ", ".join(YFinanceLoader.timeframes.keys())
        raise SystemExit(f"TIMEFRAME must be one of {valid}")

    pattern, fns = resolve_functions(pattern_input)

    config: dict = {"LOADER": "YFinanceLoader", "DEFAULT_TF": "daily"}
    loader = YFinanceLoader(config, tf=timeframe)

    logger.info(f"Scanning {len(symbols)} symbol(s) for '{pattern}' on {timeframe}...")

    all_patterns: List[dict] = []
    scanned: List[str] = []
    no_data: List[str] = []

    for sym in symbols:
        had_data, found = scan_symbol(sym, fns, loader, config)

        if not had_data:
            no_data.append(sym)
            logger.info(f"  {sym}: no data")
            continue

        scanned.append(sym)

        if found:
            all_patterns.extend(found)
            logger.info(f"  {sym}: {len(found)} pattern(s)")
        else:
            logger.info(f"  {sym}: none")

    loader.close()

    html = build_html(all_patterns, scanned, no_data, pattern, timeframe)
    report_file = DIR.parent / "scan_report.html"
    report_file.write_text(html, encoding="utf-8")
    logger.info(f"Report written to {report_file}")

    markdown = build_markdown(all_patterns, scanned, no_data, pattern, timeframe)
    print("\n" + markdown + "\n")
    write_job_summary(markdown)


if __name__ == "__main__":
    sys.exit(main())
