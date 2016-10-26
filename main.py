import os
import re
import random
import hashlib
import hmac
from string import letters

import webapp2
import jinja2

from google.appengine.ext import db


template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
                               autoescape = True)

secret = 'secret'

def make_secure_val(val):
    return '%s|%s' % (val, hmac.new(secret, val).hexdigest())

def check_secure_val(secure_val):
    val = secure_val.split('|')[0]
    if secure_val == make_secure_val(val):
        return val

class BlogHandler(webapp2.RequestHandler):
    def write(self, *a, **kw):
        self.response.write(*a, **kw)

    def render_str(self, template, **params):
        t = jinja_env.get_template(template)
        params['user'] = self.user
        return t.render(params)

    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))

    def set_secure_cookie(self, name, val):
        cookie_val = make_secure_val(val)
        self.response.headers.add_header(
                'Set-Cookie',
                '%s=%s; Path=/' % (name, cookie_val))

    def read_secure_cookie(self, name):
        cookie_val = self.request.cookies.get(name)
        return cookie_val and check_secure_val(cookie_val)

    def login(self, user):
        self.set_secure_cookie('user_id', str(user.key().id()))

    def logout(self):
        self.response.headers.add_header('Set-Cookie', 'user_id=; Path=/')

    def initialize(self, *a, **kw):
        webapp2.RequestHandler.initialize(self, *a, **kw)
        uid = self.read_secure_cookie('user_id')
        self.user = uid and User.by_id(int(uid))


def make_salt(length = 5):
    return ''.join(random.choice(letters) for x in xrange(length))

def make_pw_hash(name, pw, salt = None):
    if salt is None:
        salt = make_salt()

    h = hashlib.sha256(name + pw + salt).hexdigest()
    return '%s,%s' % (salt, h)

def valid_pw(name, password, h):
    salt = h.split(',')[0]
    return h == make_pw_hash(name, password, salt)

class User(db.Model):
    username = db.StringProperty(required = True)
    email = db.StringProperty(required = True)
    password = db.StringProperty(required = True)

    @classmethod
    def by_id(cls, uid):
        return User.get_by_id(uid)

    @classmethod
    def by_name(cls, name):
        u = User.all().filter('username =', name).get()
        return u

    @classmethod
    def login(cls, name, pw):
        u = cls.by_name(name)
        print u
        if u and valid_pw(name, pw, u.password):
            return u


USERNAME_RE = re.compile(r'^[a-zA-Z ]{3,20}$')
def valid_username(username):
    return username and USERNAME_RE.match(username)

PASSWORD_RE = re.compile(r'^.{3,20}$')
def valid_password(password):
    return password and PASSWORD_RE.match(password)

EMAIL_RE = re.compile(r'^[\S]+@[\S]+\.[\S]+$')
def valid_email(email):
    return email and EMAIL_RE.match(email)

class SignupPage(BlogHandler):
    def render_front(self, username='', email='',
                     password='', verify='', error=''):
        self.render('signup.html',
                    username = username,
                    email = email,
                    password = password,
                    verify = verify,
                    error = error)
    def get(self):
        self.render_front()

    def post(self):
        username = self.request.get('username')
        email = self.request.get('email')
        password = self.request.get('password')
        verify = self.request.get('verify')

        params = dict(username = username, email = email)
        has_error = False

        if not valid_username(username):
            has_error = True
            params['error_username'] = "That's not a valid username."
        else:
            u = db.GqlQuery("SELECT * FROM User WHERE username = '%s'"
                    % username)
            if u.count() > 0:
                has_error = True
                params['error_username'] = 'That username already exists.'


        if not valid_email(email):
            has_error = True
            params['error_email'] = "That's not a valid email."
        if not valid_password(password):
            has_error = True
            params['error_password'] = "That's not a valid password"
        elif password != verify:
            has_error = True
            params['error_verify'] = "Your password didn't match."

        if has_error:
            self.render("signup.html", **params)
        else:
            pw = make_pw_hash(username, password)
            u = User(username = username, password = pw, email = email)
            u.put()

            self.login(u)
            self.redirect('/blog')


class Login(BlogHandler):
    def get(self):
        self.render('login.html')

    def post(self):
        username = self.request.get('username')
        password = self.request.get('password')

        u = User.login(username, password)

        if u:
            self.login(u)
            self.redirect('/blog')
        else:
            msg = 'Invalid username or password'
            self.render('login.html', error = msg)

class Logout(BlogHandler):
    def get(self):
        self.logout()
        self.redirect('/blog')


class Entry(db.Model):
    subject = db.StringProperty(required = True)
    content = db.TextProperty(required = True)
    created = db.DateTimeProperty(auto_now_add = True)

class EntryPage(BlogHandler):
    def get(self, page_id):
        entry = Entry.get_by_id(int(page_id))

        if entry:
            self.render('main.html', entries=[entry])
        else:
            self.redirect('/blog')

class AboutPage(BlogHandler):
    def get(self):
        self.render('about.html')

class NewPostPage(BlogHandler):
    def render_front(self, subject='', content='', error=''):
        self.render('newpost.html', subject=subject, content=content,
                    error=error)

    def get(self):
        self.render_front()

    def post(self):
        subject = self.request.get('subject')
        content = self.request.get('content')

        if subject and content:
            b = Entry(subject=subject, content=content)
            bput = b.put()
            self.redirect('/blog/%s' % bput.id())
        else:
            error = 'subject and content are needed'
            self.render_front(subject, content, error)

class MainPage(BlogHandler):
    def get(self):
        entries = db.GqlQuery('SELECT * FROM Entry ORDER BY created DESC')
        self.render('main.html', entries = entries)

app = webapp2.WSGIApplication([
    ('/blog', MainPage),
    ('/blog/(\d+)', EntryPage),
    ('/blog/about', AboutPage),
    ('/blog/newpost', NewPostPage),
    ('/blog/signup', SignupPage),
    ('/blog/login', Login),
    ('/blog/logout', Logout),
], debug=True)

