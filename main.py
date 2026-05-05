from flask import Flask, request, jsonify
from woocommerce import API
import json
import os
import requests

app = Flask(__name__)

# ================= WOOCOMMERCE CONFIG =================

wcapi = API(
    url="https://gutmantra.in",
    consumer_key="ck_4dfb44306941ede97fb309dc441abfa42c3fdc87",
    consumer_secret="cs_d2808f39b2879c7a4a18d30db43c77dd036a61e7",
    version="wc/v3"
)

WC_STATUS_MAPPING = {
    "1": "processing",
    "10": "completed",
    "-1": "cancelled"
}

SKIP_STATUSES = ["5", "4"]

STATUS_LABELS = {
    "pending": "Order Placed",
    "1": "Accepted by Kitchen",
    "2": "Preparing",
    "4": "Out for Delivery",
    "5": "Ready for Pickup",
    "10": "Delivered",
    "-1": "Cancelled",
}

# ================= PETPOOJA CONFIG =================

APP_KEY = "73nywgsd0ab6hu4qz51ro2kfemt8xcpv"
APP_SECRET = "aaef5fe113c373a0a7ac4e8a6413c5b1c46c3a8b"
ACCESS_TOKEN = "23a33ca178836da5b3144ab299ef1bc2633e21f6"

REST_ID = "107556"

CREATE_URL = "https://pponlineordercb.petpooja.com/save_order"
CANCEL_URL = "https://pponlineordercb.petpooja.com/update_order_status"

CALLBACK_URL = "https://endpoint-rosy.vercel.app/api/webhook"

# ================= FIREBASE =================

db = None
firestore_module = None

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
        firestore_module = firestore
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

        # 🔥 STRICT ITEM VALIDATION
        items = []
        for item in body["items"]:
            eid = item.get("id")

            if not eid or not str(eid).startswith("V"):
                return jsonify({
                    "error": f"Invalid EID for item {item.get('name')}: {eid}"
                }), 400

            items.append({
                "id": str(eid),
                "name": item.get("name"),
                "price": str(item.get("price")),      # ✅ STRING
                "quantity": str(item.get("quantity")),  # ✅ STRING
                "tax_inclusive": 1                    # ✅ REQUIRED
            })

        print("🔥 FINAL ITEMS →", json.dumps(items, indent=2))

        # 🔥 FINAL PAYLOAD
        payload = {
            "app_key": APP_KEY,
            "app_secret": APP_SECRET,
            "access_token": ACCESS_TOKEN,
            "restID": REST_ID,
            "device_type": "Android",   # ✅ safer than Web
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
                    "preorder_date": ""   # ✅ IMPORTANT
                },
                "OrderItem": items
            },
            "payment_mode": body.get("paymentMode", "COD")
        }

        print("📦 PAYLOAD →")
        print(json.dumps(payload, indent=2))

        res = requests.post(CREATE_URL, json=payload, timeout=10)

        try:
            data = res.json()
        except:
            data = {"raw": res.text}

        print("📡 STATUS:", res.status_code)
        print("📡 RESPONSE:", data)

        # ❌ HARD FAIL if Petpooja rejects
        if res.status_code != 200 or data.get("success") != "1":
            return jsonify({
                "success": False,
                "petpooja_error": data
            }), 400

        # ✅ SAVE TO FIREBASE
        if db and firestore_module:
            db.collection("orders").document(order_id).set({
                "orderID": order_id,
                "petpoojaID": data.get("clientorderID"),
                "userId": order_id.split("_")[0],
                "status": "pending",
                "statusLabel": "Order Placed",
                "items": items,
                "total": sum(float(i["price"]) * int(i["quantity"]) for i in items),
                "name": body["name"],
                "phone": body["phone"],
                "address": body.get("address", ""),
                "paymentMode": body.get("paymentMode", "COD"),
                "createdAt": firestore_module.SERVER_TIMESTAMP,
                "updatedAt": firestore_module.SERVER_TIMESTAMP,
                "source": "petpooja"
            }, merge=True)

            print(f"✅ Firebase order saved: {order_id}")

        return jsonify({
            "success": True,
            "petpooja": data
        })

    except Exception as e:
        print("❌ ERROR:", e)
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
        data = res.json()

        print("🚫 CANCEL RESPONSE:", data)

        return jsonify({"success": True, "response": data})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ================= WEBHOOK =================

@app.route("/api/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        print("🔔 WEBHOOK:", data)

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
