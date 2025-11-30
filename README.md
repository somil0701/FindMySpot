# 🚗 ParkEZ - Vehicle Parking System (MAD II Project)
An advanced multi-user Vehicle Parking Management System built as part of the **Modern Application Development - II (MAD II)** course. This project supports **Admin** and **User** roles, integrates **Flask**, **Vue.js**, **Redis**, **Celery**, **SQLite**, and provides complete **parking lifecycle management**, **analytics**, and **batch jobs**.

---

# 📌 Table of Contents
- [📖 Project Overview](#-project-overview)
- [🧩 Features](#-features)
  - [Admin Features](#admin-features)
  - [User Features](#user-features)
- [🛠️ Tech Stack](#️-tech-stack)
- [📂 Folder Structure](#-folder-structure)
- [⚙️ Setup Instructions](#️-setup-instructions)
  - [Backend Setup (Flask)](#backend-setup-flask)
  - [Frontend Setup (Vue.js)](#frontend-setup-vuejs)
  - [Redis Setup](#redis-setup)
  - [Celery Worker & Beat Setup](#celery-worker--beat-setup)
- [🗄️ Database Schema](#️-database-schema)
- [🧪 Testing Instructions](#-testing-instructions)
- [📊 Admin Analytics](#-admin-analytics)
- [⏱️ Background Jobs](#️-background-jobs)
- [📸 Screenshots](#-screenshots)
- [🚀 Future Enhancements](#-future-enhancements)

---

# 📖 Project Overview
ParkEZ is an end‑to‑end web application for managing 4‑wheeler parking across multiple parking lots. It supports reservation, occupancy tracking, cost calculation, reporting, and admin dashboards with analytics. Built entirely using the mandatory MAD II technologies.

This is **Version 2** of the project.

---

# 🧩 Features
## 👨‍💼 Admin Features
- Create, edit, delete parking lots
- Automatically generate parking spots based on lot capacity
- View all parking lots & spot availability
- View detailed spot information (occupied/available)
- View **all registered users**
- Delete users (with safety checks)
- View user reservation history
- View **summary charts & analytics**:
  - Occupancy per lot
  - Revenue per lot
  - 30‑day reservation trend
- Trigger **daily reminder emails** (manual + scheduled)
- Trigger **monthly reports** (manual + scheduled)
- Trigger **CSV export** batch job
- Admin Panel with split-menu navigation

---

## 👤 User Features
- Register & login
- View available parking lots
- Automatically assigned the **first free spot** in a lot
- Reserve/occupy a spot
- Release parking spot
- Timestamp-based billing
- View booking history
- Download usage reports
- View personal analytics
- Fully responsive UI

---

# 🛠️ Tech Stack
### **Frontend**
- Vue.js 3 (CDN + Options API)
- Bootstrap 5 (UI styling)
- Chart.js (analytics charts)

### **Backend**
- Flask (API)
- SQLite (database)
- SQLAlchemy ORM
- Redis (caching + queue)
- Celery (async tasks)
- SMTP (email sending)

---

# 📂 Folder Structure
```
vehicle-parking-app-v2/
│
├── server/
│   ├── app.py                  # Flask entry point
│   ├── controllers/            # Routes & API logic
│   ├── models/                 # Database ORM models
│   ├── tasks/                  # Celery tasks
│   ├── utils/                  # Cache + helpers
│   ├── instance/               # SQLite DB location
│   ├── venv/                   # Python virtual environment
│   └── ...
│
└── client/
    ├── src/
    │   ├── views/              # Vue views
    │   ├── components/         # UI components
    │   ├── App.vue             # Main UI controller
    │   ├── main.js             # Vue entry point
    │   └── ...
    ├── index.html
    ├── package.json
    └── ...
```

---

# ⚙️ Setup Instructions
## Backend Setup (Flask)
```bash
cd server
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create `.env` file inside `server/`:
```
SECRET_KEY=your_secret_key
JWT_SECRET_KEY=your_jwt_key
REDIS_URL=redis://localhost:6379/0
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASS=your_app_password
```

### Run Flask API
```bash
python app.py
```

---

## Frontend Setup (Vue.js)
```bash
cd client
npm install
npm run dev
```
Open browser: **http://localhost:5173**

---

## Redis Setup
Install Redis (Windows via Memurai or WSL):
```bash
redis-server
```

---

## Celery Worker & Beat Setup
### Celery Worker
```bash
celery -A server.tasks.tasks worker --loglevel=info -P solo
```

### Celery Beat
```bash
celery -A server.tasks.tasks beat --loglevel=info
```

---

# 🗄️ Database Schema
### User
```
id | username | email | password | role
```

### ParkingLot
```
id | name | address | price_per_hour | number_of_spots
```

### ParkingSpot
```
id | lot_id | status (A/O)
```

### Reservation
```
id | user_id | spot_id | start_time | end_time | cost
```

---

# 🧪 Testing Instructions
## Login Credentials
- **Admin**: auto‑created (admin / admin)
- User must register manually

## Verify Admin Features
1. Create a parking lot
2. View spots & statuses
3. Book a spot as user → admin sees updated status
4. Trigger Daily Reminder → check Celery logs & email
5. Trigger Monthly Reports → check email
6. View Admin Analytics → charts should load
7. Delete a normal user → should succeed
8. Try deleting admin → blocked (error message)

## Verify User Features
1. Register → Login
2. Book parking
3. Release booking
4. Check history
5. Download report

---

# 📊 Admin Analytics
Displayed using **Chart.js**:
- Occupancy Bar Chart
- Revenue Chart
- 30‑day Trend Chart

Data source: `GET /admin/analytics/summary`

---

# ⏱️ Background Jobs
## 1️⃣ Daily Reminder (Celery Beat)
- Runs every evening
- Sends email to inactive users
- Also manually triggered via Admin Panel

## 2️⃣ Monthly Report Generation
- Generates HTML/PDF report
- Emails users
- Also manually triggered

## 3️⃣ CSV Export (User-triggered)
- Generates CSV of all past reservations
- Asynchronous job
- Notifies user upon completion

---

# 📸 Screenshots
(Add your screenshots here when preparing your submission)

---

# 🚀 Future Enhancements
- Dark mode UI
- QR code parking validation
- RazorPay Integration
- Real-time notifications
- Progressive Web App version

---

# 🎉 Final Notes
ParkEZ is a full-stack, production‑ready parking management system built strictly using the technologies mandated by **Modern Application Development II**. It includes:
- Authentication
- Parking lifecycle management
- Admin dashboards
- Analytics
- Full async job architecture
- Redis caching
- Clean and responsive UI

You can extend this easily for real-world deployments.

**Happy Coding! 🚗💨**

