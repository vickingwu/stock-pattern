"""
scan_and_report.py
==================

Scan one or more ticker symbols for chart patterns using Yahoo Finance data
and email the results as an HTML report.

Designed to be driven by GitHub Actions (workflow_dispatch), but it also runs
locally. All configuration comes from environment variables so nothing
sensitive is ever hard-coded.

Environment variables
----------------------
Scan inputs:
  SYMBOLS       Comma/space/newline separated tickers, e.g. "AAPL, MSFT NVDA"
  PATTERN       Pattern key (default: all). One of the keys in FN_DICT or a
                group: all, bull, bear, bull_harm, bear_harm.
  TIMEFRAME     daily | weekly | monthly (default: daily)

Email delivery (all required to actually send mail):
  MAIL_TO       Recipient email address
  SMTP_HOST     e.g. smtp.gmail.com
  SMTP_PORT     e.g. 465 (SSL) or 587 (STARTTLS)
  SMTP_USER     SMTP username / login email
  SMTP_PASSWORD SMTP password or app password
  MAIL_FROM     (optional) From address, defaults to SMTP_USER

If the email variables are missing, the report is still printed to stdout and
written to scan_report.html so the workflow can attach it as an artifact.
"""

import logging
import os
import smtplib
import ssl
import sys
from datetime import datetime
from email.message import EmailMessage
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


def build_report(all_patterns: List[dict], scanned: List[str], no_data: List[str],
                 pattern: str, timeframe: str) -> Tuple[str, str]:
    """Return (subject, html_body)."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    count = len(all_patterns)
    subject = f"[Stock-Pattern] {count} pattern(s) found - {pattern.upper()} {timeframe} - {now}"

    rows = ""
    if all_patterns:
        for p in all_patterns:
            sym = p.get("sym", "")
            ptn = p.get("pattern", "")
            start = p.get("start", "")
            end = p.get("end", "")
            rows += (
                f"<tr><td>{sym}</td><td>{ptn}</td>"
                f"<td>{start}</td><td>{end}</td></tr>"
            )
    else:
        rows = '<tr><td colspan="4">No patterns detected.</td></tr>'

    no_data_html = ""
    if no_data:
        no_data_html = (
            "<p><b>No data / skipped:</b> " + ", ".join(no_data) + "</p>"
        )

    html = f"""\
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
This is not financial advice. Patterns are detected prior to breakout and must
be validated manually.
</p>
</body></html>"""

    return subject, html


def send_email(subject: str, html_body: str) -> bool:
    mail_to = os.environ.get("MAIL_TO", "").strip()
    host = os.environ.get("SMTP_HOST", "").strip()
    port = os.environ.get("SMTP_PORT", "").strip()
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "").strip()
    mail_from = os.environ.get("MAIL_FROM", user).strip()

    if not all([mail_to, host, port, user, password]):
        logger.warning(
            "Email not sent: one or more of MAIL_TO / SMTP_HOST / SMTP_PORT / "
            "SMTP_USER / SMTP_PASSWORD is missing. Report saved to file instead."
        )
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = mail_to
    msg.set_content("This report requires an HTML capable email client.")
    msg.add_alternative(html_body, subtype="html")

    port_int = int(port)
    context = ssl.create_default_context()

    try:
        if port_int == 465:
            with smtplib.SMTP_SSL(host, port_int, context=context) as server:
                server.login(user, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port_int) as server:
                server.starttls(context=context)
                server.login(user, password)
                server.send_message(msg)
    except Exception as e:
        logger.error(f"Failed to send email: {e!r}")
        return False

    logger.info(f"Report emailed to {mail_to}")
    return True


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

    subject, html = build_report(all_patterns, scanned, no_data, pattern, timeframe)

    report_file = DIR.parent / "scan_report.html"
    report_file.write_text(html, encoding="utf-8")
    logger.info(f"Report written to {report_file}")

    send_email(subject, html)


if __name__ == "__main__":
    sys.exit(main())
