"""
Sample "bad code" file with intentional vulnerabilities for demoing AgentForge.

Run this through AgentForge to see all agents in action:
    python -m agentforge.cli.main review samples/vulnerable_app.py
"""

import hashlib
import os
import pickle
import sqlite3
from typing import Any

# ═══════════════════════════════════════════════════════════════════════
# SECURITY ISSUES
# ═══════════════════════════════════════════════════════════════════════

# Hardcoded credentials
DATABASE_URL = "postgresql://admin:password123@prod-db.internal:5432/myapp"
API_SECRET = "sk-live-abc123def456ghi789"
JWT_SECRET = "supersecretkey"


def authenticate_user(username: str, password: str) -> bool:
    """Authenticate a user — multiple security flaws."""
    conn = sqlite3.connect("users.db")

    # SQL Injection: string formatting in query
    query = f"SELECT password_hash FROM users WHERE username = '{username}'"
    result = conn.execute(query).fetchone()

    if result is None:
        return False

    # Weak hashing: using MD5 for passwords
    password_hash = hashlib.md5(password.encode()).hexdigest()
    return result[0] == password_hash


def load_user_session(session_data: bytes) -> dict:
    """Load session — insecure deserialization."""
    return pickle.loads(session_data)  # Arbitrary code execution risk


def run_system_command(user_input: str) -> str:
    """Execute a system command — command injection."""
    return os.popen(f"echo {user_input}").read()


# ═══════════════════════════════════════════════════════════════════════
# PERFORMANCE ISSUES
# ═══════════════════════════════════════════════════════════════════════


def find_duplicates(items: list) -> list:
    """Find duplicate items — O(n²) when O(n) is possible."""
    duplicates = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if items[i] == items[j] and items[i] not in duplicates:
                duplicates.append(items[i])
    return duplicates


def get_user_orders(user_ids: list[int]) -> list[dict]:
    """Fetch orders for multiple users — N+1 query pattern."""
    conn = sqlite3.connect("orders.db")
    results = []
    for user_id in user_ids:
        # One query per user instead of a single batch query
        orders = conn.execute(f"SELECT * FROM orders WHERE user_id = {user_id}").fetchall()
        results.extend(orders)
    conn.close()
    return results


def compute_fibonacci(n: int) -> int:
    """Recursive fibonacci — exponential time complexity."""
    if n <= 1:
        return n
    return compute_fibonacci(n - 1) + compute_fibonacci(n - 2)


def process_large_file(filepath: str) -> list[str]:
    """Process a file — reads entire file into memory."""
    with open(filepath) as f:
        content = f.read()  # Could be gigabytes
    lines = content.split("\n")
    results = []
    for line in lines:
        processed = line.strip().upper()
        results.append(processed)
    return results


# ═══════════════════════════════════════════════════════════════════════
# ARCHITECTURE ISSUES
# ═══════════════════════════════════════════════════════════════════════


class AppManager:
    """God class — violates Single Responsibility Principle."""

    def __init__(self):
        self.db = sqlite3.connect("app.db")
        self.cache = {}
        self.email_queue = []
        self.log_buffer = []

    # Database operations
    def create_user(self, name, email):
        self.db.execute("INSERT INTO users VALUES (?, ?)", (name, email))
        self.db.commit()

    def get_user(self, user_id):
        return self.db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    # Email operations (should be separate service)
    def send_email(self, to, subject, body):
        self.email_queue.append({"to": to, "subject": subject, "body": body})
        os.system(f"sendmail {to}")

    def process_email_queue(self):
        for email in self.email_queue:
            print(f"Sending to {email['to']}")
        self.email_queue.clear()

    # Caching (should be separate service)
    def cache_set(self, key, value):
        self.cache[key] = value

    def cache_get(self, key):
        return self.cache.get(key)

    # Logging (should use logging module)
    def log(self, message):
        self.log_buffer.append(message)
        print(message)

    # Report generation (should be separate module)
    def generate_report(self, report_type):
        if report_type == "users":
            data = self.db.execute("SELECT * FROM users").fetchall()
        elif report_type == "orders":
            data = self.db.execute("SELECT * FROM orders").fetchall()
        elif report_type == "products":
            data = self.db.execute("SELECT * FROM products").fetchall()
        return data

    # Payment processing (should definitely be separate!)
    def process_payment(self, amount, card_number):
        self.log(f"Processing payment of {amount}")
        # Logging sensitive data!
        self.log(f"Card: {card_number}")
        return True


# ═══════════════════════════════════════════════════════════════════════
# CORRECTNESS ISSUES
# ═══════════════════════════════════════════════════════════════════════


def calculate_average(numbers: list) -> float:
    """Calculate average — division by zero risk."""
    return sum(numbers) / len(numbers)  # Crashes on empty list


def find_element(data: dict, key: str) -> Any:
    """Find a nested element — no null checks."""
    return data["level1"]["level2"]["level3"][key]  # KeyError chain


def parse_config(config_str: str) -> dict:
    """Parse configuration — swallowed exceptions."""
    try:
        parts = config_str.split("=")
        return {parts[0]: parts[1]}
    except Exception:
        pass  # Silently ignoring all errors, returns None


def merge_lists(list_a: list, list_b: list) -> list:
    """Merge two sorted lists — off-by-one error."""
    result = []
    i, j = 0, 0
    while i <= len(list_a) and j <= len(list_b):  # Should be < not <=
        if i == len(list_a):
            result.extend(list_b[j:])
            break
        if j == len(list_b):
            result.extend(list_a[i:])
            break
        if list_a[i] <= list_b[j]:
            result.append(list_a[i])
            i += 1
        else:
            result.append(list_b[j])
            j += 1
    return result


def update_inventory(items: dict, sold: str, quantity: int) -> None:
    """Update inventory — mutation bug."""
    items[sold] -= quantity  # No check if item exists or if quantity > stock
    if items[sold] == 0:
        del items[sold]  # Modifying dict during potential iteration
