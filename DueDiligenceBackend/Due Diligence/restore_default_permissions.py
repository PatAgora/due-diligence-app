import sqlite3
import os

# Get database path - use the same database as the app
DB_PATH = os.environ.get("DB_PATH", "scrutinise_workflow.db")
db_path = os.path.join(os.path.dirname(__file__), DB_PATH)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Ensure permissions table exists
cur.execute("""
    CREATE TABLE IF NOT EXISTS permissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role TEXT NOT NULL,
        feature TEXT NOT NULL,
        can_view INTEGER DEFAULT 1,
        can_edit INTEGER DEFAULT 1,
        UNIQUE(role, feature)
    )
""")

# Define all roles
roles = [
    'admin', 'team_lead_1', 'team_lead_2', 'team_lead_3',
    'reviewer_1', 'reviewer_2', 'reviewer_3',
    'qc_1', 'qc_2', 'qc_3', 'qc_review_1', 'qc_review_2', 'qc_review_3',
    'qa_1', 'qa_2', 'qa_3',
    'sme', 'operations_manager'
]

# Define all features
features = [
    'view_dashboard',
    'assign_tasks',
    'review_tasks',
    'edit_users',
    'reset_passwords',
    'invite_users',
    'view_qc_qa',
    'manage_settings'
]

# Default permissions for each role
default_permissions = {
    'admin': {
        'view_dashboard': {'can_view': True, 'can_edit': True},
        'assign_tasks': {'can_view': True, 'can_edit': True},
        'review_tasks': {'can_view': True, 'can_edit': True},
        'edit_users': {'can_view': True, 'can_edit': True},
        'reset_passwords': {'can_view': True, 'can_edit': True},
        'invite_users': {'can_view': True, 'can_edit': True},
        'view_qc_qa': {'can_view': True, 'can_edit': True},
        'manage_settings': {'can_view': True, 'can_edit': True}
    },
    'team_lead_1': {
        'view_dashboard': {'can_view': True, 'can_edit': True},
        'assign_tasks': {'can_view': True, 'can_edit': True},
        'review_tasks': {'can_view': True, 'can_edit': True},
        'view_qc_qa': {'can_view': True, 'can_edit': False}
    },
    'team_lead_2': {
        'view_dashboard': {'can_view': True, 'can_edit': True},
        'assign_tasks': {'can_view': True, 'can_edit': True},
        'review_tasks': {'can_view': True, 'can_edit': True},
        'view_qc_qa': {'can_view': True, 'can_edit': False}
    },
    'team_lead_3': {
        'view_dashboard': {'can_view': True, 'can_edit': True},
        'assign_tasks': {'can_view': True, 'can_edit': True},
        'review_tasks': {'can_view': True, 'can_edit': True},
        'view_qc_qa': {'can_view': True, 'can_edit': False}
    },
    'reviewer_1': {
        'view_dashboard': {'can_view': True, 'can_edit': False},
        'review_tasks': {'can_view': True, 'can_edit': True}
    },
    'reviewer_2': {
        'view_dashboard': {'can_view': True, 'can_edit': False},
        'review_tasks': {'can_view': True, 'can_edit': True}
    },
    'reviewer_3': {
        'view_dashboard': {'can_view': True, 'can_edit': False},
        'review_tasks': {'can_view': True, 'can_edit': True}
    },
    'qc_1': {
        'view_dashboard': {'can_view': True, 'can_edit': True},
        'review_tasks': {'can_view': True, 'can_edit': True},
        'view_qc_qa': {'can_view': True, 'can_edit': True}
    },
    'qc_2': {
        'view_dashboard': {'can_view': True, 'can_edit': True},
        'review_tasks': {'can_view': True, 'can_edit': True},
        'view_qc_qa': {'can_view': True, 'can_edit': True}
    },
    'qc_3': {
        'view_dashboard': {'can_view': True, 'can_edit': True},
        'review_tasks': {'can_view': True, 'can_edit': True},
        'view_qc_qa': {'can_view': True, 'can_edit': True}
    },
    'qc_review_1': {
        'view_dashboard': {'can_view': True, 'can_edit': False},
        'review_tasks': {'can_view': True, 'can_edit': True},
        'view_qc_qa': {'can_view': True, 'can_edit': False}
    },
    'qc_review_2': {
        'view_dashboard': {'can_view': True, 'can_edit': False},
        'review_tasks': {'can_view': True, 'can_edit': True},
        'view_qc_qa': {'can_view': True, 'can_edit': False}
    },
    'qc_review_3': {
        'view_dashboard': {'can_view': True, 'can_edit': False},
        'review_tasks': {'can_view': True, 'can_edit': True},
        'view_qc_qa': {'can_view': True, 'can_edit': False}
    },
    'qa_1': {
        'view_dashboard': {'can_view': True, 'can_edit': True},
        'view_qc_qa': {'can_view': True, 'can_edit': True}
    },
    'qa_2': {
        'view_dashboard': {'can_view': True, 'can_edit': True},
        'view_qc_qa': {'can_view': True, 'can_edit': True}
    },
    'qa_3': {
        'view_dashboard': {'can_view': True, 'can_edit': True},
        'view_qc_qa': {'can_view': True, 'can_edit': True}
    },
    'sme': {
        'view_dashboard': {'can_view': True, 'can_edit': False},
        'review_tasks': {'can_view': True, 'can_edit': False}
    },
    'operations_manager': {
        'view_dashboard': {'can_view': True, 'can_edit': True},
        'assign_tasks': {'can_view': True, 'can_edit': True},
        'review_tasks': {'can_view': True, 'can_edit': True},
        'view_qc_qa': {'can_view': True, 'can_edit': True}
    }
}

# Clear existing permissions
print("Clearing existing permissions...")
cur.execute("DELETE FROM permissions")
print("✓ Cleared existing permissions")

# Insert default permissions
# Save ALL features for ALL roles (explicitly set to false if not in default_permissions)
print("\nInserting default permissions...")
count = 0
for role in roles:
    for feature in features:
        # Check if this role/feature combination is in default_permissions
        if role in default_permissions and feature in default_permissions[role]:
            perms = default_permissions[role][feature]
            can_view = 1 if perms['can_view'] else 0
            can_edit = 1 if perms['can_edit'] else 0
        else:
            # Not explicitly allowed, set to false
            can_view = 0
            can_edit = 0
        
        cur.execute("""
            INSERT INTO permissions (role, feature, can_view, can_edit)
            VALUES (?, ?, ?, ?)
        """, (role, feature, can_view, can_edit))
        count += 1
        if can_view or can_edit:
            print(f"  ✓ {role} -> {feature}: view={bool(can_view)}, edit={bool(can_edit)}")

conn.commit()
conn.close()

print(f"\n✓ Successfully restored {count} default permissions!")
print("\nAdmin now has full access to all features.")
print("You can now log in and access the permissions editor again.")

