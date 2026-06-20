# FraudGuard — Real-Time Fraud Detection System

A production-style AI-powered fraud detection web application that monitors incoming
financial transactions in real time, scores each one with a machine learning model,
and displays live results on an interactive dashboard.

---

## Project Goal

Financial fraud costs the global economy hundreds of billions of dollars annually.
Traditional rule-based systems flag too many false positives and miss novel attack patterns.

**FraudGuard** solves this by:

- Running every incoming transaction through a trained **Random Forest classifier** that
  evaluates 8 behavioural features (amount, time, location risk, velocity, etc.) and
  returns a **fraud probability score** in milliseconds.
- Classifying each transaction into one of three risk tiers:
  - **Safe** (probability < 30%) — green
  - **Suspicious** (30–65%) — yellow
  - **Fraud** (≥ 65%) — red, alert triggered
- Persisting all predictions to a **SQLite database** and surfacing them on a live
  dark-themed SaaS dashboard with charts, search, filters, and CSV export.

The goal is a complete, runnable system that demonstrates the full ML pipeline —
data generation → training → serving → monitoring — in a single codebase.

---

## Project Structure

```
Real-Time Fraud Detection/
│
├── app.py                   # Flask backend, REST API, simulation thread
├── requirements.txt         # Python dependencies
├── README.md
│
├── model/
│   ├── train_model.py       # Synthetic data generation + RF training
│   ├── fraud_model.pkl      # Saved model  (created after training)
│   └── scaler.pkl           # Feature scaler (created after training)
│
├── datasets/                # Place external CSV datasets here
│   └── README.md            # Dataset guide + download links
│
├── data/
│   └── fraud_data.db        # SQLite database (auto-created on first run)
│
├── templates/
│   └── index.html           # Single-page dashboard (Bootstrap 5 + Chart.js)
│
└── static/
    ├── css/style.css        # Dark fintech theme
    └── js/dashboard.js      # Live polling, charts, search, export
```

---

## Datasets

### Default — Synthetic Data (no download required)

The training script generates **60,000 labelled transactions** in memory using
hand-crafted fraud patterns. No external file is needed.

| Fraud Pattern | Feature Used |
|---|---|
| Large withdrawal at 2 AM | `amount` + `hour` |
| Foreign card, high amount | `is_foreign` + `amount` |
| 3 transactions in 90 seconds | `time_since_last` |
| High-risk geographic origin | `location_risk` |
| $1–$30 test charge | `amount` (micro-fraud) |

**Results on this dataset:** ROC-AUC **0.9947** · Accuracy **97%**

---

### Real-World Datasets (optional, place in `datasets/`)

| Dataset | Transactions | Fraud Rate | Size | Link |
|---|---|---|---|---|
| **Credit Card Fraud Detection** (ULB) | 284,807 | 0.17% | 144 MB | [Kaggle](https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud) |
| **IEEE-CIS Fraud Detection** | 590,540 | ~3.5% | 450 MB | [Kaggle](https://www.kaggle.com/competitions/ieee-fraud-detection) |
| **PaySim Mobile Money** | 6,300,000 | 0.13% | 493 MB | [Kaggle](https://www.kaggle.com/datasets/ealaxi/paysim1) |
| **Synthetic Financial Fraud** | ~200,000 | ~1% | 50 MB | [Kaggle](https://www.kaggle.com/datasets/sriharshaeedala/financial-fraud-detection-dataset) |

Download any of the above, place the CSV in `datasets/`, and see `datasets/README.md`
for instructions on swapping it into the training script.

---

## How to Run

### Prerequisites

- Python 3.11+
- pip

---

### Step 1 — Clone or navigate to the project folder

```bash
cd "Real-Time Fraud Detection"
```

---

### Step 2 — Install dependencies

```bash
pip install -r requirements.txt
```

This installs: Flask, scikit-learn, pandas, numpy, joblib.

---

### Step 3 — Train the model

```bash
python model/train_model.py
```

Expected output:

```
=======================================================
  Real-Time Fraud Detection - Model Training
=======================================================
[1/5] Generating synthetic transaction data ...
      60,000 records  |  Fraud rate: 12.0%
[2/5] Splitting into train / test sets (80 / 20) ...
[3/5] Scaling features ...
[4/5] Training Random Forest classifier ...
[5/5] Evaluating model ...

---------------------------------------------
  ROC-AUC Score : 0.9947
---------------------------------------------
  [OK] Model saved  ->  model/fraud_model.pkl
  [OK] Scaler saved ->  model/scaler.pkl
=======================================================
  Training complete - run  python app.py  to start.
=======================================================
```

This creates `model/fraud_model.pkl` and `model/scaler.pkl`.
You only need to do this once (or again if you switch to a real dataset).

---

### Step 4 — Start the application

```bash
python app.py
```

Open your browser at: **http://127.0.0.1:5000**

The simulation thread starts immediately and generates a new transaction every 2–4 seconds.
The dashboard auto-refreshes every 3 seconds — no manual reload needed.

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Live dashboard (HTML) |
| `GET` | `/api/stats` | Aggregate counts and fraud percentage |
| `GET` | `/api/transactions` | Transaction list (`?limit=`, `?risk=`, `?search=`) |
| `GET` | `/api/frauds` | Latest 30 flagged fraud transactions |
| `POST` | `/api/predict` | Score a single transaction (JSON body) |
| `GET` | `/api/charts/hourly` | Per-hour transaction + fraud counts |
| `GET` | `/api/charts/trends` | Per-minute counts for the last 30 minutes |
| `GET` | `/api/charts/distribution` | Count per risk level (safe / suspicious / fraud) |
| `GET` | `/api/charts/risk_timeline` | Recent fraud probability values |
| `GET` | `/api/export` | Download full database as `fraud_report.csv` |

### POST /api/predict — example

```bash
curl -X POST http://127.0.0.1:5000/api/predict \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 7500,
    "txn_type": "withdrawal",
    "hour": 2,
    "day_of_week": 1,
    "location_risk": 2,
    "is_foreign": 1,
    "time_since_last": 0.8,
    "amount_ratio": 30.0
  }'
```

Response:

```json
{
  "confidence": 1.0,
  "fraud_probability": 1.0,
  "is_fraud": true,
  "risk_level": "fraud"
}
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| Web framework | Flask 3.x |
| ML model | scikit-learn RandomForestClassifier |
| Data processing | pandas, numpy |
| Model persistence | joblib |
| Database | SQLite 3 |
| Frontend | Bootstrap 5 (dark theme), Chart.js 4, Font Awesome 6 |
| Fonts | Google Fonts — Inter |

---

## Dashboard Pages

| Page | What it shows |
|---|---|
| **Dashboard** | Stats cards, live transaction table, trend + distribution charts |
| **Analytics** | Hourly activity bar chart, fraud probability timeline, feature guide |
| **Fraud Alerts** | Filtered view of all flagged fraud transactions |
| **Reports** | CSV export, model info, risk threshold reference |
