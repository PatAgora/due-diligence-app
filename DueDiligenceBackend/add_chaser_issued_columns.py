#!/usr/bin/env python3
"""
Add chaser issued date columns to reviews table
"""

import sqlite3
import os

def add_columns():
    db_path = 'Due Diligence/scrutinise_workflow.db'
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get existing columns
    cursor.execute("PRAGMA table_info(reviews)")
    existing_cols = {col[1] for col in cursor.fetchall()}
    
    # Columns to add (issued dates for when chasers are actually sent)
    new_columns = [
        ('outreach_chaser_issued1', 'TEXT'),  # When chaser 1 was issued
        ('outreach_chaser_issued2', 'TEXT'),  # When chaser 2 was issued
        ('outreach_chaser_issued3', 'TEXT'),  # When chaser 3 was issued
        ('outreach_ntc_issued', 'TEXT'),      # When NTC (Notice to Close) was issued
    ]
    
    added = 0
    skipped = 0
    
    print("=" * 80)
    print("ADDING CHASER ISSUED DATE COLUMNS")
    print("=" * 80)
    
    for col_name, col_type in new_columns:
        if col_name in existing_cols:
            print(f"  ⊘ Skipped (exists): {col_name}")
            skipped += 1
        else:
            cursor.execute(f"ALTER TABLE reviews ADD COLUMN {col_name} {col_type}")
            print(f"  ✓ Added: {col_name} ({col_type})")
            added += 1
    
    conn.commit()
    
    # Verify
    cursor.execute("PRAGMA table_info(reviews)")
    all_cols = cursor.fetchall()
    chaser_cols = [col for col in all_cols if 'chaser' in col[1].lower() or 'ntc' in col[1].lower()]
    
    print("\n" + "=" * 80)
    print("VERIFICATION: All Chaser/Outreach Columns")
    print("=" * 80)
    for col in chaser_cols:
        print(f"  • {col[1]:<35} {col[2]:<10}")
    
    conn.close()
    
    print("\n" + "=" * 80)
    print(f"✅ Migration Complete!")
    print(f"   Added: {added} columns")
    print(f"   Skipped: {skipped} columns (already exist)")
    print("=" * 80)

if __name__ == '__main__':
    add_columns()
