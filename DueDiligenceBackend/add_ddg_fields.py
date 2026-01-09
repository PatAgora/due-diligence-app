#!/usr/bin/env python3
"""
Add Due Diligence, Screening, Outreach, and Decision fields to reviews table
"""

import sqlite3
import os

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), "Due Diligence/scrutinise_workflow.db")

def add_ddg_fields():
    """Add all required DDG fields to reviews table"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # DDG sections: idv, nob, income, expenditure, structure, ta, sof, sow
    ddg_sections = ['idv', 'nob', 'income', 'expenditure', 'structure', 'ta', 'sof', 'sow']
    
    print("🔧 Adding Due Diligence fields to reviews table...")
    
    fields_added = 0
    fields_skipped = 0
    
    # For each DDG section, add: rationale, outreach_required, section_completed
    for section in ddg_sections:
        # Rationale field
        try:
            cur.execute(f"ALTER TABLE reviews ADD COLUMN {section}_rationale TEXT")
            print(f"  ✅ Added {section}_rationale")
            fields_added += 1
        except sqlite3.OperationalError as e:
            if 'duplicate column' in str(e).lower():
                print(f"  ⏭️  {section}_rationale already exists")
                fields_skipped += 1
            else:
                raise
        
        # Outreach required checkbox
        try:
            cur.execute(f"ALTER TABLE reviews ADD COLUMN {section}_outreach_required INTEGER DEFAULT 0")
            print(f"  ✅ Added {section}_outreach_required")
            fields_added += 1
        except sqlite3.OperationalError as e:
            if 'duplicate column' in str(e).lower():
                print(f"  ⏭️  {section}_outreach_required already exists")
                fields_skipped += 1
            else:
                raise
        
        # Section completed checkbox
        try:
            cur.execute(f"ALTER TABLE reviews ADD COLUMN {section}_section_completed INTEGER DEFAULT 0")
            print(f"  ✅ Added {section}_section_completed")
            fields_added += 1
        except sqlite3.OperationalError as e:
            if 'duplicate column' in str(e).lower():
                print(f"  ⏭️  {section}_section_completed already exists")
                fields_skipped += 1
            else:
                raise
    
    # FinCrime concerns fields
    print("\n🔒 Adding FinCrime concern fields...")
    try:
        cur.execute("ALTER TABLE reviews ADD COLUMN sar_rationale TEXT")
        print("  ✅ Added sar_rationale")
        fields_added += 1
    except sqlite3.OperationalError as e:
        if 'duplicate column' in str(e).lower():
            print("  ⏭️  sar_rationale already exists")
            fields_skipped += 1
        else:
            raise
    
    try:
        cur.execute("ALTER TABLE reviews ADD COLUMN sar_date_raised TEXT")
        print("  ✅ Added sar_date_raised")
        fields_added += 1
    except sqlite3.OperationalError as e:
        if 'duplicate column' in str(e).lower():
            print("  ⏭️  sar_date_raised already exists")
            fields_skipped += 1
        else:
            raise
    
    try:
        cur.execute("ALTER TABLE reviews ADD COLUMN daml_rationale TEXT")
        print("  ✅ Added daml_rationale")
        fields_added += 1
    except sqlite3.OperationalError as e:
        if 'duplicate column' in str(e).lower():
            print("  ⏭️  daml_rationale already exists")
            fields_skipped += 1
        else:
            raise
    
    try:
        cur.execute("ALTER TABLE reviews ADD COLUMN daml_date_raised TEXT")
        print("  ✅ Added daml_date_raised")
        fields_added += 1
    except sqlite3.OperationalError as e:
        if 'duplicate column' in str(e).lower():
            print("  ⏭️  daml_date_raised already exists")
            fields_skipped += 1
        else:
            raise
    
    # Outreach fields
    print("\n📧 Adding Outreach fields...")
    try:
        cur.execute("ALTER TABLE reviews ADD COLUMN outreach_date1 TEXT")
        print("  ✅ Added outreach_date1")
        fields_added += 1
    except sqlite3.OperationalError as e:
        if 'duplicate column' in str(e).lower():
            print("  ⏭️  outreach_date1 already exists")
            fields_skipped += 1
        else:
            raise
    
    try:
        cur.execute("ALTER TABLE reviews ADD COLUMN outreach_chaser_date1 TEXT")
        print("  ✅ Added outreach_chaser_date1")
        fields_added += 1
    except sqlite3.OperationalError as e:
        if 'duplicate column' in str(e).lower():
            print("  ⏭️  outreach_chaser_date1 already exists")
            fields_skipped += 1
        else:
            raise
    
    try:
        cur.execute("ALTER TABLE reviews ADD COLUMN outreach_chaser_date2 TEXT")
        print("  ✅ Added outreach_chaser_date2")
        fields_added += 1
    except sqlite3.OperationalError as e:
        if 'duplicate column' in str(e).lower():
            print("  ⏭️  outreach_chaser_date2 already exists")
            fields_skipped += 1
        else:
            raise
    
    try:
        cur.execute("ALTER TABLE reviews ADD COLUMN outreach_chaser_date3 TEXT")
        print("  ✅ Added outreach_chaser_date3")
        fields_added += 1
    except sqlite3.OperationalError as e:
        if 'duplicate column' in str(e).lower():
            print("  ⏭️  outreach_chaser_date3 already exists")
            fields_skipped += 1
        else:
            raise
    
    # Screening fields
    print("\n🔍 Adding Screening fields...")
    try:
        cur.execute("ALTER TABLE reviews ADD COLUMN screening_rationale TEXT")
        print("  ✅ Added screening_rationale")
        fields_added += 1
    except sqlite3.OperationalError as e:
        if 'duplicate column' in str(e).lower():
            print("  ⏭️  screening_rationale already exists")
            fields_skipped += 1
        else:
            raise
    
    try:
        cur.execute("ALTER TABLE reviews ADD COLUMN screening_completed INTEGER DEFAULT 0")
        print("  ✅ Added screening_completed")
        fields_added += 1
    except sqlite3.OperationalError as e:
        if 'duplicate column' in str(e).lower():
            print("  ⏭️  screening_completed already exists")
            fields_skipped += 1
        else:
            raise
    
    # Decision fields
    print("\n✅ Adding Decision fields...")
    try:
        cur.execute("ALTER TABLE reviews ADD COLUMN decision_outcome TEXT")
        print("  ✅ Added decision_outcome")
        fields_added += 1
    except sqlite3.OperationalError as e:
        if 'duplicate column' in str(e).lower():
            print("  ⏭️  decision_outcome already exists")
            fields_skipped += 1
        else:
            raise
    
    try:
        cur.execute("ALTER TABLE reviews ADD COLUMN decision_rationale TEXT")
        print("  ✅ Added decision_rationale")
        fields_added += 1
    except sqlite3.OperationalError as e:
        if 'duplicate column' in str(e).lower():
            print("  ⏭️  decision_rationale already exists")
            fields_skipped += 1
        else:
            raise
    
    try:
        cur.execute("ALTER TABLE reviews ADD COLUMN decision_date TEXT")
        print("  ✅ Added decision_date")
        fields_added += 1
    except sqlite3.OperationalError as e:
        if 'duplicate column' in str(e).lower():
            print("  ⏭️  decision_date already exists")
            fields_skipped += 1
        else:
            raise
    
    conn.commit()
    conn.close()
    
    print(f"\n{'='*60}")
    print(f"✅ Migration complete!")
    print(f"   Fields added: {fields_added}")
    print(f"   Fields skipped (already exist): {fields_skipped}")
    print(f"{'='*60}")

if __name__ == '__main__':
    add_ddg_fields()
