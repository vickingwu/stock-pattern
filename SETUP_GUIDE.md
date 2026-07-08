# Stock-Pattern Fork — Multi-ticker scan + email report

This adds three things to the original
[BennyThadikaran/stock-pattern](https://github.com/BennyThadikaran/stock-pattern):

1. **`src/loaders/YFinanceLoader.py`** — downloads OHLC data online from Yahoo
   Finance, so you don't need any local CSV files.
2. **`src/scan_and_report.py`** — scans your tickers and emails an HTML report.
3. **`.github/workflows/scan-and-email.yml`** — a GitHub Actions workflow that
   gives you a "Run workflow" button where you type tickers, pick a pattern and
   timeframe, and get the report emailed.

## File placement (drop these into your fork, keeping the paths)

```
your-fork/
├── .github/workflows/scan-and-email.yml   <- new
└── src/
    ├── loaders/YFinanceLoader.py           <- new
    └── scan_and_report.py                  <- new
```

---

## Step 1 — Fork the repo

1. Sign in to GitHub in your browser.
2. Go to https://github.com/BennyThadikaran/stock-pattern
3. Click **Fork** (top right) → **Create fork**.

## Step 2 — Add the three files to your fork

Either commit them via the GitHub web UI ("Add file → Create new file", paste
the path + content) or clone your fork, copy the files in, and push:

```bash
git clone https://github.com/<your-username>/stock-pattern.git
# copy the three files into place, then:
git add .github/workflows/scan-and-email.yml src/loaders/YFinanceLoader.py src/scan_and_report.py
git commit -m "Add Yahoo Finance loader + scan-and-email workflow"
git push
```

## Step 3 — Add email credentials as GitHub Secrets

In your fork: **Settings → Secrets and variables → Actions → New repository
secret**. Add these (values are never stored in code):

| Secret name     | Example value        | Notes                                   |
|-----------------|----------------------|-----------------------------------------|
| `MAIL_TO`       | you@example.com      | Where the report is sent                |
| `SMTP_HOST`     | smtp.gmail.com       | Your mail provider's SMTP server        |
| `SMTP_PORT`     | 465                  | 465 = SSL, 587 = STARTTLS               |
| `SMTP_USER`     | you@gmail.com        | SMTP login                              |
| `SMTP_PASSWORD` | (app password)       | **Gmail: use an App Password, not your normal password** |
| `MAIL_FROM`     | you@gmail.com        | Optional; defaults to `SMTP_USER`       |

**Gmail app password:** enable 2-Step Verification, then create an App Password
at https://myaccount.google.com/apppasswords and use that 16-char value for
`SMTP_PASSWORD`.

## Step 4 — Run it

1. In your fork, open the **Actions** tab.
2. If prompted, click **"I understand my workflows, enable them"**.
3. Select **"Scan patterns and email report"** → **Run workflow**.
4. Type your tickers (e.g. `AAPL MSFT NVDA` or `RELIANCE.NS INFY.NS`), choose a
   pattern and timeframe, then **Run workflow**.
5. Within a minute or two you'll get the email. The HTML report is also saved as
   a downloadable **artifact** on the run page.

---

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
SYMBOLS="AAPL MSFT NVDA" PATTERN=all TIMEFRAME=daily \
MAIL_TO=you@example.com SMTP_HOST=smtp.gmail.com SMTP_PORT=465 \
SMTP_USER=you@gmail.com SMTP_PASSWORD=your_app_password \
python scan_and_report.py
```

Without the SMTP variables it still runs and writes `scan_report.html`.

## Notes / limitations

- **Charts:** the email contains a table of detected patterns. Plotting images
  (matplotlib) is skipped in CI since it needs a display; the JSON/table data is
  what you get by email. The artifact could be extended to attach PNGs later.
- **Not financial advice.** Patterns are detected before breakout and must be
  validated manually, per the original project's disclaimer.
