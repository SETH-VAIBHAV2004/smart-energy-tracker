from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime, timedelta
import requests  # ✅ Added for API calls
import json
from analytics.energy_analytics import EnergyAnalyticsSystem
import psycopg2
from urllib.parse import urlparse

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# Initialize analytics system
analytics_system = EnergyAnalyticsSystem()

# Database configuration
def get_db_connection():
    if os.environ.get('DATABASE_URL'):
        # Production - PostgreSQL
        result = urlparse(os.environ.get('DATABASE_URL'))
        username = result.username
        password = result.password
        database = result.path[1:]
        hostname = result.hostname
        port = result.port
        
        conn = psycopg2.connect(
            database=database,
            user=username,
            password=password,
            host=hostname,
            port=port
        )
    else:
        # Development - SQLite
        conn = sqlite3.connect('solar_energy.db')
        conn.row_factory = sqlite3.Row
    return conn

# Database Setup
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if os.environ.get('DATABASE_URL'):
        # PostgreSQL tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS energy_data (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                date TEXT,
                solar_energy REAL,
                electric_energy REAL,
                temperature REAL,
                humidity REAL
            )
        ''')
    else:
        # SQLite tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS energy_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                date TEXT,
                solar_energy REAL,
                electric_energy REAL,
                temperature REAL,
                humidity REAL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Check if temperature and humidity columns exist
        cursor.execute("PRAGMA table_info(energy_data)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'temperature' not in columns:
            cursor.execute("ALTER TABLE energy_data ADD COLUMN temperature REAL DEFAULT 25")
        if 'humidity' not in columns:
            cursor.execute("ALTER TABLE energy_data ADD COLUMN humidity REAL DEFAULT 60")
    
    conn.commit()
    conn.close()

# Index Route
@app.route('/')
def index():
    return render_template('index.html')

# Registration Page
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')
    elif request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = generate_password_hash(data.get('password'))

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
            conn.commit()
            conn.close()
            return jsonify({'status': 'success', 'message': 'User registered successfully'})
        except Exception as e:
            return jsonify({'status': 'fail', 'message': str(e)})

# User Login
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data['username']
    password = data['password']

    with sqlite3.connect('solar_energy.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, password FROM users WHERE username=?", (username,))
        user = cursor.fetchone()

    if user and check_password_hash(user[1], password):
        session['user_id'] = user[0]
        session['username'] = username
        return jsonify({'status': 'success'})
    else:
        return jsonify({'status': 'fail', 'message': 'Invalid credentials'})

# Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# Dashboard
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    return render_template('dashboard.html', username=session['username'])

# Add Energy Data
@app.route('/add_energy', methods=['POST'])
def add_energy():
    if 'user_id' not in session:
        return jsonify({'status': 'fail', 'message': 'User not logged in'})

    data = request.get_json()
    date = data['date']
    solar_energy = data['solar_energy']
    electric_energy = data['electric_energy']
    temperature = data.get('temperature', 25)
    humidity = data.get('humidity', 60)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO energy_data (user_id, date, solar_energy, electric_energy, temperature, humidity)
        VALUES (%s, %s, %s, %s, %s, %s)
    ''', (session['user_id'], date, solar_energy, electric_energy, temperature, humidity))
    conn.commit()
    conn.close()

    return jsonify({'status': 'success', 'message': 'Energy data added'})

# Get Energy Data
@app.route('/get_energy_data', methods=['GET'])
def get_energy_data():
    if 'user_id' not in session:
        return jsonify({'status': 'fail', 'message': 'Unauthorized'}), 401

    try:
        user_id = session['user_id']
        from_date = request.args.get('from_date')
        to_date = request.args.get('to_date')

        with sqlite3.connect('solar_energy.db') as conn:
            cursor = conn.cursor()
            if from_date and to_date:
                cursor.execute('''
                    SELECT id, date, solar_energy, electric_energy, temperature, humidity
                    FROM energy_data
                    WHERE user_id=? AND date BETWEEN ? AND ?
                    ORDER BY date
                ''', (user_id, from_date, to_date))
            else:
                cursor.execute('''
                    SELECT id, date, solar_energy, electric_energy, temperature, humidity
                    FROM energy_data
                    WHERE user_id=?
                    ORDER BY date
                ''', (user_id,))
            data = cursor.fetchall()

        # Convert to list of dictionaries
        energy_data = []
        for row in data:
            energy_data.append({
                'id': row[0],
                'date': row[1],
                'solar_energy': row[2],
                'electric_energy': row[3],
                'temperature': row[4],
                'humidity': row[5]
            })

        return jsonify({'status': 'success', 'data': energy_data})

    except Exception as e:
        app.logger.error(f"Error in get_energy_data: {str(e)}")
        return jsonify({'status': 'fail', 'message': 'Error retrieving energy data'}), 500

# Get Analytics
@app.route('/get_analytics', methods=['GET'])
def get_analytics():
    if 'user_id' not in session:
        return jsonify({'status': 'fail', 'message': 'Unauthorized'}), 401

    try:
        # Get energy data
        with sqlite3.connect('solar_energy.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT date, solar_energy, electric_energy, temperature, humidity
                FROM energy_data
                WHERE user_id=?
                ORDER BY date
            ''', (session['user_id'],))
            rows = cursor.fetchall()

        if not rows:
            return jsonify({
                'status': 'success',
                'analysis': {
                    'current_pattern': 0.0,
                    'next_hour_prediction': 0.0,
                    'carbon_footprint': 0.0,
                    'energy_cost': 0.0,
                    'recommendations': {
                        'carbon': ["No data available"],
                        'cost': ["No data available"]
                    }
                }
            })

        # Convert rows to list of dictionaries
        data = []
        for row in rows:
            data.append({
                'date': row[0],
                'solar_energy': float(row[1]),
                'electric_energy': float(row[2]),
                'temperature': float(row[3]) if row[3] is not None else 25.0,
                'humidity': float(row[4]) if row[4] is not None else 60.0
            })

        # Perform analytics
        analysis = analytics_system.analyze_consumption(data)
        
        return jsonify({
            'status': 'success',
            'analysis': analysis
        })

    except Exception as e:
        app.logger.error(f"Analytics error: {str(e)}")
        return jsonify({
            'status': 'success',
            'analysis': {
                'current_pattern': 0.0,
                'next_hour_prediction': 0.0,
                'carbon_footprint': 0.0,
                'energy_cost': 0.0,
                'recommendations': {
                    'carbon': [f"Error: {str(e)}"],
                    'cost': ["Unable to generate recommendations"]
                }
            }
        })

# Delete Entry
@app.route('/delete_entry', methods=['POST'])
def delete_entry():
    if 'user_id' not in session:
        return jsonify({'status': 'fail', 'message': 'Unauthorized'}), 401

    data = request.get_json()
    entry_id = data.get("id")

    if not entry_id:
        return jsonify({'status': 'fail', 'message': 'Missing entry ID'}), 400

    with sqlite3.connect("solar_energy.db") as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM energy_data WHERE id = ? AND user_id = ?", (entry_id, session["user_id"]))
        conn.commit()

    return jsonify({'status': 'success', 'message': 'Entry deleted'})

# Compare Total Energy
@app.route('/compare', methods=['GET'])
def compare():
    if 'user_id' not in session:
        return jsonify({'status': 'fail', 'message': 'User not logged in'})

    with sqlite3.connect('solar_energy.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT SUM(solar_energy), SUM(electric_energy)
            FROM energy_data
            WHERE user_id=?
        ''', (session['user_id'],))
        result = cursor.fetchone()

    return jsonify({
        'status': 'success',
        'solar_total': result[0] or 0,
        'electric_total': result[1] or 0
    })

# Energy Usage Tips
@app.route('/energy_tips', methods=['GET'])
def energy_tips():
    if 'user_id' not in session:
        return jsonify({'status': 'fail', 'message': 'User not logged in'}), 401

    user_id = session['user_id']
    today = datetime.now().date()
    start_of_this_week = today - timedelta(days=today.weekday())
    start_of_last_week = start_of_this_week - timedelta(weeks=1)
    end_of_last_week = start_of_this_week - timedelta(days=1)

    # Get user's location
    try:
        ip = request.remote_addr
        if ip == '127.0.0.1':  # For local development
            ip = requests.get('https://api.ipify.org').text
        location_response = requests.get(f'https://ipinfo.io/{ip}/json')
        location_data = location_response.json() if location_response.status_code == 200 else {}
    except:
        location_data = {}

    with sqlite3.connect('solar_energy.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT SUM(electric_energy) FROM energy_data
            WHERE user_id=? AND date BETWEEN ? AND ?
        ''', (user_id, str(start_of_last_week), str(end_of_last_week)))
        last_week_total = cursor.fetchone()[0] or 0

        cursor.execute('''
            SELECT SUM(electric_energy) FROM energy_data
            WHERE user_id=? AND date BETWEEN ? AND ?
        ''', (user_id, str(start_of_this_week), str(today)))
        this_week_total = cursor.fetchone()[0] or 0

    # Base message
    if last_week_total == 0:
        message = "Start tracking your electricity usage to get personalized tips!"
    else:
        change_percent = ((this_week_total - last_week_total) / last_week_total) * 100
        if change_percent > 10:
            message = f"You used {change_percent:.1f}% more grid power than last week. Try reducing usage by turning off appliances when not needed."
        elif change_percent < -10:
            message = f"Great job! You reduced your grid power usage by {abs(change_percent):.1f}% compared to last week."
        else:
            message = "Your electricity usage is consistent with last week. Keep monitoring for better savings."

    # Add location-specific tips
    if location_data:
        city = location_data.get('city', '').lower()
        country = location_data.get('country', '').lower()
        
        # Add regional tips
        if 'india' in country:
            message += " In India, consider using solar water heaters and LED lighting for better energy efficiency."
        elif 'usa' in country:
            message += " In the US, check for local solar incentives and tax credits to maximize your savings."
        
        # Add city-specific tips
        if 'bangalore' in city:
            message += " Bangalore has good solar potential - consider installing solar panels on your rooftop."
        elif 'mumbai' in city:
            message += " Mumbai's coastal climate is great for solar energy - take advantage of the abundant sunlight."

    return jsonify({'status': 'success', 'tip': message})

# ✅ NEW: Solar Forecast Route
@app.route('/solar_forecast', methods=['GET'])
def solar_forecast_page():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    return render_template('solar_forecast.html')

@app.route('/api/solar_forecast', methods=['GET'])
def solar_forecast_api():
    if 'user_id' not in session:
        return jsonify({'status': 'fail', 'message': 'Unauthorized'}), 401

    lat = request.args.get('lat', '12.9716')  # Default: Bangalore
    lon = request.args.get('lon', '77.5946')

    # Open-Meteo solar radiation API (no API key needed)
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}&hourly=shortwave_radiation"
    )

    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            return jsonify({'status': 'success', 'forecast': data})
        else:
            return jsonify({'status': 'fail', 'message': 'API Error'}), response.status_code
    except Exception as e:
        return jsonify({'status': 'fail', 'message': str(e)}), 500

# Geolocation API endpoint
@app.route('/api/geolocation', methods=['GET'])
def get_geolocation():
    if 'user_id' not in session:
        return jsonify({'status': 'fail', 'message': 'Unauthorized'}), 401

    try:
        # Get user's IP address from request
        ip = request.remote_addr
        if ip == '127.0.0.1':  # For local development
            ip = requests.get('https://api.ipify.org').text

        # Get location data from ipinfo.io
        response = requests.get(f'https://ipinfo.io/{ip}/json')
        if response.status_code == 200:
            location_data = response.json()
            return jsonify({
                'status': 'success',
                'data': {
                    'city': location_data.get('city', 'Unknown'),
                    'region': location_data.get('region', 'Unknown'),
                    'country': location_data.get('country', 'Unknown'),
                    'loc': location_data.get('loc', '0,0')  # Latitude,Longitude
                }
            })
        else:
            return jsonify({'status': 'fail', 'message': 'Failed to fetch location data'}), response.status_code
    except Exception as e:
        return jsonify({'status': 'fail', 'message': str(e)}), 500

if __name__ == '__main__':
    init_db()
    app.run()
