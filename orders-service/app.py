import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from sqlalchemy import create_engine, text

# ---------------------------
# DB CONFIG FROM SINGLE ENV VAR
# ---------------------------
DATABASE_URI = os.environ.get("DATABASE_URI")

if not DATABASE_URI:
    raise RuntimeError("DATABASE_URI must be set as an environment variable")

# SQLAlchemy engine
engine = create_engine(DATABASE_URI, future=True)

# Ensure table exists on startup
with engine.begin() as conn:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                user_id INT NOT NULL,
                product_id INT NOT NULL,
                qty INT NOT NULL
            )
            """
        )
    )

# ---------------------------
# FLASK APP
# ---------------------------
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})


@app.route("/", methods=["GET"])
def health():
    """Simple health check."""
    return jsonify({"status": "ok"}), 200


@app.route("/orders", methods=["GET"])
def get_orders():
    """Return all orders from Postgres."""
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, user_id, product_id, qty FROM orders ORDER BY id")
        ).mappings().all()
        return jsonify([dict(r) for r in rows]), 200


@app.route("/orders", methods=["POST"])
def create_order():
    """Create a new order and store in Postgres."""
    data = request.get_json(force=True) or {}
    user_id = int(data.get("user_id", 0))
    product_id = int(data.get("product_id", 0))
    qty = int(data.get("qty", 1))

    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO orders (user_id, product_id, qty)
                VALUES (:user_id, :product_id, :qty)
                RETURNING id, user_id, product_id, qty
                """
            ),
            {
                "user_id": user_id,
                "product_id": product_id,
                "qty": qty,
            },
        ).mappings().first()

    return jsonify(dict(row)), 201


if __name__ == "__main__":
    # IMPORTANT: orders service should listen on 5002 (matches K8s service/containerPort)
    app.run(host="0.0.0.0", port=5002)
