import json
import os
import firebase_admin
from firebase_admin import credentials, firestore
from woocommerce import API
from flask import Flask, request, jsonify

app = Flask(__name__)

# ================= FIREBASE INIT =================
if not firebase_admin._apps:
    firebase_json = json.loads(os.environ.get("FIREBASE_SERVICE_ACCOUNT"))

    firebase_json["private_key"] = firebase_json["private_key"].replace(
        "\\n", "\n")

    cred = credentials.Certificate(firebase_json)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ================= WOOCOMMERCE =================
wcapi = API(
    url="https://gutmantra.in",
    consumer_key="ck_4dfb44306941ede97fb309dc441abfa42c3fdc87",
    consumer_secret="cs_d2808f39b2879c7a4a18d30db43c77dd036a61e7",
    version="wc/v3"
)

status_mapping = {
    "1": "processing",
    "2": "processing",
    "3": "processing",
    "10": "completed",
    "-1": "cancelled"
}

# ================= WEBHOOK =================


@app.route("/api/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()

        print("🔥 WEBHOOK RECEIVED:", data)

        if not data:
            return jsonify({"error": "No data"}), 400

        # ================= HANDLE MULTIPLE ORDERS =================
        orders = []

        if "orders" in data:
            orders = data["orders"]
        elif "orderID" in data:
            orders = [data]
        else:
            print("📦 Not an order webhook")
            return jsonify({"message": "Ignored"}), 200

        # ================= PROCESS =================
        for order in orders:
            order_id = str(order.get("orderID"))

            if not order_id:
                continue

            user_id = order_id.split("_")[0] if "_" in order_id else "guest"

            customer = order.get("customer", {}) or order.get("Customer", {})
            order_info = order.get("Order", {}) or {}

            order_items = (
                order.get("items")
                or order.get("OrderItem")
                or []
            )

            total = (
                order.get("order_total")
                or order_info.get("total")
                or 0
            )

            order_data = {
                "orderID": order_id,
                "userId": user_id,
                "status": order.get("status"),
                "items": order_items,
                "total": total,
                "customerName": customer.get("name") or order.get("customer_name"),
                "customerPhone": customer.get("phone") or order.get("customer_phone"),
                "updatedAt": firestore.SERVER_TIMESTAMP,
                "createdAt": firestore.SERVER_TIMESTAMP,
                "source": "petpooja",
                "payload": order
            }

            print(f"💾 Saving Order: {order_id}")

            # FIRESTORE SAVE
            db.collection("orders").document(
                order_id).set(order_data, merge=True)

            db.collection("users").document(user_id)\
                .collection("orders").document(order_id)\
                .set(order_data, merge=True)

            # WOOCOMMERCE UPDATE
            status = str(order.get("status"))

            if status not in ["5", "4"]:
                wc_status = status_mapping.get(status)

                if wc_status:
                    try:
                        wcapi.put(f"orders/{order_id}", {"status": wc_status})
                        print(f"✅ Woo updated {order_id} → {wc_status}")
                    except Exception as e:
                        print("❌ Woo error:", e)

        return jsonify({"success": True}), 200

    except Exception as e:
        print("❌ ERROR:", str(e))
        return jsonify({"error": str(e)}), 500


# REQUIRED FOR VERCEL
app = app
