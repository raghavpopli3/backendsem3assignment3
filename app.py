"""
app.py — Flask Application Entry Point with Multi-Page Web UI & REST APIs
"""

import os
from flask import Flask, render_template, jsonify
from config import ActiveConfig
from database import init_db

# Import all route blueprints
from routes.products import products_bp
from routes.customers import customers_bp
from routes.orders import orders_bp
from routes.returns import returns_bp


def create_app():
    """Application factory — creates and configures the Flask app."""
    app = Flask(__name__)
    app.config.from_object(ActiveConfig)

    # Disable strict slashes so both /products and /products/ work seamlessly
    app.url_map.strict_slashes = False

    # Wire up the database
    init_db(app)

    # Register each blueprint with its URL prefix
    app.register_blueprint(products_bp, url_prefix="/products")
    app.register_blueprint(customers_bp, url_prefix="/customers")
    app.register_blueprint(orders_bp, url_prefix="/orders")
    app.register_blueprint(returns_bp, url_prefix="/returns")

    # Also register /api/ aliases to match PDF specifications
    app.register_blueprint(products_bp, url_prefix="/api/products", name="api_products")
    app.register_blueprint(customers_bp, url_prefix="/api/customers", name="api_customers")
    app.register_blueprint(orders_bp, url_prefix="/api/orders", name="api_orders")
    app.register_blueprint(returns_bp, url_prefix="/api/returns", name="api_returns")

    # -----------------------------------------------------------------------
    # Multi-Page Web UI Routes
    # -----------------------------------------------------------------------

    # Customer Storefront
    @app.route("/shop")
    @app.route("/store")
    def shop_page():
        return render_template("shop.html", active_page="shop")

    @app.route("/cart")
    @app.route("/checkout")
    def cart_page():
        return render_template("cart.html", active_page="cart")

    @app.route("/track")
    @app.route("/track-order")
    def track_page():
        return render_template("track.html", active_page="track")

    @app.route("/support")
    @app.route("/help")
    def support_page():
        return render_template("support.html", active_page="support")

    # Operations & Admin Hub
    @app.route("/")
    @app.route("/dashboard")
    def dashboard_page():
        return render_template("dashboard.html", active_page="dashboard")

    @app.route("/inventory")
    def inventory_page():
        return render_template("inventory.html", active_page="inventory")

    @app.route("/orders-view")
    def orders_page():
        return render_template("orders.html", active_page="orders")

    @app.route("/customers-view")
    def customers_page():
        return render_template("customers.html", active_page="customers")

    @app.route("/returns-view")
    def returns_page():
        return render_template("returns.html", active_page="returns")

    @app.route("/analytics")
    def analytics_page():
        return render_template("analytics.html", active_page="analytics")

    @app.route("/docs")
    def docs_page():
        return render_template("docs.html", active_page="docs")

    # -----------------------------------------------------------------------
    # Health Check Endpoint
    # -----------------------------------------------------------------------

    @app.route("/favicon.ico")
    def favicon():
        return "", 204

    @app.route("/health")
    def health_check():
        return jsonify({"success": True, "message": "Server is up and running"}), 200

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    # If port 5000 is already in use (e.g. macOS AirPlay Receiver), fallback to 5001
    import socket
    if "PORT" not in os.environ:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("0.0.0.0", port))
        except OSError:
            port = 5001
    print("=" * 60)
    print("🚀 NexusCommerce E-Commerce Management Platform Running")
    print(f"🌐 Open Web UI at: http://localhost:{port} or http://127.0.0.1:{port}")
    print(f"📄 Pages: / (Dashboard), /inventory, /orders-view, /customers-view, /returns-view, /analytics, /docs")
    print("=" * 60)
    app.run(host="0.0.0.0", port=port, debug=True)
