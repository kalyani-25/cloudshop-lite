from flask import Flask, jsonify
app = Flask(__name__)

products = [{"id": 101, "name": "Laptop"}, {"id": 102, "name": "Headphones"}]

@app.route("/", methods=["GET"])
def root():
    return jsonify(products), 200

@app.route("/products", methods=["GET"])
def get_products():
    return jsonify(products), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
