from flask_wtf import FlaskForm
from wtforms import *
from wtforms.validators import *
import bcrypt
import flask_login

class LoginForm(FlaskForm):
    """
    A form for user login.

    Attributes:
        username (StringField): A username field
        password (PasswordField): A password field
        wm (WebModel): The web model
    """
    username = StringField('Username', validators=[InputRequired()])
    password = PasswordField('Password', validators=[InputRequired()])

    def __init__(self, wm):
        super().__init__()
        self.wm = wm

    def validate(self):
        """
        Check whether the username / password combo is correct

        Returns:
            bool: Are the credentials valid?
        """
        if not super(LoginForm, self).validate():
            return False

        return self.wm.check_pw(self.username.data, self.password.data)


class PasswordResetForm(FlaskForm):
    """
    A form for reseting a web user's password

    Attributes:
        user (SelectField): Field to select the user whose password to reset
        current_pw (PasswordField): Field for the user's current password
        new_pw (PasswordField): Field for the user's new password
        confirm_new_pw (PasswordField): Field to confirm the user's new password
        wm (WebModel): The web model
    """
    user = SelectField('User', validators=[Optional()])
    current_pw = PasswordField('Current Password', validators=[Optional()])
    new_pw = PasswordField('New Password', validators=[InputRequired()])
    confirm_new_pw = PasswordField('Confirm New Password', validators=[InputRequired()])

    def __init__(self, wm):
        super(PasswordResetForm, self).__init__()
        self.wm = wm
        self.user.choices=[(username, username) for username in wm.users.keys()]
        self.user.choices.sort()

    def validate(self):
        """
        Check that the current password is correct and the two new passwords are the same.

        Returns:
            bool: Is the form valid?
        """
        if not super(PasswordResetForm, self).validate():
            return False

        if self.new_pw.data != self.confirm_new_pw.data:
            self.errors['samepw'] = 'Passwords don\'t match'
            return False

        # If the user is not an admin, they must enter their current password
        if not flask_login.current_user.is_admin:
            username = self.user.data
            print('formdata', username)
            if username == 'None':
                username = flask_login.current_user.name
            print(username)
            username = username.lower()
    
            pwhash = self.wm.get_user_password(username)
            pwhash = pwhash.encode('utf-8')
            passwd = self.current_pw.data.encode('utf-8')
    
            if not bcrypt.checkpw(passwd, pwhash):
                self.errors['validpw'] = 'Invalid Password'
                return False
        return True
