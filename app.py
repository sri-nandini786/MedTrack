from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime
import os
import uuid

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Make sure to use a strong secret key in production

# In-memory data storage
users = {}
appointments = []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/debug')
def debug():
       return f"Current directory: {os.getcwd()}<br>Templates: {os.listdir('templates')}"
   

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        fullname = request.form['fullname']
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        role = request.form['role']

        if username in users:
            flash('Username already exists.', 'error')
        elif password != confirm_password:
            flash('Passwords do not match.', 'error')
        else:
            users[username] = {
                'fullname': fullname,
                'email': email,
                'password': password,
                'role': role
            }
            flash('Signup successful! Please log in.', 'success')
            return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = users.get(username)

        if user and user['password'] == password:
            session['username'] = username
            flash('Login successful.', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid credentials.', 'error')
    return render_template('login.html')

@app.route('/home')
def home():
    if 'username' not in session:
        flash('Please log in first.', 'error')
        return redirect(url_for('login'))
    return render_template('home.html', username=session['username'])

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))

@app.route('/book_appointment', methods=['GET', 'POST'])
def book_appointment():
    if 'username' not in session:
        flash('Please log in to book an appointment.', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        appointment = {
            'id': str(uuid.uuid4()),
            'user': session['username'],
            'patient': request.form['patient_name'],
            'doctor': request.form['doctor'],
            'date': request.form['date'],
            'time': request.form['time'],
            'reason': request.form.get('reason', '')
        }
        appointments.append(appointment)
        flash('Appointment booked successfully!', 'success')
        return redirect(url_for('book_appointment'))

    return render_template('book_appointment.html')

@app.route('/patient_dashboard')
def patient_dashboard():
    if 'username' not in session:
        flash('Please log in.', 'error')
        return redirect(url_for('login'))

    username = session['username']
    user_appts = [a for a in appointments if a['user'] == username]
    today = datetime.today().strftime('%Y-%m-%d')
    upcoming = [a for a in user_appts if a['date'] >= today]

    return render_template('patient_dashboard.html',
                           username=username,
                           total_appointments=len(user_appts),
                           upcoming_appointments=len(upcoming),
                           upcoming_appointments_list=upcoming)

@app.route('/doctor_dashboard')
def doctor_dashboard():
    if 'username' not in session:
        flash('Please log in.', 'error')
        return redirect(url_for('login'))

    # Display the last 3 appointments for the doctor
    recent_appointments = appointments[-3:] if len(appointments) >= 3 else appointments
    return render_template('doctor_dashboard.html',
                           upcoming_appointments=len(appointments),
                           patients_today=len([a for a in appointments if a['date'] == datetime.today().strftime('%Y-%m-%d')]),
                           pending_requests=1,  # This should be dynamic based on your logic
                           recent_appointments=recent_appointments)

@app.route('/patient_appointments')
def patient_appointments():
    if 'username' not in session:
        flash('Please log in.', 'error')
        return redirect(url_for('login'))

    username = session['username']
    user_appts = [a for a in appointments if a['user'] == username]

    return render_template('patient_appointments.html', appointments=user_appts)

@app.route('/patient_details')
def patient_details():
    if 'username' not in session:
        flash('Please log in to view your details.', 'error')
        return redirect(url_for('login'))

    username = session['username']
    user = users.get(username)

    if not user:
        flash('User  not found.', 'error')
        return redirect(url_for('login'))

    return render_template('patient_details.html', username=username,
                           fullname=user['fullname'], email=user['email'], role=user['role'])

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        if not request.form.get('name') or not request.form.get('email') or not request.form.get('message'):
            flash('Please fill in all fields.', 'error')
        else:
            flash('Thank you for contacting us!', 'success')
            # Here you might want to handle the contact form submission (e.g., send an email)
        return redirect(url_for('contact'))

    return render_template('contact.html')

if __name__ == '__main__':
    app.run(debug=True)
