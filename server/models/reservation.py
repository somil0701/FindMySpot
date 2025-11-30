# server/models/reservation.py
from . import db
from datetime import datetime

class Reservation(db.Model):
    __tablename__ = 'reservation'  # ensure consistent table name

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    spot_id = db.Column(db.Integer, db.ForeignKey('parking_spot.id'), nullable=False)

    # canonical names used by controllers & frontend
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=True)
    cost = db.Column(db.Float, default=0.0)

    # NEW: optional remarks/notes column
    notes = db.Column(db.Text, nullable=True)

    # optional relationships (handy but not required)
    user = db.relationship('User', backref='reservations', lazy=True)
    spot = db.relationship('ParkingSpot', backref='reservations', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'spot_id': self.spot_id,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'cost': self.cost,
            'notes': self.notes
        }
