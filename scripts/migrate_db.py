#!/usr/bin/env python3
"""
Database migration script to add missing base_url column
"""
import sqlite3
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

DB_PATH = Path(__file__).parent.parent / "data" / "settings.db"

def check_column_exists(cursor, table_name, column_name):
    """Check if a column exists in a table"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns

def main():
    print(f"Checking database at: {DB_PATH}")

    if not DB_PATH.exists():
        print(f"❌ Database file not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check current schema
        print("\n📋 Current llm_settings table schema:")
        cursor.execute("PRAGMA table_info(llm_settings)")
        columns = cursor.fetchall()
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")

        # Check if base_url column exists
        has_base_url = check_column_exists(cursor, "llm_settings", "base_url")

        if has_base_url:
            print("\n✅ base_url column already exists")
        else:
            print("\n⚠️  base_url column is missing. Adding it now...")

            # Add base_url column
            cursor.execute("""
                ALTER TABLE llm_settings
                ADD COLUMN base_url TEXT
            """)
            conn.commit()

            print("✅ Successfully added base_url column")

            # Verify the change
            print("\n📋 Updated table schema:")
            cursor.execute("PRAGMA table_info(llm_settings)")
            columns = cursor.fetchall()
            for col in columns:
                print(f"  - {col[1]} ({col[2]})")

        # Show current data
        cursor.execute("SELECT COUNT(*) FROM llm_settings")
        count = cursor.fetchone()[0]
        print(f"\n📊 Total records in llm_settings: {count}")

        if count > 0:
            cursor.execute("""
                SELECT user_id, tenant, provider, model, base_url
                FROM llm_settings
            """)
            print("\nCurrent records:")
            for row in cursor.fetchall():
                print(f"  - user_id={row[0]}, tenant={row[1]}, provider={row[2]}, model={row[3]}, base_url={row[4]}")

    except Exception as e:
        print(f"\n❌ Error during migration: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    main()
