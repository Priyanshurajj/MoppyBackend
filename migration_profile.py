import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.session import engine
from sqlalchemy import text

with engine.begin() as conn:
    try:
        # Add profile_pic to users table
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_pic VARCHAR(500);"))
        print("Added profile_pic to users table.")
    except Exception as e:
        print("Error altering users table:", e)

    try:
        # Create user_addresses table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_addresses (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                tag VARCHAR(50),
                address TEXT NOT NULL,
                lat FLOAT,
                lng FLOAT,
                is_default BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
        """))
        print("Created user_addresses table.")
    except Exception as e:
        print("Error creating user_addresses table:", e)
