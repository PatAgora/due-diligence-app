#!/usr/bin/env python3
"""Add case_summary column to reviews table"""

import sqlite3

db_path = "Due Diligence/scrutinise_workflow.db"

def add_case_summary_column():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if column already exists
    cursor.execute("PRAGMA table_info(reviews)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'case_summary' in columns:
        print("✅ case_summary column already exists")
        conn.close()
        return
    
    # Add case_summary column
    try:
        cursor.execute("ALTER TABLE reviews ADD COLUMN case_summary TEXT")
        conn.commit()
        print("✅ Added case_summary column to reviews table")
    except Exception as e:
        print(f"❌ Error adding column: {e}")
        conn.rollback()
    
    conn.close()

if __name__ == "__main__":
    print("Adding case_summary column...")
    add_case_summary_column()
    print("Migration complete!")
