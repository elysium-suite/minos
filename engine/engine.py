from threading import Thread
from checks import checker
import sqlite3 as sql
import time, random
import db
import os
import sys

class EngineModel(object):

    def load(self):
        self.settings, self.teams, self.systems, self.checks, self.injects = db.load()

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
                    thread = Thread(target=checker, args=(check_round, system, \
                        check, type, opts, team, ip))
                    thread.start()

    def latest(self):
        try: return db.get_service_latest()
        except: return "No checks completed yet."

    def status(self):
        try: check_round = db.get_check_round()
        except: check_round = 1
        status = {}
        for team in self.teams:
            status[team] = {}
            for check in self.checks:
                try: [(result, error, time)] = \
                     db.get_service_check(team, check, check_round)
                except:
                    try: [(result, error, time)] = \
                         db.get_service_check(team, check, check_round-1)
                    except: result, error, time = (2, "Pending.", "00:00")
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
                for result, error, time in results[team][check]:
                    if not result:
                        down += 1
                    if down >= 5:
                        sla_log.append((team, check, time))
                        sla += 1
                        down = 0
                sla_totals[team][check] = sla
        return sla_totals, sla_log

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
            db.insert_totals_score(team, "service", service_score)

            # SLA
            sla_points = 0
            for check in self.checks:
                sla_points += -5 * sla_totals[team][check]
            db.insert_totals_score(team, "sla", sla_points)

            # CSS Points
            css_points = 0

            # Total Points
            db.insert_totals_score(team, "total", service_score + sla_points + css_points)

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
                                host_ip = config["systems"][system]["host"]
                                config["systems"][system] = checks
                                config["systems"][system]["checks"] = new_checks
                                config["systems"][system]["host"] = host_ip
                            else:
                                config["systems"][system] = checks
                            del config["injects"][title]["services"]
                else:
                    config["injects"][title]["ran"] = 1
                db.write_running_config(config)

def start():
    em = EngineModel()
    em.load()

    config = db.read_config()
    if "reset" in config["settings"] and config["settings"]["reset"] == 1:
        db.reset_engine()

    while True:
        em.load()
        if "reset" in em.settings:
            print("[INFO] 'reset' directive set, resetting.")
            db.reset_engine()
            em.load()
        running = em.settings['running']
        interval = em.settings['interval']
        jitter = em.settings['jitter']
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

    # stop mechanism doesnt work, systemd just shoots the process
    elif len(sys.argv) == 2 and sys.argv[1] == "stop":
        print("[CONF] Stopping engine...")
        db.stop_engine()

    else:
         print("Usage: ./engine.py [stop]")
