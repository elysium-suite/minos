from threading import Thread
from checks import checker
from Crypto.Cipher import AES
from hashlib import sha256
import sqlite3 as sql
import time, random
import db
import os
import sys

class EngineModel(object):

    def load(self):
        self.settings, self.teams, self.systems, \
        self.checks, self.injects, self.remote = db.load()

    def check(self, check_round):
        self.calculate_scores(check_round)
        self.check_injects()
        self.load()
        print("[INFO] New round of checks (CHECKROUND" + str(check_round) + ")")
        for team, team_info in self.teams.items():
            for system, sys_info in self.systems.items():
                for check in sys_info['checks']:
                    opts = None if check not in sys_info else sys_info[check]
                    if opts and "type" in sys_info[check]:
                        type = sys_info[check]["type"]
                    else:
                        type = check
                    ip = self.settings['network']. \
                        format(team_info['subnet'], sys_info['host'])
                    thread = Thread(target=checker, args=(system, \
                        check, type, opts, team, ip))
                    thread.start()

    def latest(self):
        try: return db.get_service_latest()
        except: return "No checks completed yet."

    def status(self):
        check_round = db.get_check_round()
        status = {}
        for team in self.teams:
            status[team] = {}
            for check in self.checks:
                try: [(result, error, time)] = \
                     db.get_service_check(team, check, check_round)
                except ValueError:
                    try:
                        [(result, error, time)] = \
                            db.get_service_check(team, check, check_round - 1)
                    except ValueError: result, error, time = (2, "Pending.", "00:00")
                status[team][check] = (result, error, time)
        return status

    def results(self):
        results = {}
        for team in self.teams:
            results[team] = {}
            for check in self.checks:
                result_log = db.get_service_checks(team, check)
                results[team][check] = result_log
        return results

    def get_slas(self):
        results = self.results()
        sla_totals, sla_log = {}, []
        for team in self.teams:
            sla_totals[team] = {}
            for check in self.checks:
                down, sla = 0, 0
                for result, error, time, check_round in results[team][check]:
                    if not result:
                        down += 1
                    if down >= 5:
                        sla_log.append((team, check, time))
                        sla += 1
                        down = 0
                sla_totals[team][check] = sla
        return sla_totals, sla_log

    def get_scores(self, check_round):
        scores = {}
        for team in self.teams:
            scores[team] = []
            for i in range(check_round):
                scores[team].append([db.get_totals_score(team, "service", i), \
                                db.get_totals_score(team, "sla", i), \
                                db.get_totals_score(team, "css", i), \
                                db.get_totals_score(team, "total", i)])
        return scores

    def calculate_scores(self, check_round):
        results = self.results()
        sla_totals, _ = self.get_slas()
        for team in self.teams:
            # Service Scores
            service_score = 0
            for check, check_results in results[team].items():
                for check_result in check_results:
                    if check_result[0] == 1:
                        service_score += 1
            db.insert_totals_score(team, "service", service_score, check_round)

            # SLA
            sla_points = 0
            for check in self.checks:
                sla_points += -5 * sla_totals[team][check]
            db.insert_totals_score(team, "sla", sla_points, check_round)

            # CSS Points
            css_points = db.get_css_score()
            db.insert_totals_score(team, "css", css_points, check_round)

            # Total Points
            db.insert_totals_score(team, "total", service_score + sla_points + css_points, check_round)

    def check_injects(self):
        for title, inject in self.injects.items():
            if db.get_current_time() > db.format_time(inject["time"]) and "ran" not in inject:
                print("[INFO] Checking data for inject", title)
                config = db.read_running_config()
                self.injects[title] = inject
                if inject["type"] == "service" and "services" in inject:
                    if db.get_current_time() > db.format_time(inject["enact_time"]):
                        print("[INFO] Adding service into running-config for", title)
                        config["injects"][title]["ran"] = 1
                        for system, checks in inject["services"].items():
                            if system in config["systems"]:
                                for index, check in enumerate(checks["checks"]):
                                    if check in config["systems"][system]["checks"] and "modify" in check:
                                        print("[INFO] Modifying check", check, "for", system)
                                        del config["systems"][system]["checks"][check]
                                    elif check in config["systems"][system]["checks"]:
                                        print("[ERROR] Duplicate check", check, "for", system, "without modify option")
                                        del checks["checks"][index]
                                new_checks = config["systems"][system]["checks"] + checks["checks"]
                                for propertyName, propertyValue in checks.items():
                                    if propertyName != "checks":
                                        config["systems"][system][propertyName] = propertyValue
                                config["systems"][system]["checks"] = new_checks
                            else:
                                config["systems"][system] = checks
                            del config["injects"][title]["services"]
                else:
                    config["injects"][title]["ran"] = 1

                db.write_running_config(config)

    def verify_challenge(self, challenge, password=None):
        randomHash1 = "71844fd161e20dc78ce6c985b42611cfb11cf196"
        randomHash2 = "e31ad5a009753ef6da499f961edf0ab3a8eb6e5f"
        chalString = db.printAsHex(db.xor(randomHash1, randomHash2))
        if password:
            key = db.printAsHex(sha256(password.encode()).digest())
            chalString = db.printAsHex(db.xor(chalString, key))
        if chalString == challenge:
            print("[INFO] Challenge string from score update was correct!")
            return True
        else:
            return False

    def decrypt_vulns(self, vulns, password=None):
        vulns = bytes.fromhex(vulns)

        if password:
            try:
                key = sha256(password.encode()).digest()
                iv = vulns[:12]
                mac = vulns[len(vulns)-16:]
                ciphertext = vulns[12:len(vulns)-16]
                cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
                vulns = cipher.decrypt_and_verify(ciphertext, mac)
                vulns = vulns.decode("ascii").strip().rstrip()
            except:
                print("[ERROR] Failed to decrypt client traffic.")
                return "", False
        else:
            vulns = vulns.decode("ascii")

        vulns = vulns.split("|")
        return vulns, True

def start():
    config = db.read_running_config()
    if not config or "reset" in config["settings"] and config["settings"]["reset"] == 1:
            db.reset_engine()
    config = db.read_running_config()

    if "css_mode" in config["settings"] and config["settings"]["css_mode"]:
        print("[INFO] Scoring checks not running, engine is in CCS mode.")
    else:
        em = EngineModel()
        while True:
            em.load()
            running = em.settings['running']
            if "interval" in em.settings:
                interval = em.settings['interval']
            else:
                interval = 150
            if "jitter" in em.settings:
                jitter = em.settings['jitter']
            else:
                jitter = 30

            em.wait = 1

            if running == 1:
                check_round = db.get_check_round()
                db.update_check_round(check_round + 1)
                em.check(check_round)
                em.wait = random.randint(-jitter, jitter) + interval
            elif running == 0:
                print("[INFO] Scoring is paused.")
            elif running == -1:
                print("[INFO] Scoring has been stopped.")
                return
            else:
                print("[ERROR] Unsure what 'running' is set to.")

            print("[WAIT]", str(em.wait), "seconds")
            time.sleep(em.wait)


if __name__ == '__main__':
    if len(sys.argv) == 1:
        start()
    elif len(sys.argv) == 2 and sys.argv[1] == "start":
        print("[CONF] Starting engine...")
        db.start_engine()
    elif len(sys.argv) == 2 and sys.argv[1] == "stop":
        print("[CONF] Stopping engine...")
        db.stop_engine()
    else:
         print("Usage: ./engine.py {start|stop}")
