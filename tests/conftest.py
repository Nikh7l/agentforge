"""Pytest fixtures shared across all tests."""

from __future__ import annotations

import os
import tempfile

import pytest

# Set a dummy API key for tests
os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
os.environ["DB_PATH"] = ":memory:"


@pytest.fixture
def sample_vulnerable_code():
    """Sample Python code with intentional issues across all categories."""
    return '''
import os
import pickle
import sqlite3

# SECURITY: Hardcoded secret
API_KEY = "sk-abc123secret456"
DB_PASSWORD = "admin123"

def get_user(user_id):
    """SECURITY: SQL injection vulnerability."""
    conn = sqlite3.connect("app.db")
    query = f"SELECT * FROM users WHERE id = '{user_id}'"
    result = conn.execute(query).fetchone()
    return result

def process_data(items):
    """PERFORMANCE: O(n^2) algorithm."""
    result = []
    for i in items:
        for j in items:
            if i != j:
                result.append((i, j))
    return result

def load_config(data):
    """SECURITY: Insecure deserialization."""
    return pickle.loads(data)

class DataManager:
    """ARCHITECTURE: God class doing too many things."""
    def __init__(self):
        self.data = []
        self.cache = {}
        self.conn = None
        self.logger = None

    def connect(self):
        self.conn = sqlite3.connect("app.db")

    def fetch_all(self):
        return self.conn.execute("SELECT * FROM data").fetchall()

    def process(self, items):
        """CORRECTNESS: potential None access."""
        total = 0
        for item in items:
            total += item["value"]  # May raise KeyError
        return total / len(items)  # ZeroDivisionError if empty

    def save(self, data):
        self.conn.execute("INSERT INTO data VALUES (?)", (data,))
        self.conn.commit()

    def export_csv(self, filename):
        data = self.fetch_all()
        with open(filename, "w") as f:
            for row in data:
                f.write(",".join(str(x) for x in row))

    def send_email(self, to, subject, body):
        os.system(f"mail -s '{subject}' {to} <<< '{body}'")  # SECURITY: command injection

    def calculate_stats(self):
        data = self.fetch_all()
        result = {}
        for row in data:
            if row[0] in result:
                result[row[0]] += row[1]
            else:
                result[row[0]] = row[1]
        return result
'''


@pytest.fixture
def sample_clean_code():
    """Sample clean Python code with minimal issues."""
    return '''
def fibonacci(n: int) -> int:
    """Calculate the nth Fibonacci number.

    Args:
        n: The position in the sequence (0-indexed).

    Returns:
        The nth Fibonacci number.

    Raises:
        ValueError: If n is negative.
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    if n <= 1:
        return n

    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b
'''


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    from agentforge.models.database import init_db

    init_db(db_path)

    yield db_path

    os.unlink(db_path)
