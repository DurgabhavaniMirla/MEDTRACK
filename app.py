from flask import Flask, render_template, request, redirect, session, url_for
import uuid

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# In-memory storage
users = []
appointments = []

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

        users.append({
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
        user = next((u for u in users if u['email'] == email and u['password'] == password), None)

        if user:
            session['email'] = user['email']
            session['role'] = user['role']
            session['name'] = user['name']
            return redirect('/doctor_dashboard' if user['role'] == 'doctor' else '/patient_dashboard')
        return 'Invalid credentials'
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/patient_dashboard', methods=['GET', 'POST'])
def patient_dashboard():
    if 'email' not in session or session['role'] != 'patient':
        return redirect('/login')

    # 1) Get current patient object
    current_user = next((u for u in users if u['email'] == session['email']), None)

    # 2) Handle new booking
    if request.method == 'POST':
        doctor_email = request.form['doctor_email']
        date = request.form['date']
        symptoms = request.form['symptoms']

        appt = [
            str(uuid.uuid4()),   # id
            session['email'],    # patient_email
            doctor_email,        # doctor_email
            date,                # date
            symptoms,            # symptoms
            'Pending',           # status
            ''                   # prescription
        ]
        appointments.append(appt)
        return redirect('/patient_dashboard')

    # 3) Build lists for rendering
    patient_appointments = [a for a in appointments if a[1] == session['email']]
    doctors = [u for u in users if u['role'] == 'doctor']

    # 4) Render template with both lists
    return render_template(
        'patient_dashboard.html',
        user=current_user,
        appointments=patient_appointments,
        doctors=doctors
    )

@app.route('/doctor_dashboard', methods=['GET', 'POST'])
def doctor_dashboard():
    if 'email' not in session or session['role'] != 'doctor':
        return redirect('/login')

    if request.method == 'POST':
        appointment_id = request.form['appointment_id']
        prescription = request.form['prescription']

        for appt in appointments:
            if appt[0] == appointment_id:
                appt[6] = prescription     # update prescription
                appt[5] = 'Completed'      # update status
                break

    doctor_appointments = [a for a in appointments if a[2] == session['email']]
    return render_template('doctor_dashboard.html',
                           appointments=doctor_appointments,
                           name=session['name'])

if __name__ == '__main__':
    app.run(debug=True)
