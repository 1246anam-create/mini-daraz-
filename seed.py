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

from db import query, execute, init_db, USE_POSTGRES
from werkzeug.security import generate_password_hash

PH = "?" if not USE_POSTGRES else "%s"


def seed():
    init_db()
    print("Database initialized.")

    # ---- Admin ----
    existing_admin = query("SELECT id FROM admins WHERE email = %s" % PH, ("admin@minidaraz.com",), one=True)
    if not existing_admin:
        execute(
            "INSERT INTO admins (full_name, email, password) VALUES (%s, %s, %s)" % (PH, PH, PH),
            ("Store Admin", "admin@minidaraz.com", generate_password_hash("admin123")),
        )
        print("Admin created -> admin@minidaraz.com / admin123")
    else:
        print("Admin already exists.")

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
        ("Watches", "Wrist watches"),
    ]
    cat_ids = {}
    for name, desc in categories:
        existing = query("SELECT id FROM categories WHERE name = %s" % PH, (name,), one=True)
        if existing:
            cat_ids[name] = existing["id"]
        else:
            execute("INSERT INTO categories (name, description) VALUES (%s, %s)" % (PH, PH), (name, desc))
            cat_ids[name] = query("SELECT id FROM categories WHERE name = %s" % PH, (name,), one=True)["id"]
    print("%d categories ready." % len(cat_ids))

    # ---- Products ----
    products = [
        ("iPhone 15 Pro Max", "Mobile Phones", "Apple", 1199.00, 10, 25, "Latest Apple flagship with A17 Pro chip and titanium design.", "Display: 6.7 inch OLED\nCamera: 48MP Triple\nBattery: 4441 mAh\nStorage: 256GB", {"is_new": True, "is_best_seller": True}),
        ("Samsung Galaxy S24 Ultra", "Mobile Phones", "Samsung", 1099.00, 8, 30, "Powerful Android flagship with built-in S Pen.", "Display: 6.8 inch AMOLED\nCamera: 200MP\nBattery: 5000 mAh\nStorage: 512GB", {"is_trending": True}),
        ("MacBook Air M3", "Laptops", "Apple", 1299.00, 5, 18, "Ultra-thin laptop with M3 chip for blazing performance.", "Display: 13.6 inch\nChip: Apple M3\nRAM: 8GB\nStorage: 256GB SSD", {"is_new": True, "is_best_seller": True}),
        ("Dell XPS 15", "Laptops", "Dell", 1499.00, 12, 12, "Premium Windows laptop with InfinityEdge display.", "Display: 15.6 inch 4K\nProcessor: i7 13th Gen\nRAM: 16GB\nStorage: 1TB SSD", {"is_flash_sale": True}),
        ("Sony WH-1000XM5", "Accessories", "Sony", 399.00, 15, 40, "Industry-leading noise cancelling headphones.", "Type: Over-ear\nBluetooth: 5.2\nBattery: 30 hours", {"is_trending": True}),
        ("Nike Air Max 270", "Shoes", "Nike", 150.00, 20, 50, "Comfortable lifestyle sneakers with Air Max cushioning.", "Style: Lifestyle\nClosure: Lace-up\nSole: Rubber", {"is_best_seller": True}),
        ("Adidas Ultraboost 22", "Shoes", "Adidas", 180.00, 10, 35, "Responsive running shoes with Boost midsole.", "Type: Running\nClosure: Lace-up\nWeight: 310g", {"is_new": True}),
        ("Men's Cotton T-Shirt", "Men's Clothing", "Mini Daraz", 19.99, 0, 100, "Soft 100% cotton t-shirt for everyday wear.", "Material: 100% Cotton\nFit: Regular\nCare: Machine wash", {}),
        ("Women's Summer Dress", "Women's Clothing", "Mini Daraz", 39.99, 25, 60, "Lightweight floral summer dress.", "Material: Polyester\nLength: Midi\nCare: Hand wash", {"is_flash_sale": True}),
        ("Logitech MX Master 3S", "Accessories", "Logitech", 99.00, 5, 45, "Advanced wireless mouse for productivity.", "Connectivity: Bluetooth/USB\nButtons: 8\nBattery: 70 days", {"is_trending": True}),
        ("Casio G-Shock Watch", "Watches", "Casio", 129.00, 10, 30, "Shock-resistant digital watch built for toughness.", "Type: Digital\nWater Resist: 200m\nBattery: 2 years", {"is_best_seller": True}),
        ("Lenovo ThinkPad X1", "Laptops", "Lenovo", 1399.00, 8, 15, "Business laptop with robust security features.", "Display: 14 inch\nProcessor: i7\nRAM: 16GB\nStorage: 512GB SSD", {}),
        ("Apple Watch Series 9", "Watches", "Apple", 429.00, 5, 22, "Advanced health and fitness smartwatch.", "Display: Always-On Retina\nConnectivity: GPS + Cellular\nBattery: 18 hours", {"is_new": True}),
        ("Wireless Earbuds Pro", "Accessories", "SoundCore", 79.99, 30, 80, "Affordable ANC earbuds with great sound.", "Type: In-ear\nBluetooth: 5.3\nBattery: 28 hours", {"is_flash_sale": True, "is_trending": True}),
        ("Non-Stick Cookware Set", "Home & Kitchen", "Tefal", 89.99, 15, 40, "Durable 10-piece non-stick cookware set.", "Pieces: 10\nMaterial: Aluminum\nCompatible: All stovetops", {}),
        ("Organic Green Tea", "Grocery", "OrganicLife", 12.99, 0, 120, "Premium organic green tea leaves.", "Weight: 200g\nType: Loose leaf\nOrigin: Sri Lanka", {"is_best_seller": True}),
        ("Yoga Mat Premium", "Sports", "FitPro", 34.99, 20, 55, "Non-slip eco-friendly yoga mat.", "Thickness: 6mm\nMaterial: TPE\nLength: 183cm", {"is_new": True}),
        ("Leather Backpack", "Bags", "UrbanCraft", 79.99, 10, 28, "Stylish genuine leather backpack for daily use.", "Material: Genuine Leather\nCapacity: 20L\nLaptop: Fits 15 inch", {"is_trending": True}),
        ("Facial Cleanser", "Beauty & Personal Care", "GlowSkin", 24.99, 5, 70, "Gentle foaming facial cleanser for all skin types.", "Volume: 150ml\nType: Foaming\nSkin: All types", {}),
        ("Smart LED TV 55\"", "Electronics", "TCL", 499.00, 18, 20, "4K Ultra HD smart TV with built-in streaming.", "Size: 55 inch\nResolution: 4K\nSmart: Android TV", {"is_flash_sale": True, "is_best_seller": True}),
        ("Bluetooth Speaker", "Electronics", "JBL", 59.99, 12, 65, "Portable waterproof Bluetooth speaker.", "Power: 20W\nWaterproof: IPX7\nBattery: 12 hours", {"is_trending": True}),
        ("Gaming Keyboard RGB", "Accessories", "Razer", 89.99, 10, 38, "Mechanical RGB gaming keyboard.", "Type: Mechanical\nSwitch: Red\nBacklight: RGB", {"is_new": True}),
    ]

    existing_count = query("SELECT COUNT(*) AS c FROM products", one=True)["c"]
    if existing_count > 0:
        print("Products already exist (%d). Skipping product seed." % existing_count)
        return

    for name, cat, brand, price, discount, stock, desc, specs, flags in products:
        cid = cat_ids[cat]
        execute(
            "INSERT INTO products (category_id, name, brand, description, specifications, price, discount, stock, image, status, is_flash_sale, is_new, is_best_seller, is_trending, rating) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            % (PH, PH, PH, PH, PH, PH, PH, PH, PH, PH, PH, PH, PH, PH, PH),
            (cid, name, brand, desc, specs, price, discount, stock, "default-product.svg", "active",
             int(flags.get("is_flash_sale", False)), int(flags.get("is_new", False)),
             int(flags.get("is_best_seller", False)), int(flags.get("is_trending", False)),
             round((4.0 + (hash(name) % 10) / 10.0), 1)),
        )
    print("%d products seeded." % len(products))


if __name__ == "__main__":
    seed()
    print("\nSeed complete! You can now run: python app.py")
    print("Admin login: admin@minidaraz.com / admin123")