from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'

def init_db():
    if not os.path.exists("database.db"):
        with sqlite3.connect("database.db") as conn:
            with open("schema.sql") as f:
                conn.executescript(f.read())
        print("✅ Database initialized.")
    else:
        print("ℹ️ Database already exists.")

@app.before_first_request
def initialize():
    init_db()

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', 
                            (username, password)).fetchone()
        conn.close()
        if user:
            session['user_id'] = user['id']
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (username, password, balance) VALUES (?, ?, ?)', 
                         (username, password, 0))
            conn.commit()
        except sqlite3.IntegrityError:
            return render_template('register.html', error='Username already exists')
        conn.close()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', 
                        (session['user_id'],)).fetchone()
    conn.close()
    return render_template('dashboard.html', user=user)

@app.route('/deposit', methods=['POST'])
def deposit():
    amount = float(request.form['amount'])
    conn = get_db_connection()
    conn.execute('UPDATE users SET balance = balance + ? WHERE id = ?', 
                 (amount, session['user_id']))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/withdraw', methods=['POST'])
def withdraw():
    amount = float(request.form['amount'])
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', 
                        (session['user_id'],)).fetchone()
    if user['balance'] >= amount:
        conn.execute('UPDATE users SET balance = balance - ? WHERE id = ?', 
                     (amount, session['user_id']))
        conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
