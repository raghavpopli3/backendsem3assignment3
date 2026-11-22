"""
routes/orders.py — Order Management Endpoints

This is the heart of the system. Order placement is carefully designed
so that stock checks and stock deductions happen atomically — we validate
*everything* first, then commit changes only when we know the whole order
is fulfillable. No partial deductions, no race conditions (SQLite's
file-level lock handles concurrency for our scale).
"""

from flask import Blueprint, request, jsonify
from database import db
from models import Order, OrderItem, Product, Customer, ORDER_STATUSES

orders_bp = Blueprint("orders", __name__)


# ---------------------------------------------------------------------------
# GET /orders — list orders with optional status filter
# ---------------------------------------------------------------------------

@orders_bp.route("/", methods=["GET"])
def list_orders():
    """
    Returns all orders. Use ?status= to filter by status.

    Example: GET /orders?status=pending
    """
    status_filter = request.args.get("status")

    if status_filter and status_filter not in ORDER_STATUSES:
        return jsonify({
            "success": False,
            "error": f"Invalid status '{status_filter}'. Must be one of: {', '.join(ORDER_STATUSES)}",
        }), 400

    query = Order.query

    if status_filter:
        query = query.filter_by(status=status_filter)

    orders = query.order_by(Order.created_at.desc()).all()

    return jsonify({
        "success": True,
        "data": [o.to_dict(include_items=False) for o in orders],
        "message": f"Found {len(orders)} order(s)",
    }), 200


# ---------------------------------------------------------------------------
# GET /orders/<id> — single order with all line items
# ---------------------------------------------------------------------------

@orders_bp.route("/<int:order_id>", methods=["GET"])
def get_order(order_id):
    """Fetch a single order and all its line items."""
    order = Order.query.get(order_id)

    if not order:
        return jsonify({"success": False, "error": "Order not found"}), 404

    return jsonify({
        "success": True,
        "data": order.to_dict(include_items=True),
        "message": "Order retrieved successfully",
    }), 200


# ---------------------------------------------------------------------------
# POST /orders — place a new order  ← THE CRITICAL ONE
# ---------------------------------------------------------------------------

@orders_bp.route("/", methods=["POST"])
def create_order():
    """
    Place a new order.

    Expected body:
    {
        "customer_id": 1,
        "items": [
            {"product_id": 3, "quantity": 2},
            {"product_id": 7, "quantity": 1}
        ],
        "notes": "Please gift-wrap"   <- optional
    }

    The logic is deliberately two-pass:
      Pass 1 — Validate EVERYTHING. Don't touch any stock yet.
      Pass 2 — All good? Now deduct stock and persist the order.

    This prevents partial stock deductions if validation fails mid-loop.
    """
    body = request.get_json()

    if not body:
        return jsonify({"success": False, "error": "Request body is missing or not JSON"}), 400

    # --- Basic input validation ---

    customer_id = body.get("customer_id")
    if not customer_id:
        return jsonify({"success": False, "error": "customer_id is required"}), 400

    customer = Customer.query.get(customer_id)
    if not customer:
        return jsonify({"success": False, "error": f"Customer with id {customer_id} not found"}), 404

    order_items_input = body.get("items", [])
    if not order_items_input:
        return jsonify({"success": False, "error": "Order must have at least one item"}), 400

    # --- PASS 1: Validate all items — no stock changes yet ---

    validated_items = []  # We'll build the actual order from this list in pass 2

    for item_input in order_items_input:
        product_id = item_input.get("product_id")
        quantity = item_input.get("quantity")

        # Make sure the caller gave us both required fields per item
        if not product_id or quantity is None:
            return jsonify({
                "success": False,
                "error": "Each item must have 'product_id' and 'quantity'",
            }), 400

        try:
            quantity = int(quantity)
            if quantity <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return jsonify({
                "success": False,
                "error": f"quantity for product_id {product_id} must be a positive integer",
            }), 400

        # Look up the product
        product = Product.query.get(product_id)

        if not product or not product.is_active:
            return jsonify({
                "success": False,
                "error": f"Product with id {product_id} not found",
            }), 404

        # The all-important stock check — stop right here if we can't fulfil it
        if product.stock_quantity < quantity:
            return jsonify({
                "success": False,
                "error": (
                    f"'{product.name}' is out of stock "
                    f"(available: {product.stock_quantity}, requested: {quantity})"
                ),
            }), 400

        # Keep a reference so pass 2 doesn't have to re-query
        validated_items.append({
            "product": product,
            "quantity": quantity,
        })

    # --- PASS 2: Everything checks out — deduct stock and create the order ---

    new_order = Order(
        customer_id=customer_id,
        status="pending",
        notes=body.get("notes", ""),
    )
    db.session.add(new_order)
    db.session.flush()  # Get the new_order.id before committing

    total_amount = 0.0

    for item_data in validated_items:
        product = item_data["product"]
        quantity = item_data["quantity"]
        unit_price = product.price  # Snapshot the price right now
        subtotal = unit_price * quantity

        # Deduct from stock
        product.stock_quantity -= quantity

        # Create the order line item
        order_item = OrderItem(
            order_id=new_order.id,
            product_id=product.id,
            quantity=quantity,
            unit_price=unit_price,
            subtotal=subtotal,
        )
        db.session.add(order_item)

        total_amount += subtotal

    new_order.total_amount = round(total_amount, 2)

    db.session.commit()

    return jsonify({
        "success": True,
        "data": new_order.to_dict(include_items=True),
        "message": "Order placed successfully",
    }), 201


# ---------------------------------------------------------------------------
# PUT /orders/<id>/status — update order status
# ---------------------------------------------------------------------------

@orders_bp.route("/<int:order_id>/status", methods=["PUT"])
def update_order_status(order_id):
    """
    Move an order to a new status manually (e.g. confirmed, shipped, delivered).

    For cancellation use the DELETE endpoint — it also handles stock restoration.
    For returns use the /returns endpoints.
    """
    order = Order.query.get(order_id)

    if not order:
        return jsonify({"success": False, "error": "Order not found"}), 404

    body = request.get_json()
    if not body:
        return jsonify({"success": False, "error": "Request body is missing or not JSON"}), 400

    new_status = body.get("status")
    if not new_status:
        return jsonify({"success": False, "error": "status field is required"}), 400

    if new_status not in ORDER_STATUSES:
        return jsonify({
            "success": False,
            "error": f"Invalid status '{new_status}'. Must be one of: {', '.join(ORDER_STATUSES)}",
        }), 400

    # Don't let this endpoint be used to cancel or return — use the dedicated paths
    if new_status in ("cancelled", "returned"):
        return jsonify({
            "success": False,
            "error": (
                "Use DELETE /orders/<id> to cancel an order, "
                "or POST /returns + PUT /returns/<id>/approve to process returns"
            ),
        }), 400

    old_status = order.status
    order.status = new_status
    db.session.commit()

    return jsonify({
        "success": True,
        "data": order.to_dict(),
        "message": f"Order status updated from '{old_status}' to '{new_status}'",
    }), 200


# ---------------------------------------------------------------------------
# DELETE /orders/<id> — cancel an order and restore stock
# ---------------------------------------------------------------------------

@orders_bp.route("/<int:order_id>", methods=["DELETE"])
def cancel_order(order_id):
    """
    Cancel an order.

    Only 'pending' or 'confirmed' orders can be cancelled — once something
    is shipped it's too late to cancel through this API.

    When cancelled, all stock that was deducted at order-time is put back.
    """
    order = Order.query.get(order_id)

    if not order:
        return jsonify({"success": False, "error": "Order not found"}), 404

    # Can only cancel orders that haven't shipped yet
    if order.status not in ("pending", "confirmed"):
        return jsonify({
            "success": False,
            "error": (
                f"Cannot cancel an order with status '{order.status}'. "
                "Only 'pending' and 'confirmed' orders can be cancelled."
            ),
        }), 400

    # Restore stock for every item in this order
    for item in order.items:
        product = Product.query.get(item.product_id)
        if product:
            product.stock_quantity += item.quantity

    order.status = "cancelled"
    db.session.commit()

    return jsonify({
        "success": True,
        "data": order.to_dict(),
        "message": f"Order #{order_id} has been cancelled and stock has been restored",
    }), 200
