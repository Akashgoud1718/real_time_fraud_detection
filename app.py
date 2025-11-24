from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import pandas as pd
import json
import os
from datetime import datetime
import hashlib

app = Flask(__name__)
app.secret_key = ''

USERS_FILE = 'users.json'

def load_users():
    """Load users from JSON file with proper error handling"""
    try:
        if os.path.exists(USERS_FILE) and os.path.getsize(USERS_FILE) > 0:
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
        else:
            
            return {}
    except (json.JSONDecodeError, Exception) as e:
        print(f"Error loading users: {e}")
        
        return {}

def save_users(users):
    """Save users to JSON file"""
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=4)
    except Exception as e:
        print(f"Error saving users: {e}")

def init_users_file():
    """Initialize the users file if it doesn't exist"""
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'w') as f:
            json.dump({}, f)

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()
        
        users = load_users()
        if username in users and users[username]['password'] == password:
            session['username'] = username
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        
        # Basic validation
        if not username or not password or not email:
            flash('All fields are required', 'error')
            return render_template('signup.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long', 'error')
            return render_template('signup.html')
        
        # Hash the password
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        users = load_users()
        if username in users:
            flash('Username already exists', 'error')
        else:
            users[username] = {
                'password': hashed_password,
                'email': email,
                'created_at': datetime.now().isoformat()
            }
            save_users(users)
            flash('Account created successfully! Please login.', 'success')
            return redirect(url_for('login'))
    
    return render_template('signup.html')

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', username=session['username'])

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
        
        if file and file.filename.endswith('.csv'):
            try:
                
                df = pd.read_csv(file)
                
                
                if df.empty:
                    flash('The uploaded CSV file is empty', 'error')
                    return redirect(request.url)
                
                
                session['uploaded_data'] = df.to_json()
                session['filename'] = file.filename
                
                flash('File uploaded successfully! Processing transactions...', 'success')
                return redirect(url_for('process_results'))
                
            except Exception as e:
                flash(f'Error processing file: {str(e)}', 'error')
        else:
            flash('Please upload a CSV file', 'error')
    
    return render_template('upload.html')

@app.route('/process-results')
def process_results():
    if 'username' not in session or 'uploaded_data' not in session:
        return redirect(url_for('login'))
    
    try:
        
        df = pd.read_json(session['uploaded_data'])
        
        
        results = []
        total_transactions = len(df)
        high_risk_count = 0
        medium_risk_count = 0
        low_risk_count = 0
        
        for index, row in df.iterrows():
            
            if 'probability' in df.columns:
                fraud_prob = float(row['probability'])
            elif 'fraud_probability' in df.columns:
                fraud_prob = float(row['fraud_probability'])
            else:
                
                base_prob = 0.1
                if 'amount' in df.columns:
                    amount = float(row['amount']) if pd.notna(row['amount']) else 0
                    
                    amount_factor = min(amount / 5000, 0.8)  
                    base_prob += amount_factor
                
                
                import random
                fraud_prob = round(min(base_prob + random.uniform(0, 0.3), 0.99), 2)
            
            
            if fraud_prob >= 0.7:
                risk_level = "HIGH RISK"
                alert_action = "🚨 DECLINE & BLOCK CARD"
                high_risk_count += 1
            elif fraud_prob >= 0.3:
                risk_level = "MEDIUM RISK"
                alert_action = "⚠️ FLAG FOR REVIEW"
                medium_risk_count += 1
            else:
                risk_level = "LOW RISK"
                alert_action = "✅ APPROVE"
                low_risk_count += 1
            
            
            transaction_id = row.get('transaction_id', f'TXN{index+1:04d}')
            amount = row.get('amount', 'N/A')
            merchant = row.get('merchant', row.get('merchant_name', 'Unknown'))
            location = row.get('location', row.get('merchant_location', 'Unknown'))
            
            
            try:
                if amount != 'N/A':
                    amount = f"${float(amount):.2f}"
            except (ValueError, TypeError):
                pass
            
            results.append({
                'transaction_id': transaction_id,
                'amount': amount,
                'merchant': merchant,
                'location': location,
                'fraud_probability': fraud_prob,
                'risk_level': risk_level,
                'alert_action': alert_action
            })
        
        
        summary = {
            'total_transactions': total_transactions,
            'high_risk_count': high_risk_count,
            'medium_risk_count': medium_risk_count,
            'low_risk_count': low_risk_count,
            'high_risk_percent': round((high_risk_count / total_transactions) * 100, 2) if total_transactions > 0 else 0,
            'filename': session.get('filename', 'Unknown')
        }
        
        return render_template('results.html', 
                             results=results, 
                             summary=summary,
                             username=session['username'])
        
    except Exception as e:
        flash(f'Error processing results: {str(e)}', 'error')
        return redirect(url_for('upload_file'))

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully', 'success')
    return redirect(url_for('login'))


@app.before_request
def initialize_app():
    init_users_file()

if __name__ == '__main__':
    
    init_users_file()
    app.run(debug=True)