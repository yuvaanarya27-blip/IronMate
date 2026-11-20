"""
test_backend.py - Comprehensive Test Suite for IronMate Flask Backend
Tests all REST API endpoints, JWT auth, database integrity, RAG cosine similarity,
and AI assistant features using the Flask test client.
"""

import json
import unittest
from app import app, db, User, Product, CartItem, Order, OrderItem, KnowledgeChunk

class IronMateBackendTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    def test_01_health_check(self):
        """Test GET /api/health"""
        res = self.client.get('/api/health')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get("status"), "healthy")
        self.assertGreaterEqual(data["database"]["products_count"], 30)
        print("✓ Health check passed")

    def test_02_demo_login(self):
        """Test POST /api/auth/login with demo account"""
        res = self.client.post('/api/auth/login', json={
            "email": "demo@ironmate.com",
            "password": "demo1234"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("token", data)
        self.assertEqual(data["user"]["email"], "demo@ironmate.com")
        print("✓ Demo login passed")

    def test_03_signup_and_me(self):
        """Test POST /api/auth/signup and GET /api/auth/me"""
        unique_email = "newathlete@ironmate.com"
        # Cleanup if exists from previous run
        existing = User.query.filter_by(email=unique_email).first()
        if existing:
            db.session.delete(existing)
            db.session.commit()

        # Signup
        res = self.client.post('/api/auth/signup', json={
            "name": "Alex Lift",
            "email": unique_email,
            "password": "securepassword123"
        })
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        token = data["token"]
        self.assertIsNotNone(token)

        # GET /api/auth/me with Bearer token
        headers = {"Authorization": f"Bearer {token}"}
        me_res = self.client.get('/api/auth/me', headers=headers)
        self.assertEqual(me_res.status_code, 200)
        me_data = me_res.get_json()
        self.assertEqual(me_data["user"]["email"], unique_email)
        print("✓ Signup and me endpoint passed")

    def test_04_products_and_filters(self):
        """Test GET /api/products with various filters and GET /api/products/<id>"""
        # List all
        res = self.client.get('/api/products')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertGreaterEqual(data["total"], 30)

        # Category filter (single and comma-separated)
        res_cat = self.client.get('/api/products?category=Weight')
        self.assertEqual(res_cat.status_code, 200)
        data_cat = res_cat.get_json()
        self.assertGreater(data_cat["total"], 0)
        for p in data_cat["products"]:
            self.assertIn("Weight", p["category"])

        res_multi = self.client.get('/api/products?category=Treadmill,Bike')
        self.assertEqual(res_multi.status_code, 200)
        self.assertGreater(res_multi.get_json()["total"], 0)

        # Search query
        res_search = self.client.get('/api/products?search=Dumbbell')
        self.assertEqual(res_search.status_code, 200)
        data_search = res_search.get_json()
        self.assertGreater(data_search["total"], 0)

        # Detail route
        prod_id = data["products"][0]["id"]
        res_detail = self.client.get(f'/api/products/{prod_id}')
        self.assertEqual(res_detail.status_code, 200)
        self.assertEqual(res_detail.get_json()["product"]["id"], prod_id)
        print("✓ Products catalog and filters passed")

    def test_05_cart_and_checkout_flow(self):
        """Test complete cart CRUD and checkout stock decrement flow"""
        # Login demo user
        login_res = self.client.post('/api/auth/login', json={
            "email": "demo@ironmate.com",
            "password": "demo1234"
        })
        token = login_res.get_json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Clear existing cart for clean test
        user = User.query.filter_by(email="demo@ironmate.com").first()
        CartItem.query.filter_by(user_id=user.id).delete()
        db.session.commit()

        # Pick a product with stock
        product = Product.query.filter(Product.stock >= 5).first()
        if not product:
            product = Product.query.first()
            product.stock = 20
            db.session.commit()
        initial_stock = product.stock

        # Add to cart
        add_res = self.client.post('/api/cart/add', headers=headers, json={
            "product_id": product.id,
            "quantity": 2
        })
        self.assertEqual(add_res.status_code, 200)

        # View cart
        cart_res = self.client.get('/api/cart', headers=headers)
        self.assertEqual(cart_res.status_code, 200)
        cart_data = cart_res.get_json()
        self.assertEqual(cart_data["item_count"], 2)
        self.assertAlmostEqual(cart_data["total"], round(product.price * 2, 2))

        # Update cart quantity
        update_res = self.client.put('/api/cart/update', headers=headers, json={
            "product_id": product.id,
            "quantity": 3
        })
        self.assertEqual(update_res.status_code, 200)
        cart_res2 = self.client.get('/api/cart', headers=headers)
        self.assertEqual(cart_res2.get_json()["item_count"], 3)

        # Checkout
        checkout_res = self.client.post('/api/orders/checkout', headers=headers)
        self.assertEqual(checkout_res.status_code, 201)
        checkout_data = checkout_res.get_json()
        self.assertEqual(checkout_data["order"]["status"], "Confirmed")

        # Verify stock decremented
        db.session.refresh(product)
        self.assertEqual(product.stock, initial_stock - 3)

        # Verify cart cleared
        cart_after = self.client.get('/api/cart', headers=headers)
        self.assertEqual(cart_after.get_json()["item_count"], 0)

        # Verify order history
        orders_res = self.client.get('/api/orders', headers=headers)
        self.assertEqual(orders_res.status_code, 200)
        orders_data = orders_res.get_json()
        self.assertGreater(orders_data["total"], 0)
        print("✓ Cart and checkout transaction flow passed")

    def test_06_general_rag_chat(self):
        """Test POST /api/chat with RAG retrieval and domain guardrails"""
        # Test 1: On-topic query
        res = self.client.post('/api/chat', json={
            "message": "What is your return policy and warranty on power racks?"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("reply", data)
        self.assertGreater(len(data["sources"]), 0)
        # Top sources should include Return Policy or Warranty
        top_cats = [s["category"] for s in data["sources"]]
        print(f"  RAG Retrieved Categories: {top_cats}")

        # Test 2: Off-topic query guardrail
        res_off = self.client.post('/api/chat', json={
            "message": "Write me a python script to calculate fibonacci numbers"
        })
        self.assertEqual(res_off.status_code, 200)
        off_data = res_off.get_json()
        self.assertIn("IronMate", off_data["reply"])
        print("✓ RAG chat and guardrails passed")

    def test_07_guided_plan_finder(self):
        """Test POST /api/plan-finder multi-turn flow and recommendation generation"""
        # Step 0 -> Asks question 1
        res1 = self.client.post('/api/plan-finder', json={"step": 0})
        self.assertEqual(res1.status_code, 200)
        data1 = res1.get_json()
        self.assertFalse(data1["completed"])
        self.assertEqual(data1["current_step"], 1)

        # Step 3 -> Asks question 4
        res3 = self.client.post('/api/plan-finder', json={
            "step": 3,
            "answers": {
                "goal": "muscle_gain",
                "space": "small",
                "experience": "beginner"
            }
        })
        data3 = res3.get_json()
        self.assertFalse(data3["completed"])
        self.assertEqual(data3["current_step"], 4)

        # Step 4 -> Returns recommendations
        res4 = self.client.post('/api/plan-finder', json={
            "step": 4,
            "answers": {
                "goal": "muscle_gain",
                "space": "small",
                "experience": "beginner",
                "budget": "300"
            }
        })
        data4 = res4.get_json()
        self.assertTrue(data4["completed"])
        self.assertGreater(len(data4["recommendations"]), 0)
        first_rec = data4["recommendations"][0]
        self.assertIn("id", first_rec)
        self.assertIn("name", first_rec)
        self.assertIn("reason", first_rec)
        print(f"  Plan Finder recommended: '{first_rec['name']}' (${first_rec['price']})")
        print("✓ Guided Plan Finder passed")

    def test_08_cart_aware_chat(self):
        """Test POST /api/chat/cart-aware endpoint"""
        login_res = self.client.post('/api/auth/login', json={
            "email": "demo@ironmate.com",
            "password": "demo1234"
        })
        token = login_res.get_json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Add dumbbell to cart
        dumbbells = Product.query.filter(Product.name.ilike("%dumbbell%")).first()
        self.client.post('/api/cart/add', headers=headers, json={
            "product_id": dumbbells.id,
            "quantity": 1
        })

        # Ask cart-aware assistant
        res = self.client.post('/api/chat/cart-aware', headers=headers, json={
            "message": "What should I add to complement my current equipment?"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("reply", data)
        self.assertIn("cart_summary", data)
        self.assertGreater(len(data["suggested_products"]), 0)
        print(f"  Cart-Aware suggested: {[s['name'] for s in data['suggested_products']]}")
        print("✓ Cart-aware chat endpoint passed")

    def test_09_static_serving_and_spa(self):
        """Test static asset serving, index.html at root, and SPA fallback / API 404 handling"""
        # Root / serves index.html
        res_root = self.client.get('/')
        self.assertEqual(res_root.status_code, 200)
        self.assertIn("IronMate", res_root.get_data(as_text=True))

        # CSS and JS
        res_css = self.client.get('/styles.css')
        self.assertEqual(res_css.status_code, 200)
        res_js = self.client.get('/app.js')
        self.assertEqual(res_js.status_code, 200)

        # Static product image
        res_img = self.client.get('/assets/products/weight-1.png')
        self.assertEqual(res_img.status_code, 200)

        # API 404 returns JSON
        res_api_404 = self.client.get('/api/nonexistent_route')
        self.assertEqual(res_api_404.status_code, 404)
        self.assertTrue(res_api_404.is_json)
        self.assertIn("error", res_api_404.get_json())

        # SPA fallback returns index.html for non-asset routes
        res_spa = self.client.get('/explore-deals')
        self.assertEqual(res_spa.status_code, 200)
        self.assertIn("IronMate", res_spa.get_data(as_text=True))
        print("✓ Static asset serving and SPA routing passed")

if __name__ == '__main__':
    unittest.main()
