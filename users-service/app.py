from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
# allow frontend on localhost and anywhere else (demo-safe)
CORS(app, resources={r"/*": {"origins": "*"}})

users = [
    {"id": 1, "name": "Alice"},
    {"id": 2, "name": "Bob"},
    {"id": 3, "name": "Charlie"},
    {"id": 4, "name": "Diana"},
    {"id": 5, "name": "Ethan"},
    {"id": 6, "name": "Fiona"},
    {"id": 7, "name": "George"},
    {"id": 8, "name": "Hannah"},
    {"id": 9, "name": "Ivan"},
    {"id": 10, "name": "Jasmine"},
]

# Nginx path:  /users/users  -> backend sees /users
@app.route("/users", methods=["GET"])
def get_users():
    return jsonify(users), 200

@app.route("/users", methods=["POST"])
def add_user():
    data = request.get_json(force=True)
    users.append({
        "id": len(users) + 1,
        "name": data.get("name", f"user{len(users)+1}")
    })
    return jsonify({"message": "User added"}), 201

# convenience root (Nginx won’t hit this, but ok)
@app.route("/", methods=["GET"])
def root_users():
    return jsonify(users), 200



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
