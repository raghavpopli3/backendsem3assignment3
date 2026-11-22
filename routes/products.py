"""
routes/products.py — Product Management Endpoints

Everything related to browsing and managing products in the catalogue.
Stock levels are shown here but only *modified* through the orders and
returns flows — we don't want random PUT requests bypassing order logic.
"""

from flask import Blueprint, request, jsonify
from database import db
from models import Product

products_bp = Blueprint("products", __name__)


# ---------------------------------------------------------------------------
# GET /products — list all active products
# ---------------------------------------------------------------------------

@products_bp.route("/", methods=["GET"])
def list_products():
    """
    Returns all active products. Supports optional ?category= filter.

    Example: GET /products?category=Electronics
    """
    category_filter = request.args.get("category")

    query = Product.query.filter_by(is_active=True)

    if category_filter:
        query = query.filter(Product.category.ilike(f"%{category_filter}%"))

    products = query.order_by(Product.name).all()

    return jsonify({
        "success": True,
        "data": [p.to_dict() for p in products],
        "message": f"Found {len(products)} product(s)",
    }), 200


# ---------------------------------------------------------------------------
# GET /products/low-stock — low stock report (Assignment 3 requirement)
# ---------------------------------------------------------------------------

@products_bp.route("/low-stock", methods=["GET"])
def low_stock_report():
    """
    Returns products that have low stock (<= 10 units).
    Matches Assignment 3 specifications.
    """
    threshold = request.args.get("threshold", 10, type=int)
    low_stock_items = Product.query.filter(
        Product.is_active == True,
        Product.stock_quantity <= threshold
    ).order_by(Product.stock_quantity.asc()).all()

    return jsonify({
        "success": True,
        "count": len(low_stock_items),
        "lowStockItems": [p.to_dict() for p in low_stock_items],
        "message": f"Found {len(low_stock_items)} item(s) below reorder threshold ({threshold})"
    }), 200


# ---------------------------------------------------------------------------
# GET /products/summary — category-wise summary aggregation (Assignment 3 requirement)
# ---------------------------------------------------------------------------

@products_bp.route("/summary", methods=["GET"])
def category_summary():
    """
    Returns aggregated metrics grouped by category:
      totalItems, totalQuantity, totalStockValue, avgPrice
    Matches Assignment 3 MongoDB aggregation requirement in SQLAlchemy.
    """
    categories = db.session.query(Product.category).filter_by(is_active=True).distinct().all()
    summary_data = []

    for (cat_name,) in categories:
        items = Product.query.filter_by(category=cat_name, is_active=True).all()
        total_items = len(items)
        total_qty = sum(p.stock_quantity for p in items)
        total_value = sum(round(p.price * p.stock_quantity, 2) for p in items)
        avg_price = round(sum(p.price for p in items) / total_items, 2) if total_items > 0 else 0

        summary_data.append({
            "_id": cat_name,
            "category": cat_name,
            "totalItems": total_items,
            "totalQuantity": total_qty,
            "totalStockValue": round(total_value, 2),
            "avgPrice": avg_price
        })

    return jsonify({
        "success": True,
        "categories": len(summary_data),
        "summary": summary_data
    }), 200


# ---------------------------------------------------------------------------
# PATCH /products/<id>/stock — safe stock adjustment (+/- change)
# ---------------------------------------------------------------------------

@products_bp.route("/<int:product_id>/stock", methods=["PATCH"])
def adjust_stock(product_id):
    """
    Increment or decrement stock safely.
    Body: { "change": 10 } or { "change": -5 }
    """
    product = Product.query.get(product_id)
    if not product or not product.is_active:
        return jsonify({"success": False, "error": "Product not found"}), 404

    body = request.get_json() or {}
    change = body.get("change")
    if change is None or not isinstance(change, int):
        return jsonify({"success": False, "error": "Field 'change' must be an integer"}), 400

    if product.stock_quantity + change < 0:
        return jsonify({
            "success": False,
            "error": f"Cannot reduce stock by {abs(change)}. Available: {product.stock_quantity}"
        }), 400

    product.stock_quantity += change
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Stock updated",
        "product": product.to_dict()
    }), 200


# ---------------------------------------------------------------------------
# GET /products/<id> — single product detail
# ---------------------------------------------------------------------------

@products_bp.route("/<int:product_id>", methods=["GET"])
def get_product(product_id):
    """Fetch a single product by its ID."""
    product = Product.query.get(product_id)

    if not product or not product.is_active:
        return jsonify({"success": False, "error": "Product not found"}), 404

    return jsonify({
        "success": True,
        "data": product.to_dict(),
        "message": "Product retrieved successfully",
    }), 200


# ---------------------------------------------------------------------------
# POST /products — create a new product
# ---------------------------------------------------------------------------

@products_bp.route("/", methods=["POST"])
def create_product():
    """
    Add a new product to the catalogue.

    Required fields: name, price
    Optional fields: description, stock_quantity, category
    """
    body = request.get_json()

    if not body:
        return jsonify({"success": False, "error": "Request body is missing or not JSON"}), 400

    # Validate required fields
    if not body.get("name"):
        return jsonify({"success": False, "error": "Product name is required"}), 400

    if body.get("price") is None:
        return jsonify({"success": False, "error": "Product price is required"}), 400

    try:
        price = float(body["price"])
        if price < 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Price must be a non-negative number"}), 400

    stock = body.get("stock_quantity", 0)
    try:
        stock = int(stock)
        if stock < 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "stock_quantity must be a non-negative integer"}), 400

    new_product = Product(
        name=body["name"].strip(),
        description=body.get("description", ""),
        price=price,
        stock_quantity=stock,
        category=body.get("category", "General"),
    )

    db.session.add(new_product)
    db.session.commit()

    return jsonify({
        "success": True,
        "data": new_product.to_dict(),
        "message": "Product created successfully",
    }), 201


# ---------------------------------------------------------------------------
# PUT /products/<id> — update product details or restock
# ---------------------------------------------------------------------------

@products_bp.route("/<int:product_id>", methods=["PUT"])
def update_product(product_id):
    """
    Update any product fields — name, description, price, category,
    or stock_quantity (useful for restocking).

    Only the fields you send get updated; everything else stays the same.
    """
    product = Product.query.get(product_id)

    if not product or not product.is_active:
        return jsonify({"success": False, "error": "Product not found"}), 404

    body = request.get_json()
    if not body:
        return jsonify({"success": False, "error": "Request body is missing or not JSON"}), 400

    # Update only what was provided in the request
    if "name" in body:
        product.name = body["name"].strip()

    if "description" in body:
        product.description = body["description"]

    if "price" in body:
        try:
            product.price = float(body["price"])
            if product.price < 0:
                raise ValueError
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "Price must be a non-negative number"}), 400

    if "stock_quantity" in body:
        try:
            product.stock_quantity = int(body["stock_quantity"])
            if product.stock_quantity < 0:
                raise ValueError
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "stock_quantity must be a non-negative integer"}), 400

    if "category" in body:
        product.category = body["category"]

    db.session.commit()

    return jsonify({
        "success": True,
        "data": product.to_dict(),
        "message": "Product updated successfully",
    }), 200


# ---------------------------------------------------------------------------
# DELETE /products/<id> — soft delete
# ---------------------------------------------------------------------------

@products_bp.route("/<int:product_id>", methods=["DELETE"])
def delete_product(product_id):
    """
    Soft-delete a product by marking it inactive.

    We never hard-delete because existing order records still reference
    this product's ID. Soft-deleting keeps the data integrity intact.
    """
    product = Product.query.get(product_id)

    if not product or not product.is_active:
        return jsonify({"success": False, "error": "Product not found"}), 404

    product.is_active = False
    db.session.commit()

    return jsonify({
        "success": True,
        "data": None,
        "message": f"Product '{product.name}' has been removed from the catalogue",
    }), 200
