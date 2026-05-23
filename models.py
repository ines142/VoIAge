from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'user'

    id       = db.Column(db.Integer, primary_key=True)
    name     = db.Column(db.String(80), nullable=False)
    email    = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    # Relation : un User peut avoir plusieurs Trips
    trips = db.relationship('Trip', backref='owner', lazy=True)

    def __repr__(self):
        return f'<User {self.email}>'


class Trip(db.Model):
    __tablename__ = 'trip'

    id          = db.Column(db.Integer, primary_key=True)
    destination = db.Column(db.String(100), nullable=False)
    budget      = db.Column(db.Float, nullable=False)
    date        = db.Column(db.Date, nullable=False)

    # Clé étrangère vers User
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f'<Trip {self.destination}>'
