# Minos CyberPatriot Scoring Engine

This is a scoring engine meant to replicate the functionality of UTSA's CIAS CyberPatriot Scoring System (along with some new features and some missing), with an emphasis on simplicity. It acts as an uptime scorer (ex. your service has been up 50% of the time, and is down right now). It is based on DSU's DefSec Club [Scoring Engine](https://github.com/DSUDefSec/ScoringEngine). Named after the Greek myth of King Minos, judge of the dead.

## Features

- Uptime scoring engine
    - Configurable round timing
    - HTTP/HTTPS
    - SSH, RDP
    - SMB, FTP
    - SMTP, IMAP
- Built-in patch server (folder of indexed files)
- Scoring check history, uptime percentages
- SLA Violation log and totals
- Clock and competition time tracker
- Timing-based injects and scoring
- CyberPatriot-esque scoring graphics and pages
- (TODO) CSS Find-and-fix vulnerability leaderboard

## Screenshots

![Status Page](setup/imgs/status.png)

## Installation

1. Run `setup/install.sh` as superuser.
2. Start the engine with `sudo systemctl restart scoring_engine scoring_web`. 
    - Restarting `scoring_engine` will reload the configuration from `config.cfg`.
3. Browse to `http://localhost`.

## Configuration

The configuration is loaded automatically from `config.cfg` every time the scoring engine is started. Here are the checks and their properties:

- ssh
    - private_key (filename of private key in checkfiles/)
        > note: with key, will only pass on successful auth
    - user (only for use with public key auth)
        > note: without private_key AND user, will not check auth
    - port (default 22)
- smb/samba
    - share (name of share)
    - checkfile (file to retrieve)
    - filehash (sha256 hash to compare file to)
    - domain (optional)
    - port (default 445)
- rdp
    - port (default 3389)
- smtp
- http and https
    - path (page to get)
    - file (file to compare to)
    - port (default 80 and 443)
    - tolerance (default 0, percent difference allowed)
    - host (default to ip, Host property for HTTP request)

The configuration is in TOML (Tom's Obvious, Minimal Language). Here's an example, showing all the features of the engine:

```
[settings]

# Scoring
interval = 150
jitter = 30
revert_penalty = 350

# Networking
domain = "paradis.island"
network = "172.16.{}.{}" # This is the subnet
                         # First is team ip (ex. team1 --> 1)
                         # Second is host ip (ex. calaneth --> 2)
                         # So team1 calaneth is 172.16.1.2

[web_admins]
white_team = "password"

[teams]
    [teams.team1]
    username = "team1"
    password = "FalseThreat"
    subnet = 10

    [teams.team2]
    username = "team2"
    password = "TripleWater"
    subnet = 2

[systems]
    [systems.calaneth]
    host = 2
    checks = [
        "ssh",
        "smtp",
        "smb"
    ]
    
        [systems.calaneth.ssh]
        port = 4000

    [systems.krolva]
    host = 4
    checks = [
        "ssh",
        "smb"
    ]
    
        [systems.krolva.smb]
        file="cool_titan_facts.txt"
        hash="6867d56f355fec13a828ea65824745b1790715fb"

    [systems.trost]
    host = 3
    checks = [
        "ssh",
        "smb"
    ]          
```

## Patch Server

Put any files you want served with the patch server in `/opt/minos/patch`.

## Injects

Injects are all based on the competition time. There are three types of injects:
- Service: will add a new scored service to all teams
- Manual: manually scored injects (ex. intrusion reports, memos, changelogs)
- Custom: (NOT IMPLEMENTED YET) test for a condition in the client scoring engine

## CSS Points

(NOT IMPLEMENTED YET) Engine takes CSS scores from an HTTP post request. If you're making your own client scoring software, request and auth token then use it. Your auth token will be the only one accepted for the machine for the duration of the scoring session, until it expires (5 mins without use) or the scoring engine resets.

## Scoring Engine Mechanics

- Check round runs every 2-3 minutes (in example config above)
- Team gets 1 point for each service up and functional each check
- Team gets 0 points for each service down
- Each five consecutive service down checks is -5 point penalty (SLA violation)

## Contributing and Disclaimer

If you have anything you would like to add or fix, please make a pull request :) No improvement or fix is too small, and help is always appreciated.

This project is in no affiliated with or endorsed by the Air Force Association, University of Texas San Antonio, or the CyberPatriot program.

