"""
Fraud Detection Model Training Script
Generates synthetic transaction data and trains a Random Forest classifier.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, roc_auc_score, confusion_matrix
import joblib
import os

FEATURES = ['amount', 'txn_type', 'hour', 'day_of_week',
            'location_risk', 'is_foreign', 'time_since_last', 'amount_ratio']


def generate_synthetic_data(n_samples: int = 60000) -> pd.DataFrame:
    """
    Produce labelled transaction records with realistic fraud patterns.
    Fraud rate ≈ 12 % to give the model enough positive examples.
    """
    np.random.seed(42)
    records = []

    for _ in range(n_samples):
        is_fraud = np.random.random() < 0.12

        if is_fraud:
            # --- Fraudulent transaction characteristics ---
            # Larger amounts, skewed toward night hours, foreign / high-risk origins
            if np.random.random() < 0.65:
                amount = np.random.lognormal(6.5, 1.2)      # heavy tail up to ~$15k
            else:
                amount = np.random.uniform(1, 30)            # tiny test charges
            amount = min(amount, 15000)

            hour = (np.random.choice(list(range(0, 6)) + list(range(22, 24)))
                    if np.random.random() < 0.70 else np.random.randint(0, 24))

            location_risk = (2 if np.random.random() < 0.60
                             else np.random.choice([0, 1, 2]))
            is_foreign = 1 if np.random.random() < 0.72 else 0

            # Velocity fraud: rapid successive transactions
            time_since_last = (np.random.exponential(1.5)
                               if np.random.random() < 0.40
                               else np.random.exponential(20))

            txn_type = np.random.choice([0, 1, 2, 3], p=[0.10, 0.40, 0.40, 0.10])

        else:
            # --- Legitimate transaction characteristics ---
            amount = np.random.lognormal(4.6, 1.0)           # mostly $20-$500
            amount = min(amount, 4000)

            hour = (np.random.choice(range(8, 20))
                    if np.random.random() < 0.85 else np.random.randint(0, 24))

            location_risk = (np.random.choice([0, 1], p=[0.80, 0.20])
                             if np.random.random() < 0.90
                             else 2)
            is_foreign = 1 if np.random.random() < 0.15 else 0

            time_since_last = np.random.exponential(60)       # avg 60 min between txns
            txn_type = np.random.choice([0, 1, 2, 3], p=[0.60, 0.20, 0.15, 0.05])

        day_of_week = np.random.randint(0, 7)
        amount_ratio = round(amount / 250.0, 4)               # normalised vs $250 avg

        records.append({
            'amount':           round(amount, 2),
            'txn_type':         txn_type,
            'hour':             int(hour),
            'day_of_week':      day_of_week,
            'location_risk':    location_risk,
            'is_foreign':       is_foreign,
            'time_since_last':  round(time_since_last, 3),
            'amount_ratio':     amount_ratio,
            'is_fraud':         int(is_fraud),
        })

    return pd.DataFrame(records)


def train_and_save_model():
    print("=" * 55)
    print("  Real-Time Fraud Detection - Model Training")
    print("=" * 55)

    print("\n[1/5] Generating synthetic transaction data ...")
    df = generate_synthetic_data(60000)
    fraud_rate = df['is_fraud'].mean() * 100
    print(f"      {len(df):,} records  |  Fraud rate: {fraud_rate:.1f}%")

    X = df[FEATURES].values
    y = df['is_fraud'].values

    print("\n[2/5] Splitting into train / test sets (80 / 20) ...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    print("\n[3/5] Scaling features ...")
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s  = scaler.transform(X_test)

    print("\n[4/5] Training Random Forest classifier ...")
    clf = RandomForestClassifier(
        n_estimators=200,
        max_depth=12,
        min_samples_split=10,
        min_samples_leaf=4,
        class_weight='balanced',    # handles class imbalance
        n_jobs=-1,
        random_state=42,
    )
    clf.fit(X_train_s, y_train)

    print("\n[5/5] Evaluating model ...")
    y_pred  = clf.predict(X_test_s)
    y_proba = clf.predict_proba(X_test_s)[:, 1]
    auc     = roc_auc_score(y_test, y_proba)

    print(f"\n{'-'*45}")
    print(f"  ROC-AUC Score : {auc:.4f}")
    print(f"{'-'*45}")
    print(classification_report(y_test, y_pred,
                                target_names=['Legitimate', 'Fraud']))

    cm = confusion_matrix(y_test, y_pred)
    print(f"  Confusion Matrix:\n{cm}\n")

    # Feature importance summary
    importances = sorted(
        zip(FEATURES, clf.feature_importances_), key=lambda x: x[1], reverse=True
    )
    print("  Top Feature Importances:")
    for feat, imp in importances:
        bar = "#" * int(imp * 60)
        print(f"    {feat:<22} {imp:.4f}  {bar}")

    # Save artefacts
    os.makedirs('model', exist_ok=True)
    joblib.dump(clf,    'model/fraud_model.pkl')
    joblib.dump(scaler, 'model/scaler.pkl')
    print("\n  [OK] Model saved  ->  model/fraud_model.pkl")
    print("  [OK] Scaler saved ->  model/scaler.pkl\n")
    print("=" * 55)
    print("  Training complete - run  python app.py  to start.")
    print("=" * 55)


if __name__ == '__main__':
    train_and_save_model()
