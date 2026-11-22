"""
routes/returns.py — Returns Management Endpoints

Handles customer return requests. The flow is:
  1. Customer requests a return via POST /returns
  2. Admin approves or rejects via PUT /returns/<id>/approve|reject
  3. On approval: stock is restored and order is marked 'returned'
"""

from flask import Blueprint, request, jsonify
from database import db
from models import Return, Order, Product, RETURN_STATUSES

returns_bp = Blueprint("returns", __name__)


# ---------------------------------------------------------------------------
# GET /returns — list all return requests
# ---------------------------------------------------------------------------

@returns_bp.route("/", methods=["GET"])
def list_returns():
    """
    Returns all return requests. Filter by ?status= (pending/approved/rejected).

    Example: GET /returns?status=pending
    """
    status_filter = request.args.get("status")

    if status_filter and status_filter not in RETURN_STATUSES:
        return jsonify({
            "success": False,
            "error": f"Invalid status. Must be one of: {', '.join(RETURN_STATUSES)}",
        }), 400

    query = Return.query

    if status_filter:
        query = query.filter_by(status=status_filter)

    returns = query.order_by(Return.created_at.desc()).all()

    return jsonify({
        "success": True,
        "data": [r.to_dict() for r in returns],
        "message": f"Found {len(returns)} return request(s)",
    }), 200


# ---------------------------------------------------------------------------
# POST /returns — file a return request
# ---------------------------------------------------------------------------

@returns_bp.route("/", methods=["POST"])
def create_return():
    """
    File a return request for a delivered order.

    Required fields: order_id, reason
    Optional:        refund_amount (defaults to the full order total)

    Only 'delivered' orders are eligible for returns.
    """
    body = request.get_json()

    if not body:
        return jsonify({"success": False, "error": "Request body is missing or not JSON"}), 400

    order_id = body.get("order_id")
    reason = (body.get("reason") or "").strip()

    if not order_id:
        return jsonify({"success": False, "error": "order_id is required"}), 400

    if not reason:
        return jsonify({"success": False, "error": "Return reason is required"}), 400

    order = Order.query.get(order_id)

    if not order:
        return jsonify({"success": False, "error": f"Order with id {order_id} not found"}), 404

    # Only delivered orders can be returned
    if order.status != "delivered":
        return jsonify({
            "success": False,
            "error": (
                f"Only 'delivered' orders can be returned. "
                f"This order has status: '{order.status}'"
            ),
        }), 400

    # Prevent duplicate return requests for the same order
    existing_return = Return.query.filter_by(order_id=order_id, status="pending").first()
    if existing_return:
        return jsonify({
            "success": False,
            "error": f"A return request (id={existing_return.id}) already exists for this order",
        }), 409

    # Default the refund to the full order total if not specified
    refund_amount = body.get("refund_amount", order.total_amount)
    try:
        refund_amount = float(refund_amount)
        if refund_amount < 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "refund_amount must be a non-negative number"}), 400

    new_return = Return(
        order_id=order_id,
        reason=reason,
        status="pending",
        refund_amount=refund_amount,
    )

    db.session.add(new_return)
    db.session.commit()

    return jsonify({
        "success": True,
        "data": new_return.to_dict(),
        "message": "Return request filed successfully. Awaiting approval.",
    }), 201


# ---------------------------------------------------------------------------
# PUT /returns/<id>/approve — approve the return
# ---------------------------------------------------------------------------

@returns_bp.route("/<int:return_id>/approve", methods=["PUT"])
def approve_return(return_id):
    """
    Approve a return request.

    What happens on approval:
    - Stock for every item in the order is restored
    - The order status changes to 'returned'
    - The return status changes to 'approved'
    """
    return_request = Return.query.get(return_id)

    if not return_request:
        return jsonify({"success": False, "error": "Return request not found"}), 404

    if return_request.status != "pending":
        return jsonify({
            "success": False,
            "error": f"Return request has already been {return_request.status}",
        }), 400

    order = Order.query.get(return_request.order_id)

    if not order:
        return jsonify({"success": False, "error": "Associated order not found"}), 404

    # Restore the stock for each item that was originally deducted
    for item in order.items:
        product = Product.query.get(item.product_id)
        if product:
            product.stock_quantity += item.quantity

    # Mark the return as approved and the order as returned
    return_request.status = "approved"
    order.status = "returned"

    db.session.commit()

    return jsonify({
        "success": True,
        "data": return_request.to_dict(),
        "message": (
            f"Return approved. Stock has been restored and "
            f"order #{order.id} is now marked as 'returned'."
        ),
    }), 200


# ---------------------------------------------------------------------------
# PUT /returns/<id>/reject — reject the return
# ---------------------------------------------------------------------------

@returns_bp.route("/<int:return_id>/reject", methods=["PUT"])
def reject_return(return_id):
    """
    Reject a return request.

    The order status stays as 'delivered' and stock is NOT restored.
    Optionally accept a 'reason' in the body to record why it was rejected.
    """
    return_request = Return.query.get(return_id)

    if not return_request:
        return jsonify({"success": False, "error": "Return request not found"}), 404

    if return_request.status != "pending":
        return jsonify({
            "success": False,
            "error": f"Return request has already been {return_request.status}",
        }), 400

    # Allow an optional note about why it's being rejected
    body = request.get_json() or {}
    rejection_note = body.get("reason", "")
    if rejection_note:
        # Append the rejection reason to the existing reason field
        return_request.reason = f"{return_request.reason} | Rejected: {rejection_note}"

    return_request.status = "rejected"
    db.session.commit()

    return jsonify({
        "success": True,
        "data": return_request.to_dict(),
        "message": "Return request has been rejected",
    }), 200
