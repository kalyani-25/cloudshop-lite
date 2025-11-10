from flask import Flask, jsonify, request
app = Flask(__name__)
users = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]

@app.route("/users", methods=["GET"])
def get_users():
    return jsonify(users), 200

@app.route("/users", methods=["POST"])
def add_user():
    data = request.get_json(force=True)
    users.append({"id": len(users)+1, "name": data.get("name", f"user{len(users)+1}")})
    return jsonify({"message": "User added"}), 201

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
