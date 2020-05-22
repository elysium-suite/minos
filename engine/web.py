from flask_login import UserMixin
import db
import bcrypt

class WebModel(object):

    def load(self):
        self.users = {}
        for uid, team, name, pwhash, is_admin in db.execute("SELECT * FROM users"):
            self.users[uid] = User(uid, team, name, is_admin)

    def change_pw(self, username, pw):
        pwhash = bcrypt.hashpw(pw.encode('utf-8'), bcrypt.gensalt())
        db.execute("UPDATE users SET password=? where username=?", (pwhash, username))

    def check_pw(self, username, pw):
        username = username.lower()
        data = db.execute("SELECT * FROM users WHERE username=?", (username,))
        if not data:
            return ""
        else:
            uid, team, name, pwhash, is_admin = data[0]
        return bcrypt.checkpw(pw.encode('utf-8'), pwhash)


class User(UserMixin):
    def __init__(self, uid, team, name, is_admin):
        self.id = uid
        self.team = team
        self.name = name
        self.is_admin = is_admin

    def get_id(self):
        return chr(self.id)
