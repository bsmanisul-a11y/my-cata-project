# ElderCare — Smart Elderly Care & Medication Management Platform

> An interconnected, proactive healthcare ecosystem connecting elderly individuals, family members, caregivers, and attending physicians with secure passcode-based access, proactive email alerts, visual pillbox scheduling, clinical doctor portal, emergency ambulance tracking, and senior-first accessibility.

---

## 🌟 Overview & Mission

Elder care requires a thoughtful balance between **senior independence**, **family peace of mind**, and **physician clinical oversight**.

**ElderCare** transforms elder healthcare management into a **shared, collaborative ecosystem**:
- **Elderly Individuals**: Remain at the center of their health decisions with large touch targets, natural voice readouts (Text-to-Speech), voice commands, visual 4-compartment pillbox, and 1-tap emergency assistance.
- **Family Members & Caregivers**: Enjoy effortless, secure access via **6-digit Passcodes** (e.g. `CARE74`), allowing multiple relatives and visiting nurses to monitor adherence, coordinate doctor transport, review clinical safety, and receive proactive email alerts.
- **Attending Physicians & Clinical Admins**: Dedicated **Doctor Portal** to update prescriptions, change dosages, schedule next visits, log in-clinic vitals, and upload official diagnostic reports accessible to patients.
- **Protected Patient Data**: Patient pages and APIs require a signed-in account, Senior PIN, or valid Care Circle Passcode. Caregivers may link during signup or afterward; unlinked accounts cannot access patient data. Uploaded medical files are stored outside the public static directory and served through the authenticated app.
- **Medicine Delivery Demo**: Low-stock prescriptions can be requested from St. Jude Hospital Pharmacy, checked before checkout, and tracked through an arrival alert. Cash on Delivery and UPI are simulated only; no real payment or courier dispatch occurs.
- **Emergency Ambulance Service**: Rapid-response dispatch with live 3-stage GPS tracking (`Dispatched / On the way` &rarr; `Nearby` &rarr; `Arrived`), sirens, and direct paramedic communication.
- **Doctor Visit Ride (Uber)**: 1-click ride integration in appointment schedules redirecting directly to Uber (`https://www.uber.com/in/en/`) from current location to the hospital clinic.

---

## 🚀 Key Innovations & Features

### 1. Dedicated Doctor & Clinical Admin Portal (`/doctor/portal`)
- **Separate Doctor Login**: Physicians sign in with their clinical credentials (e.g. `dr.evans@example.com` / `doc123`).
- **Update & Adjust Prescriptions**: Modify dosages (e.g., increase Metformin from 500mg to 850mg), edit timing instructions, or prescribe new medicines. Automatically updates patient pillbox and triggers a clinical plan notification.
- **Schedule Next Doctor Visit**: Set appointment date, time, specialty, clinic pavilion, and patient preparation notes (e.g., *12-hour fasting required*). Automatically notifies patient and family.
- **Upload Medical Diagnostic Reports**: Upload lab test results, ECG tracings, prescriptions, or imaging reports (with file attachments or comprehensive clinical summaries) which patients and family can download and view under the **Reports** tab.
- **In-Clinic Examination Vitals**: Doctors record clinic readings (BP, blood glucose, heart rate) which directly sync into patient trend graphs with a *"Doctor Examined"* badge.

### 2. Emergency Ambulance Service with Live Tracking (`/ambulance`)
- High-priority emergency dispatch accessible from the dashboard or SOS modal.
- **Live 3-Stage Progress Tracker**:
  1. **Ambulance Dispatched (On the Way)**: Live ETA countdown (~11 mins), paramedic team details, and vehicle unit plate.
  2. **Ambulance Nearby**: Approaching street notice (~2 mins), flashing red & blue emergency beacons, and automated audible siren alert.
  3. **Ambulance Arrived**: Doorbell alert and direct call link to paramedic on duty.
- **Simulated GPS Radar**: Visual radar sweep tracking vehicle location relative to patient residence.

### 3. "Get a Ride to Hospital" (Uber Integration)
- Every upcoming doctor appointment card features a prominent **"🚗 Get Ride to Hospital (Uber)"** button.
- When clicked, pre-populates hospital/clinic destination and redirects seamlessly to **[Uber](https://www.uber.com/in/en/)**.

### 4. Vitals Trend Graphs & Abnormal Audio Warning Chime (`/vitals`)
- **Individual Comparison Graphs (Chart.js)**:
  - **Blood Pressure Tracker**: Systolic and diastolic trends over time with hypertension alert zones (&ge;140/90 mmHg).
  - **Blood Glucose Tracker**: Fasting and post-meal glucose trends with elevated alerts (&ge;140 mg/dL).
  - **Resting Heart Rate Tracker**: BPM trend line with tachycardia alert threshold (>100 BPM).
- **Abnormal Alert Sound**:
  - Uses browser **Web Audio API** to synthesize an audible two-tone medical warning chime whenever abnormal readings are logged.
  - Accompanied by a high-contrast clinical alert banner and test button.

### 5. Medication Refill by Custom Typing or Preset Selection
- Refill prescription inventory either by:
  - **Typing any custom number of pills** (e.g. typing `45`, `90`, `120`).
  - **OR tapping one of the quick preset buttons** (`+15`, `+30`, `+60`, `+90`).

### 6. Emergency SOS Dispatches Immediately to All Family Members
- 1-tap pulsing red SOS button immediately alerts all registered Care Circle members, adult children, and emergency contacts via automated urgent email and SMS simulation.
- Contains live location, blood group, allergies, and emergency phone numbers, with a direct 1-tap option to dispatch the emergency ambulance.

### 7. Senior-Centric Accessibility ("Senior Mode")
- **Text-to-Speech Voice Assistant**: Web Speech API synthesizes natural audio narration of today's morning, afternoon, evening, and bedtime medications.
- **Voice Commands (Speech-to-Text)**: Seniors with arthritis or tremors can speak commands like *"Mark Metformin as taken"*, *"Read schedule"*, or *"Call for help"*.
- **Visual Pill Appearance**: Color and shape badges (e.g. *White Oval*, *Pink Round*, *Golden Gel*) so seniors recognize their pills at a glance.
- **Font Size Adjuster**: `A`, `A+`, `A++` toggles with local persistence.

---

## 🔑 Demo Accounts for Immediate Testing

| Role | Name | Passcode / PIN | Login Email / Password |
| :--- | :--- | :--- | :--- |
| **Attending Physician / Admin** | Dr. Robert Evans, MD | Doctor Portal Access | `dr.evans@example.com` / `doc123` |
| **Senior Individual** | Eleanor Vance (Age 74) | Passcode: **`CARE74`** <br> Senior PIN: **`1234`** | `eleanor@example.com` / `senior123` |
| **Family Caregiver** | David Vance (Son) | Connects via **`CARE74`** | `david.vance@example.com` / `care123` |
| **Visiting Home Nurse** | Nurse Maria Santos | Connects via **`CARE74`** | `nurse.maria@example.com` / `nurse123` |
| **Second Senior** | Arthur Pendelton (Age 81) | Passcode: **`CARE81`** <br> Senior PIN: **`4321`** | Registered Senior |

---

## ⚡ Quick Start & Running the Platform

1. **Navigate to the directory**:
   ```powershell
   Set-Location "c:\Users\admin\OneDrive\Desktop\Elderly_Care_Plat-form"
   ```
2. **Start the server**:
   ```powershell
   python app.py
   ```
   On startup, the app safely adds missing profile columns to older SQLite databases without deleting existing data.
3. Open your browser at **`http://127.0.0.1:5000`** for the public homepage. Use **Sign In** to open the Senior PIN, Caregiver, Doctor, and Patient sign-in options. After successful sign-in, the app opens the appropriate dashboard; patient data remains protected.

For persistent sessions across restarts or multiple server workers, set `SECRET_KEY` to a long, random value in the environment before launching the app. If it is omitted, the app generates a temporary key and existing sessions expire when the app restarts.

4. **Run Automated Test Suite (19 Comprehensive Tests)**:
   ```powershell
   python test_suite.py
   ```
   *(All 19 tests pass with 100% success against a fresh-schema test database.)*
