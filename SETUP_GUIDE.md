# Stock-Pattern Fork — Multi-ticker scan + report (no email, no secrets)

This adds three things to the original
[BennyThadikaran/stock-pattern](https://github.com/BennyThadikaran/stock-pattern):

1. **`src/loaders/YFinanceLoader.py`** — downloads OHLC data online from Yahoo
   Finance, so you don't need any local CSV files.
2. **`src/scan_and_report.py`** — scans your tickers and builds an HTML report.
3. **`.github/workflows/scan-patterns.yml`** — a GitHub Actions workflow that
   gives you a "Run workflow" button where you type tickers, pick a pattern and
   timeframe.

**No email, no secrets.** The report is delivered two ways:
- A **summary table on the run page** (GitHub Actions Job Summary).
- A **downloadable artifact** (`scan_report.html`) attached to the run.

## Run it

1. In your fork, open the **Actions** tab.
2. Select **"Scan patterns and build report"** → **Run workflow**.
3. Type your tickers (e.g. `AAPL MSFT NVDA` or `RELIANCE.NS INFY.NS`), choose a
   pattern and timeframe, then **Run workflow**.
4. Open the finished run: the results table shows at the bottom of the page, and
   `scan_report.html` is downloadable under **Artifacts**.

## Ticker format cheat sheet (Yahoo Finance)

| Market            | Format          | Example        |
|-------------------|-----------------|----------------|
| US stocks         | plain symbol    | `AAPL`, `MSFT` |
| India NSE         | `.NS` suffix    | `RELIANCE.NS`  |
| India BSE         | `.BO` suffix    | `500325.BO`    |
| Hong Kong         | `.HK` suffix    | `0700.HK`      |
| London            | `.L` suffix     | `HSBA.L`       |

## Pattern keys

- Groups: `all`, `bull`, `bear`, `bull_harm`, `bear_harm`
- Individual: `vcpu`, `vcpd`, `dbot`, `dtop`, `hnsu`, `hnsd`, `trng`,
  `flagu`, `flagd`, `abcdu/d`, `batu/d`, `gartu/d`, `crabu/d`, `bflyu/d`

## Run locally (optional)

```bash
cd src
pip install -r ../requirements.txt yfinance
SYMBOLS="AAPL MSFT NVDA" PATTERN=all TIMEFRAME=daily python scan_and_report.py
```

It prints the report and writes `scan_report.html`.

## Notes

- The report is a **table of detected patterns**. Plotting chart images
  (matplotlib) is skipped in CI since it needs a display.
- **Not financial advice.** Patterns are detected before breakout and must be
  validated manually, per the original project's disclaimer.

## Want emailed reports later?

You can add email delivery on top of this by adding SMTP repository secrets and
an email step. That path requires an SMTP password / app password (email
protocol requirement) — intentionally left out here to keep setup secret-free.
