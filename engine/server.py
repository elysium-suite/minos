#!/usr/bin/python3
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from flask import Flask, render_template, request, redirect, url_for, send_file
from urllib.parse import urlparse, urljoin
from decorators import admin_required
from web import *
from forms import *
from datetime import datetime, timedelta
from io import BytesIO
import engine
import flask
import db
import os

wm = WebModel()
em = engine.EngineModel()
app = Flask(__name__)
# Should ideally store key in config file-- but this works pretty well
app.secret_key = os.urandom(24).hex()
login_manager = LoginManager()
login_manager.init_app(app)

# CSS hardcoded values
permitted_new_css_ip = "10.10.0.2" # Put your whitelisted IP here
remote_backup_key = "ThisIsAReallyCoolAndSecureKeyLol" # Put your backup hardcoded key here (must be the same as aeacus crypto.go)

# Caching and refreshing...
refresh_threshold = timedelta(seconds=15)
scoreboard_time_refresh = datetime.now() - refresh_threshold
team_time_refresh = datetime.now() - refresh_threshold
team_scores = None # For scoreboard
team_data = {} # For details
ips = {} # Stalking incoming IPs for CSS leaderboard :eyes:

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
def home():
    em.load()
    if "css_mode" in em.settings and em.settings["css_mode"] == True:
        return redirect(flask.url_for('css'))
    else:
        return redirect(flask.url_for('status'))

@app.route('/status')
def status():
    em.load()
    error = None
    if not db.engine_status():
        error = "Warning! Scoring engine backend is not running."
    return render_template('status.html', teams=em.teams, checks=em.checks, \
        systems=em.systems, status=em.status(), latest=em.latest(), error=error)

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
            for result, error, time, check_round in results[team][check]:
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
    if "duration" in em.settings:
        duration = em.settings["duration"]
    else:
        duration = "0:00"
    try:
        if time_left.days < 0:
            time_left = "00:00:00"
    except:
        pass
    return render_template('clock.html', duration=duration, \
                            time_left=time_left)

@app.route('/injects', methods=['GET', 'POST'])
def injects():
    em.load()
    pub_injects = []
    for title, inject in em.injects.items():
        if db.get_current_time() > db.format_time(inject["time"]):
            print("[INFO] Posting inject", title)
            pub_injects.append(inject)
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

@app.route('/settings', methods=['GET', 'POST'])
@admin_required
def settings():
    if request.method == "POST" and "action" in request.form and request.form["action"] == "Reset":
        print("[INFO] Resetting database from web GUI...")
        db.reset_engine()
        return redirect(flask.url_for('status'))
    return render_template("settings.html")

@app.route('/scores/service')
def service():
    em.load()
    scores = {}
    sla_totals, _ = em.get_slas()
    for team in em.teams:
        service_points = db.get_service_points(team)
        if service_points is not None:
            service_points = service_points[0]
        else:
            service_points = 0
        for check in em.checks:
            service_points += sla_totals[team][check] * -5
        scores[team] = service_points

    red_or_green = {} # determines red or green color
    for team in em.teams:
        if scores[team] >= 0:
            red_or_green[team] = 1
        else:
            red_or_green[team] = 0

    return render_template("scores_service.html", teams = em.teams, scores = scores, \
                            rg = red_or_green)



@app.route('/scores/css')
# @admin_required # Uncomment this line if you want to prevent people from seeing the scoreboard without being admin
def css():
    global scoreboard_time_refresh
    global team_scores # for main scoreboard
    global team_data # for details
    em.load()
    if "css_mode" in em.settings:
        css_mode = em.settings["css_mode"]
    else:
        css_mode = None
    if "event" in em.remote:
        event = em.remote["event"]
    else:
        event = None

    # If filter by image:
    images = db.get_css_images(em.remote)
    image = None
    if "image" in request.args:
        image = request.args["image"]
        if image not in images:
            print("[ERROR] Invalid image specified:", image)
            image = None

    colors = {}
    color_settings = db.get_css_colors()
    image_list = db.get_css_images(em.remote)
    if color_settings is not None:
        for index, image_item in enumerate(image_list):
            colors[image_item] = color_settings[index]
    else:
        for index, image_item in enumerate(image_list):
            colors[image_item] = 'rgb(255, 255, 255)'

    # Details view for CSS
    if "team" in request.args:
        teams = db.get_css_teams(em.remote)
        team = request.args["team"]
        team_name = team
        if not team in teams:
            try:
                team = db.remove_alias(team, em.remote)
            except:
                # Invalid team
                team = None
        if team in teams:
            if image:
                print("[INFO] Fetching image-specific data for", team, "image", image)
                labels, image_data, scores = db.get_css_score(team, em.remote, image=image)
                total_score = 0
                for image_item in image_data.values():
                    total_score += image_item[3]
                team_info = (db.get_css_elapsed_time(team), \
                             db.get_css_play_time(team), \
                             total_score)
            else:
                if team not in team_data or (team in team_data and (datetime.now() - team_data[team]["refresh_time"]) > refresh_threshold):
                    print("[INFO] Refreshing data for team", team)
                    labels, image_data, scores = db.get_css_score(team, em.remote)
                    total_score = 0
                    for image_item in image_data.values():
                        total_score += image_item[3]

                    team_info = (db.get_css_elapsed_time(team), \
                                 db.get_css_play_time(team), \
                                 total_score)

                    # Wonderful caching
                    team_data[team] = {}
                    team_data[team]["labels"] = labels
                    team_data[team]["image_data"] = image_data
                    team_data[team]["scores"] = scores
                    team_data[team]["refresh_time"] = datetime.now()
                    team_data[team]["elapsed_time"] = team_info[0]
                    team_data[team]["play_time"] = team_info[1]
                    team_data[team]["total_score"] = team_info[2]

                else:

                    labels = team_data[team]["labels"]
                    image_data = team_data[team]["image_data"]
                    scores = team_data[team]["scores"]
                    team_info = (team_data[team]["elapsed_time"], \
                                 team_data[team]["play_time"],
                                 team_data[team]["total_score"])

            return render_template("scores_css_details.html", labels=labels, team_name=team_name, team_info=team_info, image_data=image_data, scores=scores, css_mode=css_mode, colors=colors, image=image)
        else:
            print("[ERROR] Invalid team specified:", request.args["team"])

    if image:
        print("[INFO] Fetching CSS scoreboard for image", image)
        team_scores = db.get_css_scores(em.remote, image=image)

    # Main scoreboard view
    if not image:
        time_since_refresh = datetime.now() - scoreboard_time_refresh
        if time_since_refresh > refresh_threshold:
            print("[INFO] Refreshing CSS scoreboard...")
            team_scores = db.get_css_scores(em.remote)
            scoreboard_time_refresh = datetime.now()
    if "team_aliases" in em.remote:
        team_scores = db.apply_aliases(team_scores, em.remote)

    return render_template("scores_css.html", team_scores=team_scores, event=event, css_mode=css_mode, images=images, image=image)

@app.route('/scores/css/update', methods=['POST'])
def css_update():
    em.load()
    config = db.read_running_config()
    try:
        password = config["remote"]["password"]
    except:
        password = remote_backup_key
    try:
        update = request.form["update"].rstrip().strip()
        update_data, result = em.parse_update(update, password)
        if not result:
            print("[ERROR] Failure parsing update field.")
            return ("FAIL")
        team = update_data["team"]
        image = update_data["image"]
        score = update_data["score"]
        challenge = update_data["challenge"]
        vulns = update_data["vulns"]
        time = update_data["time"]
    except Exception as e:
        print("[ERROR] Score update from image did not have all required fields, or had malformed fields:", e)
        return("FAIL")
    if not db.validate_alphanum(team) or not db.validate_alphanum(image):
        print("[ERROR] Team or image contained illegal characters.")
        return("FAIL")
    if "teams" in em.remote:
        if team not in em.remote["teams"]:
            print("[ERROR] Score update had invalid team name:", team)
            return("FAIL")
    if "images" in em.remote:
        if image not in em.remote["images"]:
            print("[ERROR] Score update had invalid image name:", image)
            return("FAIL")
    if em.verify_challenge(challenge, password):
        vulns, success = em.decrypt_vulns(vulns, password, score)
    else:
        print("[ERROR] Score update from image did not pass (password-protected) challenge verification.")
        return("FAIL")
    if success:
        vulns = db.printAsHex("|-|".join(vulns).encode())
        db.insert_css_score(team, image, score, vulns)
        print("Found IP", request.remote_addr, "for team", team)
        ips[team] = request.remote_addr
        return("OK")
    else:
        print("[ERROR] Vuln data decryption failed.")
        return("FAIL")
    return("FAIL")

@app.route('/scores/css/new', methods=['POST'])
def css_new_team():
    em.load()
    request_ip = request.remote_addr
    if request_ip != permitted_new_css_ip:
        print("[ERROR] New team ID request wasn't from the authorized IP.")
        return("FAIL")
    try:
        id = request.form["teamid"].rstrip().strip()
        alias = request.form["alias"].rstrip()
        if "email" in request.form:
            email = request.form["email"]
        else:
            email = None
    except:
        print("[ERROR] New team ID request did not have all required fields (teamid, alias).")
        return("FAIL")
    if not db.validate_alphanum(alias) or not db.validate_alphanum(id):
        print("[ERROR] New team or id contained illegal characters.")
        return("FAIL")
    config = db.read_running_config()
    try:
        if alias in config["remote"]["team_aliases"]:
            print("[ERROR] Duplicate team alias (team)")
            return("FAIL")
    except:
        pass
    try:
        if id in config["remote"]["teams"]:
            print("[ERROR] Duplicate team id (id)")
            return("FAIL")
    except:
        pass
    try:
        if email in config["remote"]["team_emails"]:
            print("[ERROR] Duplicate team email (email)")
            return("FAIL")
    except:
        pass
    if not "remote" in config:
        config["remote"] = {}
    if email and not db.validate_alphanum(email):
        print("[ERROR] Email was not null and contained illegal characters.")
        return("FAIL")
    else:
        if "team_emails" in config["remote"]:
            config["remote"]["team_emails"].append(email)
        else:
            config["remote"]["team_emails"] = [email]
        if "teams" in config["remote"]:
            lenTeams = 0
        else:
            lenTeams = len(config["remote"]["teams"])
        if len(config["remote"]["team_emails"]) <= lenTeams:
             for x in range(lenTeams - len(config["remote"]["team_emails"]) + 1):
                 config["remote"]["team_emails"].insert(0, "N/A")
    if "teams" in config["remote"]:
        config["remote"]["teams"].append(id)
    else:
        config["remote"]["teams"] = [id]
    if "team_aliases" in config["remote"]:
        config["remote"]["team_aliases"].append(alias)
    else:
        config["remote"]["team_aliases"] = [team]
    print(config)
    db.write_running_config(config)
    return("OK")

@app.route('/scores/css/status')
def css_status():
    return("OK")

@app.route('/scores/css/export')
@admin_required
def css_csv():
    em.load()
    csv_buffer = BytesIO()
    csv_buffer.write(db.get_css_csv(em.remote, ips))
    csv_buffer.seek(0)
    return send_file(csv_buffer, as_attachment=True,
                     attachment_filename='score_report.csv',
                     mimetype='text/csv')

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
def total():
    em.load()
    scores = em.get_scores(db.get_check_round())
    return render_template("scores_total.html", teams = em.teams, \
                           scores=scores, check_round = db.get_check_round())

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
    em.load()
    form = LoginForm(wm)
    error = None
    if "css_mode" in em.settings:
        css_mode = em.settings["css_mode"]
    else:
        css_mode = None
    if request.method == 'POST':
        if form.validate_on_submit():
            uid = db.get_uid(form.username.data)
            user = load_user(chr(uid))
            login_user(user)
            flask.flash('Logged in successfully!')
            next = flask.request.args.get('next')
            # Open redirect protection
            if not is_safe_url(next):
                return flask.abort(400)
            return redirect(next or flask.url_for("home"))
        else:
            error = "Invalid username or password."
    return render_template('login.html', form=form, error=error, css_mode=css_mode)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(flask.url_for('home'))
