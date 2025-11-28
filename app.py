from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from datetime import date

# 1. Initialize the app
app = Flask(__name__)

# 2. Database Configuration
# NOTE: Ensure 'root:root' matches your MySQL credentials
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:root@localhost/ecommerce_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 3. Initialize DB and Marshmallow
db = SQLAlchemy(app)
ma = Marshmallow(app)

# --- MODELS ---

class OrderHeader(db.Model):
    __tablename__ = 'Order_Header'
    order_id = db.Column(db.Integer, primary_key=True)
    order_date = db.Column(db.Date, nullable=False)
    customer_id = db.Column(db.Integer, nullable=False)
    shipping_contact_mech_id = db.Column(db.Integer, nullable=False)
    billing_contact_mech_id = db.Column(db.Integer, nullable=False)
    # Relationship to Items
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

# --- API ENDPOINTS ---

# HOME PAGE (Test Route)
@app.route('/')
def index():
    return "Success! The API is running. Use Postman to send requests to /orders"

# 1. Create an Order
@app.route('/orders', methods=['POST'])
def create_order():
    data = request.json
    try:
        new_order = OrderHeader(
            order_date=data.get('order_date', date.today()),
            customer_id=data['customer_id'],
            shipping_contact_mech_id=data['shipping_contact_mech_id'],
            billing_contact_mech_id=data['billing_contact_mech_id']
        )
        db.session.add(new_order)
        db.session.flush() # Flush to generate order_id

        # Process Items
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

# 2. Retrieve Order Details
@app.route('/orders/<int:order_id>', methods=['GET'])
def get_order(order_id):
    order = OrderHeader.query.get_or_404(order_id)
    return order_schema.jsonify(order)

# 3. Update an Order (Shipping/Billing info)
@app.route('/orders/<int:order_id>', methods=['PUT'])
def update_order(order_id):
    order = OrderHeader.query.get_or_404(order_id)
    data = request.json
    
    if 'shipping_contact_mech_id' in data:
        order.shipping_contact_mech_id = data['shipping_contact_mech_id']
    if 'billing_contact_mech_id' in data:
        order.billing_contact_mech_id = data['billing_contact_mech_id']
        
    db.session.commit()
    return order_schema.jsonify(order)

# 4. Delete an Order
@app.route('/orders/<int:order_id>', methods=['DELETE'])
def delete_order(order_id):
    order = OrderHeader.query.get_or_404(order_id)
    db.session.delete(order)
    db.session.commit()
    return jsonify({"message": "Order deleted successfully"}), 200

# 5. Add an Order Item
@app.route('/orders/<int:order_id>/items', methods=['POST'])
def add_order_item(order_id):
    order = OrderHeader.query.get_or_404(order_id) # Validate order exists
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

# 6. Update an Order Item
@app.route('/orders/<int:order_id>/items/<int:item_seq_id>', methods=['PUT'])
def update_order_item(order_id, item_seq_id):
    item = OrderItem.query.filter_by(order_id=order_id, order_item_seq_id=item_seq_id).first_or_404()
    data = request.json
    
    if 'quantity' in data:
        item.quantity = data['quantity']
    if 'status' in data:
        item.status = data['status']
        
    db.session.commit()
    return item_schema.jsonify(item)

# 7. Delete an Order Item
@app.route('/orders/<int:order_id>/items/<int:item_seq_id>', methods=['DELETE'])
def delete_order_item(order_id, item_seq_id):
    item = OrderItem.query.filter_by(order_id=order_id, order_item_seq_id=item_seq_id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    return jsonify({"message": "Item deleted successfully"}), 200

if __name__ == '__main__':
    app.run(debug=True)