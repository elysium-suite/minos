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

##############
# META FUNCS #
##############

def get_uid(username):
    return execute("SELECT id FROM users WHERE username=?", \
                  (username,))[0][0]

def engine_status():
    config = read_running_config()
    if "settings" in config and "running" in config["settings"] and config["settings"]["running"] == 1:
            return True
    else:
        return False

##############
# TIME FUNCS #
##############

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
    try:
        duration = read_running_config()["settings"]["duration"]
    except:
        duration = "3:30"
    hours, minutes = list(map(int, duration.split(":")))
    time_left = timedelta(hours=hours, minutes=minutes, seconds=00) \
              - get_time_elapsed()
    return(time_left)

#################
# SCORING FUNCS #
#################

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

#################
# CSS FUNCTIONS #
#################

def get_css_csv(remote, ips):
    http_csv = str.encode("")
    teams = get_css_teams(remote)
    images = get_css_images(remote)
    team_scores = []
    #ugly_results = execute("select team, image, points from css_results GROUP BY team, image ORDER BY team DESC")
    for index, team in enumerate(teams):
        team_sum = 0
        for image in images:
            try:
                image_sum = execute("SELECT `points` FROM `css_results` WHERE team=? AND image=? ORDER BY time DESC", (team, image), one=True)[0]
                if team in ips:
                    ip = ips[team]
                else:
                    ip = "N/A"
                http_csv += str.encode(find_email(index, remote) + "," + find_alias(index, remote) + "," + team + "," + image + "," + str(image_sum) + "," + ip + "," + get_css_play_time(team, image=image) + "," + get_css_elapsed_time(team) + "\n")
            except:
                # Ignoring images that a team hasn't started yet
                pass
    return http_csv

def get_css_teams(remote):
    if "teams" in remote:
        teams = remote["teams"]
    else:
        ugly_teams = execute("SELECT DISTINCT `team` FROM `css_results`")
        teams = []
        for team in ugly_teams:
            teams.append(team[0])
    return teams

def get_css_images(remote):
    if "images" in remote:
        images = remote["images"]
    else:
        ugly_images = execute("SELECT DISTINCT `image` FROM `css_results`")
        images = []
        for image in ugly_images:
            images.append(image[0])
    return images

def get_css_scores(remote):
    team_scores = []
    try:
        # Returns most recent image scores for each team
        # [(time, team, image, points), ...]
        team_data = execute("SELECT DISTINCT max(time) as time, team, image, points FROM css_results GROUP BY team, image")
    except:
        return team_scores

    current_team = ""
    team_times = get_css_all_elapsed_time()
    for data in team_data:
        if data[1] != current_team: # If new team
            # append(team, image_count, elapsed_time, total_points)
            team_scores.append([data[1], 1, team_times[data[1]], data[3]])
            current_team = data[1]
        else:
            team_scores[-1][1] += 1 # Increment image count
            team_scores[-1][3] += data[3] # Add new image points

    team_scores.sort(key=lambda tup: tup[2]) # Sort by time
    team_scores.sort(key=lambda tup: tup[3], reverse=True) # Sort by score
    return(team_scores)

# TODO optimize this
def get_css_score(team, remote):
    image_data = {}

    #print("GETTING scores for team", team)
    # Get all scores from one team
    try:
        team_scores = execute("SELECT time, image, points, vulns FROM css_results WHERE team=? ORDER BY time ASC", (team,))
        #print("TEAM SCORES IS", team_scores)
        current_block = datetime.strptime(team_scores[0][0], "%Y-%m-%d %H:%M:%S")
    except:
        return [], {}, {}

    current_delta = timedelta()
    block_threshold = timedelta(seconds=180)

    # Push starting block
    labels = []
    scores = {}
    current_scores = {}

    for index, score_data in enumerate(team_scores):
        score_time = datetime.strptime(score_data[0], "%Y-%m-%d %H:%M:%S")
        time_diff = score_time.replace(microsecond=0) \
                  - current_block.replace(microsecond=0)
        #print("SCORES IS", scores)
        if time_diff > block_threshold:
            #print("=== SCORE PUSH TRIGGERED ===")
            for image, img_score in current_scores.items():
                if image in scores:
                    scores[image].append((datetime.strftime(current_block, time_format), img_score))
                else:
                    scores[image] = [(datetime.strftime(current_block, time_format), img_score)]
            current_scores = {}
            while time_diff > block_threshold:
                labels.append(datetime.strftime(current_block, time_format))
                current_block += block_threshold
                time_diff = score_time.replace(microsecond=0) \
                          - current_block.replace(microsecond=0)
        #print("SETTING SCORE", score_data[2])
        current_scores[score_data[1]] = score_data[2]
        if score_data[1] in image_data:
            image_data[score_data[1]][3] = score_data[2]
            image_data[score_data[1]][4] = score_data[3]
        else:
            image_data[score_data[1]] = [get_css_play_time(team, image=score_data[1]), 0, 0, score_data[2], score_data[3]]

    #print("=== END SCORE PUSH ===")
    labels.append(datetime.strftime(current_block, time_format))
    for image, img_score in current_scores.items():
        if image in scores:
            scores[image].append((datetime.strftime(current_block, time_format), img_score))
        else:
            scores[image] = [(datetime.strftime(current_block, time_format), img_score)]

    for image in image_data.values():
        try:
            image[4] = bytes.fromhex(image[4])
            image[4] = image[4].decode("ascii")
            vuln_info = image[4].split("|-|")
            image[1] = vuln_info[0]
            image[2] = vuln_info[1]
            if vuln_info[-1] == "":
                image[4] = "|-|".join(vuln_info[2:-1])
            else:
                image[4] = "|-|".join(vuln_info[2:])
        except Exception as e:
            print("[ERROR] Error decoding hex vulns from databases! (" + str(e) + ")")
    return(labels, image_data, scores)

def get_css_elapsed_time(team):
    try:
        time_records = execute("SELECT `time` FROM `css_results` WHERE team=? ORDER BY time ASC", (team,))
        start_time = datetime.strptime(time_records[0][0], "%Y-%m-%d %H:%M:%S")
        end_time = datetime.strptime(time_records[-1][0], "%Y-%m-%d %H:%M:%S")
        time_elapsed = end_time.replace(microsecond=0) \
                     - start_time.replace(microsecond=0)
        return str(time_elapsed)
    except:
        return "0:00:00"

def get_css_all_elapsed_time():
    team_times = {}

    all_times = execute("SELECT time, team FROM css_results ORDER BY time ASC")
    all_times.sort(key=lambda tup: tup[0]) # Sort by time
    all_times.sort(key=lambda tup: tup[1]) # Sort by team

    time_string = "%Y-%m-%d %H:%M:%S"
    current_team = all_times[0][1]
    first_time = all_times[0][0]
    last_time = first_time

    for time_item in all_times:
        if current_team != time_item[1]: # If new team
            # Calculate previous team's elapsed time
            first_time = datetime.strptime(first_time, time_string)
            last_time = datetime.strptime(last_time, time_string)
            team_times[current_team] = str(last_time.replace(microsecond=0) - first_time.replace(microsecond=0))

            # Assign new accurate current_team value
            current_team = time_item[1]
            first_time = time_item[0]
        last_time = time_item[0]

    # Catch the last team
    start_time = datetime.strptime(first_time, time_string)
    end_time = datetime.strptime(last_time, time_string)
    team_times[current_team] = str(end_time.replace(microsecond=0) - start_time.replace(microsecond=0))

    return team_times


def get_css_play_time(team, image=None):
    try:
        if not image:
            time_records = execute("SELECT `time` FROM `css_results` WHERE team=? ORDER BY time ASC", (team,))
        else:
            time_records = execute("SELECT `time` FROM `css_results` WHERE team=? and image=? ORDER BY time ASC", (team, image))

        play_time = timedelta()
        time_threshold = timedelta(seconds=300)
        for index in range(len(time_records) - 1):
            time1 = datetime.strptime(time_records[index][0], "%Y-%m-%d %H:%M:%S")
            time2 = datetime.strptime(time_records[index + 1][0], "%Y-%m-%d %H:%M:%S")
            time_diff = time2.replace(microsecond=0) \
                      - time1.replace(microsecond=0)
            if time_diff < time_threshold:
                play_time += time_diff
        return str(play_time)
    except:
        return "0:00:00"

def insert_css_score(team, image, points, vulns):
    execute("INSERT INTO `css_results` ('team', 'image', 'points', 'vulns') VALUES (?, ?, ?, ?)", (team, image, points, vulns))

def find_alias(team_index, remote):
    try:
        aliases = remote["team_aliases"]
    except:
        aliases = []
    if not team_index > len(aliases) - 1:
        return aliases[team_index]
    return "N/A"

def find_email(team_index, remote):
    try:
        emails = remote["team_emails"]
    except:
        emails = []
    if not team_index > len(emails) - 1:
        return emails[team_index]
    return "N/A"

def apply_aliases(team_scores, remote):
    for score_index, team in enumerate(team_scores):
        for index, team_id in enumerate(remote["teams"]):
            if index >= len(remote["team_aliases"]):
                break
            if team_id == team[0]:
                team_scores[score_index] = (remote["team_aliases"][index], team[1], team[2], team[3])

    return team_scores

def remove_alias(team, remote):
    for index, team_id in enumerate(remote["team_aliases"]):
        if team_id == team:
            print("[INFO] Removing alias", team, "to", remote["teams"][index])
            return remote["teams"][index]
    return team

#############################
# CONFIG READER AND WRITERS #
#############################

def printAsHex(text):
    return ''.join(format(x, '02x') for x in text)

def xor(a, b):
    xored = []
    for i in range(max(len(a), len(b))):
        xored_value = ord(a[i%len(a)]) ^ ord(b[i%len(b)])
        xored.append(xored_value)
    return bytes(xored)

def validate_alphanum(string):
    if re.compile("^[a-zA-Z0-9-@_.]+$").match(string):
        return True
    return False

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
            config_tmp = toml.load(f)
        if "settings" not in config_tmp:
            config_tmp["settings"] = {}
    except OSError:
        print("[WARN] File running-config.cfg not found.")
        config_tmp = None
    return config_tmp

def get_css_colors():
    try:
        return read_config()["remote"]["colors"]
    except: pass

def write_running_config(config_tmp):
    with open(path + 'engine/running-config.cfg', 'w') as f:
        toml.dump(config_tmp, f)

def stop_engine():
    config = read_running_config()
    config['settings']['running'] = 0
    write_running_config(config)

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

    copy_config()
    config = read_config()
    print("[INIT] Reading config...")

    if not "settings" in config:
        config["settings"] = {}

    # Load teams and normal users
    if 'teams' in config:
        print("[INIT] Loading teams and users...")
        for team, team_info in config['teams'].items():
            pwhash = bcrypt.hashpw(team_info['password'].encode('utf-8'), bcrypt.gensalt())
            execute("INSERT INTO users (team, username, password, is_admin) \
                VALUES (?, ?, ?, ?)",  (team, team_info['username'], pwhash, 0))
    else:
        print("[WARN] No teams found in configuration! Running in CCS mode.")
        config['settings']['css_mode'] = True
        write_running_config(config)

    if not 'systems' in config:
        print("[WARN] No systems found in configuration! Running in CCS mode.")
        config['settings']['css_mode'] = True
        write_running_config(config)

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

    start_engine()

def load():
    print("[LOAD] Loading config into memory...")
    config = read_running_config()
    if not config:
        print("[INFO] No running config exists-- starting fresh.")
        reset_engine()
        config = read_running_config()

    settings = config['settings']
    if "teams" in config:
        teams = config['teams']
    else:
        teams = {}
    if "systems" in config:
        systems = config['systems']
    else:
        systems = {}
    if "injects" in config:
        injects = config['injects']
    else:
        injects = {}
    if "remote" in config:
        remote = config["remote"]
    else:
        remote = []

    checks = []
    for system, sys_info in systems.items():
        for check in sys_info['checks']:
            checks.append(system + "-" + check)

    return settings, teams, systems, checks, injects, remote

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
                `team` VARCHAR(255),
                `image` VARCHAR(255),
                `vulns` VARCHAR(2048),
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
