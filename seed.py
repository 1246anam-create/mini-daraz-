"""
Mini Daraz - Seed Data Script
=============================
Creates an admin account, sample categories and products so the store
is ready to use immediately.

Run:  python seed.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import query, execute, init_db
from werkzeug.security import generate_password_hash

PH = "?"


def seed():
    init_db()
    print("Database initialized.")

    # ---- Admin ----
    # Always ensure the admin exists AND has the correct password, so running
    # seed.py fixes a corrupted/unknown admin password on any deployment.
    existing_admin = query("SELECT id FROM admins WHERE email = %s" % PH, ("admin@minidaraz.com",), one=True)
    if not existing_admin:
        execute(
            "INSERT INTO admins (full_name, email, password) VALUES (%s, %s, %s)" % (PH, PH, PH),
            ("Store Admin", "admin@minidaraz.com", generate_password_hash("admin123")),
        )
        print("Admin created -> admin@minidaraz.com / admin123")
    else:
        execute(
            "UPDATE admins SET password = %s WHERE email = %s" % (PH, PH),
            (generate_password_hash("admin123"), "admin@minidaraz.com"),
        )
        print("Admin password reset -> admin@minidaraz.com / admin123")

    # ---- Demo customer ----
    # Ensure a working regular-user account exists and is active, so the
    # customer login (/login) always works for demos/presentations.
    existing_user = query("SELECT id FROM users WHERE email = %s" % PH, ("customer@minidaraz.com",), one=True)
    if not existing_user:
        execute(
            "INSERT INTO users (full_name, email, phone, password, status, created_at) VALUES (%s, %s, %s, %s, %s, %s)" % (PH, PH, PH, PH, PH, PH),
            ("Demo Customer", "customer@minidaraz.com", "03001234567", generate_password_hash("customer123"), "active", "2026-01-01 00:00:00"),
        )
        print("Customer created -> customer@minidaraz.com / customer123")
    else:
        execute(
            "UPDATE users SET password = %s, status = 'active' WHERE email = %s" % (PH, PH),
            (generate_password_hash("customer123"), "customer@minidaraz.com"),
        )
        print("Customer password reset -> customer@minidaraz.com / customer123")

    # Activate any existing (inactive) user accounts so they can log in.
    execute("UPDATE users SET status = 'active' WHERE status IS NULL OR status != 'active'")

    # ---- Categories ----
    categories = [
        ("Electronics", "Gadgets & devices"),
        ("Mobile Phones", "Smartphones & accessories"),
        ("Laptops", "Notebooks & computers"),
        ("Fashion", "Trendy clothing"),
        ("Men's Clothing", "Apparel for men"),
        ("Women's Clothing", "Apparel for women"),
        ("Shoes", "Footwear collection"),
        ("Beauty & Personal Care", "Cosmetics & care"),
        ("Home & Kitchen", "Household essentials"),
        ("Grocery", "Daily necessities"),
        ("Sports", "Sports & fitness"),
        ("Accessories", "Bags, watches & more"),
        ("Bags", "Backpacks & handbags"),
        ("Watches", "Wrist & smart watches"),
    ]

    existing_cat = query("SELECT COUNT(*) AS c FROM categories", one=True)
    if existing_cat and existing_cat["c"] > 0:
        print("Categories already exist (%d). Skipping category seed." % existing_cat["c"])
    else:
        for name, desc in categories:
            execute(
                "INSERT INTO categories (name, description) VALUES (%s, %s)" % (PH, PH),
                (name, desc),
            )
        print("%d categories seeded." % len(categories))

    # ---- Products ----
    existing_prod = query("SELECT COUNT(*) AS c FROM products", one=True)
    if existing_prod and existing_prod["c"] > 0:
        print("Products already exist (%d). Skipping product seed." % existing_prod["c"])
        return

    # Map category names to ids
    cat_rows = query("SELECT id, name FROM categories")
    cat_map = {row["name"]: row["id"] for row in cat_rows}

    products = [
        ("Samsung Galaxy S24", "Latest flagship smartphone with AI features.", 189999.00, 5.0, 12, "Samsung", "Electronics", "s24.jpg", 15),
        ("Apple iPhone 15 Pro", "Titanium design, A17 Pro chip, pro camera.", 389999.00, 4.8, 10, "Apple", "Mobile Phones", "iphone.jpg", 10),
        ("Dell XPS 13 Laptop", "Thin, light, powerful ultrabook.", 249999.00, 4.7, 8, "Dell", "Laptops", "laptop.jpg", 8),
        ("Sony WH-1000XM5", "Industry-leading noise cancelling headphones.", 89999.00, 4.9, 20, "Sony", "Electronics", "headphones.jpg", 20),
        ("Men's Casual Shirt", "Comfortable cotton shirt for daily wear.", 2499.00, 4.5, 50, "Mini Daraz", "Men's Clothing", "shirt.jpg", 50),
        ("Women's Summer Dress", "Elegant and breathable summer dress.", 3499.00, 4.6, 40, "Mini Daraz", "Women's Clothing", "dress.jpg", 40),
        ("Nike Air Max", "Stylish and comfortable running shoes.", 12999.00, 4.8, 30, "Nike", "Shoes", "shoes.jpg", 30),
        ("L'Oreal Face Cream", "Hydrating cream for glowing skin.", 1999.00, 4.4, 60, "L'Oreal", "Beauty & Personal Care", "cream.jpg", 60),
        ("Non-Stick Cookware Set", "Durable kitchen cookware set.", 7499.00, 4.7, 25, "Mini Daraz", "Home & Kitchen", "cookware.jpg", 25),
        ("Basmati Rice 5kg", "Premium quality basmati rice.", 1499.00, 4.9, 100, "Mini Daraz", "Grocery", "rice.jpg", 100),
        ("Yoga Mat", "Non-slip exercise yoga mat.", 1999.00, 4.6, 45, "Mini Daraz", "Sports", "yogamat.jpg", 45),
        ("Leather Wallet", "Genuine leather bifold wallet.", 1799.00, 4.5, 35, "Mini Daraz", "Accessories", "wallet.jpg", 35),
        ("Travel Backpack", "Spacious waterproof travel backpack.", 3999.00, 4.7, 28, "Mini Daraz", "Bags", "backpack.jpg", 28),
        ("Smart Watch Pro", "Fitness tracking smart watch.", 9999.00, 4.6, 22, "Mini Daraz", "Watches", "smartwatch.jpg", 22),
        ("Bluetooth Speaker", "Portable waterproof speaker.", 4499.00, 4.5, 33, "JBL", "Electronics", "speaker.jpg", 33),
        ("Wireless Mouse", "Ergonomic wireless mouse.", 1999.00, 4.4, 55, "Logitech", "Accessories", "mouse.jpg", 55),
        ("Men's Jeans", "Slim fit stretchable jeans.", 2999.00, 4.5, 48, "Mini Daraz", "Men's Clothing", "jeans.jpg", 48),
        ("Women's Handbag", "Trendy faux-leather handbag.", 4999.00, 4.6, 26, "Mini Daraz", "Bags", "handbag.jpg", 26),
        ("Air Fryer 5L", "Healthy oil-free cooking air fryer.", 11999.00, 4.8, 18, "Philips", "Home & Kitchen", "airfryer.jpg", 18),
        ("Green Tea 100 Bags", "Refreshing antioxidant green tea.", 999.00, 4.7, 80, "Lipton", "Grocery", "greentea.jpg", 80),
        ("Dumbbell Set 10kg", "Adjustable home gym dumbbells.", 6499.00, 4.5, 20, "Mini Daraz", "Sports", "dumbbell.jpg", 20),
        ("Sunglasses UV400", "Stylish UV protection sunglasses.", 1499.00, 4.4, 40, "Mini Daraz", "Accessories", "sunglasses.jpg", 40),
        ("School Backpack", "Durable kids school backpack.", 2499.00, 4.6, 30, "Mini Daraz", "Bags", "schoolbag.jpg", 30),
        ("Analog Wrist Watch", "Classic men's analog watch.", 3499.00, 4.5, 24, "Mini Daraz", "Watches", "watch.jpg", 24),
    ]

    for name, desc, price, rating, stock, brand, cat_name, img, discount in products:
        cat_id = cat_map.get(cat_name)
        if cat_id is None:
            continue
        execute(
            """INSERT INTO products
               (name, description, price, rating, stock, brand, category_id, image, discount, featured)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""" % (PH, PH, PH, PH, PH, PH, PH, PH, PH, PH),
            (name, desc, price, rating, stock, brand, cat_id, img, discount, 1),
        )
    print("%d products seeded." % len(products))


if __name__ == "__main__":
    seed()
    print("\nSeed complete! You can now run: python app.py")
    print("Admin login: admin@minidaraz.com / admin123")
