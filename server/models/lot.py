from . import db

class ParkingLot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    address = db.Column(db.String(250))
    price_per_hour = db.Column(db.Float, default=0.0)
    capacity = db.Column(db.Integer, default=0)

    spots = db.relationship('ParkingSpot', backref='lot', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'address': self.address,
            'price_per_hour': self.price_per_hour,
            'capacity': self.capacity
        }
