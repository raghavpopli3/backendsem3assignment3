"""
database.py — Database Initialisation Helper

Just a thin wrapper around SQLAlchemy so we can import `db` from one
consistent place throughout the project without circular imports.
"""

from flask_sqlalchemy import SQLAlchemy

# This is the single SQLAlchemy instance for the whole app.
# It gets properly initialised in app.py via db.init_app(app).
db = SQLAlchemy()


def init_db(app):
    """
    Bind the SQLAlchemy instance to the Flask app and create all tables.
    Auto-seeds starter data if the database is newly created, so the app
    runs directly out of the box when cloned from GitHub.
    """
    db.init_app(app)

    with app.app_context():
        # Import models here so SQLAlchemy knows about them before
        # calling create_all().
        from models import Product, Customer, Order, OrderItem, Return  # noqa: F401

        # SQLAlchemy 2.x API — engine is pulled from the app context automatically
        with db.engine.begin() as conn:
            db.metadata.create_all(conn, checkfirst=True)

        # Auto-seed initial data if brand new database
        if Product.query.count() == 0:
            _seed_starter_data()


def _seed_starter_data():
    """Seed initial products, customers, and orders on first run."""
    from models import Product, Customer, Order, OrderItem

    laptop = Product(
        name="ProBook Laptop 15",
        description="A reliable 15-inch laptop with 16GB RAM and 512GB SSD.",
        price=899.99,
        stock_quantity=24,
        category="Electronics",
    )
    headphones = Product(
        name="SoundWave Wireless Headphones",
        description="Over-ear headphones with active noise cancellation and 30h battery.",
        price=149.99,
        stock_quantity=58,
        category="Electronics",
    )
    desk_chair = Product(
        name="ErgoComfort Desk Chair",
        description="Fully adjustable ergonomic chair with lumbar support.",
        price=320.00,
        stock_quantity=15,
        category="Furniture",
    )
    notebook = Product(
        name="Premium Hardcover Notebook",
        description="A5 dotted notebook with 240 pages of fountain-pen-friendly paper.",
        price=18.50,
        stock_quantity=197,
        category="Stationery",
    )
    water_bottle = Product(
        name="HydroKeep Insulated Bottle",
        description="1-litre stainless steel bottle, keeps drinks cold for 24 hours.",
        price=34.99,
        stock_quantity=5,
        category="Lifestyle",
    )

    db.session.add_all([laptop, headphones, desk_chair, notebook, water_bottle])
    db.session.flush()

    alice = Customer(
        name="Alice Sharma",
        email="alice.sharma@example.com",
        phone="+91 98765 43210",
        address="12, Lotus Lane, Bengaluru, Karnataka 560001",
    )
    bob = Customer(
        name="Bob Mehta",
        email="bob.mehta@example.com",
        phone="+91 87654 32109",
        address="47, MG Road, Pune, Maharashtra 411001",
    )
    carol = Customer(
        name="Carol D'Souza",
        email="carol.dsouza@example.com",
        phone="+91 76543 21098",
        address="8, Church Street, Mumbai, Maharashtra 400001",
    )

    db.session.add_all([alice, bob, carol])
    db.session.flush()

    order1 = Order(
        customer_id=alice.id,
        status="confirmed",
        notes="Please include an invoice.",
    )
    db.session.add(order1)
    db.session.flush()

    item1a = OrderItem(
        order_id=order1.id,
        product_id=laptop.id,
        quantity=1,
        unit_price=laptop.price,
        subtotal=laptop.price * 1,
    )
    item1b = OrderItem(
        order_id=order1.id,
        product_id=notebook.id,
        quantity=3,
        unit_price=notebook.price,
        subtotal=notebook.price * 3,
    )
    order1.total_amount = round(item1a.subtotal + item1b.subtotal, 2)
    db.session.add_all([item1a, item1b])

    order2 = Order(
        customer_id=bob.id,
        status="delivered",
        notes="Gift wrapping requested.",
    )
    db.session.add(order2)
    db.session.flush()

    item2a = OrderItem(
        order_id=order2.id,
        product_id=headphones.id,
        quantity=2,
        unit_price=headphones.price,
        subtotal=headphones.price * 2,
    )
    order2.total_amount = round(item2a.subtotal, 2)
    db.session.add(item2a)

    db.session.commit()
    print("✨ Starter inventory & sample customer database initialized automatically.")
