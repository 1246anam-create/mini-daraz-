"""
Mini Daraz - Complete E-Commerce Website
========================================
A modern, professional, responsive and fully functional e-commerce platform.

Frontend : HTML5, CSS3, JavaScript, Bootstrap
Backend  : Python Flask
Database : SQLite

Run:  python app.py
"""

import os
import re
import uuid
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for, session,
    flash, jsonify, abort,
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from db import query, execute, init_db

import logging
import traceback

# Log all errors to app.log so they are visible on PythonAnywhere / any host.
logging.basicConfig(
    filename=os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.log"),
    level=logging.ERROR,
    format="%(asctime)s %(levelname)s %(message)s",
)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "mini-daraz-super-secret-key-2026")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_FOLDER = os.path.join(
    BASE_DIR,
    "static",
    "images",
    "products"
)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

DELIVERY_CHARGE = 99.0
FREE_DELIVERY_ABOVE = 1000.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login to continue.", "warning")
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "admin_id" not in session:
            flash("Please login as admin to continue.", "warning")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return wrapper


def discounted_price(price, discount):
    try:
        price = float(price)
        discount = float(discount or 0)
        return round(price - (price * discount / 100), 2)
    except (TypeError, ValueError):
        return float(price or 0)


def format_datetime(value, fmt="%d %b, %I:%M %p"):
    """Format a datetime that may arrive as a string (SQLite) or datetime object."""
    if not value:
        return ""
    if isinstance(value, str):
        try:
            value = datetime.strptime(value[:19], "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return value  # already a formatted string
    try:
        return value.strftime(fmt)
    except (ValueError, TypeError, AttributeError):
        return str(value)


def cart_count():
    if "user_id" in session:
        row = query(
            "SELECT COALESCE(SUM(quantity),0) AS c FROM cart WHERE user_id = ?",
            (session["user_id"],), one=True,
        )
        return row["c"] or 0
    # Guest cart is stored in the session
    return sum(it.get("quantity", 0) for it in session.get("guest_cart", []))


def wishlist_count():
    if "user_id" in session:
        row = query(
            "SELECT COUNT(*) AS c FROM wishlist WHERE user_id = ?",
            (session["user_id"],), one=True,
        )
        return row["c"] or 0
    return 0


def get_cart_items(user_id):
    ph = "?"
    return query(
        f"""
        SELECT c.id AS cart_id, c.quantity, p.*, c.quantity * p.price AS line_total
        FROM cart c
        JOIN products p ON p.id = c.product_id
        WHERE c.user_id = {ph}
        ORDER BY c.id DESC
        """,
        (user_id,),
    )


def cart_summary(user_id):
    items = get_cart_items(user_id)
    subtotal = 0.0
    discount_total = 0.0
    for it in items:
        orig = float(it["price"]) * it["quantity"]
        disc = float(it["discount"] or 0)
        final = orig - (orig * disc / 100)
        subtotal += final
        discount_total += orig * disc / 100
    delivery = 0.0 if subtotal >= FREE_DELIVERY_ABOVE else DELIVERY_CHARGE
    total = subtotal + delivery
    return {
        "items": items,
        "subtotal": round(subtotal, 2),
        "discount": round(discount_total, 2),
        "delivery": round(delivery, 2),
        "total": round(total, 2),
    }


def get_guest_cart_items():
    """Return guest cart items (dicts) with product details joined in."""
    items = session.get("guest_cart", [])
    if not items:
        return []
    ids = [it["product_id"] for it in items]
    placeholders = ",".join("?" for _ in ids)
    products = query(
        f"SELECT * FROM products WHERE id IN ({placeholders})", ids
    )
    by_id = {p["id"]: p for p in products}
    result = []
    for it in items:
        p = by_id.get(it["product_id"])
        if not p:
            continue
        entry = dict(p)
        entry["cart_id"] = "g" + str(it["product_id"])
        entry["quantity"] = it["quantity"]
        entry["line_total"] = float(p["price"]) * it["quantity"]
        result.append(entry)
    return result


def guest_cart_summary():
    items = get_guest_cart_items()
    subtotal = 0.0
    discount_total = 0.0
    for it in items:
        orig = float(it["price"]) * it["quantity"]
        disc = float(it["discount"] or 0)
        final = orig - (orig * disc / 100)
        subtotal += final
        discount_total += orig * disc / 100
    delivery = 0.0 if subtotal >= FREE_DELIVERY_ABOVE else DELIVERY_CHARGE
    total = subtotal + delivery
    return {
        "items": items,
        "subtotal": round(subtotal, 2),
        "discount": round(discount_total, 2),
        "delivery": round(delivery, 2),
        "total": round(total, 2),
    }


def merge_guest_cart(user_id):
    """Move session guest cart into the DB cart for the logged-in user."""
    guest = session.get("guest_cart", [])
    if not guest:
        return
    for it in guest:
        pid = it["product_id"]
        qty = it["quantity"]
        product = query("SELECT * FROM products WHERE id = ?", (pid,), one=True)
        if not product:
            continue
        existing = query(
            "SELECT * FROM cart WHERE user_id=? AND product_id=?",
            (user_id, pid), one=True,
        )
        if existing:
            new_qty = min(existing["quantity"] + qty, product["stock"] if product["stock"] > 0 else 99)
            execute("UPDATE cart SET quantity=? WHERE id=?", (new_qty, existing["id"]))
        else:
            execute(
                "INSERT INTO cart (user_id, product_id, quantity) VALUES (?, ?, ?)",
                (user_id, pid, qty),
            )
    session.pop("guest_cart", None)


def get_product(product_id):
    ph = "?"
    return query(
        f"""
        SELECT p.*, c.name AS category_name
        FROM products p
        JOIN categories c ON c.id = p.category_id
        WHERE p.id = {ph}
        """,
        (product_id,), one=True,
    )


def product_rating(product_id):
    ph = "?"
    row = query(
        f"SELECT AVG(rating) AS avg_r, COUNT(*) AS cnt FROM reviews WHERE product_id = {ph}",
        (product_id,), one=True,
    )
    avg = round(float(row["avg_r"] or 0), 1)
    return avg, row["cnt"]


def generate_order_number():
    return "MD" + datetime.now().strftime("%Y%m%d") + uuid.uuid4().hex[:6].upper()


# ---------------------------------------------------------------------------
# Context processor
# ---------------------------------------------------------------------------
@app.context_processor
def inject_globals():
    return {
        "cart_count": cart_count(),
        "wishlist_count": wishlist_count(),
        "current_year": datetime.now().year,
        "db_engine": "SQLite",
        "query": query,
        "site_settings": get_settings(),
    }


# Make the datetime formatter available in all templates
app.jinja_env.globals["format_datetime"] = format_datetime


def get_settings():
    """Return the single site settings row (logo / slideshow video)."""
    try:
        row = query("SELECT * FROM settings ORDER BY id LIMIT 1", one=True)
    except Exception:
        row = None
    if not row:
        row = {"logo": None, "slideshow_video": None, "slideshow_poster": None}
    return row


# ---------------------------------------------------------------------------
# Public pages
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    ph = "?"
    categories = query("SELECT * FROM categories ORDER BY name")
    flash_sale = query(
        "SELECT * FROM products WHERE status='active' AND is_flash_sale=1 ORDER BY discount DESC LIMIT 8"
    )
    popular = query("SELECT * FROM products WHERE status='active' ORDER BY rating DESC, stock DESC LIMIT 8")
    new_arrivals = query(
        "SELECT * FROM products WHERE status='active' AND is_new=1 ORDER BY id DESC LIMIT 8"
    )
    best_sellers = query(
        "SELECT * FROM products WHERE status='active' AND is_best_seller=1 ORDER BY id DESC LIMIT 8"
    )
    trending = query(
        "SELECT * FROM products WHERE status='active' AND is_trending=1 ORDER BY id DESC LIMIT 8"
    )
    special = query("SELECT * FROM products WHERE status='active' AND discount > 0 ORDER BY discount DESC LIMIT 8")
    return render_template(
        "index.html",
        categories=categories,
        flash_sale=flash_sale,
        popular=popular,
        new_arrivals=new_arrivals,
        best_sellers=best_sellers,
        trending=trending,
        special=special,
    )


@app.route("/products")
def products():
    ph = "?"
    search = request.args.get("q", "").strip()
    category_id = request.args.get("category", "")
    brand = request.args.get("brand", "").strip()
    min_price = request.args.get("min_price", "").strip()
    max_price = request.args.get("max_price", "").strip()
    rating = request.args.get("rating", "").strip()
    discount = request.args.get("discount", "").strip()
    availability = request.args.get("availability", "").strip()
    sort = request.args.get("sort", "newest")

    where = ["p.status = 'active'"]
    params = []

    if search:
        where.append(f"(p.name LIKE {ph} OR p.brand LIKE {ph} OR c.name LIKE {ph})")
        like = f"%{search}%"
        params += [like, like, like]

    if category_id:
        where.append(f"p.category_id = {ph}")
        params.append(category_id)

    if brand:
        where.append(f"p.brand LIKE {ph}")
        params.append(f"%{brand}%")

    if min_price:
        where.append(f"p.price >= {ph}")
        params.append(min_price)

    if max_price:
        where.append(f"p.price <= {ph}")
        params.append(max_price)

    if rating:
        where.append(f"p.rating >= {ph}")
        params.append(rating)

    if discount:
        where.append(f"p.discount >= {ph}")
        params.append(discount)

    if availability == "in_stock":
        where.append("p.stock > 0")
    elif availability == "out_of_stock":
        where.append("p.stock <= 0")

    sort_map = {
        "price_asc": "p.price ASC",
        "price_desc": "p.price DESC",
        "newest": "p.id DESC",
        "popular": "p.rating DESC, p.stock DESC",
        "rated": "p.rating DESC",
        "discount": "p.discount DESC",
    }
    order_by = sort_map.get(sort, "p.id DESC")

    sql = f"""
        SELECT p.*, c.name AS category_name
        FROM products p
        JOIN categories c ON c.id = p.category_id
        WHERE {' AND '.join(where)}
        ORDER BY {order_by}
    """
    product_list = query(sql, params)

    categories = query("SELECT * FROM categories ORDER BY name")
    brands = query("SELECT DISTINCT brand FROM products WHERE brand IS NOT NULL AND brand != '' ORDER BY brand")

    # Build sort URLs in Python (Jinja cannot unpack **kwargs in url_for)
    base_args = {k: v for k, v in request.args.items() if k != "sort"}
    sort_urls = {key: url_for("products", sort=key, **base_args) for key in
                 ["default", "price_asc", "price_desc", "rating", "newest"]}

    return render_template(
        "products.html",
        products=product_list,
        categories=categories,
        brands=[b["brand"] for b in brands],
        search=search,
        category_id=category_id,
        brand=brand,
        min_price=min_price,
        max_price=max_price,
        rating=rating,
        discount=discount,
        availability=availability,
        sort=sort,
        sort_urls=sort_urls,
    )


@app.route("/product/<int:product_id>")
def product_details(product_id):
    ph = "?"
    product = get_product(product_id)
    if not product:
        abort(404)

    avg_rating, review_count = product_rating(product_id)
    reviews = query(
        f"""
        SELECT r.*, u.full_name
        FROM reviews r
        JOIN users u ON u.id = r.user_id
        WHERE r.product_id = {ph}
        ORDER BY r.id DESC
        """,
        (product_id,),
    )
    related = query(
        f"""
        SELECT * FROM products
        WHERE status='active' AND category_id = {ph} AND id != {ph}
        ORDER BY id DESC LIMIT 4
        """,
        (product["category_id"], product_id),
    )
    if not related:
        related = query("SELECT * FROM products WHERE status='active' AND id != ? ORDER BY id DESC LIMIT 4", (product_id,))

    in_cart = False
    in_wishlist = False
    if "user_id" in session:
        in_cart = bool(query(f"SELECT id FROM cart WHERE user_id={ph} AND product_id={ph}",
                             (session["user_id"], product_id), one=True))
        in_wishlist = bool(query(f"SELECT id FROM wishlist WHERE user_id={ph} AND product_id={ph}",
                                 (session["user_id"], product_id), one=True))

    return render_template(
        "product-details.html",
        product=product,
        avg_rating=avg_rating,
        review_count=review_count,
        reviews=reviews,
        related=related,
        in_cart=in_cart,
        in_wishlist=in_wishlist,
    )


@app.route("/categories")
def categories_page():
    cats = query(
        f"""
        SELECT c.*, COUNT(p.id) AS product_count
        FROM categories c
        LEFT JOIN products p ON p.category_id = c.id AND p.status='active'
        GROUP BY c.id
        ORDER BY c.name
        """
    )
    return render_template("categories.html", categories=cats)


@app.route("/category/<int:category_id>")
def category_products(category_id):
    ph = "?"
    cat = query("SELECT * FROM categories WHERE id = %s" % ph, (category_id,), one=True)
    if not cat:
        abort(404)
    product_list = query(
        f"SELECT p.*, c.name AS category_name FROM products p JOIN categories c ON c.id=p.category_id WHERE p.category_id={ph} AND p.status='active' ORDER BY p.id DESC",
        (category_id,),
    )
    return render_template("products.html", products=product_list, categories=query("SELECT * FROM categories ORDER BY name"),
                           brands=[b["brand"] for b in query("SELECT DISTINCT brand FROM products WHERE brand IS NOT NULL AND brand != '' ORDER BY brand")],
                           search="", category_id=str(category_id), brand="", min_price="", max_price="",
                           rating="", discount="", availability="", sort="newest", active_category=cat,
                           sort_urls={key: url_for("category_products", category_id=category_id, sort=key) for key in
                                      ["default", "price_asc", "price_desc", "rating", "newest"]})


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        errors = []
        if len(full_name) < 3:
            errors.append("Full name must be at least 3 characters.")
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            errors.append("Please enter a valid email address.")
        if len(phone) < 7:
            errors.append("Please enter a valid phone number.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")

        existing = query("SELECT id FROM users WHERE email = ?", (email,), one=True)
        if existing:
            errors.append("An account with this email already exists.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("signup.html", form=request.form)

        hashed = generate_password_hash(password)
        execute(
            "INSERT INTO users (full_name, email, phone, password) VALUES (?, ?, ?, ?)",
            (full_name, email, phone, hashed),
        )
        flash("Account created successfully! Please login.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html", form={})


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = query("SELECT * FROM users WHERE email = ?", (email,), one=True)

        if not user or not check_password_hash(user["password"], password):
            flash("Invalid email or password.", "danger")
            return render_template("login.html", form=request.form)

        if user["status"] != "active":
            flash("Your account has been deactivated. Contact support.", "danger")
            return render_template("login.html", form=request.form)

        # Capture guest cart BEFORE clearing the session
        guest_cart = session.get("guest_cart", [])
        session.clear()
        session["user_id"] = user["id"]
        session["user_name"] = user["full_name"]
        if guest_cart:
            session["guest_cart"] = guest_cart
            merge_guest_cart(user["id"])
        flash(f"Welcome back, {user['full_name']}!", "success")
        nxt = request.args.get("next")
        return redirect(nxt or url_for("index"))

    return render_template("login.html", form={})


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# User dashboard / profile
# ---------------------------------------------------------------------------
@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    ph = "?"
    user = query("SELECT * FROM users WHERE id = %s" % ph, (session["user_id"],), one=True)
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        city = request.form.get("city", "").strip()
        postal_code = request.form.get("postal_code", "").strip()
        execute(
            "UPDATE users SET full_name=?, phone=?, address=?, city=?, postal_code=? WHERE id=?",
            (full_name, phone, address, city, postal_code, session["user_id"]),
        )
        session["user_name"] = full_name
        flash("Profile updated successfully!", "success")
        return redirect(url_for("profile"))
    return render_template("profile.html", user=user)


@app.route("/change-password", methods=["POST"])
@login_required
def change_password():
    ph = "?"
    current = request.form.get("current_password", "")
    new_pass = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")

    user = query("SELECT * FROM users WHERE id = %s" % ph, (session["user_id"],), one=True)
    if not check_password_hash(user["password"], current):
        flash("Current password is incorrect.", "danger")
    elif len(new_pass) < 6:
        flash("New password must be at least 6 characters.", "danger")
    elif new_pass != confirm:
        flash("New passwords do not match.", "danger")
    else:
        execute("UPDATE users SET password=? WHERE id=?",
                (generate_password_hash(new_pass), session["user_id"]))
        flash("Password changed successfully!", "success")
    return redirect(url_for("profile"))


# ---------------------------------------------------------------------------
# Cart
# ---------------------------------------------------------------------------
@app.route("/cart")
def cart():
    if "user_id" in session:
        summary = cart_summary(session["user_id"])
    else:
        summary = guest_cart_summary()
    return render_template("cart.html", **summary, guest=("user_id" not in session))


@app.route("/cart/add", methods=["POST"])
def add_to_cart():
    ph = "?"
    product_id = request.form.get("product_id")
    quantity = int(request.form.get("quantity", 1) or 1)
    product = query("SELECT * FROM products WHERE id = %s" % ph, (product_id,), one=True)
    if not product:
        flash("Product not found.", "danger")
        return redirect(url_for("products"))

    if "user_id" in session:
        existing = query("SELECT * FROM cart WHERE user_id=? AND product_id=?",
                         (session["user_id"], product_id), one=True)
        if existing:
            new_qty = min(existing["quantity"] + quantity, product["stock"] if product["stock"] > 0 else 99)
            execute("UPDATE cart SET quantity=? WHERE id=?",
                    (new_qty, existing["id"]))
        else:
            execute("INSERT INTO cart (user_id, product_id, quantity) VALUES (?, ?, ?)",
                    (session["user_id"], product_id, quantity))
    else:
        # Guest cart stored in session
        guest = session.get("guest_cart", [])
        found = False
        for it in guest:
            if it["product_id"] == int(product_id):
                it["quantity"] = min(it["quantity"] + quantity, product["stock"] if product["stock"] > 0 else 99)
                found = True
                break
        if not found:
            guest.append({"product_id": int(product_id), "quantity": quantity})
        session["guest_cart"] = guest
    flash("Product added to cart!", "success")
    if request.form.get("buy_now") or request.args.get("buy_now"):
        return redirect(url_for("checkout"))
    return redirect(request.referrer or url_for("cart"))


@app.route("/cart/update", methods=["POST"])
def update_cart():
    ph = "?"
    cart_id = request.form.get("cart_id")
    quantity = int(request.form.get("quantity", 1) or 1)
    if quantity < 1:
        quantity = 1
    if "user_id" in session:
        execute("UPDATE cart SET quantity=? WHERE id=? AND user_id=?",
                (quantity, cart_id, session["user_id"]))
    else:
        guest = session.get("guest_cart", [])
        for it in guest:
            if "g" + str(it["product_id"]) == str(cart_id):
                it["quantity"] = quantity
                break
        session["guest_cart"] = guest
    flash("Cart updated.", "info")
    return redirect(url_for("cart"))


@app.route("/cart/remove/<cart_id>")
def remove_from_cart(cart_id):
    if "user_id" in session:
        execute("DELETE FROM cart WHERE id=? AND user_id=?",
                (cart_id, session["user_id"]))
    else:
        # Guest cart ids are prefixed with "g" (e.g. "g25")
        pid = cart_id[1:] if str(cart_id).startswith("g") else cart_id
        try:
            pid = int(pid)
        except (ValueError, TypeError):
            pid = None
        guest = session.get("guest_cart", [])
        if pid is not None:
            guest = [it for it in guest if it["product_id"] != pid]
        session["guest_cart"] = guest
    flash("Product removed from cart.", "info")
    return redirect(url_for("cart"))


# ---------------------------------------------------------------------------
# Wishlist
# ---------------------------------------------------------------------------
@app.route("/wishlist")
@login_required
def wishlist():
    ph = "?"
    items = query(
        f"""
        SELECT w.id AS wish_id, p.*
        FROM wishlist w
        JOIN products p ON p.id = w.product_id
        WHERE w.user_id = {ph}
        ORDER BY w.id DESC
        """,
        (session["user_id"],),
    )
    return render_template("wishlist.html", items=items)


@app.route("/wishlist/add", methods=["POST"])
@login_required
def add_to_wishlist():
    ph = "?"
    product_id = request.form.get("product_id")
    existing = query("SELECT id FROM wishlist WHERE user_id=? AND product_id=?",
                     (session["user_id"], product_id), one=True)
    if existing:
        flash("Product already in wishlist.", "info")
    else:
        execute("INSERT INTO wishlist (user_id, product_id) VALUES (?, ?)",
                (session["user_id"], product_id))
        flash("Product added to wishlist!", "success")
    return redirect(request.referrer or url_for("wishlist"))


@app.route("/wishlist/remove/<int:wish_id>")
@login_required
def remove_from_wishlist(wish_id):
    execute("DELETE FROM wishlist WHERE id=? AND user_id=?",
            (wish_id, session["user_id"]))
    flash("Product removed from wishlist.", "info")
    return redirect(url_for("wishlist"))


@app.route("/wishlist/move-to-cart/<int:wish_id>")
@login_required
def move_to_cart(wish_id):
    ph = "?"
    item = query("SELECT * FROM wishlist WHERE id=? AND user_id=?",
                 (wish_id, session["user_id"]), one=True)
    if item:
        existing = query("SELECT * FROM cart WHERE user_id=? AND product_id=?",
                         (session["user_id"], item["product_id"]), one=True)
        if existing:
            execute("UPDATE cart SET quantity=quantity+1 WHERE id=%s" % ph, (existing["id"],))
        else:
            execute("INSERT INTO cart (user_id, product_id, quantity) VALUES (?, ?, 1)",
                    (session["user_id"], item["product_id"]))
        execute("DELETE FROM wishlist WHERE id=%s" % ph, (wish_id,))
        flash("Product moved to cart!", "success")
    return redirect(url_for("wishlist"))


# ---------------------------------------------------------------------------
# AJAX count endpoints
# ---------------------------------------------------------------------------
@app.route("/cart/count")
def cart_count_api():
    return jsonify({"count": cart_count()})


@app.route("/wishlist/count")
def wishlist_count_api():
    return jsonify({"count": wishlist_count()})


# ---------------------------------------------------------------------------
# Checkout & Orders
# ---------------------------------------------------------------------------
@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    ph = "?"
    if "user_id" in session:
        summary = cart_summary(session["user_id"])
        user = query("SELECT * FROM users WHERE id = %s" % ph, (session["user_id"],), one=True)
    else:
        summary = guest_cart_summary()
        user = None

    if not summary["items"]:
        flash("Your cart is empty. Add products before checkout.", "warning")
        return redirect(url_for("cart"))

    if request.method == "POST":
        customer_name = request.form.get("customer_name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        address = request.form.get("address", "").strip()
        city = request.form.get("city", "").strip()
        postal_code = request.form.get("postal_code", "").strip()
        payment_method = request.form.get("payment_method", "Cash on Delivery")

        errors = []
        if len(customer_name) < 3:
            errors.append("Please enter your full name.")
        if len(phone) < 7:
            errors.append("Please enter a valid phone number.")
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            errors.append("Please enter a valid email.")
        if len(address) < 5:
            errors.append("Please enter your complete address.")
        if not city:
            errors.append("Please enter your city.")
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("checkout.html", summary=summary, user=user, form=request.form)

        order_number = generate_order_number()
        execute(
            "INSERT INTO orders (order_number, user_id, customer_name, phone, email, address, city, postal_code, payment_method, subtotal, delivery_charge, discount, total) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (order_number, session.get("user_id"), customer_name, phone, email, address, city, postal_code,
             payment_method, summary["subtotal"], summary["delivery"], summary["discount"], summary["total"]),
        )
        order = query("SELECT * FROM orders WHERE order_number = %s" % ph, (order_number,), one=True)

        for item in summary["items"]:
            execute(
                "INSERT INTO order_items (order_id, product_id, product_name, product_image, price, quantity, subtotal) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (order["id"], item["id"], item["name"], item["image"],
                 discounted_price(item["price"], item["discount"]), item["quantity"],
                 round(discounted_price(item["price"], item["discount"]) * item["quantity"], 2)),
            )
            execute("UPDATE products SET stock = stock - ? WHERE id = ?",
                    (item["quantity"], item["id"]))

        if "user_id" in session:
            execute("DELETE FROM cart WHERE user_id = %s" % ph, (session["user_id"],))
        else:
            session.pop("guest_cart", None)

        flash(f"Order placed successfully! Your Order ID is {order_number}", "success")
        return redirect(url_for("order_confirmation", order_number=order_number))

    return render_template("checkout.html", summary=summary, user=user, form={})


@app.route("/order-confirmation/<order_number>")
def order_confirmation(order_number):
    ph = "?"
    if "user_id" in session:
        order = query("SELECT * FROM orders WHERE order_number=? AND user_id=?",
                      (order_number, session["user_id"]), one=True)
    else:
        # Guests can view their confirmation by order number alone
        order = query("SELECT * FROM orders WHERE order_number=?",
                      (order_number,), one=True)
    if not order:
        abort(404)
    items = query("SELECT * FROM order_items WHERE order_id=%s" % ph, (order["id"],))
    return render_template("order-confirmation.html", order=order, items=items)


@app.route("/orders")
@login_required
def orders():
    ph = "?"
    order_list = query("SELECT * FROM orders WHERE user_id=%s ORDER BY id DESC" % ph, (session["user_id"],))
    return render_template("orders.html", orders=order_list)


@app.route("/order/<int:order_id>")
@login_required
def order_details(order_id):
    ph = "?"
    order = query("SELECT * FROM orders WHERE id=? AND user_id=?",
                  (order_id, session["user_id"]), one=True)
    if not order:
        abort(404)
    items = query("SELECT * FROM order_items WHERE order_id=%s" % ph, (order_id,))
    return render_template("order-details.html", order=order, items=items)


@app.route("/track-order", methods=["GET", "POST"])
def track_order():
    order = None
    if request.method == "POST":
        order_number = request.form.get("order_number", "").strip()
        ph = "?"
        order = query("SELECT * FROM orders WHERE order_number=%s" % ph, (order_number,), one=True)
        if not order:
            flash("No order found with that Order ID.", "danger")
    return render_template("track-order.html", order=order)


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------
@app.route("/product/<int:product_id>/review", methods=["POST"])
@login_required
def add_review(product_id):
    ph = "?"
    rating = int(request.form.get("rating", 0))
    comment = request.form.get("comment", "").strip()

    if rating < 1 or rating > 5:
        flash("Please select a rating between 1 and 5 stars.", "danger")
        return redirect(url_for("product_details", product_id=product_id))

    existing = query("SELECT id FROM reviews WHERE user_id=? AND product_id=?",
                     (session["user_id"], product_id), one=True)
    if existing:
        execute("UPDATE reviews SET rating=?, comment=? WHERE id=?",
                (rating, comment, existing["id"]))
        flash("Your review has been updated!", "success")
    else:
        execute("INSERT INTO reviews (user_id, product_id, rating, comment) VALUES (?, ?, ?, ?)",
                (session["user_id"], product_id, rating, comment))
        flash("Thank you for your review!", "success")

    avg, cnt = product_rating(product_id)
    execute("UPDATE products SET rating=? WHERE id=?", (avg, product_id))
    return redirect(url_for("product_details", product_id=product_id))


# ---------------------------------------------------------------------------
# About / Contact
# ---------------------------------------------------------------------------
@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        subject = request.form.get("subject", "").strip()
        message = request.form.get("message", "").strip()

        if not full_name or not email or not message:
            flash("Please fill in all required fields.", "danger")
        else:
            execute(
                "INSERT INTO contact_messages (full_name, email, phone, subject, message) VALUES (?, ?, ?, ?, ?)",
                (full_name, email, phone, subject, message),
            )
            flash("Your message has been sent! Our support team will contact you soon.", "success")
            return redirect(url_for("contact"))
    return render_template("contact.html")


@app.route("/messages", methods=["GET", "POST"])
@login_required
def messages():
    """Customer support chat: logged-in users send messages and see admin replies."""
    ph = "?"
    uid = session.get("user_id")
    user = query("SELECT * FROM users WHERE id=%s" % ph, (uid,), one=True)
    if not user:
        # Defensive: session points to a missing/deleted user -> send them to login
        session.clear()
        flash("Your session expired. Please login again.", "warning")
        return redirect(url_for("login"))

    if request.method == "POST":
        message = request.form.get("message", "").strip()
        if message:
            execute(
                "INSERT INTO contact_messages (full_name, email, phone, subject, message, user_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user["full_name"], user["email"], user.get("phone", ""), "Support Chat", message, uid),
            )
            flash("Message sent! Our support team will reply soon.", "success")
            return redirect(url_for("messages"))

    thread = query(
        "SELECT * FROM contact_messages WHERE user_id=%s ORDER BY created_at ASC" % ph, (uid,)
    )
    return render_template("messages.html", thread=thread, user=user)


# ---------------------------------------------------------------------------
# Admin Authentication
# ---------------------------------------------------------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        admin = query("SELECT * FROM admins WHERE email = ?", (email,), one=True)
        if not admin or not check_password_hash(admin["password"], password):
            flash("Invalid admin credentials.", "danger")
            return render_template("admin/login.html")
        session.clear()
        session["admin_id"] = admin["id"]
        session["admin_name"] = admin["full_name"]
        flash(f"Welcome, {admin['full_name']}!", "success")
        return redirect(url_for("admin_dashboard"))
    return render_template("admin/login.html")


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    flash("Admin logged out.", "info")
    return redirect(url_for("admin_login"))


# ---------------------------------------------------------------------------
# Admin Dashboard
# ---------------------------------------------------------------------------
@app.route("/admin")
@admin_required
def admin_dashboard():
    ph = "?"
    stats = {
        "products": query("SELECT COUNT(*) AS c FROM products", one=True)["c"],
        "categories": query("SELECT COUNT(*) AS c FROM categories", one=True)["c"],
        "users": query("SELECT COUNT(*) AS c FROM users", one=True)["c"],
        "orders": query("SELECT COUNT(*) AS c FROM orders", one=True)["c"],
        "pending": query("SELECT COUNT(*) AS c FROM orders WHERE status='Pending'", one=True)["c"],
        "delivered": query("SELECT COUNT(*) AS c FROM orders WHERE status='Delivered'", one=True)["c"],
        "cancelled": query("SELECT COUNT(*) AS c FROM orders WHERE status='Cancelled'", one=True)["c"],
        "sales": query("SELECT COALESCE(SUM(total),0) AS s FROM orders WHERE status != 'Cancelled'", one=True)["s"],
    }
    recent_orders = query("SELECT * FROM orders ORDER BY id DESC LIMIT 8")
    best_sellers = query(
        f"""
        SELECT oi.product_name, SUM(oi.quantity) AS qty, SUM(oi.subtotal) AS revenue
        FROM order_items oi
        GROUP BY oi.product_name
        ORDER BY qty DESC LIMIT 6
        """
    )
    low_stock = query("SELECT * FROM products WHERE stock <= 5 ORDER BY stock ASC LIMIT 6")
    monthly_sales = query(
        f"""
        SELECT strftime('%Y-%m', created_at) AS month, SUM(total) AS sales
        FROM orders WHERE status != 'Cancelled'
        GROUP BY month ORDER BY month DESC LIMIT 6
        """
    )
    return render_template(
        "admin/dashboard.html",
        stats=stats,
        recent_orders=recent_orders,
        best_sellers=best_sellers,
        low_stock=low_stock,
        monthly_sales=monthly_sales,
    )


# ---------------------------------------------------------------------------
# Admin - Product Management
# ---------------------------------------------------------------------------
@app.route("/admin/products")
@admin_required
def admin_products():
    ph = "?"
    search = request.args.get("q", "").strip()
    if search:
        product_list = query(
            f"SELECT p.*, c.name AS category_name FROM products p JOIN categories c ON c.id=p.category_id WHERE p.name LIKE {ph} OR p.brand LIKE {ph} ORDER BY p.id DESC",
            (f"%{search}%", f"%{search}%"),
        )
    else:
        product_list = query(
            "SELECT p.*, c.name AS category_name FROM products p JOIN categories c ON c.id=p.category_id ORDER BY p.id DESC"
        )
    return render_template("admin/products.html", products=product_list, search=search)


@app.route("/admin/products/add", methods=["GET", "POST"])
@admin_required
def admin_add_product():
    ph = "?"
    categories = query("SELECT * FROM categories ORDER BY name")
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category_id = request.form.get("category_id")
        brand = request.form.get("brand", "").strip()
        price = request.form.get("price", "").strip()
        discount = request.form.get("discount", 0)
        description = request.form.get("description", "").strip()
        specifications = request.form.get("specifications", "").strip()
        stock = request.form.get("stock", 0)
        status = request.form.get("status", "active")
        is_flash_sale = 1 if request.form.get("is_flash_sale") else 0
        is_new = 1 if request.form.get("is_new") else 0
        is_best_seller = 1 if request.form.get("is_best_seller") else 0
        is_trending = 1 if request.form.get("is_trending") else 0

        errors = []
        if len(name) < 3:
            errors.append("Product name is required.")
        if not category_id:
            errors.append("Please select a category.")
        try:
            price = float(price)
            if price <= 0:
                errors.append("Price must be greater than 0.")
        except ValueError:
            errors.append("Invalid price.")
        try:
            discount = float(discount)
            if discount < 0 or discount > 90:
                errors.append("Discount must be between 0 and 90.")
        except ValueError:
            errors.append("Invalid discount.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("admin/add-product.html", categories=categories, form=request.form)

        image = "default-product.svg"
        if "image" in request.files:
            file = request.files["image"]
            if file and file.filename and allowed_file(file.filename):
                fname = secure_filename(file.filename)
                fname = f"{uuid.uuid4().hex[:8]}_{fname}"
                os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
                file.save(os.path.join(app.config["UPLOAD_FOLDER"], fname))
                image = fname

        execute(
            "INSERT INTO products (category_id, name, brand, description, specifications, price, discount, stock, image, status, is_flash_sale, is_new, is_best_seller, is_trending) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (category_id, name, brand, description, specifications, price, discount, stock, image, status,
             is_flash_sale, is_new, is_best_seller, is_trending),
        )
        flash("Product added successfully!", "success")
        return redirect(url_for("admin_products"))
    return render_template("admin/add-product.html", categories=categories, form={})


@app.route("/admin/products/edit/<int:product_id>", methods=["GET", "POST"])
@admin_required
def admin_edit_product(product_id):
    ph = "?"
    product = query("SELECT * FROM products WHERE id=%s" % ph, (product_id,), one=True)
    if not product:
        abort(404)
    categories = query("SELECT * FROM categories ORDER BY name")
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category_id = request.form.get("category_id")
        brand = request.form.get("brand", "").strip()
        price = request.form.get("price", "").strip()
        discount = request.form.get("discount", 0)
        description = request.form.get("description", "").strip()
        specifications = request.form.get("specifications", "").strip()
        stock = request.form.get("stock", 0)
        status = request.form.get("status", "active")
        is_flash_sale = 1 if request.form.get("is_flash_sale") else 0
        is_new = 1 if request.form.get("is_new") else 0
        is_best_seller = 1 if request.form.get("is_best_seller") else 0
        is_trending = 1 if request.form.get("is_trending") else 0

        image = product["image"]
        if "image" in request.files:
            file = request.files["image"]
            if file and file.filename and allowed_file(file.filename):
                fname = secure_filename(file.filename)
                fname = f"{uuid.uuid4().hex[:8]}_{fname}"
                os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
                file.save(os.path.join(app.config["UPLOAD_FOLDER"], fname))
                image = fname

        execute(
            "UPDATE products SET category_id=?, name=?, brand=?, description=?, specifications=?, price=?, discount=?, stock=?, image=?, status=?, is_flash_sale=?, is_new=?, is_best_seller=?, is_trending=? WHERE id=?",
            (category_id, name, brand, description, specifications, price, discount, stock, image, status,
             is_flash_sale, is_new, is_best_seller, is_trending, product_id),
        )
        flash("Product updated successfully!", "success")
        return redirect(url_for("admin_products"))
    return render_template("admin/edit-product.html", product=product, categories=categories)


@app.route("/admin/products/delete/<int:product_id>")
@admin_required
def admin_delete_product(product_id):
    execute("DELETE FROM products WHERE id=?", (product_id,))
    flash("Product deleted.", "info")
    return redirect(url_for("admin_products"))


# ---------------------------------------------------------------------------
# Admin - Category Management
# ---------------------------------------------------------------------------
@app.route("/admin/categories", methods=["GET", "POST"])
@admin_required
def admin_categories():
    ph = "?"
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        if len(name) < 2:
            flash("Category name is required.", "danger")
        else:
            existing = query("SELECT id FROM categories WHERE name=%s" % ph, (name,), one=True)
            if existing:
                flash("Category already exists.", "danger")
            else:
                execute("INSERT INTO categories (name, description) VALUES (?, ?)",
                        (name, description))
                flash("Category added successfully!", "success")
        return redirect(url_for("admin_categories"))

    cats = query(
        f"""
        SELECT c.*, COUNT(p.id) AS product_count
        FROM categories c
        LEFT JOIN products p ON p.category_id = c.id
        GROUP BY c.id
        ORDER BY c.name
        """
    )
    return render_template("admin/categories.html", categories=cats)


@app.route("/admin/categories/edit/<int:category_id>", methods=["POST"])
@admin_required
def admin_edit_category(category_id):
    ph = "?"
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    if len(name) < 2:
        flash("Category name is required.", "danger")
    else:
        execute("UPDATE categories SET name=?, description=? WHERE id=?",
                (name, description, category_id))
        flash("Category updated!", "success")
    return redirect(url_for("admin_categories"))


@app.route("/admin/categories/delete/<int:category_id>")
@admin_required
def admin_delete_category(category_id):
    execute("DELETE FROM categories WHERE id=?", (category_id,))
    flash("Category deleted.", "info")
    return redirect(url_for("admin_categories"))


# ---------------------------------------------------------------------------
# Admin - User Management
# ---------------------------------------------------------------------------
@app.route("/admin/users")
@admin_required
def admin_users():
    ph = "?"
    search = request.args.get("q", "").strip()
    if search:
        users = query(
            f"SELECT * FROM users WHERE full_name LIKE {ph} OR email LIKE {ph} ORDER BY id DESC",
            (f"%{search}%", f"%{search}%"),
        )
    else:
        users = query("SELECT * FROM users ORDER BY id DESC")
    return render_template("admin/users.html", users=users, search=search)


@app.route("/admin/users/toggle/<int:user_id>")
@admin_required
def admin_toggle_user(user_id):
    ph = "?"
    user = query("SELECT * FROM users WHERE id=%s" % ph, (user_id,), one=True)
    if user:
        new_status = "inactive" if user["status"] == "active" else "active"
        execute("UPDATE users SET status=? WHERE id=?",
                (new_status, user_id))
        flash(f"User account {new_status}.", "info")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/delete/<int:user_id>")
@admin_required
def admin_delete_user(user_id):
    execute("DELETE FROM users WHERE id=?", (user_id,))
    flash("User deleted.", "info")
    return redirect(url_for("admin_users"))


# ---------------------------------------------------------------------------
# Admin - Order Management
# ---------------------------------------------------------------------------
@app.route("/admin/orders")
@admin_required
def admin_orders():
    ph = "?"
    search = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    where = []
    params = []
    if search:
        where.append(f"order_number LIKE {ph}")
        params.append(f"%{search}%")
    if status:
        where.append(f"status = {ph}")
        params.append(status)
    sql = "SELECT * FROM orders"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC"
    order_list = query(sql, params)
    return render_template("admin/orders.html", orders=order_list, search=search, status=status)


@app.route("/admin/orders/<int:order_id>")
@admin_required
def admin_order_details(order_id):
    ph = "?"
    order = query("SELECT * FROM orders WHERE id=%s" % ph, (order_id,), one=True)
    if not order:
        abort(404)
    items = query("SELECT * FROM order_items WHERE order_id=%s" % ph, (order_id,))
    return render_template("admin/order-details.html", order=order, items=items)


@app.route("/admin/orders/<int:order_id>/status", methods=["POST"])
@admin_required
def admin_update_order_status(order_id):
    ph = "?"
    status = request.form.get("status", "").strip()
    valid = ["Pending", "Confirmed", "Processing", "Shipped", "Delivered", "Cancelled"]
    if status in valid:
        execute("UPDATE orders SET status=? WHERE id=?",
                (status, order_id))
        flash(f"Order status updated to {status}.", "success")
    return redirect(url_for("admin_order_details", order_id=order_id))


# ---------------------------------------------------------------------------
# Admin - Reports
# ---------------------------------------------------------------------------
@app.route("/admin/reports")
@admin_required
def admin_reports():
    ph = "?"
    total_sales = query("SELECT COALESCE(SUM(total),0) AS s FROM orders WHERE status != 'Cancelled'", one=True)["s"]
    total_orders = query("SELECT COUNT(*) AS c FROM orders", one=True)["c"]
    pending = query("SELECT COUNT(*) AS c FROM orders WHERE status='Pending'", one=True)["c"]
    delivered = query("SELECT COUNT(*) AS c FROM orders WHERE status='Delivered'", one=True)["c"]
    cancelled = query("SELECT COUNT(*) AS c FROM orders WHERE status='Cancelled'", one=True)["c"]

    monthly = query(
        f"""
        SELECT strftime('%Y-%m', created_at) AS month, COUNT(*) AS orders, SUM(total) AS sales
        FROM orders WHERE status != 'Cancelled'
        GROUP BY month ORDER BY month DESC LIMIT 12
        """
    )
    daily = query(
        f"""
        SELECT date(created_at) AS day, COUNT(*) AS orders, SUM(total) AS sales
        FROM orders WHERE status != 'Cancelled'
        GROUP BY day ORDER BY day DESC LIMIT 14
        """
    )
    best_sellers = query(
        f"""
        SELECT oi.product_name, SUM(oi.quantity) AS qty, SUM(oi.subtotal) AS revenue
        FROM order_items oi
        GROUP BY oi.product_name
        ORDER BY qty DESC LIMIT 10
        """
    )
    low_stock = query("SELECT * FROM products WHERE stock <= 5 ORDER BY stock ASC LIMIT 10")
    status_counts = query(
        f"""
        SELECT status, COUNT(*) AS c FROM orders GROUP BY status ORDER BY c DESC
        """
    )
    return render_template(
        "admin/reports.html",
        total_sales=total_sales,
        total_orders=total_orders,
        pending=pending,
        delivered=delivered,
        cancelled=cancelled,
        monthly=monthly,
        daily=daily,
        best_sellers=best_sellers,
        low_stock=low_stock,
        status_counts=status_counts,
    )


# ---------------------------------------------------------------------------
# Admin - Site Settings (logo + slideshow video)
# ---------------------------------------------------------------------------
ALLOWED_VIDEO_EXTENSIONS = {"mp4", "webm", "ogg", "mov"}


def allowed_video(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_VIDEO_EXTENSIONS


@app.route("/admin/settings", methods=["GET", "POST"])
@admin_required
def admin_settings():
    ph = "?"
    settings = query("SELECT * FROM settings ORDER BY id LIMIT 1", one=True)
    if request.method == "POST":
        logo = settings["logo"] if settings else None
        video = settings["slideshow_video"] if settings else None
        poster = settings["slideshow_poster"] if settings else None

        # Logo upload
        logo_file = request.files.get("logo")
        if logo_file and logo_file.filename:
            if allowed_file(logo_file.filename):
                fname = secure_filename(logo_file.filename)
                logo_file.save(os.path.join(app.config["UPLOAD_FOLDER"], fname))
                logo = fname
            else:
                flash("Invalid logo format. Use JPG, JPEG, PNG or WEBP.", "danger")

        # Slideshow video upload
        video_file = request.files.get("slideshow_video")
        if video_file and video_file.filename:
            if allowed_video(video_file.filename):
                fname = secure_filename(video_file.filename)
                video_file.save(os.path.join(app.config["UPLOAD_FOLDER"], fname))
                video = fname
            else:
                flash("Invalid video format. Use MP4, WEBM, OGG or MOV.", "danger")

        # Slideshow poster image (optional)
        poster_file = request.files.get("slideshow_poster")
        if poster_file and poster_file.filename:
            if allowed_file(poster_file.filename):
                fname = secure_filename(poster_file.filename)
                poster_file.save(os.path.join(app.config["UPLOAD_FOLDER"], fname))
                poster = fname

        # Text / content fields
        def g(field, default=""):
            val = request.form.get(field, "").strip()
            return val or default

        site_name = g("site_name", "Mini Daraz")
        phone = g("phone", "0300-1234567")
        email = g("email", "support@minidaraz.com")
        address = g("address", "Karachi, Pakistan")
        facebook = request.form.get("facebook", "").strip()
        instagram = request.form.get("instagram", "").strip()
        twitter = request.form.get("twitter", "").strip()
        youtube = request.form.get("youtube", "").strip()
        hero_title = g("hero_title", "Mega Sale is Live!")
        hero_subtitle = g("hero_subtitle", "Up to 70% off on mobiles, electronics, fashion & home.")
        hero_cta = g("hero_cta", "Shop Now")
        about_title = g("about_title", "About Mini Daraz")
        about_text = request.form.get("about_text", "").strip()
        primary_color = request.form.get("primary_color", "").strip() or "#f57224"

        def checkbox(field):
            return 1 if request.form.get(field) else 0

        show_flash_sale = checkbox("show_flash_sale")
        show_categories = checkbox("show_categories")
        show_popular = checkbox("show_popular")
        show_new_arrivals = checkbox("show_new_arrivals")
        show_best_sellers = checkbox("show_best_sellers")
        show_trending = checkbox("show_trending")

        if settings:
            execute(
                """UPDATE settings SET
                    logo=%s, slideshow_video=%s, slideshow_poster=%s,
                    site_name=%s, phone=%s, email=%s, address=%s,
                    facebook=%s, instagram=%s, twitter=%s, youtube=%s,
                    hero_title=%s, hero_subtitle=%s, hero_cta=%s,
                    about_title=%s, about_text=%s, primary_color=%s,
                    show_flash_sale=%s, show_categories=%s, show_popular=%s,
                    show_new_arrivals=%s, show_best_sellers=%s, show_trending=%s
                WHERE id=%s""",
                (logo, video, poster, site_name, phone, email, address,
                 facebook, instagram, twitter, youtube, hero_title, hero_subtitle,
                 hero_cta, about_title, about_text, primary_color, show_flash_sale,
                 show_categories, show_popular, show_new_arrivals, show_best_sellers,
                 show_trending, settings["id"]),
            )
        else:
            execute(
                """INSERT INTO settings (
                    logo, slideshow_video, slideshow_poster, site_name, phone, email, address,
                    facebook, instagram, twitter, youtube, hero_title, hero_subtitle, hero_cta,
                    about_title, about_text, primary_color, show_flash_sale, show_categories,
                    show_popular, show_new_arrivals, show_best_sellers, show_trending
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                .replace("%s", "%s"),
                (logo, video, poster, site_name, phone, email, address,
                 facebook, instagram, twitter, youtube, hero_title, hero_subtitle,
                 hero_cta, about_title, about_text, primary_color, show_flash_sale,
                 show_categories, show_popular, show_new_arrivals, show_best_sellers,
                 show_trending),
            )
        flash("Site settings saved successfully!", "success")
        return redirect(url_for("admin_settings"))

    return render_template("admin/settings.html", settings=settings)


@app.route("/admin/messages", methods=["GET", "POST"])
@app.route("/admin/messages/<int:msg_id>", methods=["GET", "POST"])
@admin_required
def admin_messages(msg_id=None):
    """Admin inbox: view customer messages and reply to them."""
    ph = "?"

    if request.method == "POST" and msg_id is not None:
        reply = request.form.get("reply", "").strip()
        if reply:
            execute(
                "UPDATE contact_messages SET reply=?, replied_at=CURRENT_TIMESTAMP WHERE id=?",
                (reply, msg_id),
            )
            flash("Reply sent to customer.", "success")
        return redirect(url_for("admin_messages", msg_id=msg_id))

    # Group messages by user (or by email for guests) to form conversations
    conversations = query(
        f"""
        SELECT
            COALESCE(user_id, 0) AS conv_key,
            MIN(id) AS first_id,
            full_name, email,
            COUNT(*) AS msg_count,
            MAX(created_at) AS last_at
        FROM contact_messages
        GROUP BY COALESCE(user_id, 0), email
        ORDER BY last_at DESC
        """
    )

    selected = None
    selected_id = msg_id
    if msg_id is not None:
        # Load the full conversation thread for this customer
        row = query("SELECT * FROM contact_messages WHERE id=%s" % ph, (msg_id,), one=True)
        if row:
            selected = query(
                "SELECT * FROM contact_messages WHERE COALESCE(user_id,0)=%s AND email=%s ORDER BY created_at ASC" % (ph, ph),
                (row.get("user_id") or 0, row["email"]),
            )
    else:
        # Default to the most recent conversation's thread
        if conversations:
            first = conversations[0]
            selected = query(
                "SELECT * FROM contact_messages WHERE COALESCE(user_id,0)=%s AND email=%s ORDER BY created_at ASC" % (ph, ph),
                (first["conv_key"], first["email"]),
            )
            selected_id = first["first_id"]

    return render_template(
        "admin/messages.html",
        conversations=conversations,
        selected=selected,
        selected_id=selected_id,
    )


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404

@app.errorhandler(500)
def server_error(e):
    logging.error("500 error: %s", traceback.format_exc())
    return render_template("500.html"), 500


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    init_db()
    print("=" * 60)
    print("  MINI DARAZ - E-Commerce Platform")
    print("  Database : SQLite")
    print("  URL      : http://127.0.0.1:5000")
    print("  Admin    : http://127.0.0.1:5000/admin/login")
    print("=" * 60)
    app.run(debug=True, host="127.0.0.1", port=5000)

# =========================
# PRODUCT IMAGE UPLOAD
# =========================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_FOLDER = os.path.join(
    BASE_DIR,
    "static",
    "images",
    "products"
)

# Create the folder automatically if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp",
    "svg"
}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB


# Check allowed image extensions
def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


# =========================
# PRODUCT IMAGE UPLOAD ROUTE
# =========================

@app.route("/upload-product-image", methods=["POST"])
def upload_product_image():

    if "image" not in request.files:
        flash("No image selected.")
        return redirect(request.referrer or url_for("index"))

    file = request.files["image"]

    if file.filename == "":
        flash("Please select an image.")
        return redirect(request.referrer or url_for("index"))

    if file and allowed_file(file.filename):

        filename = secure_filename(file.filename)

        file_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename
        )

        file.save(file_path)

        flash("Product image uploaded successfully!")

        return redirect(request.referrer or url_for("index"))

    flash(
        "Invalid image format. "
        "Allowed formats: PNG, JPG, JPEG, GIF, WEBP, SVG."
    )

    return redirect(request.referrer or url_for("index"))


# =========================
# DELIVERY SETTINGS
# =========================

DELIVERY_CHARGE = 99.0
FREE_DELIVERY_ABOVE = 1000.0

# Ensure database tables exist on import (WSGI servers like PythonAnywhere
# never run the __main__ block, so init_db must be called at module load).
init_db()

# ---------------------------------------------------------------------------
# Ensure a working admin account exists on every startup.
# Fixes "Invalid admin credentials" on fresh/deployed databases without
# needing to run seed.py manually.
# ---------------------------------------------------------------------------
def _ensure_admin():
    from werkzeug.security import generate_password_hash
    admin = query("SELECT id FROM admins WHERE email = ?", ("admin@minidaraz.com",), one=True)
    if not admin:
        execute(
            "INSERT INTO admins (full_name, email, password) VALUES (?, ?, ?)",
            ("Store Admin", "admin@minidaraz.com", generate_password_hash("admin123")),
        )
    else:
        execute(
            "UPDATE admins SET password = ? WHERE email = ?",
            (generate_password_hash("admin123"), "admin@minidaraz.com"),
        )

_ensure_admin()


# =========================
# RUN (local development)
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
