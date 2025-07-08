from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
import uuid
from datetime import datetime
import logging
from decimal import Decimal, InvalidOperation
import random
import string

# Configure logging
logging.basicConfig(filename='atm.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
app.secret_key = 'supersecretkey123'

# Initialize SQLite database
def init_db():
    try:
        with sqlite3.connect('atm.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    account_number TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    pin TEXT NOT NULL,
                    balance DECIMAL NOT NULL
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id TEXT PRIMARY KEY,
                    account_number TEXT NOT NULL,
                    type TEXT NOT NULL,
                    amount DECIMAL NOT NULL,
                    date TEXT NOT NULL,
                    to_account TEXT,
                    FOREIGN KEY (account_number) REFERENCES users (account_number)
                )
            ''')
            conn.commit()
            logging.info("Database initialized successfully")
    except sqlite3.Error as e:
        logging.error(f"Database initialization failed: {str(e)}")
        raise

init_db()

def validate_account_number(account_number):
    """Validate account number: numeric, 8+ digits."""
    if not account_number.isdigit() or len(account_number) < 8:
        return False, "Account number must be numeric and have 8 or more digits"
    return True, None

def validate_pin(pin):
    """Validate PIN: numeric, exactly 4 digits."""
    if not pin.isdigit() or len(pin) != 4:
        return False, "PIN must be numeric and exactly 4 digits"
    return True, None

def validate_amount(amount_str):
    """Validate and convert amount to Decimal."""
    try:
        amount = Decimal(amount_str).quantize(Decimal('0.01'))
        if amount <= 0:
            return None, "Amount must be positive"
        return amount, None
    except (InvalidOperation, ValueError):
        return None, "Invalid amount format"

@app.route('/')
def index():
    if 'account_number' in session:
        return redirect(url_for('dashboard'))
    return render_template('signin.html')

@app.route('/signin', methods=['POST'])
def signin():
    account_number = request.form['account_number']
    pin = request.form['pin']
    
    # Validate inputs
    valid_acc, acc_error = validate_account_number(account_number)
    valid_pin, pin_error = validate_pin(pin)
    
    if not valid_acc:
        flash(acc_error, 'error')
        logging.warning(f"Sign-in failed: {acc_error}")
        return redirect(url_for('index'))
    if not valid_pin:
        flash(pin_error, 'error')
        logging.warning(f"Sign-in failed: {pin_error}")
        return redirect(url_for('index'))
    
    try:
        with sqlite3.connect('atm.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE account_number = ? AND pin = ?', 
                          (account_number, pin))
            user = cursor.fetchone()
    except sqlite3.Error as e:
        flash('Database error during sign-in', 'error')
        logging.error(f"Sign-in database error for {account_number}: {str(e)}")
        return redirect(url_for('index'))
    
    if user:
        session['account_number'] = account_number
        logging.info(f"User with account {account_number} signed in")
        return redirect(url_for('dashboard'))
    flash('Invalid account number or PIN', 'error')
    logging.warning(f"Failed sign-in attempt for account: {account_number}")
    return redirect(url_for('index'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name'].strip()
        account_number = request.form['account_number']
        pin = request.form.get('pin')  # Generated PIN from form
        
        # Validate inputs
        if not name:
            flash('Name is required', 'error')
            logging.warning('Sign-up failed: Name is required')
            return redirect(url_for('signup'))
        
        valid_acc, acc_error = validate_account_number(account_number)
        if not valid_acc:
            flash(acc_error, 'error')
            logging.warning(f"Sign-up failed: {acc_error}")
            return redirect(url_for('signup'))
        
        valid_pin, pin_error = validate_pin(pin)
        if not valid_pin:
            flash(pin_error, 'error')
            logging.warning(f"Sign-up failed: {pin_error}")
            return redirect(url_for('signup'))
        
        try:
            with sqlite3.connect('atm.db') as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT account_number FROM users WHERE account_number = ?', 
                              (account_number,))
                if cursor.fetchone():
                    flash('Account number already exists', 'error')
                    logging.warning(f"Sign-up failed: Account number {account_number} already exists")
                    return redirect(url_for('signup'))
                
                # Create new user
                cursor.execute('INSERT INTO users (account_number, name, pin, balance) VALUES (?, ?, ?, ?)',
                              (account_number, name, pin, 0.00))
                conn.commit()
        except sqlite3.Error as e:
            flash('Database error during sign-up', 'error')
            logging.error(f"Sign-up database error for {account_number}: {str(e)}")
            return redirect(url_for('signup'))
        
        flash('Account created successfully! Please sign in.', 'success')
        logging.info(f"New account created: {account_number} for {name}")
        return redirect(url_for('index'))
    
    return render_template('signup.html')

@app.route('/generate_pin', methods=['POST'])
def generate_pin():
    pin = ''.join(random.choices(string.digits, k=4))
    return pin

@app.route('/dashboard')
def dashboard():
    if 'account_number' not in session:
        return redirect(url_for('index'))
    account_number = session['account_number']
    
    try:
        with sqlite3.connect('atm.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT account_number, name, balance FROM users WHERE account_number = ?', 
                          (account_number,))
            user = cursor.fetchone()
            cursor.execute('SELECT id, type, amount, date, to_account FROM transactions WHERE account_number = ? ORDER BY date DESC',
                          (account_number,))
            user_transactions = cursor.fetchall()
    except sqlite3.Error as e:
        flash('Database error while loading dashboard', 'error')
        logging.error(f"Dashboard database error for {account_number}: {str(e)}")
        return redirect(url_for('index'))
    
    if not user:
        session.pop('account_number', None)
        flash('Account not found', 'error')
        logging.warning(f"Account not found: {account_number}")
        return redirect(url_for('index'))
    
    user_dict = {'account_number': user[0], 'name': user[1], 'balance': user[2]}
    transactions_list = [
        {'id': t[0], 'type': t[1], 'amount': float(t[2]), 'date': t[3], 'to_account': t[4]}
        for t in user_transactions
    ]
    
    return render_template('dashboard.html', user=user_dict, transactions=transactions_list)

@app.route('/deposit', methods=['POST'])
def deposit():
    if 'account_number' not in session:
        flash('Please sign in to continue', 'error')
        return redirect(url_for('index'))
    account_number = session['account_number']
    amount_str = request.form['amount']
    amount, error = validate_amount(amount_str)
    if error:
        flash(error, 'error')
        logging.error(f"Deposit failed for {account_number}: {error}")
        return redirect(url_for('dashboard'))
    
    try:
        with sqlite3.connect('atm.db') as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET balance = balance + ? WHERE account_number = ?',
                          (float(amount), account_number))  # Convert Decimal to float
            cursor.execute('INSERT INTO transactions (id, account_number, type, amount, date, to_account) VALUES (?, ?, ?, ?, ?, ?)',
                          (str(uuid.uuid4()), account_number, 'Deposit', float(amount), datetime.now().strftime('%Y-%m-%d %H:%M:%S'), None))
            conn.commit()
        flash(f'Successfully deposited ${amount:.2f}', 'success')
        logging.info(f"Deposit of ${amount:.2f} for {account_number}")
    except sqlite3.OperationalError as e:
        flash('Database operation error during deposit', 'error')
        logging.error(f"Deposit operational error for {account_number}: {str(e)}")
    except sqlite3.IntegrityError as e:
        flash('Database integrity error during deposit', 'error')
        logging.error(f"Deposit integrity error for {account_number}: {str(e)}")
    except Exception as e:
        flash('Unexpected error during deposit', 'error')
        logging.error(f"Deposit unexpected error for {account_number}: {str(e)}")
    return redirect(url_for('dashboard'))

@app.route('/withdraw', methods=['POST'])
def withdraw():
    if 'account_number' not in session:
        flash('Please sign in to continue', 'error')
        return redirect(url_for('index'))
    account_number = session['account_number']
    amount_str = request.form['amount']
    amount, error = validate_amount(amount_str)
    if error:
        flash(error, 'error')
        logging.error(f"Withdrawal failed for {account_number}: {error}")
        return redirect(url_for('dashboard'))
    
    try:
        with sqlite3.connect('atm.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT balance FROM users WHERE account_number = ?', (account_number,))
            balance = cursor.fetchone()
            if not balance or amount > balance[0]:
                flash('Insufficient funds', 'error')
                logging.warning(f"Withdrawal failed for {account_number}: Insufficient funds (${amount:.2f} > ${balance[0]:.2f})")
                return redirect(url_for('dashboard'))
            cursor.execute('UPDATE users SET balance = balance - ? WHERE account_number = ?',
                          (float(amount), account_number))  # Convert Decimal to float
            cursor.execute('INSERT INTO transactions (id, account_number, type, amount, date, to_account) VALUES (?, ?, ?, ?, ?, ?)',
                          (str(uuid.uuid4()), account_number, 'Withdrawal', float(amount), datetime.now().strftime('%Y-%m-%d %H:%M:%S'), None))
            conn.commit()
        flash(f'Successfully withdrew ${amount:.2f}', 'success')
        logging.info(f"Withdrawal of ${amount:.2f} for {account_number}")
    except sqlite3.OperationalError as e:
        flash('Database operation error during withdrawal', 'error')
        logging.error(f"Withdrawal operational error for {account_number}: {str(e)}")
    except sqlite3.IntegrityError as e:
        flash('Database integrity error during withdrawal', 'error')
        logging.error(f"Withdrawal integrity error for {account_number}: {str(e)}")
    except Exception as e:
        flash('Unexpected error during withdrawal', 'error')
        logging.error(f"Withdrawal unexpected error for {account_number}: {str(e)}")
    return redirect(url_for('dashboard'))

@app.route('/transfer', methods=['POST'])
def transfer():
    if 'account_number' not in session:
        flash('Please sign in to continue', 'error')
        return redirect(url_for('index'))
    account_number = session['account_number']
    amount_str = request.form['amount']
    to_account = request.form['to_account'].strip()
    amount, error = validate_amount(amount_str)
    if error:
        flash(error, 'error')
        logging.error(f"Transfer failed for {account_number}: {error}")
        return redirect(url_for('dashboard'))
    
    valid_acc, acc_error = validate_account_number(to_account)
    if not valid_acc:
        flash(acc_error, 'error')
        logging.warning(f"Transfer failed for {account_number}: {acc_error}")
        return redirect(url_for('dashboard'))
    
    try:
        with sqlite3.connect('atm.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT balance FROM users WHERE account_number = ?', (account_number,))
            balance = cursor.fetchone()
            if not balance or amount > balance[0]:
                flash('Insufficient funds', 'error')
                logging.warning(f"Transfer failed for {account_number}: Insufficient funds (${amount:.2f} > ${balance[0]:.2f})")
                return redirect(url_for('dashboard'))
            
            cursor.execute('SELECT account_number FROM users WHERE account_number = ?', (to_account,))
            recipient = cursor.fetchone()
            if not recipient:
                flash('Recipient account not found', 'error')
                logging.warning(f"Transfer failed for {account_number}: Recipient account {to_account} not found")
                return redirect(url_for('dashboard'))
            if to_account == account_number:
                flash('Cannot transfer to your own account', 'error')
                logging.warning(f"Transfer failed for {account_number}: Attempted self-transfer to {to_account}")
                return redirect(url_for('dashboard'))
            
            # Perform atomic transfer
            cursor.execute('UPDATE users SET balance = balance - ? WHERE account_number = ?',
                          (float(amount), account_number))  # Convert Decimal to float
            cursor.execute('UPDATE users SET balance = balance + ? WHERE account_number = ?',
                          (float(amount), to_account))  # Convert Decimal to float
            cursor.execute('INSERT INTO transactions (id, account_number, type, amount, date, to_account) VALUES (?, ?, ?, ?, ?, ?)',
                          (str(uuid.uuid4()), account_number, 'Transfer', float(amount), datetime.now().strftime('%Y-%m-%d %H:%M:%S'), to_account))
            cursor.execute('INSERT INTO transactions (id, account_number, type, amount, date, to_account) VALUES (?, ?, ?, ?, ?, ?)',
                          (str(uuid.uuid4()), to_account, 'Received', float(amount), datetime.now().strftime('%Y-%m-%d %H:%M:%S'), account_number))
            conn.commit()
        flash(f'Successfully transferred ${amount:.2f} to account {to_account}', 'success')
        logging.info(f"Transfer of ${amount:.2f} from {account_number} to {to_account}")
    except sqlite3.OperationalError as e:
        flash('Database operation error during transfer', 'error')
        logging.error(f"Transfer operational error for {account_number}: {str(e)}")
    except sqlite3.IntegrityError as e:
        flash('Database integrity error during transfer', 'error')
        logging.error(f"Transfer integrity error for {account_number}: {str(e)}")
    except Exception as e:
        flash('Unexpected error during transfer', 'error')
        logging.error(f"Transfer unexpected error for {account_number}: {str(e)}")
    return redirect(url_for('dashboard'))

@app.route('/signout')
def signout():
    account_number = session.pop('account_number', None)
    if account_number:
        logging.info(f"User with account {account_number} signed out")
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=False)