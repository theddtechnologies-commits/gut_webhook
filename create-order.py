import json
import requests

# ================= CONFIG =================

APP_KEY = "73nywgsd0ab6hu4qz51ro2kfemt8xcpv"
APP_SECRET = "aaef5fe113c373a0a7ac4e8a6413c5b1c46c3a8b"
ACCESS_TOKEN = "23a33ca178836da5b3144ab299ef1bc2633e21f6"

REST_ID = "107556"

PETPOOJA_URL = "https://pponlineordercb.petpooja.com/save_order"

# ✅ YOUR ACTUAL DOMAIN
CALLBACK_URL = "https://endpoint-rosy.vercel.app/api/main"


# ================= HANDLER =================

def handler(request):
    try:
        body = request.get_json()

        print("🔥 Incoming Order:", body)

        # ================= VALIDATION =================
        required_fields = ["orderID", "name", "phone", "items"]
        for field in required_fields:
            if field not in body:
                return {
                    "statusCode": 400,
                    "body": json.dumps({
                        "success": False,
                        "error": f"Missing field: {field}"
                    })
                }

        order_id = str(body["orderID"])

        # ================= SANITIZE ITEMS =================
        items = []
        for item in body["items"]:
            items.append({
                "id": str(item.get("id")),  # MUST be Petpooja item ID
                "name": item.get("name"),
                "price": float(item.get("price", 0)),
                "quantity": int(item.get("quantity", 1)),
                "tax_inclusive": 1
            })

        # ================= BUILD PAYLOAD =================
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

            # 🔥 PAYMENT MODE SUPPORT
            "payment_mode": body.get("paymentMode", "COD")  # COD / ONLINE
        }

        print("📦 Sending to Petpooja:", payload)

        # ================= API CALL =================
        response = requests.post(
            PETPOOJA_URL,
            json=payload,
            timeout=10
        )

        response_data = response.json()

        print("✅ Petpooja Response:", response_data)

        # ================= FAILURE HANDLING =================
        if response.status_code != 200:
            return {
                "statusCode": 500,
                "body": json.dumps({
                    "success": False,
                    "error": "Petpooja API failed",
                    "response": response_data
                })
            }

        return {
            "statusCode": 200,
            "body": json.dumps({
                "success": True,
                "message": "Order sent to Petpooja",
                "orderID": order_id,
                "petpooja_response": response_data
            })
        }

    except Exception as e:
        print("❌ ERROR:", str(e))

        return {
            "statusCode": 500,
            "body": json.dumps({
                "success": False,
                "error": str(e)
            })
        }
