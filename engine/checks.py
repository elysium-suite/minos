import timeout_decorator
import db

path = "/opt/minos/"

def gopt(varname, check_opts):
    try:
        if varname in check_opts:
            return check_opts[varname]
        return None
    except:
        return None

def checker(system, check, type, opts, team, ip):
    try:
        if type == "ssh":
            port = gopt('port', opts) or 22
            private_key = gopt('private_key', opts) or None
            user = gopt('user', opts) or None
            result, error = check_ssh(ip, port, user, private_key)
        elif type == "smb":
            port = gopt('port', opts) or 445
            anon = gopt('anon', opts) or "no"
            share = gopt('share', opts) or ""
            checkfile = gopt('file', opts) or None
            filehash = gopt('hash', opts) or None
            domain = gopt('domain', opts) or None
            result, error = check_smb(ip, port, anon, share, checkfile, filehash, domain)
        elif type == "http" or type == "https":
            if gopt('port', opts):
                port = gopt('port', opts)
            elif check == "https":
                port = 443
            else:
                port = 80
            if gopt('proto', opts):
                proto = gopt('proto', opts)
            elif check == "https":
                proto = "https"
            else:
                proto = "http"
            host = gopt('host', opts) or ip
            path = gopt('path', opts) or ""
            checkfile = gopt('file', opts) or None
            tolerance = gopt('tolerance', opts) or 20
            result, error = check_http(ip, port, proto, host, path, checkfile, tolerance)
        elif type == "ftp":
            port = gopt('port', opts) or "21"
            path = gopt('path', opts) or ""
            checkfile = gopt('file', opts) or None
            filehash = gopt('hash', opts) or None
            result, error = check_ftp(ip, port, checkfile, filehash)
        elif type == "smtp":
            port = gopt('port', opts) or "25"
            testhost = gopt('testhost', opts) or "example.org"
            result, error = check_smtp(ip, port, testhost)
        elif type == "dns":
            port = gopt('port', opts) or "53"
            query = gopt('query', opts) or None
            query_type = gopt('query_type', opts) or "A"
            answer = gopt('answer', opts) or None
            if not query or not answer:
                result, error = (0, "No query specified")
            else:
                result, error = check_dns(ip, port, query, query_type, answer)
        elif type == "rdp":
            result, error = check_rdp(ip, port, testhost)
        else:
            result, error = (0, "Checker not found.")
            print("[ERROR] Oops... checker not found for", check)
    except Exception as e:
        result, error = (0, e)

    db.insert_service_score(db.get_check_round(), team, system, check, result, error)

###############
# SSH Checker #
###############

from paramiko import client, RSAKey
from paramiko.ssh_exception import *
import socket

@timeout_decorator.timeout(20, use_signals=False)
def check_ssh(ip, port, user, private_key):
    try:
        cli = client.SSHClient()
        cli.load_host_keys("/dev/null")
        cli.set_missing_host_key_policy(client.AutoAddPolicy())
        if private_key and user:
            print("[DEBUG-SSH] Trying pubkey auth for", ip)
            k = RSAKey.from_private_key_file(path + "checkfiles/" + private_key)
            cli.connect(ip, port, user, banner_timeout=20, timeout=20, auth_timeout=20, pkey=k)
        else:
            cli.connect(ip, port, "root", "Password3#", banner_timeout=20, timeout=20, auth_timeout=20)
        cli.close()
        return 1, None
    except Exception as e:
        if str(e) == "Authentication failed." and not private_key:
            return 1, None
        return 0, str(e)

###############
# SMB Checker #
###############

import subprocess
import hashlib
import socket
from smb.SMBConnection import SMBConnection

@timeout_decorator.timeout(20, use_signals=False)
def check_smb(ip, port, anon, share, checkfile, filehash, domain):
    if not domain:
        domain = ""

    conn = SMBConnection("Guest", "", socket.gethostname(), "none", domain, is_direct_tcp=True)
    try:
        conn.connect(ip, port)
    except Exception as e:
        return 0, "Failed to connect to ip: %s on port %s." % (ip, port)

    try:
        shareList = conn.listShares(timeout=5)
        found = False
        for i in range(len(shareList)):
            if shareList[i].name == share:
                found = True
                break

        if found == False:
            return 0, "Samba share %s not found." % (share)
    except Exception as e:
            return 0, "Failed to retrieve list of shares."

    if checkfile and filehash:
        print("[DEBUG-SMB] Grabbing file for", ip)
        tmpfile = path + "engine/tmpfiles/smb-%s-%s-%s-checkfile" % (share, ip, checkfile)
        try:
            with open(tmpfile, "wb") as fp:
                conn.retrieveFile(share, checkfile, fp)
            
            with open(tmpfile, "rb") as f:
                content = f.read()
                checkhash = hashlib.sha1(content).hexdigest();
            if checkhash != filehash:
                return(0, "Hash %s does not match %s." % (checkhash, filehash))
            return 1, None
        except Exception as e:
            return 0, "Failed to read share %s." % (share)
    else:
        print("[DEBUG-SMB] Trying anonymous/noauth for", ip)
        try:
            fileList = conn.listPath(share, "/")
            return 1, None
        except Exception as e:
            return 0, "Failed to read share %s." % (share) 


###################
# HTTP{S} Checker #
###################

import requests
import urllib3
from difflib import SequenceMatcher
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

@timeout_decorator.timeout(20, use_signals=False)
def check_http(ip, port, proto, host, path, checkfile, tolerance):
    url = '{}://{}/{}'.format(proto, ip, path, checkfile)
    tmpfile = "tmpfiles/%s-%s-%sresult" % (proto, ip, path)
    headers = {'Host': host}
    try:
        session = requests.Session()
        r = session.get(url, headers=headers, verify=False, allow_redirects=True)
        r.raise_for_status()
        content = str.encode(r.text)
        if checkfile:
            with open("/opt/minos/checkfiles/" + checkfile, 'rb') as f:
                expected = f.read()
            seq = SequenceMatcher(None, expected, content)
            difference = round(100 - (seq.quick_ratio() * 100))
            print("[DEBUG-HTTP] Difference between retrieved page and", \
                   checkfile, "is", difference, "while tolerance is", tolerance)
            if difference >= tolerance:
                with open("/opt/minos/engine/" + tmpfile, "wb") as cf:
                    cf.write(content)
                return (0, "Page differed too greatly (difference " + \
                            str(difference) + "% tolerance " + str(tolerance) + \
                             "%). See file retrieved at /static/" + tmpfile)
            return (1, None)
        return (1, None)
    except Exception as e:
        return (0, str(e))

###############
# FTP Checker #
###############

import ftplib

@timeout_decorator.timeout(20, use_signals=False)
def check_ftp(ip, port, checkfile, filehash):
    ftp = ftplib.FTP()
    if checkfile and filehash:
        tmpfile = path + "engine/tmpfiles/%s-%s-%sresult" % (port, ip, checkfile)
        try:
            print("[DEBUG-FTP] Trying anonymous login to grab file for", ip)
            ftp.connect(ip, int(port))
            ftp.login(user="anonymous", passwd="anonymous@example.com")
            ftp.set_pasv(True)
            with open(tmpfile, "w") as f:
                ftp.retrbinary('RETR %s' % checkfile, open(tmpfile, 'wb').write)
            with open(tmpfile, "rb") as f:
                checkhash = hashlib.sha1(f.read()).hexdigest();
            if checkhash != filehash:
                return(0, "Hash %s does not match %s." % (checkhash, filehash))
            ftp.quit()
            return (1, "None")
        except Exception as e:
            return (0, e)
    else:
        try:
            ftp.connect(ip, int(port))
            ftp.quit()
            return (1, "None")
        except Exception as e:
            return (0, e)

################
# SMTP Checker #
################

from smtplib import SMTP

@timeout_decorator.timeout(20, use_signals=False)
def check_smtp(ip, port, testhost):
    try:
        print("[DEBUG-SMTP] Connecting to server with testhost", testhost, "for", ip)
        smtp = SMTP(ip, port)
        # smtp.sendmail(testhost, root@localhost, 'Subject: {}'.format(message)) # mail to send option?
        smtp.quit()
        return (1, "None")
    except Exception as e:
        return (0, e)

###############
# DNS Checker #
###############

from dns import resolver

@timeout_decorator.timeout(20, use_signals=False)
def check_dns(ip, port, query, query_type, answer):
    res = resolver.Resolver()
    res.nameservers = [ip]
    try:
        query_answer = str(res.query(query, query_type).rrset[0])
        print("[DEBUG-DNS] DNS answered", query_answer)
        if answer != query_answer:
            return (0, "DNS server returned incorrect answer " +\
                        query_answer + " to query " + query +". Correct \
                        answer was " + answer + ".")
        return (1, None)
    except Exception as e:
        return (0, e)

###############
# RDP Checker #
###############

@timeout_decorator.timeout(20, use_signals=False)
def check_rdp(ip, domain, username, password):
    """ # WORK IN PRORESS
    cmd = ['xfreerdp', '--ignore-certificate', '--authonly', '-u', username, '-p', password]
    if not domain is None:
        cmd.extend(['-d', domain.domain])
        opt_str = '--ignore-certificate --authonly -u \'{}\' -p \'{}\' {}:{}'
    cmd.append('{}:{}'.format(poll_input.ip, poll_input.port))

    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        result = RdpPollResult(True)
        return result
    except Exception as e:
#            if e.returncode == 131 and 'negotiation' in str(e.output) and not 'Connection reset by peer' in str(e.output):
#                result = RdpPollResult(True)
#                return result
        #print("{{{{%s}}}}" % e.output)
        result = RdpPollResult(False, e)
        return result
    """
    return (0, "RDP is WIP sorry :("    )
