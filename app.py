"""FreelanceDesk: a client and project tracker built with Flask + SQLite."""
import os
from datetime import date, datetime
from functools import wraps

from flask import (Flask, flash, redirect, render_template, request,
                   session, url_for)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-in-production")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///freelancedesk.db"
db = SQLAlchemy(app)

STATUSES = ["Lead", "In progress", "Review", "Paid"]


# ---------- Models ----------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(40), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)


class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120))
    company = db.Column(db.String(80))
    projects = db.relationship("Project", backref="client", cascade="all, delete")


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    budget = db.Column(db.Float, default=0)
    status = db.Column(db.String(20), default="Lead")
    deadline = db.Column(db.Date)

    @property
    def is_overdue(self):
        return bool(self.deadline and self.deadline < date.today() and self.status != "Paid")


# ---------- Auth helpers ----------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Log in to continue.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_user():
    return {"current_user": session.get("username")}


# ---------- Auth routes ----------
@app.route("/")
def index():
    return redirect(url_for("dashboard" if "user_id" in session else "login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        if len(username) < 3 or len(password) < 6:
            flash("Username needs 3+ characters and password 6+.", "error")
        elif User.query.filter_by(username=username).first():
            flash("That username is taken. Try another.", "error")
        else:
            user = User(username=username, password_hash=generate_password_hash(password))
            db.session.add(user)
            db.session.commit()
            flash("Account created. You can log in now.", "ok")
            return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(username=request.form["username"].strip()).first()
        if user and check_password_hash(user.password_hash, request.form["password"]):
            session.clear()
            session["user_id"], session["username"] = user.id, user.username
            return redirect(url_for("dashboard"))
        flash("Wrong username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- Dashboard ----------
@app.route("/dashboard")
@login_required
def dashboard():
    uid = session["user_id"]
    totals = dict(
        db.session.query(Project.status, func.coalesce(func.sum(Project.budget), 0))
        .filter_by(user_id=uid).group_by(Project.status).all()
    )
    counts = dict(
        db.session.query(Project.status, func.count(Project.id))
        .filter_by(user_id=uid).group_by(Project.status).all()
    )
    overdue = [p for p in Project.query.filter_by(user_id=uid).all() if p.is_overdue]
    recent = Project.query.filter_by(user_id=uid).order_by(Project.id.desc()).limit(5).all()
    return render_template("dashboard.html", statuses=STATUSES, totals=totals,
                           counts=counts, overdue=overdue, recent=recent)


# ---------- Clients ----------
@app.route("/clients", methods=["GET", "POST"])
@login_required
def clients():
    uid = session["user_id"]
    if request.method == "POST":
        name = request.form["name"].strip()
        if not name:
            flash("Client name is required.", "error")
        else:
            db.session.add(Client(user_id=uid, name=name,
                                  email=request.form["email"].strip(),
                                  company=request.form["company"].strip()))
            db.session.commit()
            flash(f"Added {name}.", "ok")
        return redirect(url_for("clients"))
    rows = Client.query.filter_by(user_id=uid).order_by(Client.name).all()
    return render_template("clients.html", clients=rows)


@app.route("/clients/<int:client_id>/delete", methods=["POST"])
@login_required
def delete_client(client_id):
    client = Client.query.filter_by(id=client_id, user_id=session["user_id"]).first_or_404()
    db.session.delete(client)
    db.session.commit()
    flash("Client and their projects deleted.", "ok")
    return redirect(url_for("clients"))


# ---------- Projects ----------
@app.route("/projects", methods=["GET", "POST"])
@login_required
def projects():
    uid = session["user_id"]
    my_clients = Client.query.filter_by(user_id=uid).order_by(Client.name).all()
    if request.method == "POST":
        title = request.form["title"].strip()
        client = Client.query.filter_by(id=request.form.get("client_id"), user_id=uid).first()
        if not title or not client:
            flash("Pick a client and give the project a title.", "error")
        else:
            deadline = request.form.get("deadline")
            db.session.add(Project(
                user_id=uid, client_id=client.id, title=title,
                budget=float(request.form.get("budget") or 0),
                status=request.form.get("status", "Lead"),
                deadline=datetime.strptime(deadline, "%Y-%m-%d").date() if deadline else None,
            ))
            db.session.commit()
            flash(f"Added project: {title}.", "ok")
        return redirect(url_for("projects"))
    status = request.args.get("status")
    query = Project.query.filter_by(user_id=uid)
    if status in STATUSES:
        query = query.filter_by(status=status)
    return render_template("projects.html", projects=query.order_by(Project.deadline).all(),
                           clients=my_clients, statuses=STATUSES, active=status)


@app.route("/projects/<int:project_id>/status", methods=["POST"])
@login_required
def update_status(project_id):
    project = Project.query.filter_by(id=project_id, user_id=session["user_id"]).first_or_404()
    new_status = request.form.get("status")
    if new_status in STATUSES:
        project.status = new_status
        db.session.commit()
    return redirect(request.referrer or url_for("projects"))


@app.route("/projects/<int:project_id>/delete", methods=["POST"])
@login_required
def delete_project(project_id):
    project = Project.query.filter_by(id=project_id, user_id=session["user_id"]).first_or_404()
    db.session.delete(project)
    db.session.commit()
    flash("Project deleted.", "ok")
    return redirect(url_for("projects"))


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
