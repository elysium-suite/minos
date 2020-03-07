#!/usr/bin/python3
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from flask import Flask, render_template, request, redirect, url_for
from urllib.parse import urlparse, urljoin
from decorators import admin_required
from web import *
from forms import *
import engine
import flask
import db
import os

wm = WebModel()
em = engine.EngineModel()
app = Flask(__name__)
app.secret_key = 'this is a secret'
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(uid):
    wm.load()
    uid = int(ord(uid))
    if uid in wm.users:
        return wm.users[uid]
    return None

@login_manager.unauthorized_handler
def unauthorized():
    return redirect(flask.url_for('login'))

def is_safe_url(target):
    ref_url = urlparse(flask.request.host_url)
    test_url = urlparse(urljoin(flask.request.host_url, target))
    return test_url.scheme in ('http', 'https') and \
           ref_url.netloc == test_url.netloc


@app.route('/')
@app.route('/status')
def status():
    em.load()
    return render_template('status.html', teams=em.teams, checks=em.checks, \
        systems=em.systems, status=em.status(), latest=em.latest())

@app.route('/uptime')
def uptime():
    em.load()
    percents = {}
    results = em.results()
    latest = em.latest()
    for team in em.teams:
        percents[team] = {}
        for check in em.checks:
            total, passed = 0, 0
            for result, error, time in results[team][check]:
                if result: passed += 1
                total += 1
            if total == 0: percents[team][check] = -1
            else: percents[team][check] = int((passed/total) * 100)
    return render_template('uptime.html', teams=em.teams, checks=em.checks, latest=latest, percents=percents)

@app.route('/scores/result', methods=['GET'])
def result():
    em.load()
    results = em.results()
    try:
        team = request.args.get('team')
        check = request.args.get('check')
        system, check_type = check.split("-") # hacky solution
        if check_type in em.systems[system]:
            opts = em.systems[system][check_type]
        else:
            opts = None
        results = results[team][check]
    except:
        check_opts = "None"
        results = []
    return render_template('result_log.html', results=results, opts=opts)

@app.route('/clock')
def clock():
    em.load()
    time_left = db.get_time_left()
    try:
        if time_left.days < 0:
            time_left = "00:00:00"
    except:
        pass
    return render_template('clock.html', duration=em.settings["duration"], \
                            time_left=time_left)

@app.route('/injects', methods=['GET', 'POST'])
def injects():
    em.load()
    pub_injects = {}
    for title, inject in em.injects.items():
        if db.get_current_time() > db.format_time(inject["time"]):
            print("[INFO] Posting inject", title)
            pub_injects[title] = inject
    return render_template('injects.html', injects=em.injects, \
                            pub_injects=pub_injects)

@app.route('/patch')
def patch():
    path = "/opt/minos/patch/"
    tree = dict(name=path, children=[])
    try: lst = os.listdir(path)
    except OSError: pass
    else:
       for name in lst:
            if name != ".keep":
                fn = os.path.join(path, name)
                tree['children'].append(dict(name=name))
    return render_template('patch.html', tree=tree)

@app.route('/scores/service')
def service():
    em.load()
    scores = {}
    sla_totals, _ = em.get_slas()
    for team in em.teams:
        service_points = db.get_service_points(team)
        print("[SCORING] Service points for team", team, "is", service_points)
        if service_points is not None:
            service_points = service_points[0]
        else:
            service_points = 0
        print("SERVICE POINTS", service_points)
        for check in em.checks:
            service_points += sla_totals[team][check] * -5
        scores[team] = service_points

    red_or_green = {} # Determines red or green color
    for team in em.teams:
        if scores[team] >= 0:
            red_or_green[team] = 1
        else:
            red_or_green[team] = 0

    return render_template("scores_service.html", teams = em.teams, scores = scores, \
                            rg = red_or_green)

@app.route('/scores/css')
def css():
    return("TODO: CSS Scores")

@app.route('/scores/injects')
def inject_scores():
    if request.method == 'POST':
        #request.args.get('end')
        if all (k in request.args for k in ("team", "inject", "points")):
            # add inject score in db
            pub_injects[request.form['inject']]["done"] = "graded"
        return render_template('injects.html')
    return("It'd be very convenient if there was some kind of inject scoring panel here.")

@app.route('/scores/total')
@login_required
@admin_required
def total():
    return("TODO: Total scores (CSS, Service, Inject)")

@app.route('/settings', methods=['GET', 'POST'])
@admin_required
def settings():
    if request.method == "POST" and "action" in request.form and request.form["action"] == "Reset":
        print("[INFO] Resetting database from web GUI...")
        db.pause_engine()
        db.write()
        db.set_start_time()
        print("[INFO] Starting! Start time is", db.get_start_time())
        db.start_engine()
    return render_template("settings.html")

@app.route('/scores/sla', methods=['GET'])
@login_required
def sla():
    em.load()
    sla_totals, sla_log = em.get_slas()
    return render_template('sla.html', sla_totals=sla_totals, sla_log=sla_log, checks=em.checks, teams=em.teams)

@app.route('/team_page', methods=['GET'])
@login_required
def team_page():
    return("No page here yet. Would include just your service statuses, injects, etc.")

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm(wm)
    error = None
    if request.method == 'POST':
        if form.validate_on_submit():
            uid = db.get_uid(form.username.data)
            user = load_user(chr(uid))
            login_user(user)
            flask.flash('Logged in successfully!')
            next = flask.request.args.get('next')
            if not is_safe_url(next): # Open redirect protection
                return flask.abort(400)
            return redirect(next or flask.url_for('status'))
        else:
            error = "Invalid username or password."
    return render_template('login.html', form=form, error=error)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(flask.url_for('status'))
