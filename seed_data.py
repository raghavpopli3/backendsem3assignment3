"""
seed_data.py — Populate the database with sample data

Run this once after setting up the project to get some starter data
you can immediately test the API against.

Usage:
    python3 seed_data.py
"""

from app import create_app
from database import db
from models import Product, Customer, Order, OrderItem

app = create_app()

with app.app_context():

    # Wipe existing data so we start fresh on each run
    print("Clearing old seed data...")
    OrderItem.query.delete()
    Order.query.delete()
    Customer.query.delete()
    Product.query.delete()
    db.session.commit()

    # -----------------------------------------------------------------
    # Products — 5 items across different categories
    # -----------------------------------------------------------------
    print("Seeding products...")

    laptop = Product(
        name="ProBook Laptop 15",
        description="A reliable 15-inch laptop with 16GB RAM and 512GB SSD.",
        price=899.99,
        stock_quantity=25,
        category="Electronics",
    )

    headphones = Product(
        name="SoundWave Wireless Headphones",
        description="Over-ear headphones with active noise cancellation and 30h battery.",
        price=149.99,
        stock_quantity=60,
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
        stock_quantity=200,
        category="Stationery",
    )

    water_bottle = Product(
        name="HydroKeep Insulated Bottle",
        description="1-litre stainless steel bottle, keeps drinks cold for 24 hours.",
        price=34.99,
        stock_quantity=5,  # Low stock — good for testing out-of-stock errors
        category="Lifestyle",
    )

    db.session.add_all([laptop, headphones, desk_chair, notebook, water_bottle])
    db.session.flush()  # Get IDs before creating orders

    # -----------------------------------------------------------------
    # Customers — 3 people
    # -----------------------------------------------------------------
    print("Seeding customers...")

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

    # -----------------------------------------------------------------
    # Orders — 2 sample orders
    # -----------------------------------------------------------------
    print("Seeding orders...")

    # Order 1: Alice buys a laptop and a notebook
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

    # Deduct stock for order 1
    laptop.stock_quantity -= 1
    notebook.stock_quantity -= 3

    db.session.add_all([item1a, item1b])

    # Order 2: Bob buys headphones
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

    # Deduct stock for order 2
    headphones.stock_quantity -= 2

    db.session.add(item2a)

    # Commit everything in one shot
    db.session.commit()

    # -----------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------
    print("\n✅ Seed data loaded successfully!")
    print(f"   Products : {Product.query.count()}")
    print(f"   Customers: {Customer.query.count()}")
    print(f"   Orders   : {Order.query.count()}")
    print(f"   Items    : {OrderItem.query.count()}")
    print("\nYou're good to go. Start the server with: python3 app.py")
