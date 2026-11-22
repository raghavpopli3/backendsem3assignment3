"""
routes/customers.py — Customer Management Endpoints

Handles registration, lookup, and updates for customers.
When you fetch a single customer we also include their order history
so the caller doesn't have to make a second request.
"""

from flask import Blueprint, request, jsonify
from database import db
from models import Customer

customers_bp = Blueprint("customers", __name__)


# ---------------------------------------------------------------------------
# GET /customers — list all customers
# ---------------------------------------------------------------------------

@customers_bp.route("/", methods=["GET"])
def list_customers():
    """Return every customer in the system, ordered by name."""
    customers = Customer.query.order_by(Customer.name).all()

    return jsonify({
        "success": True,
        "data": [c.to_dict() for c in customers],
        "message": f"Found {len(customers)} customer(s)",
    }), 200


# ---------------------------------------------------------------------------
# GET /customers/<id> — single customer + their order history
# ---------------------------------------------------------------------------

@customers_bp.route("/<int:customer_id>", methods=["GET"])
def get_customer(customer_id):
    """
    Fetch a single customer by ID.

    The response includes their full order history so you can see
    everything they've ever ordered in one call.
    """
    customer = Customer.query.get(customer_id)

    if not customer:
        return jsonify({"success": False, "error": "Customer not found"}), 404

    return jsonify({
        "success": True,
        "data": customer.to_dict(include_orders=True),
        "message": "Customer retrieved successfully",
    }), 200


# ---------------------------------------------------------------------------
# POST /customers — register a new customer
# ---------------------------------------------------------------------------

@customers_bp.route("/", methods=["POST"])
def create_customer():
    """
    Register a new customer.

    Required fields: name, email
    Optional fields: phone, address

    Duplicate emails are rejected — email is our unique identifier.
    """
    body = request.get_json()

    if not body:
        return jsonify({"success": False, "error": "Request body is missing or not JSON"}), 400

    # Both name and email are mandatory
    name = (body.get("name") or "").strip()
    email = (body.get("email") or "").strip().lower()

    if not name:
        return jsonify({"success": False, "error": "Customer name is required"}), 400

    if not email:
        return jsonify({"success": False, "error": "Customer email is required"}), 400

    # Make sure we don't already have this email registered
    existing = Customer.query.filter_by(email=email).first()
    if existing:
        return jsonify({
            "success": False,
            "error": f"A customer with email '{email}' already exists",
        }), 409  # 409 Conflict

    new_customer = Customer(
        name=name,
        email=email,
        phone=body.get("phone", ""),
        address=body.get("address", ""),
    )

    db.session.add(new_customer)
    db.session.commit()

    return jsonify({
        "success": True,
        "data": new_customer.to_dict(),
        "message": "Customer registered successfully",
    }), 201


# ---------------------------------------------------------------------------
# PUT /customers/<id> — update customer info
# ---------------------------------------------------------------------------

@customers_bp.route("/<int:customer_id>", methods=["PUT"])
def update_customer(customer_id):
    """
    Update a customer's details.

    You can change name, phone, and address freely. Email changes are
    also allowed but we check for duplicates first.
    """
    customer = Customer.query.get(customer_id)

    if not customer:
        return jsonify({"success": False, "error": "Customer not found"}), 404

    body = request.get_json()
    if not body:
        return jsonify({"success": False, "error": "Request body is missing or not JSON"}), 400

    if "name" in body:
        customer.name = body["name"].strip()

    if "email" in body:
        new_email = body["email"].strip().lower()
        # Only check for duplicates if the email is actually changing
        if new_email != customer.email:
            duplicate = Customer.query.filter_by(email=new_email).first()
            if duplicate:
                return jsonify({
                    "success": False,
                    "error": f"Email '{new_email}' is already in use by another customer",
                }), 409
        customer.email = new_email

    if "phone" in body:
        customer.phone = body["phone"]

    if "address" in body:
        customer.address = body["address"]

    db.session.commit()

    return jsonify({
        "success": True,
        "data": customer.to_dict(),
        "message": "Customer updated successfully",
    }), 200
