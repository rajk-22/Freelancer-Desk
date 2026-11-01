# FreelanceDesk

A client and project tracker for freelancers. Built with Flask, SQLAlchemy and SQLite.

## Features
- Register / log in (hashed passwords, session-based auth)
- Add and delete clients
- Add projects with budget, deadline and status (Lead → In progress → Review → Paid)
- Dashboard with money and project count per stage, plus overdue projects
- Every query is scoped to the logged-in user

## Run locally
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000

## Deploy (Render or PythonAnywhere)
1. Push to GitHub.
2. `pip install gunicorn`, add it to requirements.txt, start with `gunicorn app:app`.
3. Set a real `SECRET_KEY` environment variable.
4. Create the tables once: `python -c "from app import app, db; app.app_context().push(); db.create_all()"`

## Ideas to extend
- Invoice PDF export, edit forms, search, CSV export, email reminders for deadlines, tests with pytest.
