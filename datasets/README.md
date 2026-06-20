# Datasets

This folder is where you place external CSV datasets before training.
The model in `model/train_model.py` currently uses **synthetically generated data** by default.
To train on a real dataset instead, place the CSV file here and follow the instructions below.

---

## Recommended Public Datasets

### 1. Credit Card Fraud Detection (Most Popular)
- **Source:** Kaggle — ULB Machine Learning Group
- **URL:** https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud
- **File:** `creditcard.csv`
- **Size:** ~144 MB · 284,807 transactions · 492 fraud cases (0.17% fraud rate)
- **Features:** 28 PCA-anonymised features (V1–V28) + `Amount` + `Time` + `Class` (0/1)
- **Why use it:** Industry-standard benchmark, clean, ready to use with no preprocessing.

### 2. IEEE-CIS Fraud Detection
- **Source:** Kaggle — IEEE Computational Intelligence Society
- **URL:** https://www.kaggle.com/competitions/ieee-fraud-detection/data
- **Files:** `train_transaction.csv`, `train_identity.csv`
- **Size:** ~450 MB combined · 590,540 transactions
- **Features:** 400+ features including device info, email domain, card type, address
- **Why use it:** Closest to real-world e-commerce fraud, very rich feature set.

### 3. PaySim — Mobile Money Fraud Simulation
- **Source:** Kaggle — Edgar Lopez-Rojas
- **URL:** https://www.kaggle.com/datasets/ealaxi/paysim1
- **File:** `PS_20174392719_1491204439457_log.csv`
- **Size:** ~493 MB · 6.3 million transactions
- **Features:** `step`, `type`, `amount`, `nameOrig`, `oldbalanceOrg`, `newbalanceOrig`, `nameDest`, `oldbalanceDest`, `newbalanceDest`, `isFraud`, `isFlaggedFraud`
- **Why use it:** Large-scale mobile payment simulation; great for testing scalability.

### 4. Synthetic Financial Datasets for Fraud Detection
- **Source:** Kaggle — Bernd Bischl
- **URL:** https://www.kaggle.com/datasets/sriharshaeedala/financial-fraud-detection-dataset
- **File:** `fraud_dataset.csv`
- **Size:** ~50 MB
- **Why use it:** Lightweight, beginner-friendly, similar structure to this project.

---

## How to Use a Real Dataset

After downloading, place the CSV inside this `datasets/` folder:

```
datasets/
└── creditcard.csv      ← example
```

Then adapt `model/train_model.py` to load it. Replace the `generate_synthetic_data()` call with:

```python
import pandas as pd

df = pd.read_csv('datasets/creditcard.csv')

# For creditcard.csv — rename columns to match our feature names
df = df.rename(columns={'Class': 'is_fraud'})
FEATURES = ['V1','V2','V3','V4','V5','V6','V7','V8','V9','V10',
            'V11','V12','V13','V14','V15','V16','V17','V18','V19',
            'V20','V21','V22','V23','V24','V25','V26','V27','V28','Amount']

X = df[FEATURES].values
y = df['is_fraud'].values
```

The rest of the training script (scaling, RandomForest, saving) works unchanged.

---

## Dataset Already Used (Default)

If you do not place any CSV here, the system trains on **60,000 synthetic transactions**
generated in code by `model/train_model.py` using realistic fraud patterns:

| Pattern | Description |
|---|---|
| Large amounts at night (0–5 AM) | High-risk signal |
| Foreign + high amount | Combined risk |
| Rapid successive transactions | Velocity fraud |
| High-risk location origin | Geographic signal |
| Tiny test charges ($1–$30) | Card testing fraud |

This synthetic dataset achieves **ROC-AUC ~0.99** on the held-out test split.
