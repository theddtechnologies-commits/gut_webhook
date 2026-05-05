import json
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ================= CONFIG =================

APP_KEY = "73nywgsd0ab6hu4qz51ro2kfemt8xcpv"
APP_SECRET = "aaef5fe113c373a0a7ac4e8a6413c5b1c46c3a8b"
ACCESS_TOKEN = "23a33ca178836da5b3144ab299ef1bc2633e21f6"

REST_ID = "107556"

CANCEL_URL = "https://pponlineordercb.petpooja.com/update_order_status"


# ================= ROUTE =================

@app.route("/api/cancel-order", methods=["POST"])
def cancel_order():
    try:
        body = request.get_json()

        print("🔥 Cancel Request:", body)

        order_id = body.get("orderID")
        reason = body.get("reason", "User cancelled order")

        if not order_id:
            return jsonify({
                "success": False,
                "error": "orderID required"
            }), 400

        # ================= PAYLOAD =================
        payload = {
            "app_key": APP_KEY,
            "app_secret": APP_SECRET,
            "access_token": ACCESS_TOKEN,

            "restID": REST_ID,

            # IMPORTANT: this is YOUR order ID
            "clientorderID": str(order_id),

            "status": "-1",
            "cancelReason": reason
        }

        print("📦 Sending Cancel to Petpooja:", payload)

        # ================= API CALL =================
        response = requests.post(
            CANCEL_URL,
            json=payload,
            timeout=10
        )

        response_data = response.json()

        print("📩 Petpooja Cancel Response:", response_data)

        # ================= STRICT CHECK =================
        if (
            response.status_code != 200 or
            response_data.get("success") == False or
            response_data.get("status") == "failed"
        ):
            return jsonify({
                "success": False,
                "error": "Cancel failed at Petpooja",
                "response": response_data
            }), 500

        return jsonify({
            "success": True,
            "message": "Order cancelled successfully",
            "orderID": order_id,
            "petpooja_response": response_data
        }), 200

    except Exception as e:
        print("❌ ERROR:", str(e))

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# REQUIRED FOR VERCEL
app = app
