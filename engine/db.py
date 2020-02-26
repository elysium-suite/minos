import sqlite3 as sql
import toml
import bcrypt
import time
from datetime import datetime, timedelta

# Database name
db = "scoring.db"

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

def get_check_round():
    return execute("SELECT check_round FROM service_results \
                ORDER BY time DESC", one=True)[0]

def get_service_check(team, check, check_round):
    try:
        return execute("SELECT result, error, time \
                         FROM service_results WHERE team=? AND name=? \
                         AND check_round=?", (team, check, check_round))
    except:
        return False

def get_service_latest():
    return execute("SELECT time FROM service_results \
                ORDER BY time DESC", one=True)[0]

def get_service_points(team):
    return execute("SELECT points FROM totals WHERE \
        type=? and team=? ORDER BY time DESC", ("service", team), one=True)
        
def insert_service_score(check_round, team, system, check, result, error):
    execute("INSERT INTO `service_results` ('check_round', 'team', 'name', 'result', 'error') VALUES (?, ?, ?, ?, ?)", (check_round, team, system + "-" + check, result, error))

        
#############################
# CONFIG READER AND WRITERS #
#############################

def copy_config():
    print("[INFO] Loading config into running-config...")
    with open('config.cfg', 'r') as f:
        config = toml.load(f)
    with open('running-config.cfg', 'w') as f:
        toml.dump(config, f)
        
def read_config():
    with open('config.cfg', 'r') as f:
        config = toml.load(f)
    return config
    
def read_running_config():
    with open('running-config.cfg', 'r') as f:
        config = toml.load(f)
    return config
    
def write_running_config(config):
    with open('running-config.cfg', 'w') as f:
        toml.dump(config, f)

def stop_engine():
    with open('running-config.cfg', 'r') as f:
        config = toml.load(f)
    with open('running-config.cfg', 'w') as f:
        if "settings" in config:
            config['settings']['running'] = 0
            toml.dump(config, f)

def write():
    copy_config()
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

def load():
    print("[LOAD] Loading config into memory...")
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

