"""
mongo_db.py — MongoDB Client & Aggregation Engine

Provides connection handling, health checks, automatic starter seeding,
and native MongoDB aggregation pipelines for NexusCommerce.
"""

import os
from config import ActiveConfig

try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False


_mongo_client = None


def get_mongo_client():
    """Returns a singleton PyMongo MongoClient instance or None if not configured."""
    global _mongo_client
    if not PYMONGO_AVAILABLE:
        return None

    uri = ActiveConfig.MONGO_URI or os.environ.get("MONGO_URI")
    if not uri:
        return None

    if _mongo_client is None:
        try:
            _mongo_client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        except Exception as e:
            print(f"⚠️ MongoDB Client initialization warning: {e}")
            return None

    return _mongo_client


def get_mongo_db():
    """Returns the MongoDB database instance if configured, else None."""
    client = get_mongo_client()
    if client is None:
        return None

    db_name = ActiveConfig.MONGO_DB_NAME or os.environ.get("MONGO_DB_NAME", "inventory_db")
    return client[db_name]


def check_mongo_status():
    """Pings MongoDB and returns diagnostic status."""
    if not PYMONGO_AVAILABLE:
        return {
            "connected": False,
            "status": "pymongo not installed",
            "message": "Run: pip install pymongo dnspython"
        }

    uri = ActiveConfig.MONGO_URI or os.environ.get("MONGO_URI")
    if not uri:
        return {
            "connected": False,
            "status": "not configured",
            "message": "MONGO_URI environment variable is not set. Add it to .env or environment."
        }

    client = get_mongo_client()
    if client is None:
        return {
            "connected": False,
            "status": "initialization failed",
            "message": "Could not instantiate MongoClient."
        }

    try:
        # Ping command
        client.admin.command('ping')
        db = get_mongo_db()
        collections = db.list_collection_names()
        return {
            "connected": True,
            "status": "connected",
            "database": db.name,
            "collections": collections,
            "message": f"Successfully connected to MongoDB ({db.name})"
        }
    except (ConnectionFailure, ServerSelectionTimeoutError) as err:
        return {
            "connected": False,
            "status": "connection timed out",
            "error": str(err),
            "message": "Failed to connect to MongoDB cluster. Check network/credentials."
        }
    except Exception as err:
        return {
            "connected": False,
            "status": "error",
            "error": str(err),
            "message": f"MongoDB error: {err}"
        }


def seed_mongo_starter_data():
    """Seeds default sample documents into MongoDB collections if empty."""
    db = get_mongo_db()
    if db is None:
        return False

    try:
        # Products
        if db.products.count_documents({}) == 0:
            sample_products = [
                {
                    "productId": 1,
                    "name": "ProBook Laptop 15",
                    "description": "A reliable 15-inch laptop with 16GB RAM and 512GB SSD.",
                    "price": 899.99,
                    "stock_quantity": 24,
                    "category": "Electronics",
                    "is_active": True
                },
                {
                    "productId": 2,
                    "name": "SoundWave Wireless Headphones",
                    "description": "Over-ear headphones with active noise cancellation and 30h battery.",
                    "price": 149.99,
                    "stock_quantity": 58,
                    "category": "Electronics",
                    "is_active": True
                },
                {
                    "productId": 3,
                    "name": "ErgoComfort Desk Chair",
                    "description": "Fully adjustable ergonomic chair with lumbar support.",
                    "price": 320.00,
                    "stock_quantity": 15,
                    "category": "Furniture",
                    "is_active": True
                },
                {
                    "productId": 4,
                    "name": "Premium Hardcover Notebook",
                    "description": "A5 dotted notebook with 240 pages of fountain-pen-friendly paper.",
                    "price": 18.50,
                    "stock_quantity": 197,
                    "category": "Stationery",
                    "is_active": True
                },
                {
                    "productId": 5,
                    "name": "HydroKeep Insulated Bottle",
                    "description": "1-litre stainless steel bottle, keeps drinks cold for 24 hours.",
                    "price": 34.99,
                    "stock_quantity": 5,
                    "category": "Lifestyle",
                    "is_active": True
                }
            ]
            db.products.insert_many(sample_products)
            print("🌱 MongoDB: Seeded sample products collection.")

        # Customers
        if db.customers.count_documents({}) == 0:
            sample_customers = [
                {
                    "customerId": 1,
                    "name": "Alice Sharma",
                    "email": "alice.sharma@example.com",
                    "phone": "+91 98765 43210",
                    "address": "12, Lotus Lane, Bengaluru, Karnataka 560001"
                },
                {
                    "customerId": 2,
                    "name": "Bob Mehta",
                    "email": "bob.mehta@example.com",
                    "phone": "+91 87654 32109",
                    "address": "47, MG Road, Pune, Maharashtra 411001"
                },
                {
                    "customerId": 3,
                    "name": "Carol D'Souza",
                    "email": "carol.dsouza@example.com",
                    "phone": "+91 76543 21098",
                    "address": "8, Church Street, Mumbai, Maharashtra 400001"
                }
            ]
            db.customers.insert_many(sample_customers)
            print("🌱 MongoDB: Seeded sample customers collection.")

        return True
    except Exception as e:
        print(f"⚠️ Error seeding MongoDB: {e}")
        return False


def mongo_aggregate_category_summary():
    """
    Executes a native MongoDB Aggregation Pipeline:
    Matches Lab 3 Assignment requirements:
      - Groups by category
      - Computes totalItems, totalQuantity, totalStockValue, avgPrice
    """
    db = get_mongo_db()
    if db is None:
        return None

    pipeline = [
        {"$match": {"is_active": True}},
        {
            "$group": {
                "_id": "$category",
                "totalItems": {"$sum": 1},
                "totalQuantity": {"$sum": "$stock_quantity"},
                "totalStockValue": {"$sum": {"$multiply": ["$price", "$stock_quantity"]}},
                "avgPrice": {"$avg": "$price"}
            }
        },
        {
            "$project": {
                "_id": 1,
                "category": "$_id",
                "totalItems": 1,
                "totalQuantity": 1,
                "totalStockValue": {"$round": ["$totalStockValue", 2]},
                "avgPrice": {"$round": ["$avgPrice", 2]}
            }
        },
        {"$sort": {"category": 1}}
    ]

    try:
        return list(db.products.aggregate(pipeline))
    except Exception as e:
        print(f"⚠️ MongoDB aggregation error: {e}")
        return None


if __name__ == "__main__":
    print("=" * 60)
    print("🍃 Testing MongoDB Connection Status...")
    print("=" * 60)
    status = check_mongo_status()
    for k, v in status.items():
        print(f"  {k}: {v}")
    if status.get("connected"):
        seed_mongo_starter_data()
    print("=" * 60)
