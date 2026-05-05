import json
import os
import requests
import firebase_admin
from firebase_admin import credentials, firestore

# ================= CONFIG =================

APP_KEY = "73nywgsd0ab6hu4qz51ro2kfemt8xcpv"
APP_SECRET = "aaef5fe113c373a0a7ac4e8a6413c5b1c46c3a8b"
ACCESS_TOKEN = "23a33ca178836da5b3144ab299ef1bc2633e21f6"

REST_ID = "107556"

CREATE_URL = "https://pponlineordercb.petpooja.com/save_order"
CANCEL_URL = "https://pponlineordercb.petpooja.com/update_order_status"

CALLBACK_URL = "https://endpoint-rosy.vercel.app/api/webhook"

# ================= FIREBASE INIT =================

if not firebase_admin._apps:
    firebase_json = json.loads(os.environ.get("FIREBASE_SERVICE_ACCOUNT"))

    firebase_json["private_key"] = firebase_json["private_key"].replace(
        "\\n", "\n")

    cred = credentials.Certificate(firebase_json)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ================= MAIN HANDLER =================


def handler(request):
    try:
        path = request.path

        # 🔥 SAFE JSON PARSE (VERCEL FIX)
        try:
            raw_body = request.body
            data = json.loads(raw_body.decode("utf-8")) if raw_body else {}
            print("📩 Incoming:", data)
        except Exception as e:
            print("❌ JSON ERROR:", str(e))
            return response(400, {"error": "Invalid JSON"})

        if "/create-order" in path:
            return create_order(data)

        elif "/cancel-order" in path:
            return cancel_order(data)

        elif "/webhook" in path:
            return webhook_handler(data)

        else:
            return response(404, {"error": "Route not found"})

    except Exception as e:
        print("🔥 CRASH:", str(e))
        return response(500, {"error": str(e)})

# ================= CREATE ORDER =================


def create_order(body):
    try:
        required = ["orderID", "name", "phone", "items"]
        for f in required:
            if f not in body:
                return response(400, {"error": f"{f} missing"})

        order_id = str(body["orderID"])

        items = []
        for item in body["items"]:
            items.append({
                "id": str(item.get("id") or item.get("sku")),  # SKU fallback
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

        print("📦 Sending to Petpooja:", payload)

        res = requests.post(CREATE_URL, json=payload, timeout=10)
        data = res.json()

        print("✅ Petpooja:", data)

        if res.status_code != 200:
            return response(500, {"error": data})

        return response(200, {
            "success": True,
            "orderID": order_id,
            "petpooja": data
        })

    except Exception as e:
        print("❌ CREATE ERROR:", str(e))
        return response(500, {"error": str(e)})

# ================= CANCEL ORDER =================


def cancel_order(body):
    try:
        order_id = body.get("orderID")
        reason = body.get("reason", "User cancelled")

        if not order_id:
            return response(400, {"error": "orderID required"})

        payload = {
            "app_key": APP_KEY,
            "app_secret": APP_SECRET,
            "access_token": ACCESS_TOKEN,
            "restID": REST_ID,
            "clientorderID": order_id,
            "status": "-1",
            "cancelReason": reason
        }

        print("🚫 Cancel:", payload)

        res = requests.post(CANCEL_URL, json=payload, timeout=10)
        data = res.json()

        return response(200, {"success": True, "response": data})

    except Exception as e:
        print("❌ CANCEL ERROR:", str(e))
        return response(500, {"error": str(e)})

# ================= WEBHOOK =================


def webhook_handler(data):
    try:
        print("🔔 WEBHOOK:", data)

        orders = []

        if "orders" in data:
            orders = data["orders"]
        elif "orderID" in data:
            orders = [data]
        else:
            return response(200, {"message": "ignored"})

        for order in orders:
            order_id = str(order.get("orderID"))

            user_id = order_id.split("_")[0] if "_" in order_id else "guest"

            order_data = {
                "orderID": order_id,
                "userId": user_id,
                "status": order.get("status"),
                "items": order.get("OrderItem", []),
                "total": order.get("order_total", 0),
                "customerName": order.get("customer_name"),
                "customerPhone": order.get("customer_phone"),
                "updatedAt": firestore.SERVER_TIMESTAMP,
                "createdAt": firestore.SERVER_TIMESTAMP,
                "source": "petpooja",
                "payload": order
            }

            db.collection("orders").document(
                order_id).set(order_data, merge=True)

            db.collection("users").document(user_id)\
                .collection("orders").document(order_id)\
                .set(order_data, merge=True)

        return response(200, {"success": True})

    except Exception as e:
        print("❌ WEBHOOK ERROR:", str(e))
        return response(500, {"error": str(e)})

# ================= RESPONSE =================


def response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(body)
    }
