from flask import Flask, request, jsonify
from datetime import datetime
from database import get_connection, initialize_database

app = Flask(__name__)

API_TOKEN = "my-secure-api-token"
ALLOWED_STATUSES = ["pending", "in_progress", "completed"]


def log_request(endpoint):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    method = request.method
    print(f"[{timestamp}] {method} request to {endpoint}")


def is_authorized():
    auth_header = request.headers.get("Authorization")

    if not auth_header:
        return False

    expected_header = f"Bearer {API_TOKEN}"
    return auth_header == expected_header


@app.before_request
def require_authentication():
    public_endpoints = ["home"]

    if request.endpoint in public_endpoints:
        return

    if not is_authorized():
        return jsonify({"error": "Unauthorized. Missing or invalid token."}), 401


def validate_task_data(data, require_all_fields=True):
    if not data:
        return False, "Request body cannot be empty."

    title = data.get("title")
    description = data.get("description", "")
    status = data.get("status", "pending")

    if require_all_fields and not title:
        return False, "Title is required."

    if title is not None:
        if not isinstance(title, str):
            return False, "Title must be a string."

        if len(title.strip()) == 0:
            return False, "Title cannot be empty."

        if len(title) > 100:
            return False, "Title cannot exceed 100 characters."

    if description is not None:
        if not isinstance(description, str):
            return False, "Description must be a string."

        if len(description) > 300:
            return False, "Description cannot exceed 300 characters."

    if status is not None:
        if status not in ALLOWED_STATUSES:
            return False, "Status must be one of: pending, in_progress, completed."

    blocked_patterns = ["<script>", "DROP TABLE", "../", "--"]

    for value in [title, description]:
        if isinstance(value, str):
            for pattern in blocked_patterns:
                if pattern.lower() in value.lower():
                    return False, "Input contains blocked content."

    return True, "Valid data."


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "Secure REST API Task Manager is running.",
        "available_endpoints": [
            "GET /tasks",
            "GET /tasks/<id>",
            "POST /tasks",
            "PUT /tasks/<id>",
            "DELETE /tasks/<id>"
        ],
        "authentication": "Bearer token required for task endpoints."
    })


@app.route("/tasks", methods=["GET"])
def get_tasks():
    log_request("/tasks")

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM tasks")
    tasks = cursor.fetchall()

    connection.close()

    result = [dict(task) for task in tasks]

    return jsonify({
        "count": len(result),
        "tasks": result
    }), 200


@app.route("/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id):
    log_request(f"/tasks/{task_id}")

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()

    connection.close()

    if task is None:
        return jsonify({"error": "Task not found."}), 404

    return jsonify(dict(task)), 200


@app.route("/tasks", methods=["POST"])
def create_task():
    log_request("/tasks")

    data = request.get_json()

    is_valid, validation_message = validate_task_data(data)

    if not is_valid:
        return jsonify({"error": validation_message}), 400

    title = data.get("title").strip()
    description = data.get("description", "").strip()
    status = data.get("status", "pending")

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "INSERT INTO tasks (title, description, status) VALUES (?, ?, ?)",
        (title, description, status)
    )

    connection.commit()
    task_id = cursor.lastrowid
    connection.close()

    return jsonify({
        "message": "Task created successfully.",
        "task_id": task_id
    }), 201


@app.route("/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    log_request(f"/tasks/{task_id}")

    data = request.get_json()

    is_valid, validation_message = validate_task_data(data, require_all_fields=False)

    if not is_valid:
        return jsonify({"error": validation_message}), 400

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    existing_task = cursor.fetchone()

    if existing_task is None:
        connection.close()
        return jsonify({"error": "Task not found."}), 404

    title = data.get("title", existing_task["title"])
    description = data.get("description", existing_task["description"])
    status = data.get("status", existing_task["status"])

    cursor.execute(
        """
        UPDATE tasks
        SET title = ?, description = ?, status = ?
        WHERE id = ?
        """,
        (title, description, status, task_id)
    )

    connection.commit()
    connection.close()

    return jsonify({"message": "Task updated successfully."}), 200


@app.route("/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    log_request(f"/tasks/{task_id}")

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    existing_task = cursor.fetchone()

    if existing_task is None:
        connection.close()
        return jsonify({"error": "Task not found."}), 404

    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    connection.commit()
    connection.close()

    return jsonify({"message": "Task deleted successfully."}), 200


if __name__ == "__main__":
    initialize_database()
    app.run(host="127.0.0.1", port=5000, debug=True)