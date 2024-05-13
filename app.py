from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import select, delete
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
from flask_marshmallow import Marshmallow
from marshmallow import fields, ValidationError
from typing import List
import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = "mysql+mysqlconnector://root:!@localhost/e_commerce_db2"

class Base(DeclarativeBase): pass # kinda like... |Base = DeclarativeBase|

db = SQLAlchemy(app, model_class=Base)
ma = Marshmallow(app)

class Customer(Base):
    __tablename__ = "Customers"
    id:    Mapped[int] = mapped_column(primary_key=True)
    name:  Mapped[str] = mapped_column(db.String(255), nullable=False)
    email: Mapped[str] = mapped_column(db.String(320))
    phone: Mapped[str] = mapped_column(db.String( 15))

    customer_account: Mapped["CustomerAccount"] = db.relationship(back_populates="customer")
    orders:           Mapped[List["Order"]] =     db.relationship(back_populates="customer")

class Product(Base):
    __tablename__ = "Products"
    id:    Mapped[int]   = mapped_column(primary_key=True)
    name:  Mapped[str]   = mapped_column(db.String(255), nullable=False)
    price: Mapped[float] = mapped_column(db.Float, nullable=False)

order_product = db.Table("Order_Product", Base.metadata, 
    db.Column("order_id", db.ForeignKey("Orders.id"),   primary_key=True),
    db.Column("prod_id",  db.ForeignKey("Products.id"), primary_key=True))

class Order(Base):
    __tablename__ = "Orders"
    id:          Mapped[int]           = mapped_column(primary_key=True)
    date:        Mapped[datetime.date] = mapped_column(db.Date, nullable=False)
    customer_id: Mapped[int]           = mapped_column(db.ForeignKey('Customers.id'))

    customer:    Mapped["Customer"]      = db.relationship(back_populates="orders")
    products:    Mapped[List["Product"]] = db.relationship(secondary=order_product)

class CustomerAccount(Base):
    __tablename__ = "Customer_Accounts"
    id:           Mapped[int] = mapped_column(primary_key=True)
    username:     Mapped[str] = mapped_column(db.String(255), unique=True, nullable=False)
    password:     Mapped[str] = mapped_column(db.String(255), nullable=False)
    customer_id:  Mapped[int] = mapped_column(db.ForeignKey('Customers.id'))

    customer: Mapped["Customer"] = db.relationship(back_populates="customer_account")

with app.app_context(): db.create_all()

class CustomerSchema(ma.Schema):
    id =    fields.Integer()
    name =  fields.String(required=True)
    email = fields.String(required=True)
    phone = fields.String(required=True)

customer_schema  = CustomerSchema()
customers_schema = CustomerSchema(many=True)

class ProductSchema(ma.Schema):
    id =    fields.Integer()
    name =  fields.String(required=True)
    price = fields.Float(required=True)

product_schema = ProductSchema()
products_schema = ProductSchema(many=True)

@app.route("/")
def home(): return "<h1>Mini Project: E-commerce API</h1>"

@app.route("/customers", methods=["GET"])
def get_customers(): 
    return customers_schema.jsonify(db.session.execute(select(Customer)).scalars().all())

@app.route("/customers", methods=["POST"])
def add_customer():
    try: new = customer_schema.load(request.json)
    except ValidationError as err: return jsonify(err.messages)
    db.session.add(Customer(name=new["name"], email=new["email"], phone=new["phone"]))
    db.session.commit()
    return jsonify({"message":"New Customer Added Successfully"}), 201

@app.route("/customers/<int:id>", methods=["PUT"])
def update_customer(id):
    customer = db.session.execute(select(Customer).where(Customer.id == id)).scalar()
    if not customer: return jsonify({"Error":"Customer Not Found!"}), 404
    try: cust_data = customer_schema.load(request.json)
    except ValidationError as err: jsonify(err.messages), 400
    for field, value in cust_data.items(): setattr(customer, field, value)
    db.session.commit()
    return jsonify({"message":"Customer Updated Successfully"}), 200

@app.route("/customers/<int:id>", methods=["DELETE"])
def delete_customer(id):
    with db.session.begin():
        result = db.session.execute(delete(Customer).where(Customer.id == id))
        if result.rowcount == 0: return jsonify({"Error":"Customer Not Found!"})
        return jsonify({"Message":"Customer Removed Successfully!"})

@app.route('/products', methods=["GET"])
def get_products(): 
    return products_schema.jsonify(db.session.execute(select(Product)).scalars().all())

@app.route('/products', methods=["POST"])
def add_product():
    try: new = product_schema.load(request.json)
    except ValidationError as err: return jsonify(err.messages), 400
    db.session.add(Product(name=new['name'], price=new['price']))
    db.session.commit()
    return jsonify({"Message":"Product Added Successfully"})

@app.route('/products/<int:id>', methods=["PUT"])
def update_product(id):
    product = db.session.execute(select(Product).where(Product.id==id)).scalar()
    if not product: return jsonify({"Error":"Product Not Found!"}), 404
    try: product_to_update = product_schema.load(request.json)
    except ValidationError as err: return jsonify(err.messages), 400
    for field, value in product_to_update.items(): setattr(product, field, value)
    db.session.commit()
    return jsonify({"Message":"Product Updated Successfully!"})
        
@app.route('/products/<int:id>', methods=["DELETE"])
def delete_product(id):
    with db.session.begin():
        result = db.session.execute(delete(Product).where(Product.id == id))
        if result.rowcount == 0: return jsonify({"Error":"Product Not Found!"}), 400
        return jsonify({"Message":"Product Deleted Successfully!"})
    
@app.route("/products/by-name/<string:name>", methods=["GET"])
def get_product_by_name(name):
    query = select(Product).where(Product.name.like(f"%{name}%"))
    return products_schema.jsonify(db.session.execute(query).scalars().all())

@app.route('/customers/<int:id>', methods=["GET"])
def get_customers_by_id(id):
    customer = db.session.execute(select(Customer).where(Customer.id==id)).scalar()
    if customer: return customer_schema.jsonify(customer)
    return jsonify({"Message":f"Customer ID {id} Not Found!"}) 

@app.route('/products/<int:id>', methods=["GET"])   # Add May 11, 2024
def get_product_by_id(id):
    product = db.session.execute(select(Product).where(Product.id==id)).scalar()
    if product: return product_schema.jsonify(product)
    return jsonify({"Message":f"Product ID {id} Not Found!"}) 

@app.route("/orders", methods=["GET"])
def get_order_details():
    order_details = []
    for order in db.session.query(Order).all():
        order_data = {
            "order_id": order.id,
            "order_date": order.date.strftime("%Y-%m-%d"),
            "customer": customer_schema.dump(order.customer),
            "products": products_schema.dump(order.products, many=True)
        }
        order_details.append(order_data)
    return jsonify(order_details)

@app.route('/orders', methods=["POST"])
def add_order():
    try: 
        data = request.json
        if not data or "product_id" not in data or "customer_id" not in data:
            raise ValidationError({"Error": "Missing Required Fields in Request"})

        product = db.session.query(Product).filter_by(id=data["product_id"]).first()
        customer = db.session.query(Customer).filter_by(id=data["customer_id"]).first()

        if not product or not customer: 
            raise ValidationError({"Error": "Invalid Product or Customer ID"})

        new_order = Order(date=datetime.date.today(), customer=customer)
        new_order.products.append(product)  
        db.session.add(new_order)
        db.session.commit()
        return jsonify({"Message": "Order Created Successfully!"}), 201
    except ValidationError as err: return jsonify(err.messages), 400

@app.route("/orders/<int:order_id>", methods=["GET"])
def get_order_details_by_order_id(order_id):
    order = db.session.query(Order).filter_by(id=order_id).first()
    if not order: return jsonify({"Message": f"Order ID {order_id} Not Found!"}), 404
    order_details = {
        "order_id": order.id,
        "order_date": order.date.strftime("%Y-%m-%d"), 
        "customer": customer_schema.dump(order.customer), 
        "products": products_schema.dump(order.products, many=True) 
    }
    return jsonify(order_details)

if __name__ == "__main__": app.run(debug=True)
