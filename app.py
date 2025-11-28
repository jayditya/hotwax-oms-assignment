from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date

# 1. Initialize the app
app = Flask(__name__)

# 2. Configuration
# NOTE: Ensure 'root:root' matches your MySQL credentials
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:root@localhost/ecommerce_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = 'super-secret-key'  # Change this in production!

# 3. Initialize Libraries
db = SQLAlchemy(app)
ma = Marshmallow(app)
jwt = JWTManager(app)

# --- MODELS ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class OrderHeader(db.Model):
    __tablename__ = 'Order_Header'
    order_id = db.Column(db.Integer, primary_key=True)
    order_date = db.Column(db.Date, nullable=False)
    customer_id = db.Column(db.Integer, nullable=False)
    shipping_contact_mech_id = db.Column(db.Integer, nullable=False)
    billing_contact_mech_id = db.Column(db.Integer, nullable=False)
    items = db.relationship('OrderItem', backref='order', cascade="all, delete-orphan", lazy=True)

class OrderItem(db.Model):
    __tablename__ = 'Order_Item'
    order_item_seq_id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('Order_Header.order_id'), nullable=False)
    product_id = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False)

# --- SCHEMAS ---

class OrderItemSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = OrderItem
        include_fk = True

class OrderHeaderSchema(ma.SQLAlchemyAutoSchema):
    items = ma.Nested(OrderItemSchema, many=True)
    class Meta:
        model = OrderHeader
        include_fk = True

order_schema = OrderHeaderSchema()
orders_schema = OrderHeaderSchema(many=True)
item_schema = OrderItemSchema()

# --- AUTH ROUTES (New!) ---

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    # Hash the password for security
    hashed_password = generate_password_hash(data['password'], method='pbkdf2:sha256')
    new_user = User(username=data['username'], password=hashed_password)
    
    try:
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"message": "User registered successfully"}), 201
    except:
        return jsonify({"message": "Username already exists"}), 400

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(username=data['username']).first()
    
    # Check if user exists and password matches
    if user and check_password_hash(user.password, data['password']):
        access_token = create_access_token(identity=str(user.id))
        return jsonify(access_token=access_token), 200
    
    return jsonify({"message": "Invalid credentials"}), 401

# --- PROTECTED API ENDPOINTS ---

@app.route('/orders', methods=['POST'])
@jwt_required()  # <--- This protects the route
def create_order():
    current_user_id = get_jwt_identity() # You can use this to track who made the order
    data = request.json
    try:
        new_order = OrderHeader(
            order_date=data.get('order_date', date.today()),
            customer_id=data['customer_id'],
            shipping_contact_mech_id=data['shipping_contact_mech_id'],
            billing_contact_mech_id=data['billing_contact_mech_id']
        )
        db.session.add(new_order)
        db.session.flush()
        
        items_data = data.get('order_items', [])
        for item in items_data:
            new_item = OrderItem(
                order_id=new_order.order_id,
                product_id=item['product_id'],
                quantity=item['quantity'],
                status=item.get('status', 'Pending')
            )
            db.session.add(new_item)
        
        db.session.commit()
        return order_schema.jsonify(new_order), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route('/orders/<int:order_id>', methods=['GET'])
@jwt_required()
def get_order(order_id):
    order = OrderHeader.query.get_or_404(order_id)
    return order_schema.jsonify(order)

@app.route('/orders/<int:order_id>', methods=['PUT'])
@jwt_required()
def update_order(order_id):
    order = OrderHeader.query.get_or_404(order_id)
    data = request.json
    if 'shipping_contact_mech_id' in data:
        order.shipping_contact_mech_id = data['shipping_contact_mech_id']
    if 'billing_contact_mech_id' in data:
        order.billing_contact_mech_id = data['billing_contact_mech_id']
    db.session.commit()
    return order_schema.jsonify(order)

@app.route('/orders/<int:order_id>', methods=['DELETE'])
@jwt_required()
def delete_order(order_id):
    order = OrderHeader.query.get_or_404(order_id)
    db.session.delete(order)
    db.session.commit()
    return jsonify({"message": "Order deleted successfully"}), 200

@app.route('/orders/<int:order_id>/items', methods=['POST'])
@jwt_required()
def add_order_item(order_id):
    order = OrderHeader.query.get_or_404(order_id)
    data = request.json
    new_item = OrderItem(
        order_id=order_id,
        product_id=data['product_id'],
        quantity=data['quantity'],
        status=data.get('status', 'Pending')
    )
    db.session.add(new_item)
    db.session.commit()
    return item_schema.jsonify(new_item), 201

@app.route('/orders/<int:order_id>/items/<int:item_seq_id>', methods=['PUT'])
@jwt_required()
def update_order_item(order_id, item_seq_id):
    item = OrderItem.query.filter_by(order_id=order_id, order_item_seq_id=item_seq_id).first_or_404()
    data = request.json
    if 'quantity' in data:
        item.quantity = data['quantity']
    if 'status' in data:
        item.status = data['status']
    db.session.commit()
    return item_schema.jsonify(item)

@app.route('/orders/<int:order_id>/items/<int:item_seq_id>', methods=['DELETE'])
@jwt_required()
def delete_order_item(order_id, item_seq_id):
    item = OrderItem.query.filter_by(order_id=order_id, order_item_seq_id=item_seq_id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    return jsonify({"message": "Item deleted successfully"}), 200

if __name__ == '__main__':
    app.run(debug=True)