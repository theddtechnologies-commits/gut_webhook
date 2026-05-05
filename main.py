from flask import Flask, request, jsonify
import json
import os
import requests

app = Flask(__name__)

# ================= CONFIG =================

APP_KEY = "73nywgsd0ab6hu4qz51ro2kfemt8xcpv"
APP_SECRET = "aaef5fe113c373a0a7ac4e8a6413c5b1c46c3a8b"
ACCESS_TOKEN = "23a33ca178836da5b3144ab299ef1bc2633e21f6"

REST_ID = "107556"

CREATE_URL = "https://pponlineordercb.petpooja.com/save_order"
CANCEL_URL = "https://pponlineordercb.petpooja.com/update_order_status"

CALLBACK_URL = "https://endpoint-rosy.vercel.app/api/webhook"

# ================= FIREBASE =================

db = None

try:
    import firebase_admin
    from firebase_admin import credentials, firestore

    firebase_env = os.environ.get("FIREBASE_SERVICE_ACCOUNT")

    if firebase_env:
        firebase_json = json.loads(firebase_env)
        firebase_json["private_key"] = firebase_json["private_key"].replace(
            "\\n", "\n")

        if not firebase_admin._apps:
            cred = credentials.Certificate(firebase_json)
            firebase_admin.initialize_app(cred)

        db = firestore.client()
        print("✅ Firebase initialized")

except Exception as e:
    print("❌ Firebase error:", e)


# ================= CREATE ORDER =================

@app.route("/api/create-order", methods=["POST"])
def create_order():
    try:
        body = request.json

        required = ["orderID", "name", "phone", "items"]
        for f in required:
            if f not in body:
                return jsonify({"error": f"{f} missing"}), 400

        order_id = str(body["orderID"])

        items = []
        for item in body["items"]:
            items.append({
                "id": str(item.get("id") or item.get("sku")),
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

        res = requests.post(CREATE_URL, json=payload, timeout=10)
        data = res.json()

        return jsonify({
            "success": True,
            "petpooja": data
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ================= CANCEL ORDER =================

@app.route("/api/cancel-order", methods=["POST"])
def cancel_order():
    try:
        body = request.json
        order_id = body.get("orderID")

        if not order_id:
            return jsonify({"error": "orderID required"}), 400

        payload = {
            "app_key": APP_KEY,
            "app_secret": APP_SECRET,
            "access_token": ACCESS_TOKEN,
            "restID": REST_ID,
            "clientorderID": order_id,
            "status": "-1",
            "cancelReason": body.get("reason", "User cancelled")
        }

        res = requests.post(CANCEL_URL, json=payload, timeout=10)

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ================= WEBHOOK =================

@app.route("/api/webhook", methods=["POST"])
def webhook():
    try:
        data = request.json

        print("🔔 WEBHOOK:", data)

        if not db:
            return jsonify({"warning": "No DB"})

        order_id = str(data.get("orderID"))

        user_id = order_id.split("_")[0] if "_" in order_id else "guest"

        order_data = {
            "orderID": order_id,
            "userId": user_id,
            "status": data.get("status"),
            "items": data.get("OrderItem", []),
            "total": data.get("order_total", 0),
            "updatedAt": firestore.SERVER_TIMESTAMP,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "source": "petpooja"
        }

        db.collection("orders").document(order_id).set(order_data, merge=True)

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
