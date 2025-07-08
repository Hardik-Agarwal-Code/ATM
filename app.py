from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'super_secret_key'

# --- DB Utilities ---
def get_db():
    conn = sqlite3.connect('atm.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    with app.open_resource('schema.sql') as f:
        conn.executescript(f.read().decode('utf8'))
    conn.commit()
    conn.close()

# --- Routes ---
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        pin = request.form['pin']
        hashed_pin = generate_password_hash(pin)
        conn = get_db()
        try:
            conn.execute('INSERT INTO users (username, pin, balance) VALUES (?, ?, ?)', (username, hashed_pin, 0.0))
            conn.commit()
            flash('Registration successful. Please login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists.', 'error')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        pin = request.form['pin']
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user['pin'], pin):
            session['user_id'] = user['id']
            return redirect(url_for('dashboard'))
        flash('Invalid credentials.', 'error')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    return render_template('dashboard.html', user=user)

@app.route('/transaction', methods=['POST'])
def transaction():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    amount = float(request.form['amount'])
    action = request.form['action']
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    balance = user['balance']
    if action == 'withdraw' and balance >= amount:
        balance -= amount
        conn.execute('INSERT INTO transactions (user_id, type, amount) VALUES (?, ?, ?)', (user['id'], 'withdraw', amount))
    elif action == 'deposit':
        balance += amount
        conn.execute('INSERT INTO transactions (user_id, type, amount) VALUES (?, ?, ?)', (user['id'], 'deposit', amount))
    else:
        flash('Insufficient funds or invalid action.', 'error')
        conn.close()
        return redirect(url_for('dashboard'))
    conn.execute('UPDATE users SET balance = ? WHERE id = ?', (balance, user['id']))
    conn.commit()
    conn.close()
    flash(f'Successful {action} of ${amount:.2f}', 'success')
    return redirect(url_for('dashboard'))

@app.route('/transactions')
def transactions():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    txns = conn.execute('SELECT * FROM transactions WHERE user_id = ? ORDER BY timestamp DESC', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('transactions.html', transactions=txns)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
