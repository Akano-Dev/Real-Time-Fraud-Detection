"""
Real-Time Fraud Detection — Flask Backend
Serves the dashboard, runs the simulation loop, exposes the REST API.
"""

import csv
import io
import os
import random
import sqlite3
import threading
import time
import uuid
from datetime import datetime

import joblib
import numpy as np
from flask import Flask, Response, jsonify, render_template, request

# ─────────────────────────────────────────────
#  App & paths
# ─────────────────────────────────────────────
app = Flask(__name__)

DB_PATH    = os.path.join('data', 'fraud_data.db')
MODEL_PATH = os.path.join('model', 'fraud_model.pkl')
SCALER_PATH = os.path.join('model', 'scaler.pkl')

FEATURES = ['amount', 'txn_type', 'hour', 'day_of_week',
            'location_risk', 'is_foreign', 'time_since_last', 'amount_ratio']

TXN_TYPES  = ['purchase', 'withdrawal', 'transfer', 'refund']
LOCATIONS  = {
    'New York': 0, 'Los Angeles': 0, 'Chicago': 0, 'Houston': 0, 'Phoenix': 0,
    'London': 1,   'Paris': 1,       'Berlin': 1,  'Sydney': 1,
    'Dubai': 2,    'Lagos': 2,       'Moscow': 2,  'Beijing': 2, 'Cairo': 2,
}
FOREIGN_CITIES  = {'London', 'Paris', 'Berlin', 'Sydney', 'Dubai',
                   'Lagos', 'Moscow', 'Beijing', 'Cairo'}

# ─────────────────────────────────────────────
#  Model (lazy-loaded)
# ─────────────────────────────────────────────
_model  = None
_scaler = None
_model_lock = threading.Lock()


def load_model():
    global _model, _scaler
    with _model_lock:
        if os.path.exists(MODEL_PATH):
            _model  = joblib.load(MODEL_PATH)
            _scaler = joblib.load(SCALER_PATH) if os.path.exists(SCALER_PATH) else None
            print('[INFO] Fraud model loaded successfully.')
        else:
            print('[WARN] Model not found — using rule-based fallback.')


def predict_fraud(features: dict) -> float:
    """Return fraud probability [0, 1] for a feature dict."""
    if _model is None:
        # Simple rule-based fallback until the model is trained
        risk = 0.0
        if features['amount'] > 3000:                          risk += 0.35
        if features['is_foreign'] and features['amount'] > 500: risk += 0.25
        if features['hour'] < 5:                               risk += 0.20
        if features['location_risk'] == 2:                     risk += 0.15
        if features['time_since_last'] < 2:                    risk += 0.20
        return min(risk, 0.97)

    X = np.array([[
        features['amount'],
        TXN_TYPES.index(features['txn_type']),
        features['hour'],
        features['day_of_week'],
        features['location_risk'],
        features['is_foreign'],
        features['time_since_last'],
        features['amount_ratio'],
    ]])
    if _scaler is not None:
        X = _scaler.transform(X)
    return float(_model.predict_proba(X)[0][1])


def risk_level(prob: float) -> str:
    if prob >= 0.65:
        return 'fraud'
    if prob >= 0.30:
        return 'suspicious'
    return 'safe'

# ─────────────────────────────────────────────
#  Database
# ─────────────────────────────────────────────
def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs('data', exist_ok=True)
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id      TEXT    UNIQUE,
            amount              REAL,
            txn_type            TEXT,
            location            TEXT,
            hour                INTEGER,
            day_of_week         INTEGER,
            location_risk       INTEGER,
            is_foreign          INTEGER,
            time_since_last     REAL,
            amount_ratio        REAL,
            is_fraud            INTEGER,
            fraud_probability   REAL,
            risk_level          TEXT,
            timestamp           DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# ─────────────────────────────────────────────
#  Transaction simulation
# ─────────────────────────────────────────────
def _random_txn() -> dict:
    """Build a random synthetic transaction."""
    city     = random.choice(list(LOCATIONS.keys()))
    is_for   = 1 if city in FOREIGN_CITIES else 0
    loc_risk = LOCATIONS[city]
    now      = datetime.now()

    # Occasionally inject an obvious fraudulent transaction
    inject_fraud = random.random() < 0.08

    if inject_fraud:
        amount = round(random.uniform(2000, 12000), 2)
        txn_t  = random.choice(['withdrawal', 'transfer'])
        tsl    = round(np.random.exponential(1.5), 3)
        is_for = 1
        loc_risk = 2
    else:
        amount = round(np.random.lognormal(4.6, 1.0), 2)
        amount = min(amount, 5000)
        txn_t  = random.choices(TXN_TYPES, weights=[60, 20, 15, 5])[0]
        tsl    = round(np.random.exponential(45), 3)

    return {
        'transaction_id':  str(uuid.uuid4())[:8].upper(),
        'amount':          amount,
        'txn_type':        txn_t,
        'location':        city,
        'hour':            now.hour,
        'day_of_week':     now.weekday(),
        'location_risk':   loc_risk,
        'is_foreign':      is_for,
        'time_since_last': tsl,
        'amount_ratio':    round(amount / 250.0, 4),
    }


def _save_txn(txn: dict, prob: float):
    rl = risk_level(prob)
    conn = get_db()
    try:
        conn.execute('''
            INSERT OR IGNORE INTO transactions
            (transaction_id, amount, txn_type, location, hour, day_of_week,
             location_risk, is_foreign, time_since_last, amount_ratio,
             is_fraud, fraud_probability, risk_level)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            txn['transaction_id'], txn['amount'], txn['txn_type'], txn['location'],
            txn['hour'], txn['day_of_week'], txn['location_risk'], txn['is_foreign'],
            txn['time_since_last'], txn['amount_ratio'],
            1 if rl == 'fraud' else 0, round(prob, 4), rl
        ))
        conn.commit()
    finally:
        conn.close()


_sim_running = True


def _simulation_worker():
    """Background thread: generate and classify transactions continuously."""
    while _sim_running:
        try:
            txn  = _random_txn()
            prob = predict_fraud(txn)
            _save_txn(txn, prob)
        except Exception as exc:
            print(f'[SIM ERROR] {exc}')
        time.sleep(random.uniform(2.0, 4.5))

# ─────────────────────────────────────────────
#  Routes
# ─────────────────────────────────────────────
@app.route('/')
def dashboard():
    model_status = 'Active' if _model is not None else 'Rule-based fallback'
    return render_template('index.html', model_status=model_status)


# ── Stats ──────────────────────────────────
@app.route('/api/stats')
def api_stats():
    conn = get_db()
    try:
        total  = conn.execute('SELECT COUNT(*) FROM transactions').fetchone()[0]
        fraud  = conn.execute('SELECT COUNT(*) FROM transactions WHERE is_fraud=1').fetchone()[0]
        sus    = conn.execute("SELECT COUNT(*) FROM transactions WHERE risk_level='suspicious'").fetchone()[0]
        legit  = total - fraud - sus
        pct    = round(fraud / total * 100, 2) if total else 0
        avg_p  = conn.execute('SELECT AVG(fraud_probability) FROM transactions').fetchone()[0] or 0
        return jsonify({
            'total': total, 'fraud': fraud,
            'suspicious': sus, 'legitimate': max(legit, 0),
            'fraud_percentage': pct,
            'avg_risk': round(avg_p, 4),
        })
    finally:
        conn.close()


# ── Transactions ───────────────────────────
@app.route('/api/transactions')
def api_transactions():
    limit  = request.args.get('limit',  50,   type=int)
    risk   = request.args.get('risk',   '',   type=str)
    search = request.args.get('search', '',   type=str)

    conn = get_db()
    try:
        q      = 'SELECT * FROM transactions WHERE 1=1'
        params = []
        if risk and risk != 'all':
            q += ' AND risk_level = ?'
            params.append(risk)
        if search:
            q += ' AND (transaction_id LIKE ? OR location LIKE ? OR txn_type LIKE ?)'
            params += [f'%{search}%'] * 3
        q += ' ORDER BY timestamp DESC LIMIT ?'
        params.append(limit)
        rows = conn.execute(q, params).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


# ── Fraud list ─────────────────────────────
@app.route('/api/frauds')
def api_frauds():
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM transactions WHERE is_fraud=1 ORDER BY timestamp DESC LIMIT 30"
        ).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


# ── Manual prediction ──────────────────────
@app.route('/api/predict', methods=['POST'])
def api_predict():
    data = request.get_json(force=True)
    required = {'amount', 'txn_type', 'hour', 'day_of_week',
                'location_risk', 'is_foreign', 'time_since_last', 'amount_ratio'}
    missing = required - set(data.keys())
    if missing:
        return jsonify({'error': f'Missing fields: {missing}'}), 400
    prob = predict_fraud(data)
    rl   = risk_level(prob)
    return jsonify({
        'fraud_probability': round(prob, 4),
        'risk_level':        rl,
        'is_fraud':          rl == 'fraud',
        'confidence':        round(abs(prob - 0.5) * 2, 4),
    })


# ── Chart: hourly activity ─────────────────
@app.route('/api/charts/hourly')
def chart_hourly():
    conn = get_db()
    try:
        rows = conn.execute('''
            SELECT CAST(strftime('%H', timestamp) AS INTEGER) AS hour,
                   COUNT(*) AS total, SUM(is_fraud) AS fraud
            FROM transactions
            GROUP BY hour ORDER BY hour
        ''').fetchall()
        # Ensure all 24 hours present
        data = {r['hour']: dict(r) for r in rows}
        result = []
        for h in range(24):
            result.append(data.get(h, {'hour': h, 'total': 0, 'fraud': 0}))
        return jsonify(result)
    finally:
        conn.close()


# ── Chart: recent trends (last 30 min) ────
@app.route('/api/charts/trends')
def chart_trends():
    conn = get_db()
    try:
        rows = conn.execute('''
            SELECT strftime('%H:%M', timestamp) AS minute,
                   COUNT(*) AS total, SUM(is_fraud) AS fraud
            FROM transactions
            WHERE timestamp >= datetime('now', '-30 minutes')
            GROUP BY minute ORDER BY minute
        ''').fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


# ── Chart: risk distribution ───────────────
@app.route('/api/charts/distribution')
def chart_distribution():
    conn = get_db()
    try:
        rows = conn.execute('''
            SELECT risk_level, COUNT(*) AS count
            FROM transactions GROUP BY risk_level
        ''').fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


# ── Chart: fraud prob timeline ─────────────
@app.route('/api/charts/risk_timeline')
def chart_risk_timeline():
    conn = get_db()
    try:
        rows = conn.execute('''
            SELECT strftime('%H:%M:%S', timestamp) AS ts,
                   fraud_probability, risk_level
            FROM transactions
            ORDER BY timestamp DESC LIMIT 40
        ''').fetchall()
        return jsonify(list(reversed([dict(r) for r in rows])))
    finally:
        conn.close()


# ── Export CSV ─────────────────────────────
@app.route('/api/export')
def api_export():
    conn = get_db()
    try:
        rows = conn.execute('SELECT * FROM transactions ORDER BY timestamp DESC').fetchall()
        buf  = io.StringIO()
        w    = csv.writer(buf)
        w.writerow(['ID', 'Transaction ID', 'Amount', 'Type', 'Location',
                    'Hour', 'Day', 'Location Risk', 'Foreign',
                    'Time Since Last', 'Amount Ratio',
                    'Is Fraud', 'Fraud Probability', 'Risk Level', 'Timestamp'])
        for row in rows:
            w.writerow(list(row))
        buf.seek(0)
        return Response(buf.getvalue(), mimetype='text/csv',
                        headers={'Content-Disposition':
                                 'attachment; filename=fraud_report.csv'})
    finally:
        conn.close()

# ─────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────
if __name__ == '__main__':
    init_db()
    load_model()
    threading.Thread(target=_simulation_worker, daemon=True, name='sim').start()
    print('[INFO] Simulation thread started.')
    print('[INFO] Dashboard → http://127.0.0.1:5000')
    app.run(debug=True, use_reloader=False, port=5000)
