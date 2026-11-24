# Salon Queue Management System

## 1. Project Overview

The **Salon Queue Management System** is a web-based application developed using Django and Python. It is designed to support the management of customer queues in a salon.

The project aims to provide a structured way to handle salon queue operations through a web interface.

## 2. Key Features

The application is developed around salon queue management.

- Web-based application built using Django.
- Organized application structure using Django apps.
- HTML templates for rendering application pages.
- Static files for frontend styling and resources.
- Database integration for application data.

*Note: Add specific customer, staff, and queue-management actions here after verifying the implemented workflows.*

## 3. Technology Stack

| Technology | Purpose |
|---|---|
| Python | Backend programming |
| Django | Web framework |
| SQLite | Database |
| HTML | Page structure |
| CSS | Styling |
| Gunicorn | Production application server |
| WhiteNoise | Static file serving |

## 4. Project Structure

```text
salon-queue/
│
├── manage.py
├── requirements.txt
├── prompts.md
├── AGENTS.md
│
├── docs/
│   ├── 01-brief.md
│   ├── 02-screens.md
│   └── 03-flows-rules.md
│
├── queue_app/
│   ├── migrations/
│   ├── models.py
│   ├── views.py
│   └── ...
│
├── salon_queue/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── templates/
│
└── static/
```

## 5. Installation and Setup

Follow these steps to run the project locally.

### Prerequisites

- Python 3 installed
- pip (Python package manager)

### Step 1: Clone the repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
```

### Step 2: Navigate to the project directory

```bash
cd salon-queue
```

### Step 3: Create a virtual environment

```bash
python -m venv .venv
```

Activate it:

**Windows:**
```bash
.venv\Scripts\activate
```

**Linux / macOS:**
```bash
source .venv/bin/activate
```

### Step 4: Install dependencies

```bash
pip install -r requirements.txt
```

### Step 5: Apply database migrations

```bash
python manage.py migrate
```

### Step 6: Start the development server

```bash
python manage.py runserver
```

Open the following address in your browser:

```text
http://127.0.0.1:8000/
```

## 6. Database

The project uses SQLite as its database.

Django migrations are used to create and manage the database schema.

## 7. Application Configuration

The Django project configuration is maintained in:

```text
salon_queue/settings.py
```

The project uses environment variables for deployment-related configuration, including the Django secret key and debug setting.

## 8. Project Documentation

The repository also contains supporting project documentation:

- `AGENTS.md` – Project instructions.
- `docs/01-brief.md` – Project brief.
- `docs/02-screens.md` – Screen documentation.
- `docs/03-flows-rules.md` – Application flows and rules.
- `prompts.md` – Prompts used during project development.

## 9. Deployment

Deployment information and the live application URL will be added after successful deployment.

## 10. Project Status

The Salon Queue Management System is developed as part of the MSc IT Vibe Coding Lab project.
