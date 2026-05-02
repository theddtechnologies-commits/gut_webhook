from flask import Flask, request, jsonify, render_template
from woocommerce import API

app = Flask(__name__)

# WooCommerce API credentials
wcapi = API(
    url="https://gutmantra.in",  # Use https if possible
    consumer_key="ck_4dfb44306941ede97fb309dc441abfa42c3fdc87",
    consumer_secret="cs_d2808f39b2879c7a4a18d30db43c77dd036a61e7",
    version="wc/v3"
)

status_mapping = {
    "1": "processing",  # Accepted
    "10": "completed",   # Delivered
    "-1": "cancelled"    # Cancelled
}

webhook_data = []


@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "message": "No data received"}), 400

        webhook_data.append(data)
        print("Received webhook data:", data)

        order_id = data.get("orderID")
        status = data.get("status")

        if order_id and status:
            # Skip updating the order if status is 5 (Ready) or 4 (Dispatched)
            if status not in ["5", "4"]:
                # Map the status from webhook to WooCommerce order status
                wc_status = status_mapping.get(status)
                if wc_status:
                    # Update WooCommerce order status
                    update_order_status(order_id, wc_status)
            else:
                print(f"Skipped updating order {
                      order_id} because status is {status}")

        return jsonify({
            "success": True,
            "message": "Webhook received and processed successfully",
            "receivedData": data
        }), 200

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({
            "success": False,
            "message": "Error processing webhook"
        }), 500


def update_order_status(order_id, status):
    try:
        # Fetch the WooCommerce order by orderID
        order = wcapi.get(f"orders/{order_id}").json()

        if order:
            # Update the order status
            response = wcapi.put(f"orders/{order_id}", {
                "status": status
            }).json()

            print(f"Updated order {order_id} to status {status}: {response}")
        else:
            print(f"Order {order_id} not found.")
    except Exception as e:
        print(f"Error updating order {order_id}: {e}")


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/get-webhook-data', methods=['GET'])
def get_webhook_data():
    return jsonify({
        "success": True,
        "message": "Fetched webhook data successfully",
        "data": webhook_data
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
