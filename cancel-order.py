import json
import requests

APP_KEY = "73nywgsd0ab6hu4qz51ro2kfemt8xcpv"
APP_SECRET = "aaef5fe113c373a0a7ac4e8a6413c5b1c46c3a8b"
ACCESS_TOKEN = "23a33ca178836da5b3144ab299ef1bc2633e21f6"

REST_ID = "107556"

CANCEL_URL = "https://pponlineordercb.petpooja.com/update_order_status"


def handler(request):
    try:
        body = request.get_json()

        order_id = body.get("orderID")
        reason = body.get("reason", "User cancelled order")

        if not order_id:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "orderID required"})
            }

        payload = {
            "app_key": APP_KEY,
            "app_secret": APP_SECRET,
            "access_token": ACCESS_TOKEN,

            "restID": REST_ID,

            # 🔥 IMPORTANT
            "clientorderID": order_id,

            "status": "-1",
            "cancelReason": reason
        }

        print("🔥 Cancelling Order:", payload)

        response = requests.post(CANCEL_URL, json=payload, timeout=10)
        data = response.json()

        print("✅ Cancel Response:", data)

        return {
            "statusCode": 200,
            "body": json.dumps({
                "success": True,
                "response": data
            })
        }

    except Exception as e:
        print("❌ ERROR:", str(e))

        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
