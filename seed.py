"""
seed.py - Database Initializer & Knowledge Base Vectorizer for IronMate
Seeds 30 realistic fitness & gym products across 5 categories, creates default demo user,
and generates vector embeddings for products and store FAQs into KnowledgeChunk records.

Zero-cost architecture: Embeddings stored directly in SQLite without vector database subscription fees.
"""

import os
import json
import logging
from typing import List, Dict, Any
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

# Load environment variables from .env
load_dotenv()

from models import db, User, Product, KnowledgeChunk
from ai_service import generate_embedding

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default 30 Fitness Products across 5 categories
DEFAULT_PRODUCTS: List[Dict[str, Any]] = [
    # ---------------- 1. STRENGTH TRAINING ----------------
    {
        "name": "IronMate Pro 50 lb Adjustable Dumbbells (Pair)",
        "category": "Strength Training",
        "price": 299.99,
        "description": "Rapid-dial weight adjustment from 5 to 50 lbs per dumbbell in 5 lb increments. Replaces 10 pairs of individual dumbbells with commercial-grade knurled steel grip and thermoplastic weight plates.",
        "stock": 15,
        "goal_tags": ["strength", "muscle_gain", "home_gym"],
        "experience_level": "beginner",
        "space_needed": "small",
        "image_url": "https://images.unsplash.com/photo-1584735935682-2f2b69dff9d2?auto=format&fit=crop&w=800&q=80"
    },
    {
        "name": "Olympic 7ft Hard Chrome Barbell (20kg / 45 lbs)",
        "category": "Strength Training",
        "price": 189.99,
        "description": "Standard 28mm shaft with 190,000 PSI tensile strength, dual knurl marks for powerlifting and Olympic lifting, brass bushings, and a tested weight capacity of 1,200 lbs.",
        "stock": 12,
        "goal_tags": ["strength", "muscle_gain"],
        "experience_level": "intermediate",
        "space_needed": "medium",
        "image_url": "https://images.unsplash.com/photo-1517838277536-f5f99be501cd?auto=format&fit=crop&w=800&q=80"
    },
    {
        "name": "IronMate Heavy Duty Power Cage & Squat Rack",
        "category": "Strength Training",
        "price": 499.99,
        "description": "Constructed from 2x2 inch 14-gauge heavy-duty steel tube with multi-grip pull-up bar, safety spotter bars, J-hooks, and weight plate storage pegs. 800 lb max capacity.",
        "stock": 8,
        "goal_tags": ["strength", "home_gym", "muscle_gain"],
        "experience_level": "advanced",
        "space_needed": "large",
        "image_url": "https://images.unsplash.com/photo-1540497077202-7c8a3999166f?auto=format&fit=crop&w=800&q=80"
    },
    {
        "name": "Adjustable Multi-Angle Utility Weight Bench",
        "category": "Strength Training",
        "price": 149.99,
        "description": "7 backrest incline/decline positions (-20° to 85°) and 3 ergonomic seat adjustments. High-density 2.5-inch sweatproof leather padding supporting up to 650 lbs.",
        "stock": 20,
        "goal_tags": ["strength", "home_gym", "muscle_gain"],
        "experience_level": "beginner",
        "space_needed": "small",
        "image_url": "https://images.unsplash.com/photo-1581009146145-b5ef050c2e1e?auto=format&fit=crop&w=800&q=80"
    },
    {
        "name": "Cast Iron Powder-Coated Kettlebell 3-Pack (15, 25, 35 lbs)",
        "category": "Strength Training",
        "price": 119.99,
        "description": "Single-piece solid cast iron casting with color-coded handles and flat machined base to prevent wobbling during floor exercises. Rust-resistant matte powder coat finish.",
        "stock": 14,
        "goal_tags": ["strength", "cardio", "endurance"],
        "experience_level": "beginner",
        "space_needed": "small",
        "image_url": "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?auto=format&fit=crop&w=800&q=80"
    },
    {
        "name": "Wall-Mounted Multi-Grip Pull-Up & Dip Station",
        "category": "Strength Training",
        "price": 64.99,
        "description": "Solid steel bar with narrow, wide, and neutral rubber grip positions. Anchors securely into wooden wall studs or concrete with 440 lb weight capacity.",
        "stock": 18,
        "goal_tags": ["strength", "muscle_gain", "home_gym"],
        "experience_level": "intermediate",
        "space_needed": "small",
        "image_url": "https://images.unsplash.com/photo-1598971639058-fab3c3109a00?auto=format&fit=crop&w=800&q=80"
    },

    # ---------------- 2. CARDIO & CONDITIONING ----------------
    {
        "name": "Blitz Pro Air Resistance Fan Bike",
        "category": "Cardio & Conditioning",
        "price": 549.99,
        "description": "Dynamic steel fan blade creates infinite wind resistance proportional to pedaling speed. Heavy-duty chain and belt drive system with interval training LCD monitor.",
        "stock": 6,
        "goal_tags": ["cardio", "endurance", "fat_loss"],
        "experience_level": "intermediate",
        "space_needed": "medium",
        "image_url": "https://images.unsplash.com/photo-1574680096145-d05b474e2155?auto=format&fit=crop&w=800&q=80"
    },
    {
        "name": "Ultra-Quiet Magnetic Rowing Machine",
        "category": "Cardio & Conditioning",
        "price": 389.99,
        "description": "16-level whisper-quiet magnetic flywheel resistance with aluminum slide rail and full folding frame. Digital console tracks 500m split times, watts, strokes, and calories.",
        "stock": 10,
        "goal_tags": ["cardio", "endurance", "fat_loss", "home_gym"],
        "experience_level": "beginner",
        "space_needed": "medium",
        "image_url": "https://images.unsplash.com/photo-1517838277536-f5f99be501cd?auto=format&fit=crop&w=800&q=80"
    },
    {
        "name": "IronMate Horizon Foldable Treadmill with 12% Auto-Incline",
        "category": "Cardio & Conditioning",
        "price": 679.99,
        "description": "3.0 HP continuous brushless DC motor reaching up to 10 MPH. Multi-layer shock absorption running deck (48x18 inches), hydraulic easy-fold mechanism, and Bluetooth speakers.",
        "stock": 5,
        "goal_tags": ["cardio", "fat_loss", "endurance"],
        "experience_level": "beginner",
        "space_needed": "large",
        "image_url": "https://images.unsplash.com/photo-1538805060514-97d9cc17730c?auto=format&fit=crop&w=800&q=80"
    },
    {
        "name": "Pro Speed Bearing Aluminum Jump Rope",
        "category": "Cardio & Conditioning",
        "price": 19.99,
        "description": "360-degree double ball bearing swivel handles with ultra-light aircraft aluminum casing and 10ft adjustable steel coated cable for effortless double-unders.",
        "stock": 40,
        "goal_tags": ["cardio", "fat_loss", "endurance"],
        "experience_level": "beginner",
        "space_needed": "none",
        "image_url": "https://images.unsplash.com/photo-1518611012118-696072aa579a?auto=format&fit=crop&w=800&q=80"
    },
    {
        "name": "Poly Dacron Heavy Battle Rope (1.5 Inch x 30 Ft)",
        "category": "Cardio & Conditioning",
        "price": 69.99,
        "description": "Wear-resistant nylon sleeve wrap with heat-shrink comfort handles and steel anchor kit. Delivers intense metabolic conditioning and upper-body power endurance.",
        "stock": 15,
        "goal_tags": ["endurance", "cardio", "strength"],
        "experience_level": "intermediate",
        "space_needed": "medium",
        "image_url": "https://images.unsplash.com/photo-1517838277536-f5f99be501cd?auto=format&fit=crop&w=800&q=80"
    },
    {
        "name": "Pro Agility Ladder & Cone Footwork Training Kit",
        "category": "Cardio & Conditioning",
        "price": 24.99,
        "description": "20-foot adjustable 12-rung agility ladder with 10 high-visibility cones, 4 steel ground stakes, and durable carry bag for athletic footwork and sprint training.",
        "stock": 30,
        "goal_tags": ["cardio", "endurance", "general_fitness"],
        "experience_level": "beginner",
        "space_needed": "small",
        "image_url": "https://images.unsplash.com/photo-1526506118085-60ce8714f8c5?auto=format&fit=crop&w=800&q=80"
    },

    # ---------------- 3. APPAREL ----------------
    {
        "name": "Men's Kinetic Compression Performance Tee",
        "category": "Apparel",
        "price": 34.99,
        "description": "Four-way stretch poly-elastane fabric with zoned mesh ventilation panels along the spine and underarms. Flatlock anti-chafing seams and moisture-wicking technology.",
        "stock": 25,
        "goal_tags": ["general_fitness", "muscle_gain"],
        "experience_level": "beginner",
        "space_needed": "none",
        "image_url": "https://images.unsplash.com/photo-1521804906057-1df8fdb718b7?auto=format&fit=crop&w=800&q=80"
    },
    {
        "name": "Women's High-Waisted Squat-Proof Sculpt Leggings",
        "category": "Apparel",
        "price": 44.99,
        "description": "Buttery soft non-see-through fabric blend with ribbed compressive high-rise waistband that stays locked during deep squats and lunges. Dual side smartphone pockets.",
        "stock": 25,
        "goal_tags": ["general_fitness", "muscle_gain"],
        "experience_level": "beginner",
        "space_needed": "none",
        "image_url": "https://images.unsplash.com/photo-1506126613408-eca07ce68773?auto=format&fit=crop&w=800&q=80"
    },
    {
        "name": "IronMate Heavyweight Oversized Pump Cover Hoodie",
        "category": "Apparel",
        "price": 54.99,
        "description": "450 GSM ultra-dense French Terry cotton with drop shoulder silhouette, double-layered hood, and minimal embroidered IronMate chest logo. Ideal for gym warmups.",
        "stock": 20,
        "goal_tags": ["strength", "general_fitness"],
        "experience_level": "beginner",
        "space_needed": "none",
        "image_url": "https://images.unsplash.com/photo-1556905055-8f358a7a47b2?auto=format&fit=crop&w=800&q=80"
    },
    {
        "name": "Men's 7-Inch 2-in-1 Running & Lifting Shorts with Liner",
        "category": "Apparel",
        "price": 29.99,
        "description": "Quick-drying outer shell with built-in compression boxer-brief liner, zippered secure card pocket, and dedicated towel loop for high-intensity lifting sessions.",
        "stock": 30,
        "goal_tags": ["cardio", "general_fitness"],
        "experience_level": "beginner",
        "space_needed": "none",
        "image_url": "https://images.unsplash.com/photo-1591195853828-11db59a44f6b?auto=format&fit=crop&w=800&q=80"
    },
    {
        "name": "Performance Drop-Arm Muscle Tank",
        "category": "Apparel",
        "price": 22.99,
        "description": "Breathable cotton-modal blend with deep cut armholes for unrestricted shoulder mobility and optimal lat room during overhead presses and pull-ups.",
        "stock": 25,
        "goal_tags": ["strength", "general_fitness"],
        "experience_level": "beginner",
        "space_needed": "none",
        "image_url": "https://images.unsplash.com/photo-1583473848882-f9a5bc7fd2ee?auto=format&fit=crop&w=800&q=80"
    },
    {
        "name": "High-Impact Seamless Cross-Back Sports Bra",
        "category": "Apparel",
        "price": 32.99,
        "description": "Molded cups with breathable mesh cross-strap backing and wide under-bust elastic band designed for zero-bounce support during sprints, HIIT, and plyometrics.",
        "stock": 22,
        "goal_tags": ["cardio", "general_fitness"],
        "experience_level": "beginner",
        "space_needed": "none",
        "image_url": "https://images.unsplash.com/photo-1518611012118-696072aa579a?auto=format&fit=crop&w=800&q=80"
    },

    # ---------------- 4. ACCESSORIES ----------------
    {
        "name": "10mm Genuine Leather Quick-Release Lever Weightlifting Belt",
        "category": "Accessories",
        "price": 79.99,
        "description": "IPF-spec 4-inch wide, 10mm thick genuine vegetable-tanned cowhide leather with matte black zinc alloy lever buckle for instant bracing support on heavy squats and deadlifts.",
        "stock": 16,
        "goal_tags": ["strength", "muscle_gain"],
        "experience_level": "intermediate",
        "space_needed": "none",
        "image_url": "https://images.unsplash.com/photo-1584735935682-2f2b69dff9d2?auto=format&fit=crop&w=800&q=80"
    },
    {
        "name": "Heavy-Duty Padded Wrist Wraps & Figure-8 Lifting Straps",
        "category": "Accessories",
        "price": 21.99,
        "description": "Combo pack including 18-inch thumb loop elastic wrist wraps for bench press stabilization and heavy-duty cotton webbing Figure-8 deadlift straps rated for 1,000 lbs.",
        "stock": 35,
        "goal_tags": ["strength", "muscle_gain"],
        "experience_level": "beginner",
        "space_needed": "none",
        "image_url": "https://images.unsplash.com/photo-1517838277536-f5f99be501cd?auto=format&fit=crop&w=800&q=80"
    },
    {
        "name": "Insulated Stainless Steel Protein Shaker Bottle (26 oz)",
        "category": "Accessories",
        "price": 18.99,
        "description": "Double-wall vacuum insulated kitchen-grade stainless steel keeping drinks ice cold for 24 hours. Odor-resistant interior with silent wire whisk ball and leakproof twist cap.",
        "stock": 50,
        "goal_tags": ["general_fitness"],
        "experience_level": "beginner",
        "space_needed": "none",
        "image_url": "https://images.unsplash.com/photo-1579758630661-5360e93f3508?auto=format&fit=crop&w=800&q=80"
    },
    {
        "name": "High-Density Interlocking Rubber Gym Floor Tiles (6 Pack / 24 sq ft)",
        "category": "Accessories",
        "price": 64.99,
        "description": "3/4-inch ultra-dense recycled rubber with non-skid textured top surface. Absorbs heavy barbell drop impacts and prevents concrete floor cracking in garage gyms.",
        "stock": 15,
        "goal_tags": ["home_gym"],
        "experience_level": "beginner",
        "space_needed": "medium",
        "image_url": "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?auto=format&fit=crop&w=800&q=80"
    },
    {
        "name": "Fabric Resistance Loop Booty & Glute Bands (Set of 3)",
        "category": "Accessories",
        "price": 24.99,
        "description": "Non-slip cotton-latex blend with internal rubber grip strips that will not roll or pinch skin. Includes Light, Medium, and Heavy resistance for warmups and glute activation.",
        "stock": 40,
        "goal_tags": ["general_fitness", "muscle_gain"],
        "experience_level": "beginner",
        "space_needed": "none",
        "image_url": "https://images.unsplash.com/photo-1598289431512-b97b0917affc?auto=format&fit=crop&w=800&q=80"
    },
    {
        "name": "Pro Percussion Deep Tissue Massage Gun",
        "category": "Accessories",
        "price": 119.99,
        "description": "QuietGlide brushless high-torque motor delivering 14mm stroke amplitude and 3,200 PPM. 6 interchangeable massage heads and 6-hour rechargeable lithium-ion battery.",
        "stock": 12,
        "goal_tags": ["general_fitness", "home_gym"],
        "experience_level": "beginner",
        "space_needed": "none",
        "image_url": "https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?auto=format&fit=crop&w=800&q=80"
    },

    # ---------------- 5. NUTRITION & SUPPLEMENTS ----------------
    {
        "name": "100% Grass-Fed Whey Isolate Protein (5 lbs / Double Chocolate)",
        "category": "Nutrition & Supplements",
        "price": 74.99,
        "description": "27g pure microfiltered whey protein isolate per scoop, with 6.2g BCAAs and zero added sugars. Rapid post-workout digestion with rich Dutch cocoa flavor.",
        "stock": 25,
        "goal_tags": ["muscle_gain", "general_fitness"],
        "experience_level": "beginner",
        "space_needed": "none",
        "image_url": "https://images.unsplash.com/photo-1579758630661-5360e93f3508?auto=format&fit=crop&w=800&q=80"
    },
    {
        "name": "Micronized 100% Pure Creatine Monohydrate (500g / 100 Servings)",
        "category": "Nutrition & Supplements",
        "price": 29.99,
        "description": "Creapure ultra-fine 200-mesh micronized creatine dissolves instantly in water or protein shakes without grittiness. Clinically proven to boost ATP strength and muscle fullness.",
        "stock": 35,
        "goal_tags": ["strength", "muscle_gain"],
        "experience_level": "beginner",
        "space_needed": "none",
        "image_url": "https://images.unsplash.com/photo-1584735935682-2f2b69dff9d2?auto=format&fit=crop&w=800&q=80"
    },
    {
        "name": "Nitric Oxide Explosive Pre-Workout Powder (Sour Green Apple)",
        "category": "Nutrition & Supplements",
        "price": 39.99,
        "description": "300mg natural caffeine, 6g L-Citrulline Malate, 3.2g Beta-Alanine, and Huperzine A for laser focus and skin-splitting muscle pumps without midday jitters or crashes.",
        "stock": 20,
        "goal_tags": ["strength", "endurance"],
        "experience_level": "intermediate",
        "space_needed": "none",
        "image_url": "https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?auto=format&fit=crop&w=800&q=80"
    },
    {
        "name": "Plant-Based Organic Vegan Protein (Vanilla Bean / 2.2 lbs)",
        "category": "Nutrition & Supplements",
        "price": 44.99,
        "description": "Complete amino acid profile formulated from organic yellow pea, organic brown rice, and chia seeds. Naturally sweetened with stevia, gluten-free, soy-free, and easy on digestion.",
        "stock": 18,
        "goal_tags": ["general_fitness", "muscle_gain"],
        "experience_level": "beginner",
        "space_needed": "none",
        "image_url": "https://images.unsplash.com/photo-1579758630661-5360e93f3508?auto=format&fit=crop&w=800&q=80"
    },
    {
        "name": "HydraPeak Electrolyte Recovery Powder (40 Single-Serve Sticks)",
        "category": "Nutrition & Supplements",
        "price": 26.99,
        "description": "Optimal 3:1 sodium-to-potassium ratio with magnesium, zinc, and vitamin C. Zero sugar and artificial coloring, formulated for rapid hydration after heavy sweat workouts.",
        "stock": 30,
        "goal_tags": ["endurance", "cardio"],
        "experience_level": "beginner",
        "space_needed": "none",
        "image_url": "https://images.unsplash.com/photo-1517838277536-f5f99be501cd?auto=format&fit=crop&w=800&q=80"
    },
    {
        "name": "Fermented BCAA + Glutamine Intra-Workout (Watermelon Splash)",
        "category": "Nutrition & Supplements",
        "price": 31.99,
        "description": "Instantized 2:1:1 vegan fermented Branched Chain Amino Acids with 2.5g L-Glutamine and coconut water powder to preserve lean muscle tissue and accelerate recovery.",
        "stock": 22,
        "goal_tags": ["muscle_gain", "endurance"],
        "experience_level": "intermediate",
        "space_needed": "none",
        "image_url": "https://images.unsplash.com/photo-1540497077202-7c8a3999166f?auto=format&fit=crop&w=800&q=80"
    }
]

# Store Policies and Frequently Asked Questions
STORE_FAQS: List[Dict[str, str]] = [
    {
        "category": "Shipping Policy",
        "text": "IronMate Shipping Policy: We offer free standard shipping on all equipment and apparel orders over $75 within the continental US. Standard shipping delivers in 3-5 business days. Expedited 2-day air shipping is available at checkout for $14.99. Heavy freight equipment (power racks, treadmills, rowers) includes complimentary curbside freight delivery with scheduled appointment windows."
    },
    {
        "category": "Return & Refund Policy",
        "text": "IronMate 30-Day Hassle-Free Returns: We offer a 30-day money-back satisfaction guarantee on all equipment, apparel, and unopened supplements. If you are not completely satisfied, return the item in original packaging for a full refund or exchange. We provide pre-paid return shipping labels for defective or damaged items."
    },
    {
        "category": "Warranty & Guarantee",
        "text": "IronMate Equipment Warranty: All structural steel power cages, squat racks, and Olympic barbells come with a Lifetime Structural Frame Warranty. Electronic components, treadmill motors, rowing consoles, and massage guns are covered by a comprehensive 2-Year Full Replacement Warranty against manufacturer defects."
    },
    {
        "category": "Equipment Assembly & Care",
        "text": "Assembly & Support: Every heavy equipment order includes step-by-step 3D visual assembly manuals and tool kits. We offer optional white-glove in-home installation in select metropolitan areas. For maintenance, lubricate barbell sleeves every 6 months with 3-in-1 oil and wipe sweat from bench leather after workouts."
    },
    {
        "category": "Customer Support & Contact",
        "text": "Customer Support: The IronMate team is available 24/7 via live in-app AI chat, email at support@ironmate.com, or toll-free telephone at 1-800-IRON-MATE (Mon-Fri 8am-8pm EST). For order tracking and invoice queries, log into your user account dashboard."
    }
]


def load_products_data() -> List[Dict[str, Any]]:
    """Loads products from products-seed.json if present; otherwise returns DEFAULT_PRODUCTS."""
    basedir = os.path.abspath(os.path.dirname(__file__))
    seed_file_path = os.path.join(basedir, "products-seed.json")
    if os.path.exists(seed_file_path):
        try:
            with open(seed_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    logger.info(f"Loaded {len(data)} products from {seed_file_path}")
                    return data
        except Exception as e:
            logger.warning(f"Failed to parse {seed_file_path}: {e}. Using default products.")

    # Save default products to products-seed.json so it is accessible for inspection
    try:
        with open(seed_file_path, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_PRODUCTS, f, indent=2)
            logger.info(f"Saved {len(DEFAULT_PRODUCTS)} products to {seed_file_path}")
    except Exception as e:
        logger.warning(f"Could not write {seed_file_path}: {e}")

    return DEFAULT_PRODUCTS


def seed_database() -> None:
    """
    Seeds the SQLite database with:
    1. Default demo user: demo@ironmate.com / demo1234
    2. 30 fitness products across 5 categories
    3. Vector embeddings for products & store FAQs in knowledge_chunks
    """
    logger.info("Starting IronMate database initialization and seeding...")

    # 1. Create Default Demo Account if not exists
    demo_email = "demo@ironmate.com"
    demo_user = User.query.filter_by(email=demo_email).first()
    if not demo_user:
        demo_user = User(
            name="IronMate Demo Athlete",
            email=demo_email
        )
        demo_user.set_password("demo1234")
        db.session.add(demo_user)
        db.session.commit()
        logger.info(f"Created demo account: {demo_email} (password: demo1234)")
    else:
        logger.info(f"Demo account already exists: {demo_email}")

    # 2. Seed Products
    existing_product_count = Product.query.count()
    if existing_product_count == 0:
        products_data = load_products_data()
        created_products = []

        for p_data in products_data:
            product = Product(
                name=p_data["name"],
                category=p_data["category"],
                price=float(p_data["price"]),
                mrp=float(p_data["mrp"]) if "mrp" in p_data and p_data["mrp"] else float(p_data["price"] * 1.5),
                description=p_data["description"],
                stock=int(p_data.get("stock", 10)),
                goal_tags=p_data.get("goal_tags", []),
                experience_level=p_data.get("experience_level", "beginner"),
                space_needed=p_data.get("space_needed", "small"),
                image_url=p_data.get("image_url", "https://images.unsplash.com/photo-1517838277536-f5f99be501cd")
            )
            db.session.add(product)
            created_products.append(product)

        db.session.commit()
        logger.info(f"Successfully seeded {len(created_products)} products.")

        # 3. Generate Knowledge Chunks & Embeddings for Products
        logger.info("Generating vector embeddings for products...")
        for product in created_products:
            tags_str = ", ".join(product.goal_tags) if isinstance(product.goal_tags, list) else ""
            chunk_text = (
                f"Product: {product.name} | Category: {product.category} | Price: ${product.price:.2f} | "
                f"Level: {product.experience_level} | Space Needed: {product.space_needed} | "
                f"Stock: {product.stock} units | Focus: {tags_str} | "
                f"Description: {product.description}"
            )
            embedding_vector = generate_embedding(chunk_text)

            chunk = KnowledgeChunk(
                product_id=product.id,
                category=f"Product: {product.category}",
                text=chunk_text,
                embedding=embedding_vector
            )
            db.session.add(chunk)

        db.session.commit()
        logger.info("Generated product knowledge embeddings.")
    else:
        logger.info(f"Database already contains {existing_product_count} products. Skipping product insertion.")

    # 4. Generate Knowledge Chunks & Embeddings for Store FAQs
    existing_faq_chunks = KnowledgeChunk.query.filter_by(product_id=None).count()
    if existing_faq_chunks == 0:
        logger.info("Generating vector embeddings for Store Policy FAQs...")
        for faq in STORE_FAQS:
            embedding_vector = generate_embedding(faq["text"])
            chunk = KnowledgeChunk(
                product_id=None,
                category=faq["category"],
                text=faq["text"],
                embedding=embedding_vector
            )
            db.session.add(chunk)

        db.session.commit()
        logger.info(f"Seeded {len(STORE_FAQS)} store FAQ knowledge chunks.")
    else:
        logger.info(f"Store FAQs already seeded ({existing_faq_chunks} chunks).")

    total_chunks = KnowledgeChunk.query.count()
    logger.info(f"Database seeding complete! Total knowledge chunks ready for RAG: {total_chunks}")


if __name__ == "__main__":
    from flask import Flask
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ironmate.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    with app.app_context():
        db.create_all()
        seed_database()
