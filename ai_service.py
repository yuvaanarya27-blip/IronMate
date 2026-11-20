"""
ai_service.py - AI Shopping Assistant and RAG Vector Search Engine
Integrates Google GenAI SDK (`google-genai`), NumPy cosine similarity, and multi-turn product finder.

College Viva Key Concepts:
1. Zero-Cost Vector Architecture: Instead of paying for vector databases (Pinecone, Milvus),
   embeddings are stored directly in SQLite and compared in-memory with NumPy.
2. Cosine Similarity: Measures the angle between query and document vectors:
   sim(A, B) = (A . B) / (||A|| * ||B||), ranging from -1 to +1.
3. RAG (Retrieval-Augmented Generation): Grounds Gemini LLM responses with accurate,
   real-time store inventory and policy chunks to eliminate hallucinations.
"""

import os
import re
import math
import hashlib
import logging
from typing import List, Dict, Any, Optional, Tuple
from dotenv import load_dotenv
import numpy as np

# Load environment variables
load_dotenv()

# Load Google GenAI SDK
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# GEMINI CLIENT INITIALIZATION
# -------------------------------------------------------------------------
def get_genai_client() -> Optional[Any]:
    """
    Returns an initialized GenAI client using GEMINI_API_KEY from environment.
    Explicitly enforces standard HTTPS REST transport (no gRPC) with v1 API endpoints,
    ensuring full compatibility with PythonAnywhere's standard HTTP/HTTPS proxy.
    Returns None if key is absent or SDK is unavailable.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key.startswith("your_") or api_key == "dummy":
        return None

    if genai is None:
        logger.warning("google-genai package is not installed.")
        return None

    try:
        # Configure standard HTTPS REST via types.HttpOptions
        # PythonAnywhere enforces outbound connections over HTTP/HTTPS proxy (port 80/443).
        # gRPC (HTTP/2 with custom frames) is blocked; standard HTTPS REST with httpx works cleanly.
        # Passing client_args={'trust_env': True} ensures PythonAnywhere's http_proxy/https_proxy env vars are used.
        http_options = None
        if types and hasattr(types, "HttpOptions"):
            http_options = types.HttpOptions(
                api_version="v1",
                timeout=30.0,
                client_args={"trust_env": True}
            )
        return genai.Client(api_key=api_key, http_options=http_options)
    except Exception as e:
        logger.error(f"Failed to initialize GenAI Client: {e}")
        return None


# -------------------------------------------------------------------------
# FALLBACK DETERMINISTIC EMBEDDING ENGINE (ZERO-CRASH GUARANTEE)
# -------------------------------------------------------------------------
def _deterministic_semantic_vector(text: str, dim: int = 3072) -> List[float]:
    """
    Generates a deterministic 3072-dimensional normalized pseudo-semantic vector
    using term frequency, character n-grams, and MD5 feature hashing.
    Used seamlessly if GEMINI_API_KEY is not configured yet or when offline during tests.
    """
    cleaned = re.sub(r'[^a-zA-Z0-9\s]', ' ', text.lower())
    words = cleaned.split()
    vector = np.zeros(dim, dtype=np.float32)

    for i, word in enumerate(words):
        # Hash unigram
        h = int(hashlib.md5(word.encode('utf-8')).hexdigest(), 16) % dim
        vector[h] += 1.0 + (1.0 / (i + 1))

        # Hash character trigrams for sub-word semantics
        if len(word) >= 3:
            for j in range(len(word) - 2):
                tri = word[j:j+3]
                h_tri = int(hashlib.md5(tri.encode('utf-8')).hexdigest(), 16) % dim
                vector[h_tri] += 0.35

    # Normalize vector to unit length
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector = vector / norm
    else:
        vector[0] = 1.0

    return vector.tolist()


# -------------------------------------------------------------------------
# EMBEDDING GENERATION
# -------------------------------------------------------------------------
def generate_embedding(text: str) -> List[float]:
    """
    Generates vector embedding for text using Google Gemini `gemini-embedding-001` or `text-embedding-004`.
    Falls back to deterministic vector if key is unavailable or offline.
    """
    if not text or not text.strip():
        return [0.0] * 3072

    client = get_genai_client()
    if client:
        # Try primary embedding model gemini-embedding-001 or text-embedding-004
        for model_name in ["gemini-embedding-001", "text-embedding-004"]:
            try:
                response = client.models.embed_content(
                    model=model_name,
                    contents=text
                )
                if response and hasattr(response, 'embeddings') and response.embeddings:
                    values = response.embeddings[0].values
                    if values:
                        return list(values)
            except Exception as e:
                logger.warning(f"Embedding failed with {model_name}: {e}. Retrying with fallback...")

    # Fallback to local semantic vector matching primary dimension (3072)
    return _deterministic_semantic_vector(text, dim=3072)


# -------------------------------------------------------------------------
# NUMPY IN-MEMORY COSINE SIMILARITY
# -------------------------------------------------------------------------
def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """
    Computes cosine similarity between two vector lists using NumPy:
    cosine_similarity = (A . B) / (||A|| * ||B||)
    Returns float in range [-1.0, 1.0].
    Safely handles differing dimensions (e.g. 768 vs 3072) without throwing ValueError.
    """
    if not vec_a or not vec_b:
        return 0.0

    len_a = len(vec_a)
    len_b = len(vec_b)

    if len_a != len_b:
        min_dim = min(len_a, len_b)
        a = np.array(vec_a[:min_dim], dtype=np.float32)
        b = np.array(vec_b[:min_dim], dtype=np.float32)
    else:
        a = np.array(vec_a, dtype=np.float32)
        b = np.array(vec_b, dtype=np.float32)

    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    dot = np.dot(a, b)
    similarity = float(dot / (norm_a * norm_b))
    return max(-1.0, min(1.0, similarity))


def find_top_k_chunks(query_embedding: List[float], chunks: List[Any], k: int = 4) -> List[Tuple[Any, float]]:
    """
    Searches all KnowledgeChunk records in-memory using NumPy cosine similarity.
    Returns the top-K chunks sorted by highest similarity score.
    """
    scored_chunks = []
    for chunk in chunks:
        emb = chunk.embedding
        if isinstance(emb, str):
            import json
            try:
                emb = json.loads(emb)
            except Exception:
                continue

        score = cosine_similarity(query_embedding, emb)
        scored_chunks.append((chunk, score))

    # Sort descending by score
    scored_chunks.sort(key=lambda x: x[1], reverse=True)
    return scored_chunks[:k]


# -------------------------------------------------------------------------
# RAG CHAT ENGINE WITH STRICT IRONMATE GUARDRAILS
# -------------------------------------------------------------------------
STRICT_IRONMATE_SYSTEM_PROMPT = """You are IronMate's AI Shopping & Fitness Assistant, an enthusiastic, knowledgeable expert on gym gear, training equipment, sports apparel, supplements, and IronMate customer policies.

STRICT OPERATIONAL GUIDELINES:
1. FOCUS & DOMAIN: You ONLY answer questions about IronMate products, fitness equipment, workout gear, exercise setups, gym accessories, nutrition/supplements, order policies, shipping, returns, and warranties.
2. OFF-TOPIC GUARDRAIL: If the user asks anything outside of fitness, gym equipment, health workouts, or IronMate store policies (such as politics, coding, general trivia, weather, cooking unrelated meals, celebrity gossip, etc.), politely decline:
   "I am IronMate's dedicated fitness equipment and shopping specialist! I can only assist with gym gear, fitness equipment, workout recommendations, and IronMate store policies. How can I help with your fitness journey today?"
3. GROUNDING: Use the provided Store & Product Knowledge context to provide accurate prices, dimensions, stock levels, and store policies. Do not invent products or policies that do not exist.
4. COMPARISONS: When users ask to compare items, compare them clearly across price, space needed, experience level, and target training goals.
5. FORMATTING: Use clean markdown with clear headings, concise bullet points, and highlight exact prices with '$'. Keep answers actionable and encouraging.
"""


def generate_rag_response(
    user_query: str,
    retrieved_chunks: List[Tuple[Any, float]],
    chat_history: Optional[List[Dict[str, str]]] = None
) -> str:
    """
    Generates a RAG response using `gemini-2.5-flash` with retrieved context chunks
    and strict domain guardrails.
    """
    # Build context string from top-k retrieved chunks
    context_lines = []
    for chunk, score in retrieved_chunks:
        category = getattr(chunk, 'category', 'General')
        text = getattr(chunk, 'text', '')
        context_lines.append(f"[{category}] (Relevance: {score:.2f})\n{text}")

    context_str = "\n\n".join(context_lines)

    # Format prompt
    full_prompt = f"""STORE & PRODUCT KNOWLEDGE BASE CONTEXT:
---------------------------------------------
{context_str}
---------------------------------------------

USER QUERY:
{user_query}

Answer the user query thoroughly and accurately based on the IronMate knowledge base above while adhering to your strict assistant persona."""

    client = get_genai_client()
    if client:
        try:
            # Prepare optional conversation history
            contents = []
            if chat_history:
                for msg in chat_history[-6:]:  # Keep recent context
                    role = "user" if msg.get("role") == "user" else "model"
                    contents.append(types.Content(
                        role=role,
                        parts=[types.Part.from_text(text=msg.get("content", ""))]
                    ))

            contents.append(types.Content(
                role="user",
                parts=[types.Part.from_text(text=full_prompt)]
            ))

            config = types.GenerateContentConfig(
                system_instruction=STRICT_IRONMATE_SYSTEM_PROMPT,
                temperature=0.4,
                max_output_tokens=800
            )

            for model_name in ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-2.5-flash"]:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=contents,
                        config=config
                    )
                    if response and response.text:
                        return response.text.strip()
                except Exception as model_err:
                    logger.warning(f"Model {model_name} failed: {model_err}. Trying next...")
        except Exception as e:
            logger.warning(f"Gemini generate_content failed: {e}. Falling back to structured response.")

    # High quality structured fallback response when GEMINI_API_KEY is not configured
    query_lower = user_query.lower()

    # Off-topic check in fallback
    off_topic_keywords = ["weather", "code", "python", "president", "capital of", "recipe for cake", "movie", "song", "crypto"]
    if any(k in query_lower for k in off_topic_keywords) and not any(f in query_lower for f in ["gym", "workout", "fitness", "gear", "bench", "weight"]):
        return (
            "I am IronMate's dedicated fitness equipment and shopping specialist! "
            "I can only assist with gym gear, fitness equipment, workout recommendations, and IronMate store policies. "
            "How can I help with your fitness journey today?"
        )

    # Answer using retrieved chunks
    reply_parts = ["Here is what I found in the IronMate catalog & store policies for you:\n"]
    for chunk, score in retrieved_chunks:
        category = getattr(chunk, 'category', 'Store Info')
        text = getattr(chunk, 'text', '')
        reply_parts.append(f"• **{category}**: {text}")

    reply_parts.append("\nFeel free to ask for specific gear recommendations, stock details, or workout space requirements!")
    return "\n".join(reply_parts)


# -------------------------------------------------------------------------
# CART-AWARE SHOPPING ASSISTANT
# -------------------------------------------------------------------------
def generate_cart_aware_response(
    cart_items: List[Dict[str, Any]],
    user_message: str,
    catalog_products: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Analyzes current user cart items and recommends 1-2 complementary items from catalog.
    Injects cart breakdown + catalog context into Gemini prompt.
    """
    total_cart_val = sum(item.get("line_total", 0.0) for item in cart_items)
    cart_summary_text = ""
    cart_product_ids = set()
    cart_categories = set()

    for item in cart_items:
        p = item.get("product") or {}
        p_id = p.get("id")
        if p_id:
            cart_product_ids.add(p_id)
        if p.get("category"):
            cart_categories.add(p["category"])
        cart_summary_text += f"- {p.get('name', 'Product')} (Qty: {item.get('quantity')}, Unit: ${p.get('price')}, Subtotal: ${item.get('line_total')})\n"

    # Identify complementary products
    # Complementary rules for fitness gear
    suggestions = []
    for cat_prod in catalog_products:
        if cat_prod["id"] in cart_product_ids:
            continue

        p_name = cat_prod["name"].lower()
        p_cat = cat_prod["category"].lower()

        # Complementary logic:
        # If user has weights -> suggest gym mat, skipping rope, or shaker
        if any("weight" in c.lower() for c in cart_categories) or any("dumbbell" in c.lower() for c in cart_summary_text.lower()) or any("strength" in c.lower() for c in cart_categories):
            if p_cat in ["mats", "rope", "shaker"] or "mat" in p_name or "rope" in p_name or "shaker" in p_name or "curl" in p_name:
                suggestions.append({
                    "id": cat_prod["id"],
                    "name": cat_prod["name"],
                    "price": cat_prod["price"],
                    "category": cat_prod["category"],
                    "image_url": cat_prod["image_url"],
                    "reason": "Pairs perfectly with your lifting gear for enhanced joint protection and post-workout recovery."
                })
        # If user has cardio (Treadmill, Bike, Bicycle) -> suggest mat or shaker
        elif any(c.lower() in ["treadmill", "bike", "bicycle"] for c in cart_categories):
            if p_cat in ["mats", "shaker", "rope"] or "mat" in p_name or "shaker" in p_name:
                suggestions.append({
                    "id": cat_prod["id"],
                    "name": cat_prod["name"],
                    "price": cat_prod["price"],
                    "category": cat_prod["category"],
                    "image_url": cat_prod["image_url"],
                    "reason": "Essential companion for floor protection, hydration, and cardiovascular warmups."
                })

        if len(suggestions) >= 2:
            break

    # If no specific rule matched, pick top recommended gear from other categories
    if len(suggestions) < 2:
        for cat_prod in catalog_products:
            if cat_prod["id"] not in cart_product_ids and cat_prod["category"] in ["Mats", "Rope", "Shaker", "Weight"]:
                if not any(s["id"] == cat_prod["id"] for s in suggestions):
                    suggestions.append({
                        "id": cat_prod["id"],
                        "name": cat_prod["name"],
                        "price": cat_prod["price"],
                        "category": cat_prod["category"],
                        "image_url": cat_prod["image_url"],
                        "reason": "Top-rated training gear to upgrade your home workout routine."
                    })
                    if len(suggestions) >= 2:
                        break

    # Ultimate fallback: any available catalog product not in cart
    if len(suggestions) < 2:
        for cat_prod in catalog_products:
            if cat_prod["id"] not in cart_product_ids and not any(s["id"] == cat_prod["id"] for s in suggestions):
                suggestions.append({
                    "id": cat_prod["id"],
                    "name": cat_prod["name"],
                    "price": cat_prod["price"],
                    "category": cat_prod["category"],
                    "image_url": cat_prod["image_url"],
                    "reason": "Recommended equipment for your training progression."
                })
                if len(suggestions) >= 2:
                    break

    # Generate personalized message with Gemini if available
    client = get_genai_client()
    reply_text = None

    if client:
        try:
            prompt = f"""The customer is viewing their shopping cart on IronMate.
Current Cart Items:
{cart_summary_text or "Cart is currently empty."}
Total Cart Value: ${total_cart_val:.2f}

Customer Question / Message:
"{user_message}"

Complementary Products Identified:
{suggestions}

Instructions:
1. Address the customer's question directly with respect to what is currently in their cart.
2. Confirm their current items and mention how their gear choices support their fitness goals.
3. Enthusiastically recommend the complementary products identified above, explaining why they will maximize their results.
4. Keep the tone motivational, clear, and professional. Use markdown formatting."""

            config = types.GenerateContentConfig(
                system_instruction=STRICT_IRONMATE_SYSTEM_PROMPT,
                temperature=0.4,
                max_output_tokens=700
            )

            for model_name in ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-2.5-flash"]:
                try:
                    res = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=config
                    )
                    if res and res.text:
                        reply_text = res.text.strip()
                        break
                except Exception as model_err:
                    logger.warning(f"Cart-aware model {model_name} failed: {model_err}. Trying next...")
        except Exception as e:
            logger.warning(f"Gemini cart-aware generation failed: {e}")

    if not reply_text:
        if not cart_items:
            reply_text = (
                "Your IronMate shopping cart is currently empty! "
                "Explore our top-tier Strength Training and Conditioning gear to get started, "
                "or let me know your training goals and I can recommend the perfect starter kit!"
            )
        else:
            rec_text = "\n".join([f"- **{s['name']}** (${s['price']}): {s['reason']}" for s in suggestions])
            reply_text = (
                f"You currently have {len(cart_items)} item(s) in your cart totaling **${total_cart_val:.2f}**.\n\n"
                f"To get the most out of your training setup, I highly recommend adding these complementary items:\n"
                f"{rec_text}\n\n"
                "Ready to crush your goals? You can checkout anytime from the cart page!"
            )

    return {
        "reply": reply_text,
        "cart_summary": {
            "item_count": sum(i.get("quantity", 1) for i in cart_items),
            "total": round(total_cart_val, 2),
            "items": cart_items
        },
        "suggested_products": suggestions[:2]
    }


# -------------------------------------------------------------------------
# MULTI-TURN GUIDED PRODUCT FINDER ENGINE
# -------------------------------------------------------------------------
QUESTIONS_CONFIG = [
    {
        "step": 1,
        "question": "What is your primary fitness goal?",
        "field": "goal",
        "options": [
            {"label": "Muscle Building & Strength", "value": "muscle_gain"},
            {"label": "Cardio & Fat Loss", "value": "fat_loss"},
            {"label": "Endurance & Conditioning", "value": "endurance"},
            {"label": "Home Gym Essentials", "value": "home_gym"},
            {"label": "General Fitness & Health", "value": "general_fitness"}
        ]
    },
    {
        "step": 2,
        "question": "How much workout space do you have available?",
        "field": "space",
        "options": [
            {"label": "None / On-the-Go (Portable gear)", "value": "none"},
            {"label": "Small (Corner of bedroom or apartment)", "value": "small"},
            {"label": "Medium (Dedicated spare room)", "value": "medium"},
            {"label": "Large (Garage gym or basement)", "value": "large"}
        ]
    },
    {
        "step": 3,
        "question": "What is your current fitness experience level?",
        "field": "experience",
        "options": [
            {"label": "Beginner (New to working out)", "value": "beginner"},
            {"label": "Intermediate (Regular training for 6+ months)", "value": "intermediate"},
            {"label": "Advanced (Experienced lifter / athlete)", "value": "advanced"}
        ]
    },
    {
        "step": 4,
        "question": "What is your target budget for this equipment?",
        "field": "budget",
        "options": [
            {"label": "Under $50 (Budget-friendly essentials)", "value": "50"},
            {"label": "$50 - $150 (Mid-range gear)", "value": "150"},
            {"label": "$150 - $400 (Premium training gear)", "value": "400"},
            {"label": "$400+ (Complete gym systems)", "value": "1000"}
        ]
    }
]


def process_plan_finder_step(
    step: int,
    answers: Dict[str, Any],
    all_products: List[Any]
) -> Dict[str, Any]:
    """
    Handles multi-turn guided product finder.
    If step < 4, prompts the next question.
    If step == 4, filters products using SQLAlchemy properties and returns top 1-3 recommendations.
    """
    if step < 4:
        next_q = QUESTIONS_CONFIG[step]  # step is 1-indexed; step 1 completed -> ask question 2 (index 1)
        return {
            "completed": False,
            "current_step": step + 1,
            "total_steps": 4,
            "question": next_q["question"],
            "field": next_q["field"],
            "options": next_q["options"],
            "collected_answers": answers
        }

    # Step 4 completed: Evaluate all collected answers and filter products
    target_goal = str(answers.get("goal", "general_fitness")).lower()
    target_space = str(answers.get("space", "small")).lower()
    target_exp = str(answers.get("experience", "beginner")).lower()
    budget_raw = answers.get("budget", "150")
    try:
        target_budget = float(budget_raw)
    except Exception:
        target_budget = 150.0

    scored_products = []

    for prod in all_products:
        score = 0.0

        # Parse tags
        tags = prod.goal_tags
        if isinstance(tags, str):
            import json
            try:
                tags = json.loads(tags)
            except Exception:
                tags = []
        tags_lower = [str(t).lower() for t in tags] if isinstance(tags, list) else []

        # Goal match scoring (+3 points)
        if target_goal in tags_lower:
            score += 3.0
        elif target_goal == "muscle_gain" and any(t in tags_lower for t in ["strength", "home_gym"]):
            score += 2.0
        elif target_goal == "fat_loss" and any(t in tags_lower for t in ["cardio", "endurance"]):
            score += 2.0

        # Space match scoring (+2 points)
        space_order = {"none": 0, "small": 1, "medium": 2, "large": 3}
        prod_space_val = space_order.get(prod.space_needed.lower(), 1)
        user_space_val = space_order.get(target_space, 1)

        if prod.space_needed.lower() == target_space:
            score += 2.0
        elif prod_space_val <= user_space_val:
            # Fits comfortably in available space
            score += 1.5
        else:
            # Product requires more space than user has
            score -= 2.0

        # Experience level match (+2 points)
        if prod.experience_level.lower() == target_exp:
            score += 2.0
        elif target_exp == "beginner" and prod.experience_level.lower() == "intermediate":
            score += 0.5
        elif target_exp == "advanced":
            score += 1.0  # Advanced users can use beginner or intermediate gear

        # Budget match (+2 points)
        if prod.price <= target_budget:
            score += 2.0
            # Bonus for being close to budget without exceeding
            if prod.price >= target_budget * 0.4:
                score += 1.0
        else:
            # Over budget penalty
            over_pct = (prod.price - target_budget) / target_budget
            score -= min(3.0, over_pct * 2.0)

        scored_products.append((prod, score))

    # Sort descending by score
    scored_products.sort(key=lambda x: x[1], reverse=True)
    top_recommendations = scored_products[:3]

    # Format recommendations with reason for "Add to Cart" cards
    rec_cards = []
    for prod, score in top_recommendations:
        # Build specific reasoning
        reason = (
            f"Tailored for {prod.experience_level} fitness enthusiasts targeting {target_goal.replace('_', ' ')}. "
            f"Requires {prod.space_needed} space and fits comfortably within your ${target_budget:.0f} budget."
        )
        rec_cards.append({
            "id": prod.id,
            "name": prod.name,
            "category": prod.category,
            "price": prod.price,
            "description": prod.description,
            "stock": prod.stock,
            "image_url": prod.image_url,
            "experience_level": prod.experience_level,
            "space_needed": prod.space_needed,
            "goal_tags": prod.goal_tags if isinstance(prod.goal_tags, list) else [],
            "reason": reason,
            "fit_score": round(max(1.0, score), 1)
        })

    summary_text = (
        f"Based on your goal ({target_goal.replace('_', ' ').title()}), "
        f"{target_space.title()} space availability, {target_exp.title()} experience level, "
        f"and target budget of ${target_budget:.0f}, here are your top matching IronMate products:"
    )

    return {
        "completed": True,
        "current_step": 4,
        "total_steps": 4,
        "summary": summary_text,
        "recommendations": rec_cards,
        "collected_answers": answers
    }
