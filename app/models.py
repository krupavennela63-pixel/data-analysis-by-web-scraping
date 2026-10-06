from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    scrape_sessions = db.relationship('ScrapeSession', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.email}>'


class ScrapeSession(db.Model):
    __tablename__ = 'scrape_sessions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    url = db.Column(db.String(2000), nullable=False)
    title = db.Column(db.String(500))
    status = db.Column(db.String(50), default='pending')  # pending, completed, failed
    selected_selectors = db.Column(db.Text)  # JSON string
    record_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)

    scraped_data = db.relationship('ScrapedData', backref='session', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<ScrapeSession {self.id} - {self.url[:50]}>'


class ScrapedData(db.Model):
    __tablename__ = 'scraped_data'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('scrape_sessions.id'), nullable=False, index=True)
    data_json = db.Column(db.Text, nullable=False)  # JSON string of row data
    row_index = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
