import sqlite3 as sql
import re
import toml
import bcrypt
import time
from datetime import datetime, timedelta

# Database name
path = "/opt/minos/"
db = path + "engine/scoring.db"

#######################
# DB HELPER FUNCTIONS #
#######################

def execute(cmd, values=None, one=False):
    with sql.connect(db) as conn:
        cur = conn.cursor()
        if values:
            cur.execute(cmd, values)
        else:
            cur.execute(cmd)
        if one:
            return cur.fetchone()
        else:
            return cur.fetchall()

#############################
# HUGE LIST OF DB FUNCTIONS #
#############################

# Startup/administrative

def get_uid(username):
    return execute("SELECT id FROM users WHERE username=?", \
                  (username,))[0][0]

def engine_status():
    config = read_running_config()
    if config["settings"]["running"] == 1:
        return True
    else:
        return False

# Times

time_format = "%Y-%m-%d %H:%M:%S"
simple_time_format = "%H:%M:%S"

def print_time(time_obj):
    return time_obj.strftime(simple_time_format)

def print_time_all(time_obj):
    return time_obj.strftime(time_format)

def get_current_time():
    return datetime.now()

def set_start_time():
    start_time = datetime.strftime(datetime.now(), time_format)
    execute("INSERT INTO `info` ('key', 'value') VALUES (?, ?)", \
           ("start_time", start_time))

def get_start_time():
    try:
        start_time_text = execute("SELECT value FROM info WHERE \
                                   key='start_time'")[0][0]
        return datetime.strptime(start_time_text, time_format)
    except: return datetime.now()

def format_time(time_string):
    # take time in "%H:%M" format and put it in "%Y-%m-%d %H:%M:%S" format
    # assuming that time is time from start of competition
    start_time = get_start_time()
    hour_offset, minute_offset = list(map(int, time_string.split(":")))
    goal_time = start_time + timedelta(hours=hour_offset, minutes=minute_offset)
    return(goal_time)

def get_time_elapsed():
    start_time = get_start_time()
    current_time = datetime.now()
    time_elapsed = current_time.replace(microsecond=0) \
                 - start_time.replace(microsecond=0)
    return(time_elapsed)

def get_time_left():
    duration = read_config()["settings"]["duration"]
    hours, minutes = list(map(int, duration.split(":")))
    time_left = timedelta(hours=hours, minutes=minutes, seconds=00) \
              - get_time_elapsed()
    return(time_left)

# Scoring

def init_check_round():
    execute("INSERT INTO `info` ('key', 'value') VALUES (?, ?)", \
           ("check_round", 0))

def get_check_round():
    try:
        check_round = execute("SELECT value FROM info \
                               WHERE key='check_round'", one=True)[0]
    except TypeError:
        check_round = 0
    return int(check_round)

def update_check_round(check_round):
    execute("UPDATE info SET value=? \
             WHERE key='check_round'", (check_round,), one=True)

def get_service_check(team, check, check_round):
    return execute("SELECT result, error, time \
                     FROM service_results WHERE team=? AND name=? \
                     AND check_round=?", (team, check, check_round))

def get_service_checks(team, check):
    try:
        return execute("SELECT result, error, time, check_round FROM \
                service_results WHERE team=? and name=? ORDER BY time DESC", \
                (team, check))
    except Exception as e:
        print("[ERROR] Error occured in get_service_checks:", e)
        return False

def get_service_latest():
    return execute("SELECT time FROM service_results \
                ORDER BY time DESC", one=True)[0]

def get_service_points(team):
    return execute("SELECT points FROM totals WHERE \
        type=? and team=? ORDER BY time DESC", ("service", team), one=True)

def insert_service_score(check_round, team, system, check, result, error):
    if error:
        error = re.sub('[^a-zA-Z.\d\s\/\-\%\(\)]', '', str(error))
    try:
        execute("INSERT INTO `service_results` ('check_round', 'team', 'name', \
                'result', 'error') VALUES (?, ?, ?, ?, ?)", (check_round, team, \
                system + "-" + check, result, error))
    except Exception as e:
        print("[ERROR] Error couldn't be processed for", check, ":", error)
        error = "Error couldn't be processed:" + str(e)

def get_totals_score(team, type, check_round):
    try:
        return execute("SELECT points FROM `totals` WHERE team=? and type=? \
                         and check_round=?", (team, type, check_round))[0][0]
    except:
        return 0

def insert_totals_score(team, type, points, check_round):
    execute("INSERT INTO `totals` ('team', 'type', 'points', 'check_round') VALUES \
            (?, ?, ?, ?)", (team, type, points, check_round))

#############################
# CONFIG READER AND WRITERS #
#############################

def copy_config():
    print("[INFO] Copying config into running-config...")
    write_running_config(read_config())

def read_config():
    with open(path + 'config.cfg', 'r') as f:
        config = toml.load(f)
    return config

def read_running_config():
    try:
        with open(path + 'engine/running-config.cfg', 'r') as f:
            config = toml.load(f)
    except OSError:
        print("[WARNING] File running-config.cfg not found.")
        config = None
    return config

def write_running_config(config):
    with open(path + 'engine/running-config.cfg', 'w') as f:
        toml.dump(config, f)

def stop_engine():
    config = read_running_config()
    if config:
        config['settings']['running'] = 0
        write_running_config(config)
    else:
        print("[WARNING] No running-config.cfg, can't stop engine.")

def start_engine():
    config = read_running_config()
    config['settings']['running'] = 1
    write_running_config(config)

def pause_engine():
    config = read_running_config()
    if config:
        config['settings']['running'] = 0
        write_running_config(config)
    else:
        print("[WARNING] No running-config.cfg, can't pause engine.")

def stop_engine():
    config = read_running_config()
    config['settings']['running'] = -1
    write_running_config(config)

def reset_engine():
    pause_engine()
    print("[INIT] Resetting database...")
    reset()

    config = read_config()
    print("[INIT] Reading config...")

    # Load teams and normal users
    print("[INIT] Loading teams and users...")
    for team, team_info in config['teams'].items():
        pwhash = bcrypt.hashpw(team_info['password'].encode('utf-8'), bcrypt.gensalt())
        execute("INSERT INTO users (team, username, password, is_admin) \
            VALUES (?, ?, ?, ?)",  (team, team_info['username'], pwhash, 0))

    # Load web admin
    print("[INIT] Loading web admins...")
    for user, password in config['web_admins'].items():
        pwhash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        execute("INSERT INTO users (team, username, password, is_admin) \
            VALUES (?, ?, ?, ?)",  (None, user, pwhash, 1))

    set_start_time()
    print("[INFO] Starting! Start time is", get_start_time())

    init_check_round()
    print("[INFO] Set check round to", get_check_round())

    copy_config()
    start_engine()

def load():
    print("[LOAD] Loading config into memory...")
    config = read_running_config()
    if not config:
        print("[INFO] No running config exists-- starting fresh.")
        reset_engine()
        config = read_running_config()

    settings = config['settings']
    teams = config['teams']
    systems = config['systems']
    injects = config['injects']

    checks = []
    for system, sys_info in systems.items():
        for check in sys_info['checks']:
            checks.append(system + "-" + check)

    return settings, teams, systems, checks, injects

def reset():
    execute("DROP TABLE IF EXISTS `info`;")
    execute("""CREATE TABLE `info` (
                `key` VARCHAR(255),
                `value` VARCHAR(255)
            );""")
    execute("DROP TABLE IF EXISTS `users`;")
    execute("""CREATE TABLE `users` (
                `id` INTEGER PRIMARY KEY AUTOINCREMENT,
                `team` VARCHAR(255),
                `username` VARCHAR(255),
                `password` CHAR(60),
                `is_admin` BOOL
            );""")
    execute("DROP TABLE IF EXISTS `service_results`;")
    execute("""CREATE TABLE `service_results` (
                `time` DATETIME DEFAULT CURRENT_TIMESTAMP,
                `check_round` INTEGER,
                `team` INTEGER,
                `name` VARCHAR(255),
                `error` VARCHAR(255),
                `result` BOOL
            );""")
    execute("DROP TABLE IF EXISTS `inject_results`;")
    execute("""CREATE TABLE `inject_results` (
                `time` DATETIME DEFAULT CURRENT_TIMESTAMP,
                `team` INTEGER,
                `inject` VARCHAR(255),
                `points` BOOL
            );""")
    execute("DROP TABLE IF EXISTS `css_results`;")
    execute("""CREATE TABLE `css_results` (
                `time` DATETIME DEFAULT CURRENT_TIMESTAMP,
                `team` INTEGER,
                `system` INTEGER,
                `points` INTEGER
            );""")
    execute("DROP TABLE IF EXISTS `totals`;")
    execute("""CREATE TABLE `totals` (
                `time` DATETIME DEFAULT CURRENT_TIMESTAMP,
                `check_round` INTEGER,
                `team` INTEGER,
                `type` VARCHAR(255),
                `points` INTEGER
            );""")
    execute("DROP TABLE IF EXISTS `reverts`;")
    execute("""CREATE TABLE `reverts` (
                `time` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                `team_id` INTEGER,
                `system` VARCHAR(255)
            );""")
