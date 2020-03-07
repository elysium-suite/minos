# Minos Scoring Engine

This is a scoring engine meant to imitate the functionality of UTSA's CIAS CyberPatriot Scoring Engine with an emphasis on simplicity.  It acts as an uptime scorer (ex. your service has been up 50% of the time, and is down right now). It is based on DSU's DefSec Club [Scoring Engine](https://github.com/DSUDefSec/ScoringEngine). Named after the Greek myth of King Minos, judge of the dead.

## Features

- Uptime scoring engine
    - HTTP/HTTPS
    - SSH
    - SMB
    - FTP
    - SMTP
    - DNS
- Built-in patch server (folder of indexed files)
- Scoring check history, uptime percentages
- SLA Violation log and totals
- Clock and competition time tracker
- Timing-based injects and scoring
- CyberPatriot-esque scoring graphics and pages :)
- (WIP) CSS Find-and-fix vulnerability leaderboard

## Screenshots

![Status Page](setup/imgs/status.png)

## Installation

> The engine is supported and tested on Ubuntu 18.04 and above. YMMV on other distributions.

0. Clone this repository to `/opt/minos`.
```
cd /opt
git clone https://github.com/sourque/minos
```
1. Run `setup/install.sh` as superuser.
```
sudo /opt/minos/setup/install.sh
```
2. Start/restart the engine.
```
sudo systemctl restart scoring_engine scoring_web
```
3. Browse to `http://localhost`.

By default, the configuration and database don't reset when you start the engine, as long as there is a currently existing `running-config.cfg`. Set the `"reset=1"` flag in the `[settings]` directive to reset every time the engine launches.

## Scoring Engine Mechanics

- Check round runs every 2-3 minutes
- Team gets 1 point for each service up and functional each check
- Team gets 0 points for each service down
- Each five consecutive service down checks is -5 point penalty (SLA violation)

## CSS Points

(WIP) Engine takes CSS scores from an HTTP post request. If you're making your own client scoring software, request and auth token then use it. Your auth token will be the only one accepted for the machine for the duration of the scoring session, until it expires (5 mins without use) or the scoring engine resets.

## Configuration

The configuration is in TOML (Tom's Obvious, Minimal Language). See farther below for details on how to configure each service. Here's a quick example, scoring one box for one team with one inject:

```
[settings]
running = 1
interval = 150
jitter = 30
revert_penalty = 350

# Networking
domain = "paradis.island"
network = "172.16.{}.{}"

[web_admins]
white_team = "password"

[teams]
    [teams.team1]
    username = "team1"
    password = "FalseThreat"
    subnet = 10

[systems]
    [systems.calaneth]
    host = 2
    checks = [
        "ssh",
    ]

        [systems.calaneth.ssh]
        port = 2222

[injects.1]
time = "0:00"
type = "service"
enact_time = "0:30"
title = "Add HTTPS to website"
details = "Get HTTPS working on E-Commerce."

    [injects.1.services.calaneth]
    checks = [ "https",]

         [injects.1.services.calaneth.https]
         checkfile = "calaneth.html"

```

### Service Configuration

The configuration is loaded automatically from `config.cfg` every time the scoring engine is started. The configuration is the same whether the service is scored at startup or later, through an inject. Inject services can be new or modify existing services (if the `modify="True"` flag is set under the services settings). Here are the checks and their properties:

#### ssh
```
[systems.systemname.ssh]
port = 2000 # Default 22
private_key = "id_rsa" # Score authentication with keys
user = "root" # User must be set for key auth
```

#### smb
```
[systems.systemname.smb]
port = 1234 # Default 445
file = "cool_bug_facts.txt" # File to retrieve
hash = "9bb6c1dc2408ee6cb09778ca2ac6abad91de9be4 " # sha1 hash of the file
domain = "bugfacts.lan" # Default None
```
> Without file or hash, authentication won't be tested.

#### http/https
```
[systems.systemname.http]
port = 1234 # Default 80
host = localhost # Parameter to pass to "Host" header (Default IP)
path = "/index.php" # Remote path to retrieve (default '/'')
file = "systemname.html" # Local checkfile to compare with
tolerance = 50 # Difference tolerance, default 10%
```
```
[systems.systemname.https]
port = 1234 # Default 443
host = localhost # Parameter to pass to "Host" header (Default IP)
path = "/index.php" # Remote path to retrieve (default '/'')
file = "systemname.html" # Local checkfile to compare with
tolerance = 50 # Difference tolerance, default 10%
```

#### ftp
```
[systems.systemname.ftp]
port = 1234 # Default 21
file = "cool_bug_facts.txt" # File to retrieve
hash = "9bb6c1dc2408ee6cb09778ca2ac6abad91de9be4 " # sha1 hash of the file
file = "systemname.html" # Local checkfile to compare with
```
> Without file or hash, authentication won't be tested.

#### smtp
```
[system.systemname.smtp]
port = 1234 # Default 25
testhost = localhost.lan # Server to declare yourself as. Default example.org
```

#### dns
```
[system.systemname.dns]
port = 1234 # Default 53
query = "cool-site.lan" # Domain to query
query_type = "AAAA" # Default 'A' (IPv4)
answer = "127.0.0.1" # Correct answer to query
```
> Without query or answer, the checker won't work.

#### rdp
Not supported yet.

## Patch Server

Put any files you want served with the patch server in `/opt/minos/patch`.

## Injects

Injects are all based on the competition time. There are three types of injects:
- Service: will add a new scored service to all teams
```
[injects.1]
time = "0:05"
type = "service"
enact_time = "0:35"
title = "Add FTP server"
files = [ "file.pdf", ]
details = "Hello, please add the attached file to a new FTP server on Server3."

    [injects.1.services.server3]
    checks = [ "ftp",]

        [injects.1.services.server3.ftp]
        file = "file.pdf"
        hash = "05ec7de5d536998263a73b5da698711f7bfffb58"
```
- Manual: manually scored injects (ex. intrusion reports, memos, changelogs)
```
[injects.1]
time = "0:05"
type = "manual"
title = "Add Server2 to the Domain"
details = "Hello, please attach Server2 to the domain LocalDomain.lan."
points = 500
```
- Custom: (WIP) test for a condition in the client scoring engine



### Detailed Example

Here's an example, showing all the features of the engine:

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
white_team = "password" # Username = "Password"

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

[injects.1]
time = "0:00" # Inject will be posted at this time into the comp
type = "service"
enact_time = "0:30" # Service will start scoring at this time into the comp
title = "Add HTTPS to website"
details = "We need some extra security for our E-Commerce site. Please have HTTPS functional on the machine in thirty minutes."

    [injects.1.services.krolva] # At the enact time, this service will begin scoring
    checks = [ "https",]

         [injects.1.services.krolva.https] # Same syntax as the normal services. Be careful not to make typos
         checkfile = "krolva.html"

[injects.2]
time = "0:30"
type = "manual"
title = "Add the machine to the domain"
details = "In order to effectively distribute our group policy, please add the last Windows machine to the paradis.island domain."
points = "500"
```

## Contributing and Disclaimer

If you have anything you would like to add or fix, please make a pull request :) No improvement or fix is too small, and help is always appreciated.

This project is in no affiliated with or endorsed by the Air Force Association, University of Texas San Antonio, or the CyberPatriot program.
