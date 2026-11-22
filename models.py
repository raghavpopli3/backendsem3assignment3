"""
models.py — SQLAlchemy Database Models

Each class here maps directly to a table in SQLite. I've tried to keep
the field names obvious and added short comments where the purpose
might not be immediately clear.

Relationships are defined so SQLAlchemy can do the JOIN work for us
when we need related data.
"""

from datetime import datetime
from database import db


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------

class Product(db.Model):
    """
    Represents a product in our inventory catalogue.

    stock_quantity is the live count of units we have on hand.
    It goes DOWN when orders are placed and UP when orders are cancelled
    or returns are approved.
    """

    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    price = db.Column(db.Float, nullable=False)
    stock_quantity = db.Column(db.Integer, nullable=False, default=0)
    category = db.Column(db.String(100), default="General")

    # Soft-delete flag — we never truly remove products from the DB
    # because historical orders still reference them.
    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Back-reference so we can do product.order_items to see what's ordered
    order_items = db.relationship("OrderItem", backref="product", lazy=True)

    def to_dict(self):
        """Return a plain dictionary — safe to JSON-serialise."""
        return {
            "id": self.id,
            "_id": str(self.id),
            "name": self.name,
            "description": self.description,
            "price": self.price,
            "stock_quantity": self.stock_quantity,
            "quantity": self.stock_quantity,
            "stockValue": round(self.price * self.stock_quantity, 2),
            "category": self.category,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def __repr__(self):
        return f"<Product {self.id}: {self.name} (stock={self.stock_quantity})>"


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------

class Customer(db.Model):
    """
    Stores customer information. Email must be unique — we use it
    as the natural identifier when looking someone up.
    """

    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), nullable=False, unique=True)
    phone = db.Column(db.String(20), default="")
    address = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # All orders placed by this customer
    orders = db.relationship("Order", backref="customer", lazy=True)

    def to_dict(self, include_orders=False):
        """
        Serialise the customer. Pass include_orders=True when you need
        the full order history (e.g. the GET /customers/<id> detail view).
        """
        data = {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "address": self.address,
            "created_at": self.created_at.isoformat(),
        }
        if include_orders:
            data["orders"] = [order.to_dict() for order in self.orders]
        return data

    def __repr__(self):
        return f"<Customer {self.id}: {self.name} ({self.email})>"


# ---------------------------------------------------------------------------
# Order
# ---------------------------------------------------------------------------

# Allowed statuses for an order — using a plain tuple here instead of
# a Python enum keeps things simple and SQLite-friendly.
ORDER_STATUSES = ("pending", "confirmed", "shipped", "delivered", "cancelled", "returned")


class Order(db.Model):
    """
    An order ties a customer to one or more products (via OrderItem rows).

    Status flow (happy path):  pending → confirmed → shipped → delivered
    Cancellation:              pending/confirmed → cancelled
    Return:                    delivered → returned  (via Returns table)
    """

    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)

    # Status is stored as a plain string — validated at the application layer
    status = db.Column(db.String(20), nullable=False, default="pending")

    total_amount = db.Column(db.Float, nullable=False, default=0.0)
    notes = db.Column(db.Text, default="")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # All line-items in this order
    items = db.relationship("OrderItem", backref="order", lazy=True, cascade="all, delete-orphan")

    # Any return requests filed for this order
    returns = db.relationship("Return", backref="order", lazy=True)

    def to_dict(self, include_items=True):
        """Serialise the order. Items are included by default."""
        data = {
            "id": self.id,
            "customer_id": self.customer_id,
            "status": self.status,
            "total_amount": self.total_amount,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if include_items:
            data["items"] = [item.to_dict() for item in self.items]
        return data

    def __repr__(self):
        return f"<Order {self.id}: customer={self.customer_id} status={self.status}>"


# ---------------------------------------------------------------------------
# OrderItem
# ---------------------------------------------------------------------------

class OrderItem(db.Model):
    """
    One line in an order — which product, how many, at what price.

    We snapshot the unit_price at order time so historical orders aren't
    affected if we later change a product's price.
    """

    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

    # Price at the time the order was placed — NOT the current product price
    unit_price = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)  # quantity × unit_price

    def to_dict(self):
        """Serialise the order item, including a brief product name for convenience."""
        return {
            "id": self.id,
            "order_id": self.order_id,
            "product_id": self.product_id,
            "product_name": self.product.name if self.product else "Unknown",
            "quantity": self.quantity,
            "unit_price": self.unit_price,
            "subtotal": self.subtotal,
        }

    def __repr__(self):
        return f"<OrderItem {self.id}: order={self.order_id} product={self.product_id} qty={self.quantity}>"


# ---------------------------------------------------------------------------
# Return
# ---------------------------------------------------------------------------

RETURN_STATUSES = ("pending", "approved", "rejected")


class Return(db.Model):
    """
    A return request filed by a customer for a delivered order.

    When approved:  stock is restored, order status → 'returned'
    When rejected:  order stays as 'delivered', stock unchanged
    """

    __tablename__ = "returns"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")

    # How much we're giving back — can be partial, defaults to full order total
    refund_amount = db.Column(db.Float, default=0.0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        """Serialise the return request."""
        return {
            "id": self.id,
            "order_id": self.order_id,
            "reason": self.reason,
            "status": self.status,
            "refund_amount": self.refund_amount,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def __repr__(self):
        return f"<Return {self.id}: order={self.order_id} status={self.status}>"
