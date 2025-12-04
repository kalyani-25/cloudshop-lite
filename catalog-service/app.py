from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

PRODUCTS = [
    {"id": 101, "name": "Laptop"},
    {"id": 102, "name": "Headphones"},
    {"id": 103, "name": "Smartphone"},
    {"id": 104, "name": "Keyboard"},
    {"id": 105, "name": "Mouse"},
    {"id": 106, "name": "Monitor"},
    {"id": 107, "name": "Webcam"},
    {"id": 108, "name": "USB-C Hub"},
    {"id": 109, "name": "External SSD"},
    {"id": 110, "name": "Gaming Chair"},
]

# Support BOTH /products and /catalog/products
@app.route("/products", methods=["GET"])
@app.route("/catalog/products", methods=["GET"])
def get_products():
    return jsonify(PRODUCTS), 200

# Optional: root returns same data
@app.route("/", methods=["GET"])
def root():
    return jsonify(PRODUCTS), 200



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)

