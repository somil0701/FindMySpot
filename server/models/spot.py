from . import db

class ParkingSpot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lot_id = db.Column(db.Integer, db.ForeignKey('parking_lot.id'), nullable=False)
    number = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(1), default='A')  # A=available, O=occupied

    def to_dict(self):
        return {
            'id': self.id,
            'lot_id': self.lot_id,
            'number': self.number,
            'status': self.status
        }
