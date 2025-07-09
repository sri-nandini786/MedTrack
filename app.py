from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime
import boto3
import os
from dotenv import load_dotenv
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
from botocore.exceptions import ClientError

# Load environment variables
load_dotenv()

SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable not set!")

app = Flask(__name__)
app.secret_key = SECRET_KEY

# Initialize AWS clients
try:
    dynamodb = boto3.resource(
        'dynamodb',
        aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
        region_name=os.environ.get('AWS_REGION')
    )
    sns = boto3.client(
        'sns',
        aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
        region_name=os.environ.get('AWS_REGION')
    )
except Exception as e:
    raise RuntimeError(f"Error initializing AWS clients: {e}")

sns_topic_arn = os.environ.get('SNS_TOPIC_ARN')

# DynamoDB tables
try:
    users_table = dynamodb.Table('Users')
    appointments_table = dynamodb.Table('Appointments')
except Exception as e:
    raise RuntimeError(f"Error accessing DynamoDB tables: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        fullname = request.form.get('fullname', '').strip()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        role = request.form.get('role', '').strip()

        if not all([fullname, username, email, password, confirm_password, role]):
            flash('All fields are required.', 'error')
            return render_template('signup.html')

        try:
            response = users_table.get_item(Key={'username': username})
        except ClientError:
            flash('Database error. Please try again.', 'error')
            return render_template('signup.html')

        if 'Item' in response:
            flash('Username already exists.', 'error')
        elif password != confirm_password:
            flash('Passwords do not match.', 'error')
        else:
            hashed_password = generate_password_hash(password)
            try:
                users_table.put_item(Item={
                    'username': username,
                    'fullname': fullname,
                    'email': email,
                    'password': hashed_password,
                    'role': role
                })
                flash('Signup successful! Please log in.', 'success')
                return redirect(url_for('login'))
            except ClientError:
                flash('Database error. Please try again.', 'error')

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        try:
            response = users_table.get_item(Key={'username': username})
            user = response.get('Item')
        except ClientError:
            flash('Database error. Please try again.', 'error')
            return render_template('login.html')

        if user and check_password_hash(user['password'], password):
            session['username'] = username
            flash('Login successful.', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid credentials.', 'error')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))

@app.route('/home')
def home():
    if 'username' not in session:
        flash('Please log in.', 'error')
        return redirect(url_for('login'))
    return render_template('home.html', username=session['username'])

@app.route('/book_appointment', methods=['GET', 'POST'])
def book_appointment():
    if 'username' not in session:
        flash('Please log in to book an appointment.', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        appointment_id = str(uuid.uuid4())
        username = session['username']
        patient_name = request.form.get('patient_name', '').strip()
        doctor = request.form.get('doctor', '').strip()
        date = request.form.get('date', '').strip()
        time = request.form.get('time', '').strip()
        reason = request.form.get('reason', '')

        if not all([patient_name, doctor, date, time]):
            flash('All fields except reason are required.', 'error')
            return render_template('book_appointment.html')

        try:
            appointments_table.put_item(Item={
                'appointment_id': appointment_id,
                'username': username,
                'patient_name': patient_name,
                'doctor': doctor,
                'date': date,
                'time': time,
                'reason': reason
            })

            # Send SNS notification
            if sns_topic_arn:
                message = f"New appointment booked:\nPatient: {patient_name}\nDoctor: {doctor}\nDate: {date} {time}"
                try:
                    sns.publish(TopicArn=sns_topic_arn, Message=message, Subject="New Appointment Booked")
                except ClientError:
                    flash('Appointment booked, but failed to send notification.', 'warning')
            flash('Appointment booked successfully!', 'success')
            return redirect(url_for('book_appointment'))
        except ClientError:
            flash('Failed to book appointment. Please try again.', 'error')

    return render_template('book_appointment.html')

@app.route('/patient_dashboard')
def patient_dashboard():
    if 'username' not in session:
        flash('Please log in.', 'error')
        return redirect(url_for('login'))

    username = session['username']
    try:
        response = appointments_table.scan()
        user_appts = [item for item in response.get('Items', []) if item['username'] == username]
    except ClientError:
        flash('Database error. Please try again.', 'error')
        user_appts = []

    today = datetime.today().strftime('%Y-%m-%d')
    upcoming = [a for a in user_appts if a['date'] >= today]

    return render_template('patient_dashboard.html',
                           username=username,
                           total_appointments=len(user_appts),
                           upcoming_appointments=len(upcoming),
                           upcoming_appointments_list=upcoming)

@app.route('/patient_appointments')
def patient_appointments():
    if 'username' not in session:
        flash('Please log in.', 'error')
        return redirect(url_for('login'))

    username = session['username']
    try:
        response = appointments_table.scan()
        user_appts = [item for item in response.get('Items', []) if item['username'] == username]
    except ClientError:
        flash('Database error. Please try again.', 'error')
        user_appts = []

    return render_template('patient_appointments.html', appointments=user_appts)

@app.route('/patient_details')
def patient_details():
    if 'username' not in session:
        flash('Please log in.', 'error')
        return redirect(url_for('login'))

    username = session['username']
    try:
        response = users_table.get_item(Key={'username': username})
        user = response.get('Item')
    except ClientError:
        flash('Database error. Please try again.', 'error')
        return redirect(url_for('login'))

    if not user:
        flash('User not found.', 'error')
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
        return redirect(url_for('contact'))

    return render_template('contact.html')

if __name__ == '__main__':
    app.run(debug=True)
