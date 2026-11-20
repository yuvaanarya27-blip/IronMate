"""
models.py - Database Models for IronMate E-Commerce Storefront
Defines SQLAlchemy ORM models for Users, Products, Cart, Orders, Chat, and Knowledge Chunks.
Zero-cost embedded database architecture using SQLite.
"""

from datetime import datetime, timezone
import json
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

def utc_now():
    """Returns current UTC timestamp."""
    return datetime.now(timezone.utc)


class User(db.Model):
    """User account model for customer authentication and profile management."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    # Relationships
    cart_items = db.relationship('CartItem', backref='user', lazy=True, cascade='all, delete-orphan')
    orders = db.relationship('Order', backref='user', lazy=True, cascade='all, delete-orphan')
    chat_messages = db.relationship('ChatMessage', backref='user', lazy=True)

    def set_password(self, password: str) -> None:
        """Hash and store secure password using Werkzeug scrypt/pbkdf2."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify password hash validity."""
        return check_password_hash(self.password_hash, password)

    def to_dict(self) -> dict:
        """Serialize user object without sensitive password hash."""
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'created_at': self.created_at.isoformat()
        }


class Product(db.Model):
    """
    Product model representing fitness & gym equipment, apparel, accessories, and nutrition.
    Includes categorical and physical attributes for the AI Plan Finder filtering engine.
    """
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    category = db.Column(db.String(100), nullable=False, index=True)
    price = db.Column(db.Float, nullable=False)
    mrp = db.Column(db.Float, nullable=True)
    description = db.Column(db.Text, nullable=False)
    stock = db.Column(db.Integer, default=10, nullable=False)
    goal_tags = db.Column(db.JSON, nullable=False)  # Stored as JSON array (e.g. ["muscle_gain", "strength"])
    experience_level = db.Column(db.String(50), nullable=False)  # "beginner" | "intermediate" | "advanced"
    space_needed = db.Column(db.String(50), nullable=False)      # "none" | "small" | "medium" | "large"
    image_url = db.Column(db.String(500), nullable=False)

    # Relationships
    knowledge_chunks = db.relationship('KnowledgeChunk', backref='product', lazy=True, cascade='all, delete-orphan')

    def to_dict(self) -> dict:
        """Serialize product data for REST responses."""
        tags = self.goal_tags
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except Exception:
                tags = [tags]

        return {
            'id': self.id,
            'name': self.name,
            'category': self.category,
            'price': round(float(self.price), 2),
            'mrp': round(float(self.mrp), 2) if self.mrp else round(float(self.price * 1.5), 2),
            'description': self.description,
            'stock': int(self.stock),
            'goal_tags': tags if isinstance(tags, list) else [],
            'experience_level': self.experience_level,
            'space_needed': self.space_needed,
            'image_url': self.image_url
        }


class CartItem(db.Model):
    """Shopping cart item linking a User to a Product with desired quantity."""
    __tablename__ = 'cart_items'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    product = db.relationship('Product', lazy='joined')

    def to_dict(self) -> dict:
        """Serialize cart item with associated product metadata and calculated line total."""
        unit_price = self.product.price if self.product else 0.0
        line_total = round(unit_price * self.quantity, 2)
        return {
            'id': self.id,
            'user_id': self.user_id,
            'product_id': self.product_id,
            'quantity': self.quantity,
            'updated_at': self.updated_at.isoformat(),
            'product': self.product.to_dict() if self.product else None,
            'line_total': line_total
        }


class Order(db.Model):
    """Customer purchase order recording total cost, fulfillment status, and items."""
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    total = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default="Confirmed", nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    # Relationships
    items = db.relationship('OrderItem', backref='order', lazy='joined', cascade='all, delete-orphan')

    def to_dict(self) -> dict:
        """Serialize complete order summary with line items."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'total': round(float(self.total), 2),
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'items': [item.to_dict() for item in self.items]
        }


class OrderItem(db.Model):
    """Line item snapshot representing a purchased product at checkout price."""
    __tablename__ = 'order_items'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price_at_purchase = db.Column(db.Float, nullable=False)

    # Relationships
    product = db.relationship('Product', lazy='joined')

    def to_dict(self) -> dict:
        """Serialize order item with frozen purchase price."""
        return {
            'id': self.id,
            'order_id': self.order_id,
            'product_id': self.product_id,
            'product_name': self.product.name if self.product else 'Unknown Product',
            'product_category': self.product.category if self.product else '',
            'image_url': self.product.image_url if self.product else '',
            'quantity': self.quantity,
            'price_at_purchase': round(float(self.price_at_purchase), 2),
            'line_total': round(float(self.price_at_purchase * self.quantity), 2)
        }


class ChatMessage(db.Model):
    """Conversational log for AI shopping assistant interactions."""
    __tablename__ = 'chat_messages'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    role = db.Column(db.String(20), nullable=False)  # "user" | "bot"
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=utc_now, nullable=False)

    def to_dict(self) -> dict:
        """Serialize chat message record."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'role': self.role,
            'content': self.content,
            'timestamp': self.timestamp.isoformat()
        }


class KnowledgeChunk(db.Model):
    """
    RAG vector knowledge base entry.
    Stores vectorized chunks of product catalogs and store policies (shipping, returns, warranty)
    as JSON float vectors for zero-cost in-memory cosine similarity search.
    """
    __tablename__ = 'knowledge_chunks'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=True, index=True)
    category = db.Column(db.String(100), nullable=False)  # e.g., "Product", "Shipping Policy", "Return Policy"
    text = db.Column(db.Text, nullable=False)
    embedding = db.Column(db.JSON, nullable=False)  # JSON list of floats (vector representation)

    def to_dict(self, include_embedding: bool = False) -> dict:
        """Serialize chunk metadata for response and RAG debugging."""
        emb = self.embedding
        if isinstance(emb, str):
            try:
                emb = json.loads(emb)
            except Exception:
                emb = []

        data = {
            'id': self.id,
            'product_id': self.product_id,
            'category': self.category,
            'text': self.text,
        }
        if include_embedding:
            data['embedding'] = emb
        return data
