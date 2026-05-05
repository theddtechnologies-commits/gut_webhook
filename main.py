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
    "1":  "Accepted by Kitchen",
    "2":  "Preparing",
    "4":  "Out for Delivery",
    "5":  "Ready for Pickup",
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


# ================= WOOCOMMERCE HELPER =================

def update_wc_order_status(order_id, status):
    try:
        order = wcapi.get(f"orders/{order_id}").json()
        if order:
            response = wcapi.put(
                f"orders/{order_id}", {"status": status}).json()
            print(
                f"✅ WooCommerce order {order_id} updated to '{status}': {response}")
        else:
            print(f"⚠️ WooCommerce order {order_id} not found.")
    except Exception as e:
        print(f"❌ Error updating WooCommerce order {order_id}: {e}")


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

            eid = item.get("id")

            # ✅ STRICT EID VALIDATION — no SKU fallback, fail hard
            if not eid or not str(eid).startswith("V"):
                print(f"❌ Invalid or missing Petpooja EID for item: {item}")
                return jsonify({
                    "error": f"Invalid Petpooja EID for item '{item.get('name')}' — got '{eid}'. Must start with 'V'."
                }), 400

            items.append({
                "id": str(eid),
                "name": item.get("name"),
                "price": float(item.get("price", 0)),
                "quantity": int(item.get("quantity", 1)),
                "tax_inclusive": 1
            })

        # ✅ FAIL FAST if no valid items
        if not items:
            return jsonify({"error": "No valid items to send"}), 400

        # ✅ DEBUG — log items before building payload
        print("🔥 FINAL ORDER ITEMS SENT TO PETPOOJA:")
        print(json.dumps(items, indent=2))

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

        # ✅ DEBUG — log full payload before sending
        print("📦 FULL PAYLOAD:")
        print(json.dumps(payload, indent=2))

        res = requests.post(CREATE_URL, json=payload, timeout=10)
        data = res.json()

        # ✅ DEBUG — log Petpooja response
        print("✅ PETPOOJA RESPONSE:")
        print(data)

        petpooja_id = data.get("clientorderID") or order_id

        if db and firestore_module:
            db.collection("orders").document(order_id).set({
                "orderID": order_id,
                "petpoojaID": petpooja_id,
                "userId": order_id.split("_")[0],
                "status": "pending",
                "statusLabel": "Order Placed",
                "items": items,
                "total": sum(i["price"] * i["quantity"] for i in items),
                "name": body["name"],
                "phone": body["phone"],
                "email": body.get("email", ""),
                "address": body.get("address", ""),
                "paymentMode": body.get("paymentMode", "COD"),
                "createdAt": firestore_module.SERVER_TIMESTAMP,
                "updatedAt": firestore_module.SERVER_TIMESTAMP,
                "source": "petpooja"
            }, merge=True)
            print(f"✅ Firebase order created: {order_id}")

        return jsonify({"success": True, "petpooja": data})

    except Exception as e:
        print(f"❌ create_order error: {e}")
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

        requests.post(CANCEL_URL, json=payload, timeout=10)

        if db and firestore_module:
            db.collection("orders").document(order_id).set({
                "status": "-1",
                "statusLabel": "Cancelled",
                "updatedAt": firestore_module.SERVER_TIMESTAMP
            }, merge=True)
            print(f"✅ Firebase order cancelled: {order_id}")

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ================= WEBHOOK (Petpooja → Firebase + WooCommerce) =================

@app.route("/api/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "message": "No data received"}), 400

        print("🔔 WEBHOOK:", data)

        order_id = str(data.get("orderID", ""))
        status = str(data.get("status", ""))
        label = STATUS_LABELS.get(status, status)

        # --- Update WooCommerce ---
        if order_id and status:
            if status in SKIP_STATUSES:
                print(
                    f"⏭️ Skipping WooCommerce update for order {order_id} (status {status})")
            else:
                wc_status = WC_STATUS_MAPPING.get(status)
                if wc_status:
                    update_wc_order_status(order_id, wc_status)
                else:
                    print(f"⚠️ No WooCommerce mapping for status '{status}'")

        # --- Update Firebase ---
        if db and firestore_module:
            user_id = order_id.split("_")[0] if "_" in order_id else "guest"

            db.collection("orders").document(order_id).set({
                "orderID":     order_id,
                "userId":      user_id,
                "status":      status,
                "statusLabel": label,
                "items":       data.get("OrderItem", []),
                "total":       data.get("order_total", 0),
                "updatedAt":   firestore_module.SERVER_TIMESTAMP,
                "source":      "petpooja"
            }, merge=True)
            print(f"✅ Firebase updated for order {order_id} → {label}")
        else:
            print("⚠️ Firebase not initialized, skipping DB write")

        return jsonify({
            "success": True,
            "message": "Webhook received and processed successfully",
            "receivedData": data
        }), 200

    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# ================= GET WEBHOOK DATA =================

@app.route("/api/webhook-data", methods=["GET"])
def get_webhook_data():
    try:
        if not db:
            return jsonify({"success": False, "message": "Firebase not initialized"}), 500

        orders = db.collection("orders").stream()
        data = [doc.to_dict() for doc in orders]

        return jsonify({"success": True, "data": data})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
