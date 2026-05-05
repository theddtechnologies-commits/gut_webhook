import json
import os
import requests
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, request, jsonify

app = Flask(__name__)

# ================= FIREBASE INIT =================

if not firebase_admin._apps:
    firebase_env = os.environ.get("FIREBASE_SERVICE_ACCOUNT")

    if not firebase_env:
        raise Exception("FIREBASE_SERVICE_ACCOUNT missing")

    firebase_json = json.loads(firebase_env)
    firebase_json["private_key"] = firebase_json["private_key"].replace(
        "\\n", "\n")

    cred = credentials.Certificate(firebase_json)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ================= PETPOOJA CONFIG =================

APP_KEY = "73nywgsd0ab6hu4qz51ro2kfemt8xcpv"
APP_SECRET = "aaef5fe113c373a0a7ac4e8a6413c5b1c46c3a8b"
ACCESS_TOKEN = "23a33ca178836da5b3144ab299ef1bc2633e21f6"

REST_ID = "107556"

SAVE_ORDER_URL = "https://pponlineordercb.petpooja.com/save_order"
CANCEL_URL = "https://pponlineordercb.petpooja.com/update_order_status"

CALLBACK_URL = "https://endpoint-rosy.vercel.app/api/webhook"

# ================= STATUS MAP =================

status_mapping = {
    "1": "processing",
    "2": "processing",
    "3": "processing",
    "10": "completed",
    "-1": "cancelled"
}

# =========================================================
# 🔥 CREATE ORDER
# =========================================================


@app.route("/api/create-order", methods=["POST"])
def create_order():
    try:
        body = request.get_json()

        print("🔥 Incoming Order:", body)

        order_id = str(body["orderID"])

        items = []
        for item in body["items"]:
            items.append({
                "id": str(item.get("id")),  # MUST be Petpooja ID
                "name": item.get("name"),
                "price": float(item.get("price", 0)),
                "quantity": int(item.get("quantity", 1)),
                "tax_inclusive": 1
            })

        payload = {
            "app_key": APP_KEY,
            "app_secret": APP_SECRET,
            "access_token": ACCESS_TOKEN,
            "restID": REST_ID,
            "device_type": "Web",
            "callback_url": CALLBACK_URL,
            "OrderInfo": {
                "Customer": {
                    "name": body["name"],
                    "phone": body["phone"],
                    "email": body.get("email", ""),
                    "address": body.get("address", "")
                },
                "Order": {
                    "orderID": order_id,
                    "preorder_date": ""
                },
                "OrderItem": items
            },
            "payment_mode": body.get("paymentMode", "COD")
        }

        res = requests.post(SAVE_ORDER_URL, json=payload, timeout=10)
        data = res.json()

        print("📩 Petpooja Response:", data)

        if res.status_code != 200:
            return jsonify({"success": False, "error": data}), 500

        return jsonify({"success": True, "orderID": order_id})

    except Exception as e:
        print("❌ ERROR:", str(e))
        return jsonify({"error": str(e)}), 500


# =========================================================
# 🔥 WEBHOOK (Petpooja → Firestore)
# =========================================================

@app.route("/api/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()

        print("🔥 WEBHOOK:", data)

        orders = []

        if "orders" in data:
            orders = data["orders"]
        elif "orderID" in data:
            orders = [data]
        else:
            return jsonify({"message": "ignored"}), 200

        for order in orders:
            order_id = str(order.get("orderID"))

            user_id = order_id.split("_")[0] if "_" in order_id else "guest"

            order_data = {
                "orderID": order_id,
                "userId": user_id,
                "status": order.get("status"),
                "items": order.get("items") or order.get("OrderItem") or [],
                "total": order.get("order_total", 0),
                "updatedAt": firestore.SERVER_TIMESTAMP,
                "createdAt": firestore.SERVER_TIMESTAMP,
                "payload": order
            }

            # SAVE GLOBAL
            db.collection("orders").document(
                order_id).set(order_data, merge=True)

            # SAVE USER
            db.collection("users").document(user_id)\
                .collection("orders").document(order_id)\
                .set(order_data, merge=True)

        return jsonify({"success": True})

    except Exception as e:
        print("❌ ERROR:", str(e))
        return jsonify({"error": str(e)}), 500


# =========================================================
# 🔥 CANCEL ORDER
# =========================================================

@app.route("/api/cancel-order", methods=["POST"])
def cancel_order():
    try:
        body = request.get_json()

        order_id = body.get("orderID")
        reason = body.get("reason", "User cancelled")

        payload = {
            "app_key": APP_KEY,
            "app_secret": APP_SECRET,
            "access_token": ACCESS_TOKEN,
            "restID": REST_ID,
            "clientorderID": str(order_id),
            "status": "-1",
            "cancelReason": reason
        }

        res = requests.post(CANCEL_URL, json=payload, timeout=10)
        data = res.json()

        print("🔥 Cancel Response:", data)

        return jsonify({"success": True, "response": data})

    except Exception as e:
        print("❌ ERROR:", str(e))
        return jsonify({"error": str(e)}), 500


# REQUIRED FOR VERCEL
app = app
