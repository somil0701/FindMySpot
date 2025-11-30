# ParkEZ — Vehicle Parking App (Restored)

## Overview
This project includes a Flask backend, Vue 3 frontend, Redis + Celery background jobs (CSV/PDF/Reminders), and Docker Compose configuration.

## Quick Start (local, without Docker)
1. Backend
```bash
cd vehicle_parking_project_restored/server
python3 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
