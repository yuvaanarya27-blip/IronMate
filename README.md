# IronMate Backend API & AI Shopping Assistant

Complete Python + Flask backend and SQLite database for **IronMate**, a fitness & gym gear e-commerce storefront with an AI shopping assistant, strictly built on a **zero-cost architecture**.

---

## 🏛️ Zero-Cost Architecture & College Viva Highlights

| Component | Technology | Rationale & Zero-Cost Benefit |
| :--- | :--- | :--- |
| **Backend Framework** | Flask 3.x, Werkzeug | Lightweight, fast, zero hosting overhead, Pythonic |
| **Database** | SQLite (`ironmate.db`) | Embedded serverless database, ACID compliant, $0 subscription costs |
| **Vector Search (RAG)** | In-Memory NumPy Cosine Similarity | Replaces expensive vector databases (Pinecone, Weaviate, Milvus) with fast local in-memory cosine math |
| **AI LLM & Embeddings** | Google GenAI SDK (`gemini-2.5-flash` & `text-embedding-004`) | Leverages Google Gemini free tier with built-in deterministic offline fallback |
| **Security & Auth** | Flask-JWT-Extended, Werkzeug Security | Stateless JWT authentication, PBKDF2/scrypt password hashing |
| **Deployment / Container Ready** | Auto-seeding on startup | Ephemeral-host friendly: auto-creates tables and seeds if `Product.count() == 0` |

---

## 🚀 Quick Setup & Installation

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Set your keys in `.env`:
```ini
GEMINI_API_KEY=your_gemini_api_key_here
JWT_SECRET_KEY=ironmate-dev-jwt-secret-key-32b-secure
PORT=5000
DATABASE_URL=sqlite:///ironmate.db
```
*(Note: If `GEMINI_API_KEY` is not provided or offline, the app automatically runs high-fidelity semantic embeddings and guardrails so it never crashes!)*

### 3. Run Server
```bash
python app.py
```
*The database and 30 products across 7 categories (Treadmill, Bike, Bicycle, Mats, Rope, Shaker, Weight) + store policies will auto-initialize on first launch.*

### 4. Run Test Suite
```bash
python test_backend.py
```

---

## 🔑 Demo Account
- **Email:** `demo@ironmate.com`
- **Password:** `demo1234`

---

## 📡 REST API Reference

### 🔐 1. Authentication
- `POST /api/auth/signup`: Body: `{ "name": "...", "email": "...", "password": "..." }`
- `POST /api/auth/login`: Body: `{ "email": "demo@ironmate.com", "password": "demo1234" }`
- `GET /api/auth/me`: Header: `Authorization: Bearer <token>`

### 🏋️ 2. Product Catalog
- `GET /api/products`: Query params:
  - `category`: e.g. `Treadmill`, `Bike`, `Bicycle`, `Mats`, `Rope`, `Shaker`, `Weight` (supports comma-separated queries e.g. `Treadmill,Bike,Weight`)
  - `search`: Keyword search in name and description
  - `goal`: e.g. `strength`, `muscle_gain`, `cardio`, `endurance`, `home_gym`, `general_fitness`
  - `experience`: `beginner` | `intermediate` | `advanced`
  - `space`: `none` | `small` | `medium` | `large`
  - `sort`: `price_asc` | `price_desc` | `name`
- `GET /api/products/<id>`: Returns single product detail.

### 🛒 3. Shopping Cart (JWT Protected)
- `GET /api/cart`: Returns user cart items, individual line totals, and overall total.
- `POST /api/cart/add`: Body: `{ "product_id": 1, "quantity": 2 }`
- `PUT /api/cart/update`: Body: `{ "product_id": 1, "quantity": 1 }` (quantity <= 0 removes item)
- `DELETE /api/cart/remove/<product_id>`: Removes item from cart.

### 📦 4. Order & Checkout (JWT Protected)
- `POST /api/orders/checkout`: Validates live inventory stock, creates order, decrements stock atomically, and clears user cart.
- `GET /api/orders`: Returns customer order history.

### 🤖 5. AI Assistant Endpoints

#### A. General RAG Chat (`POST /api/chat`)
- **Body:** `{ "message": "What is your return policy and warranty on power racks?", "history": [] }`
- **Mechanism:**
  1. Generates 768-dim query embedding using Gemini `text-embedding-004`.
  2. Computes in-memory NumPy cosine similarity across SQLite `KnowledgeChunk` records.
  3. Retrieves top 4 chunks.
  4. Calls `gemini-2.5-flash` with a strict system prompt.
  5. Strict Guardrail: Answers fitness/gym gear/IronMate store questions; politely declines off-topic questions (e.g. coding, politics, weather).

#### B. Guided Product Finder (`POST /api/plan-finder`)
- **Multi-turn guided flow** that asks 4 concise questions:
  1. Fitness goal (muscle_gain, fat_loss, endurance, home_gym, general_fitness)
  2. Workout space (none, small, medium, large)
  3. Experience level (beginner, intermediate, advanced)
  4. Target budget ($50, $150, $400, $1000)
- Evaluates SQLAlchemy `Product` attributes and returns top 1–3 recommended products with custom coach reasoning and fit scores for instant "Add to Cart" display.

#### C. Cart-Aware Chat (`POST /api/chat/cart-aware` - JWT Protected)
- **Body:** `{ "message": "What else do I need with my current cart?" }`
- Injects current cart items, quantities, and prices into the prompt.
- Suggests 1–2 complementary products from the catalog (e.g., dumbbells -> bench & lifting straps; protein -> shaker bottle & creatine).

---

## 🎓 Viva Questions & Answers (College / Interview Prep)

1. **Q: Why use NumPy for vector search instead of a vector database like Pinecone?**
   - **A:** For e-commerce catalogs with hundreds or thousands of products, in-memory NumPy vector cosine similarity executes in less than 2 milliseconds with zero cloud subscription fees, zero external latency, and zero infrastructure complexity.
2. **Q: What is Cosine Similarity?**
   - **A:** It measures the cosine of the angle between two multi-dimensional vectors:
     $$\text{Cosine Similarity}(A, B) = \frac{A \cdot B}{\|A\| \|B\|}$$
     A score of 1.0 indicates identical orientation in semantic embedding space.
3. **Q: How does the checkout process prevent overselling?**
   - **A:** The checkout route uses an atomic database transaction. It verifies each item's quantity against live `Product.stock`. If any item exceeds available stock, it immediately rejects the request with an informative error before modifying inventory or creating orders.

---

## ☁️ PythonAnywhere Deployment Guide

Deploying IronMate on **PythonAnywhere** is free and takes under 5 minutes:

### 1. Upload or Clone the Repository
Open a **Bash Console** on PythonAnywhere and clone your repo or upload files:
```bash
git clone <your-repo-url> IronMate
cd IronMate
```

### 2. Create Virtual Environment & Install Dependencies
```bash
mkvirtualenv --python=/usr/bin/python3.10 ironmate-env
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Create a `.env` file in the project root:
```bash
nano .env
```
Paste your configuration:
```ini
GEMINI_API_KEY=your_actual_gemini_api_key
JWT_SECRET_KEY=any_random_32_character_secret_key
FLASK_ENV=production
```

### 4. Configure Web Tab on PythonAnywhere
1. Go to the **Web** tab and click **Add a new web app** (choose **Manual configuration** with **Python 3.10**).
2. Set **Source code** to: `/home/<your-username>/IronMate`
3. Set **Working directory** to: `/home/<your-username>/IronMate`
4. Set **Virtualenv** to: `/home/<your-username>/.virtualenvs/ironmate-env`
5. Click on the **WSGI configuration file** link (`/var/www/<your-username>_pythonanywhere_com_wsgi.py`), clear existing content, and paste:
```python
import sys
import os

project_home = '/home/<your-username>/IronMate'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

from dotenv import load_dotenv
load_dotenv(os.path.join(project_home, '.env'))

from app import app as application
```

### 5. Static Files (Optional - Flask serves them automatically)
Flask in `app.py` automatically serves the `frontend/` folder, images, CSS, and JS. You can also map them in the Web tab's Static Files section:
- **URL**: `/assets/` ➔ **Directory**: `/home/<your-username>/IronMate/frontend/assets/`
- **URL**: `/styles.css` ➔ **Directory**: `/home/<your-username>/IronMate/frontend/styles.css`
- **URL**: `/app.js` ➔ **Directory**: `/home/<your-username>/IronMate/frontend/app.js`

### 6. Reload Web App
Click the green **Reload <your-username>.pythonanywhere.com** button.
Your store with the AI Assistant, full catalog, and shopping cart is now live!
