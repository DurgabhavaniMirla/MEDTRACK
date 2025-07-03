from flask import Flask, render_template, request, redirect, session, url_for
import boto3
import uuid

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# AWS Config
dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
sns = boto3.client('sns', region_name='ap-south-1')

# Replace with your actual table names and SNS ARN
users_table = dynamodb.Table('Users')
appointments_table = dynamodb.Table('Appointments')
TOPIC_ARN = 'arn:aws:sns:ap-south-1:YOUR_ACCOUNT_ID:medtrack-topic'

# ------------------ ROUTES ------------------

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        name = request.form.get('name')
        gender = request.form.get('gender', '')
        age = request.form.get('age', '')
        specialization = request.form.get('specialization', '') if role == 'doctor' else ''

        users_table.put_item(Item={
            'email': email,
            'password': password,
            'role': role,
            'name': name,
            'gender': gender,
            'age': age,
            'specialization': specialization
        })
        return redirect('/login')
    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        response = users_table.get_item(Key={'email': email})
        user = response.get('Item')

        if user and user['password'] == password:
            session['email'] = user['email']
            session['role'] = user['role']
            session['name'] = user['name']
            return redirect('/doctor_dashboard' if user['role'] == 'doctor' else '/patient_dashboard')
        else:
            return 'Invalid credentials'
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


@app.route('/patient_dashboard')
def patient_dashboard():
    if 'email' not in session or session['role'] != 'patient':
        return redirect('/login')

    response = appointments_table.scan(
        FilterExpression=boto3.dynamodb.conditions.Attr('patient_email').eq(session['email'])
    )
    appointments = response['Items']
    return render_template('patient_dashboard.html', appointments=appointments)


@app.route('/doctor_dashboard')
def doctor_dashboard():
    if 'email' not in session or session['role'] != 'doctor':
        return redirect('/login')

    response = appointments_table.scan(
        FilterExpression=boto3.dynamodb.conditions.Attr('doctor_email').eq(session['email'])
    )
    appointments = response['Items']
    return render_template('doctor_dashboard.html', appointments=appointments)


@app.route('/book_appointment', methods=['POST'])
def book_appointment():
    if 'email' not in session or session['role'] != 'patient':
        return redirect('/login')

    specialization = request.form['specialization']
    date = request.form['date']
    time = request.form['time']
    symptoms = request.form['symptoms']

    # Get doctor with matching specialization
    doctors = users_table.scan(
        FilterExpression=boto3.dynamodb.conditions.Attr('specialization').eq(specialization)
    ).get('Items', [])

    if not doctors:
        return "No doctor found for this specialization"

    doctor = doctors[0]
    doctor_email = doctor['email']

    appointment_data = {
        'id': str(uuid.uuid4()),
        'patient_email': session['email'],
        'doctor_email': doctor_email,
        'appointment_date': date,
        'time': time,
        'symptoms': symptoms,
        'status': 'Pending',
        'prescription': ''
    }

    appointments_table.put_item(Item=appointment_data)
    return redirect('/patient_dashboard')


@app.route('/submit_prescription/<string:appointment_id>', methods=['POST'])
def submit_prescription(appointment_id):
    if 'email' not in session or session['role'] != 'doctor':
        return redirect('/login')

    prescription = request.form['prescription']

    # Get appointment to get patient email
    response = appointments_table.get_item(Key={'id': appointment_id})
    appointment = response.get('Item')

    if not appointment:
        return 'Appointment not found'

    # Update appointment with prescription
    appointments_table.update_item(
        Key={'id': appointment_id},
        UpdateExpression="SET prescription = :p, #s = :s",
        ExpressionAttributeNames={'#s': 'status'},
        ExpressionAttributeValues={':p': prescription, ':s': 'Completed'}
    )

    # Send SNS Notification
    try:
        sns.publish(
            TopicArn=TOPIC_ARN,
            Subject='MedTrack Prescription Uploaded',
            Message=f"Hello {appointment['patient_email']},\n\nYour doctor has uploaded your prescription:\n\n{prescription}\n\n- MedTrack"
        )
    except Exception as e:
        print("SNS Error:", e)

    return redirect('/doctor_dashboard')


# ------------------ START APP ------------------
if __name__ == '__main__':
    app.run(debug=True)
