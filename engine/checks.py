import timeout_decorator
import db

def gopt(varname, check_opts):
    try:
        if varname in check_opts:
            return check_opts[varname]
        return None
    except:
        return None

@timeout_decorator.timeout(20, use_signals=False)
def checker(check_round, system, check, opts, team, ip):    
    # SSH checker
    if check == "ssh":
        port = gopt('port', opts) or 22
        private_key = gopt('private_key', opts) or None
        user = gopt('user', opts) or None
        try:
            result, error = check_ssh(ip, port, user, private_key)
        except:
            result, error = (0, "Timed out!")    
    # SMB checker
    elif check == "smb":
        port = gopt('port', opts) or 445
        anon = gopt('anon', opts) or "no"
        share = gopt('share', opts) or ""
        checkfile = gopt('file', opts) or None
        filehash = gopt('hash', opts) or None
        domain = gopt('domain', opts) or None
        try:
            result, error = check_smb(ip, port, anon, share, checkfile, filehash, domain)
        except:
            result, error = (0, "Timed out!")
    # HTTP/HTTPS checker
    elif check == "http" or check == "https":
        if gopt('port', opts):
            port = gopt('port', opts)
        elif check == "https":
            port = 443
        else:
            port = 80
        proto = gopt('proto', opts) or "http"
        host = gopt('host', opts) or ip
        path = gopt('path', opts) or ""
        checkfile = gopt('file', opts) or None
        tolerance = gopt('tolerance', opts) or 100
        try:
            result, error = check_http(ip, port, proto, host, path, checkfile, tolerance)
        except:
            result, error = (0, "Timed out!")
    # FTP checker
    elif check == "ftp":
        port = gopt('port', opts) or "21"
        path = gopt('path', opts) or ""
        anon = gopt('anon', opts) or "no"
        checkfile = gopt('file', opts) or None
        filehash = gopt('hash', opts) or None
        #try:
        result, error = check_ftp(ip, port, anon, checkfile, filehash)
        #except:
        #    result, error = (0, "Timed out!")
    else:
        result, error = (0, "Checker not found.")
        print("[ERROR] Oops... checker not found for", check)
        
    db.insert_service_score(check_round, team, system, check, result, error)

###############
# SSH Checker #
###############

from paramiko import client, RSAKey
from paramiko.ssh_exception import *
import socket

def check_ssh(server, port, user, private_key):
    try:
        cli = client.SSHClient()
        cli.load_host_keys("/dev/null")
        cli.set_missing_host_key_policy(client.AutoAddPolicy())
        if private_key and user:
            k = RSAKey.from_private_key_file("/opt/minos/engine/checkfiles/" + private_key)
            cli.connect(server, port, user, "Password2@", timeout=5, auth_timeout=5, pkey=k)
        else:
            cli.connect(server, port, "root", "Password3#", timeout=5, auth_timeout=5)
        cli.close()
        return 1, None
    except (Exception, socket.error) as e:
        if str(e) == "Authentication failed." and not private_key:
            return 1, None
        return 0, str(e)

###############
# SMB Checker #
###############

import subprocess
import hashlib

def check_smb(server, port, anon, share, checkfile, filehash, domain):
    path = '//{}/{}'.format(server, share)
    if checkfile and filehash:
        tmpfile = "./tmpfiles/smb-%s-%s-%s-checkfile" % (share, server, checkfile)
        cmd = 'get "{}" "{}"'.format(checkfile, tmpfile)
        smbcli = ['smbclient', "-N", path, '-c', cmd]
        if domain:
            smbcli.extend(['-W', domain])
        try:
            output = subprocess.check_output(smbcli, stderr=subprocess.STDOUT)
            with open(tmpfile, "r") as f: 
                content = f.read().encode('ascii')
                checkhash = hashlib.sha1(content).hexdigest();
            if checkhash != filehash:
                return(0, "Hash %s does not match %s." % (checkhash, filehash))
            return 1, None
        except Exception as e:
            return 0, str(e)
    else:
        smbcli = ['smbclient', "-L", path]
        if domain:
            smbcli.extend(['-W', domain])
        try:
            output = subprocess.check_output(smbcli, stderr=subprocess.STDOUT)
            return 1, None
        except Exception as e:
            return 0, str(e)
        

###################
# HTTP{S} Checker #
###################

import requests
import urllib3
from difflib import SequenceMatcher
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def check_http(ip, port, proto, host, path, checkfile, tolerance):
    url = '{}://{}/{}'.format(proto, ip, path, checkfile)
    tmpfile = "tmpfiles/%s-%s-%sresult" % (proto, ip, path)
    headers = {'Host': host}
    try:
        session = requests.Session()
        r = session.get(url, headers=headers, verify=False, allow_redirects=True)
        r.raise_for_status()
        content = r.text
        if checkfile:
            with open("checkfiles/%s" % checkfile, 'r') as f:
                expected = f.read()
            seq = SequenceMatcher(None, expected, content)
            difference = seq.quick_ratio()
            if difference <= (100 - tolerance):
                with open(tmpfile, "w") as cf:
                    cf.write(content)
                return (0, "Page differed too greatly. See file retrived at " + tmpfile)
        return (1, None)
    except Exception as e:
        return (0, str(e))

###############
# FTP Checker #
###############

import ftplib
def check_ftp(ip, port, anon, checkfile, filehash):
    ftp = ftplib.FTP()
    if checkfile and filehash:
        tmpfile = "tmpfiles/%s-%s-%sresult" % (port, ip, checkfile)
        extension = self.get_extension(poll_input.filepath)
        f = self.open_file(extension)

        try:
            ftp.connect("anonymous", "anonymous@example.com")
            ftp.login(user="anonymous", passwd="anonymous@example.com")
            ftp.set_pasv(True)
            with open(tmpfile, "w") as f:
                ftp.retrbinary('RETR {}'.format(), f.write)
            with open(tmpfile, "r") as f: 
                content = f.read().encode('ascii')
                checkhash = hashlib.sha1(content).hexdigest();
            if checkhash != filehash:
                return(0, "Hash %s does not match %s." % (checkhash, filehash))
            return 1, None
            f.close()
            ftp.quit()
            result = FtpPollResult(f.name, None)
            return result
        except Exception as e:
            f.close()
            result = FtpPollResult(None, e)
            return result
    else:

################
# SMTP Checker #
################

from smtplib import SMTP

def check_smtp(ip, port, proto, host, path, checkfile, tolerance):
    try:
        smtp = SMTP(poll_input.server, poll_input.port)
        smtp.sendmail(from_addr, to_addr, 'Subject: {}'.format(message))
        smtp.quit()
        result = SmtpPollResult(True)
        return result
    except Exception as e:
        result = SmtpPollResult(False, e)
        return result


###############
# RDP Checker #
###############

def check_rdp(username, password, domain):
    username = poll_input.credentials.username
    password = poll_input.credentials.password
    domain = poll_input.credentials.domain
    cmd = ['xfreerdp', '--ignore-certificate', '--authonly', '-u', username, '-p', password]
    if not domain is None:
        cmd.extend(['-d', domain.domain])
        opt_str = '--ignore-certificate --authonly -u \'{}\' -p \'{}\' {}:{}'
    cmd.append('{}:{}'.format(poll_input.server, poll_input.port))

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


###############
# DNS Checker #
###############

from dns import resolver

@timeout_decorator.timeout(20, use_signals=False)
def check_dns(ip, query, record_type):
    def poll(self, poll_input):
        res = resolver.Resolver()
        res.nameservers = [poll_input.server]
        res.port = poll_input.port
    
        try:
            answer = res.query(poll_input.query, 
                    poll_input.record_type).rrset[0]
            result = DnsPollResult(str(answer))
            return result
        except Exception as e:
            result = DnsPollResult(None, e)
            return result


