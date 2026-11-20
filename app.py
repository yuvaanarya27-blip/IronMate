"""
app.py - IronMate Fitness E-Commerce & AI Shopping Assistant Backend
Production-ready Flask REST API strictly following a zero-cost architecture.

Key Architecture Highlights for College Viva:
1. Zero-Cost Infrastructure: SQLite database (ironmate.db), NumPy in-memory vector cosine similarity,
   and Google Gemini API (gemini-2.5-flash & text-embedding-004) under the free tier.
2. Modular Design: Separated into models (SQLAlchemy ORM), seed data generator, and ai_service (RAG + Guided Finder).
3. Secure Authentication: JWT (Flask-JWT-Extended) with Werkzeug password hashing.
4. ACID-compliant Checkout: Atomic transaction stock validation, order creation, and cart clearing.
5. Auto-seeding: Automatically initializes tables and seeds 30 fitness products on startup if empty.
"""

import os
import logging
from datetime import timedelta
from dotenv import load_dotenv

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required,
    get_jwt_identity
)

# Load environment variables from .env
load_dotenv()

# Import models and database
from models import db, User, Product, CartItem, Order, OrderItem, ChatMessage, KnowledgeChunk
from seed import seed_database
import ai_service

# -------------------------------------------------------------------------
# FLASK APPLICATION CONFIGURATION
# -------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ironmate_app")

basedir = os.path.abspath(os.path.dirname(__file__))
frontend_dir = os.path.join(basedir, 'frontend')

app = Flask(__name__, static_folder=frontend_dir, static_url_path='')

@app.route('/')
def serve_index():
    """Serves the IronMate frontend storefront."""
    return send_from_directory(frontend_dir, 'index.html')

@app.errorhandler(404)
def handle_not_found(e):
    """
    Handle 404s cleanly:
    - /api/* returns JSON 404 error
    - Static file if exists in frontend_dir
    - Otherwise fallback to frontend/index.html (SPA client-side routing)
    """
    if request.path.startswith('/api/'):
        return jsonify({"error": "Not Found", "message": f"API endpoint {request.path} does not exist."}), 404
    rel_path = request.path.lstrip('/')
    target_path = os.path.join(frontend_dir, rel_path)
    if os.path.isfile(target_path):
        return send_from_directory(frontend_dir, rel_path)
    return send_from_directory(frontend_dir, 'index.html'), 200

# Security & Database Settings
app.config['SECRET_KEY'] = os.getenv("JWT_SECRET_KEY", "ironmate-dev-jwt-secret-key-32b-secure")
app.config['JWT_SECRET_KEY'] = os.getenv("JWT_SECRET_KEY", "ironmate-dev-jwt-secret-key-32b-secure")
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=7)
db_file = os.path.join(basedir, "ironmate.db")
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", f"sqlite:///{db_file}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Cross-Origin Resource Sharing (CORS) for modern frontend development (React, Next.js, Vue, mobile)
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

# Initialize Database and JWT Manager
db.init_app(app)
jwt = JWTManager(app)


# -------------------------------------------------------------------------
# JWT ERROR HANDLERS (CLEAN JSON ERROR RESPONSES)
# -------------------------------------------------------------------------
@jwt.unauthorized_loader
def unauthorized_callback(callback):
    return jsonify({"error": "Unauthorized", "message": "Missing Bearer Authorization Token in request header."}), 401

@jwt.invalid_token_loader
def invalid_token_callback(callback):
    return jsonify({"error": "Unauthorized", "message": "Provided JWT token is invalid or corrupted."}), 401

@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    return jsonify({"error": "Unauthorized", "message": "Token has expired. Please log in again."}), 401


# -------------------------------------------------------------------------
# SYSTEM & HEALTH CHECK ROUTE
# -------------------------------------------------------------------------
@app.route('/api/health', methods=['GET'])
def health_check():
    """System health inspection route reporting database connection & product count."""
    try:
        product_count = Product.query.count()
        chunk_count = KnowledgeChunk.query.count()
        gemini_ready = ai_service.get_genai_client() is not None
        return jsonify({
            "status": "healthy",
            "service": "IronMate Backend API",
            "gemini_api_configured": gemini_ready,
            "database": {
                "type": "SQLite (ironmate.db)",
                "products_count": product_count,
                "knowledge_chunks_count": chunk_count
            }
        }), 200
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({"status": "degraded", "error": str(e)}), 500


# -------------------------------------------------------------------------
# AUTHENTICATION ENDPOINTS (SIGNUP, LOGIN, ME)
# -------------------------------------------------------------------------
@app.route('/api/auth/signup', methods=['POST'])
def signup():
    """
    Registers a new customer account.
    Expects JSON: { name, email, password }
    """
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '').strip()

    if not name or not email or not password:
        return jsonify({"error": "Validation Error", "message": "Name, email, and password are required."}), 400

    if len(password) < 6:
        return jsonify({"error": "Validation Error", "message": "Password must be at least 6 characters long."}), 400

    # Check if user already exists
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Conflict", "message": "An account with this email already exists."}), 409

    try:
        user = User(name=name, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        # Generate JWT access token with user.id as identity
        access_token = create_access_token(identity=str(user.id))
        return jsonify({
            "message": "User registered successfully",
            "token": access_token,
            "user": user.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Signup error: {e}")
        return jsonify({"error": "Internal Server Error", "message": "Failed to create user account."}), 500


@app.route('/api/auth/login', methods=['POST'])
def login():
    """
    Authenticates user and returns JWT access token.
    Expects JSON: { email, password }
    """
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '').strip()

    if not email or not password:
        return jsonify({"error": "Validation Error", "message": "Email and password are required."}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Unauthorized", "message": "Invalid email or password."}), 401

    access_token = create_access_token(identity=str(user.id))
    return jsonify({
        "message": "Login successful",
        "token": access_token,
        "user": user.to_dict()
    }), 200


@app.route('/api/auth/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """Fetches profile details of the currently authenticated customer."""
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "Not Found", "message": "User account not found."}), 404

    return jsonify({"user": user.to_dict()}), 200


# -------------------------------------------------------------------------
# PRODUCT CATALOG ENDPOINTS
# -------------------------------------------------------------------------
@app.route('/api/products', methods=['GET'])
def list_products():
    """
    Retrieves filtered product catalog.
    Query Params:
      - category: filter by product category
      - search: keyword search in product name and description
      - goal: filter by goal_tags (e.g., strength, cardio, muscle_gain)
      - experience: "beginner" | "intermediate" | "advanced"
      - space: "none" | "small" | "medium" | "large"
      - sort: "price_asc" | "price_desc" | "name"
    """
    query = Product.query

    category = request.args.get('category')
    search = request.args.get('search')
    goal = request.args.get('goal')
    experience = request.args.get('experience')
    space = request.args.get('space')
    sort = request.args.get('sort')

    if category:
        cats = [c.strip() for c in category.split(",") if c.strip()]
        if len(cats) == 1:
            query = query.filter(Product.category.ilike(f"%{cats[0]}%"))
        elif len(cats) > 1:
            query = query.filter(db.or_(*[Product.category.ilike(f"%{c}%") for c in cats]))

    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter(
            db.or_(
                Product.name.ilike(search_term),
                Product.description.ilike(search_term),
                Product.category.ilike(search_term)
            )
        )

    if experience:
        query = query.filter(Product.experience_level.ilike(experience.strip()))

    if space:
        query = query.filter(Product.space_needed.ilike(space.strip()))

    products = query.all()

    # In-memory filtering for goal_tags (handles JSON arrays cleanly across SQLite)
    if goal:
        target_goal = goal.strip().lower()
        filtered = []
        for p in products:
            tags = p.goal_tags if isinstance(p.goal_tags, list) else []
            if any(target_goal in str(t).lower() for t in tags):
                filtered.append(p)
        products = filtered

    # Sorting
    if sort == "price_asc":
        products.sort(key=lambda p: p.price)
    elif sort == "price_desc":
        products.sort(key=lambda p: p.price, reverse=True)
    elif sort == "name":
        products.sort(key=lambda p: p.name.lower())

    return jsonify({
        "total": len(products),
        "products": [p.to_dict() for p in products]
    }), 200


@app.route('/api/products/<int:product_id>', methods=['GET'])
def get_product(product_id: int):
    """Retrieves full specification of a single product by ID."""
    product = db.session.get(Product, product_id)
    if not product:
        return jsonify({"error": "Not Found", "message": f"Product with ID {product_id} not found."}), 404

    return jsonify({"product": product.to_dict()}), 200


# -------------------------------------------------------------------------
# SHOPPING CART ENDPOINTS (JWT PROTECTED)
# -------------------------------------------------------------------------
@app.route('/api/cart', methods=['GET'])
@jwt_required()
def get_cart():
    """Retrieves all items in the authenticated user's cart with calculated totals."""
    user_id = int(get_jwt_identity())
    cart_items = CartItem.query.filter_by(user_id=user_id).all()

    items_data = [item.to_dict() for item in cart_items]
    total_amount = sum(item["line_total"] for item in items_data)
    total_count = sum(item["quantity"] for item in items_data)

    return jsonify({
        "items": items_data,
        "total": round(total_amount, 2),
        "item_count": total_count
    }), 200


@app.route('/api/cart/add', methods=['POST'])
@jwt_required()
def add_to_cart():
    """
    Adds an item to customer's cart or increments quantity if already present.
    Expects JSON: { product_id, quantity }
    """
    user_id = int(get_jwt_identity())
    data = request.get_json() or {}

    product_id = data.get('product_id')
    try:
        quantity = int(data.get('quantity', 1))
    except (ValueError, TypeError):
        quantity = 1

    if not product_id or quantity <= 0:
        return jsonify({"error": "Validation Error", "message": "Valid product_id and positive quantity are required."}), 400

    product = db.session.get(Product, product_id)
    if not product:
        return jsonify({"error": "Not Found", "message": f"Product {product_id} does not exist."}), 404

    # Check stock availability
    if product.stock < quantity:
        return jsonify({
            "error": "Insufficient Stock",
            "message": f"Only {product.stock} units available for '{product.name}'."
        }), 400

    cart_item = CartItem.query.filter_by(user_id=user_id, product_id=product_id).first()
    if cart_item:
        if cart_item.quantity + quantity > product.stock:
            return jsonify({
                "error": "Insufficient Stock",
                "message": f"Cannot add {quantity} more. Current in cart: {cart_item.quantity}, Available stock: {product.stock}."
            }), 400
        cart_item.quantity += quantity
    else:
        cart_item = CartItem(user_id=user_id, product_id=product_id, quantity=quantity)
        db.session.add(cart_item)

    db.session.commit()

    return jsonify({
        "message": f"Added '{product.name}' to cart.",
        "cart_item": cart_item.to_dict()
    }), 200


@app.route('/api/cart/update', methods=['PUT'])
@jwt_required()
def update_cart_item():
    """
    Updates the quantity of a specific item in the cart.
    If quantity <= 0, the item is removed.
    Expects JSON: { product_id, quantity }
    """
    user_id = int(get_jwt_identity())
    data = request.get_json() or {}

    product_id = data.get('product_id')
    if product_id is None:
        return jsonify({"error": "Validation Error", "message": "product_id is required."}), 400

    try:
        quantity = int(data.get('quantity', 1))
    except (ValueError, TypeError):
        return jsonify({"error": "Validation Error", "message": "quantity must be an integer."}), 400

    cart_item = CartItem.query.filter_by(user_id=user_id, product_id=product_id).first()
    if not cart_item:
        return jsonify({"error": "Not Found", "message": "Item is not in your cart."}), 404

    if quantity <= 0:
        db.session.delete(cart_item)
        db.session.commit()
        return jsonify({"message": "Item removed from cart.", "cart_item": None}), 200

    # Stock validation
    product = db.session.get(Product, product_id)
    if product and quantity > product.stock:
        return jsonify({
            "error": "Insufficient Stock",
            "message": f"Only {product.stock} units available for '{product.name}'."
        }), 400

    cart_item.quantity = quantity
    db.session.commit()

    return jsonify({
        "message": "Cart quantity updated successfully.",
        "cart_item": cart_item.to_dict()
    }), 200


@app.route('/api/cart/remove/<int:product_id>', methods=['DELETE'])
@jwt_required()
def remove_from_cart(product_id: int):
    """Removes a specific product from the authenticated user's cart."""
    user_id = int(get_jwt_identity())
    cart_item = CartItem.query.filter_by(user_id=user_id, product_id=product_id).first()

    if not cart_item:
        return jsonify({"error": "Not Found", "message": "Product not found in cart."}), 404

    db.session.delete(cart_item)
    db.session.commit()

    return jsonify({"message": "Product removed from cart successfully."}), 200


# -------------------------------------------------------------------------
# ORDER CHECKOUT & HISTORY ENDPOINTS
# -------------------------------------------------------------------------
@app.route('/api/orders/checkout', methods=['POST'])
@jwt_required()
def checkout():
    """
    ACID-compliant checkout transaction:
    1. Validates cart is not empty.
    2. Validates live inventory stock for each item.
    3. Creates Order and OrderItem records.
    4. Decrements Product stock in atomic session.
    5. Clears user cart items.
    """
    user_id = int(get_jwt_identity())
    cart_items = CartItem.query.filter_by(user_id=user_id).all()

    if not cart_items:
        return jsonify({"error": "Empty Cart", "message": "Cannot checkout with an empty cart."}), 400

    try:
        total_order_amount = 0.0

        # Step 1: Pre-validate stock for all items
        for item in cart_items:
            product = item.product
            if not product:
                return jsonify({"error": "Product Error", "message": f"Product ID {item.product_id} no longer exists."}), 400
            if product.stock < item.quantity:
                return jsonify({
                    "error": "Stock Exhausted",
                    "message": f"Insufficient stock for '{product.name}'. Available: {product.stock}, requested: {item.quantity}."
                }), 400
            total_order_amount += (product.price * item.quantity)

        # Step 2: Create Order entity
        order = Order(
            user_id=user_id,
            total=round(total_order_amount, 2),
            status="Confirmed"
        )
        db.session.add(order)
        db.session.flush()  # Populates order.id

        # Step 3: Create OrderItems, decrement stock, and delete cart items
        for item in cart_items:
            product = item.product
            order_item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=item.quantity,
                price_at_purchase=product.price
            )
            db.session.add(order_item)

            # Atomic inventory decrement
            product.stock -= item.quantity

            # Clear cart item
            db.session.delete(item)

        db.session.commit()

        logger.info(f"Order #{order.id} placed successfully by User #{user_id}. Total: ${order.total:.2f}")

        return jsonify({
            "message": "Order placed successfully!",
            "order": order.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        logger.error(f"Checkout transaction failed: {e}")
        return jsonify({"error": "Checkout Failed", "message": "An error occurred while processing checkout."}), 500


@app.route('/api/orders', methods=['GET'])
@jwt_required()
def get_orders():
    """Retrieves order history for the authenticated customer."""
    user_id = int(get_jwt_identity())
    orders = Order.query.filter_by(user_id=user_id).order_by(Order.created_at.desc()).all()

    return jsonify({
        "total": len(orders),
        "orders": [order.to_dict() for order in orders]
    }), 200


# -------------------------------------------------------------------------
# AI ENDPOINT 1: GENERAL RAG CHAT (/api/chat)
# -------------------------------------------------------------------------
@app.route('/api/chat', methods=['POST'])
@jwt_required(optional=True)
def general_rag_chat():
    """
    RAG AI Chatbot Endpoint:
    1. Embeds user query using Gemini embedding API (`text-embedding-004`).
    2. Runs in-memory NumPy cosine similarity across SQLite `KnowledgeChunk` records.
    3. Retrieves top 4 most relevant chunks.
    4. Passes retrieved context into Gemini LLM (`gemini-2.5-flash`) with strict IronMate system prompt.
    5. Saves conversation history to ChatMessage table if user is logged in.
    """
    data = request.get_json() or {}
    user_message = data.get('message', '').strip()
    history = data.get('history', [])

    if not user_message:
        return jsonify({"error": "Validation Error", "message": "Message field cannot be empty."}), 400

    # Optional authenticated user
    current_user_id = None
    try:
        identity = get_jwt_identity()
        if identity:
            current_user_id = int(identity)
    except Exception:
        pass

    try:
        # Step 1: Generate query embedding
        query_vector = ai_service.generate_embedding(user_message)

        # Step 2: Fetch all knowledge chunks
        all_chunks = KnowledgeChunk.query.all()
        if not all_chunks:
            return jsonify({
                "reply": "Our store knowledge base is initializing. Please try again in a few moments.",
                "sources": []
            }), 200

        # Step 3: Compute in-memory cosine similarity and get top 4 chunks
        top_chunks = ai_service.find_top_k_chunks(query_vector, all_chunks, k=4)

        # Step 4: Generate LLM response grounded by retrieved context
        bot_reply = ai_service.generate_rag_response(user_message, top_chunks, history)

        # Step 5: Save chat message in database
        try:
            user_chat = ChatMessage(user_id=current_user_id, role="user", content=user_message)
            bot_chat = ChatMessage(user_id=current_user_id, role="bot", content=bot_reply)
            db.session.add_all([user_chat, bot_chat])
            db.session.commit()
        except Exception as log_err:
            db.session.rollback()
            logger.warning(f"Could not persist chat message: {log_err}")

        # Format sources for response
        sources_info = []
        for chunk, score in top_chunks:
            sources_info.append({
                "id": chunk.id,
                "category": chunk.category,
                "product_id": chunk.product_id,
                "similarity": round(float(score), 3),
                "snippet": chunk.text[:120] + "..." if len(chunk.text) > 120 else chunk.text
            })

        return jsonify({
            "reply": bot_reply,
            "sources": sources_info
        }), 200

    except Exception as e:
        logger.error(f"RAG chat endpoint error: {e}")
        return jsonify({
            "error": "AI Processing Error",
            "message": "Failed to generate AI response. Please try again."
        }), 500


# -------------------------------------------------------------------------
# AI ENDPOINT 2: GUIDED PRODUCT FINDER (/api/plan-finder)
# -------------------------------------------------------------------------
@app.route('/api/plan-finder', methods=['POST'])
def guided_plan_finder():
    """
    Multi-Turn Guided Product Finder Flow:
    Asks 4 concise questions one-by-one:
      1. Primary fitness goal (muscle_gain, fat_loss, endurance, home_gym, general_fitness)
      2. Available workout space (none, small, medium, large)
      3. Fitness experience level (beginner, intermediate, advanced)
      4. Target budget ($50, $150, $400, $1000)
    Filters SQLite `Product` rows using SQLAlchemy attributes and returns 1-3 recommended
    products with product IDs, photos, prices, and reasoning for "Add to Cart" cards.
    """
    data = request.get_json() or {}
    try:
        step = int(data.get('step', 0))
    except (ValueError, TypeError):
        step = 0

    answers = data.get('answers', {})

    # Fetch all catalog products for evaluation at step 4
    all_products = Product.query.all()

    result = ai_service.process_plan_finder_step(step, answers, all_products)
    return jsonify(result), 200


# -------------------------------------------------------------------------
# AI ENDPOINT 3: CART-AWARE CHAT (/api/chat/cart-aware)
# -------------------------------------------------------------------------
@app.route('/api/chat/cart-aware', methods=['POST'])
@jwt_required()
def cart_aware_chat():
    """
    Cart-Aware Shopping Assistant:
    1. Fetches authenticated customer's current `CartItem` rows joined with `Product`.
    2. Injects exact cart items, prices, and quantities into Gemini prompt.
    3. Answers customer queries regarding their current cart.
    4. Evaluates catalog and suggests 1-2 complementary products with product IDs and reasoning.
    """
    user_id = int(get_jwt_identity())
    data = request.get_json() or {}
    user_message = data.get('message', '').strip()

    if not user_message:
        user_message = "Review my current cart and recommend what else I need for my workouts."

    # Fetch user's cart items
    cart_items = CartItem.query.filter_by(user_id=user_id).all()
    serialized_cart = [item.to_dict() for item in cart_items]

    # Fetch all catalog products for complementary item selection
    catalog = [p.to_dict() for p in Product.query.all()]

    response_data = ai_service.generate_cart_aware_response(
        cart_items=serialized_cart,
        user_message=user_message,
        catalog_products=catalog
    )

    return jsonify(response_data), 200


# -------------------------------------------------------------------------
# AUTOMATIC INITIALIZATION & SEEDING ON STARTUP
# -------------------------------------------------------------------------
def initialize_database():
    """
    Ensures database tables exist and seeds products ONLY if Product.query.count() == 0.
    Handles ephemeral hosting container resets cleanly.
    """
    with app.app_context():
        db.create_all()
        count = Product.query.count()
        if count == 0:
            logger.info("Empty database detected (0 products). Initializing seed data...")
            seed_database()
        else:
            logger.info(f"Database already populated with {count} products. Ready to serve.")


# Run auto-initialization when module loads
try:
    initialize_database()
except Exception as init_err:
    logger.error(f"Database auto-initialization error: {init_err}")


# -------------------------------------------------------------------------
# ENTRYPOINT
# -------------------------------------------------------------------------
if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV") == "development"
    logger.info(f"Starting IronMate Backend Server on http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
