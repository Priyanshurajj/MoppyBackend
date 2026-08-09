import os
import sys

# Ensure backend directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.session import engine
from sqlalchemy import text

# Connect without transaction block for ALTER TYPE
with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
    try:
        conn.execute(text("ALTER TYPE bookingstatus ADD VALUE IF NOT EXISTS 'PENDING';"))
        print("Successfully added PENDING to bookingstatus")
    except Exception as e:
        print("Error:", e)
