from flask import Flask, jsonify, request
import requests
app = Flask(__name__)
orders = []

@app.route("/orders", methods=["GET"])
def list_orders():
    return jsonify(orders), 200

@app.route("/orders", methods=["POST"])
def create_order():
    data = request.get_json(force=True)
    # (optional) touch catalog to prove service discovery works
    try:
        _ = requests.get("http://catalog:5002/products", timeout=3)
    except Exception:
        pass
    orders.append({
        "id": len(orders)+1,
        "user_id": data.get("user_id"),
        "product_id": data.get("product_id"),
        "qty": data.get("qty", 1)
    })
    return jsonify({"message": "Order created"}), 201

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003)

@app.route("/", methods=["GET"])
def root_orders():
    return jsonify(orders), 200
