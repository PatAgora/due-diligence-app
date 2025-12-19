#!/bin/bash

# Update Team Leader Dashboard with Agora theme
FILE="/home/user/webapp/DueDiligenceFrontend/src/components/TeamLeaderDashboard.jsx"

# Backup original
cp "$FILE" "${FILE}.backup"

# Read file
CONTENT=$(cat "$FILE")

# Replace imports
CONTENT=$(echo "$CONTENT" | sed "6 i import '../styles/agora-theme.css';")

# Replace all occurrences using sed
sed -i '
# Update loading/error containers
s/className="container my-4"/className="agora-main-content">\n        <div className="agora-container"/g
s/spinner-border text-primary/spinner-border" style={{ color: '\''var(--agora-orange)'\'' }}/g
s/alert alert-danger/agora-alert agora-alert-danger/g
s/btn btn-primary/agora-btn agora-btn-primary/g

# Update main content wrapper
s/<h1 className="fw-bold mb-2">/<h1 className="fw-bold mb-4" style={{ color: '\''var(--agora-navy)'\'' }}>/g

# Update form elements
s/form-select form-select-sm/agora-form-select/g

# Update cards and KPI
s/card shadow-sm h-100/agora-kpi-card accent-orange/g
s/card-body kpi/agora-kpi-top/g

# Update chart cards
s/card shadow-sm/agora-card/g
s/card-header/agora-card-header/g
s/card-body/agora-card-body/g
s/card-title/agora-chart-title/g

# Update tables
s/table table-striped table-hover/agora-table/g
s/thead className="table-light"/thead/g

# Update badges
s/badge bg-success/agora-badge agora-badge-success/g
s/badge bg-warning/agora-badge agora-badge-warning/g
s/badge bg-danger/agora-badge agora-badge-danger/g
s/badge bg-primary/agora-badge agora-badge-primary/g

# Change chart colors to Agora orange
s/#0d6efd/#F89D43/g
s/rgba(13, 110, 253,/rgba(248, 157, 67,/g
s/#198754/#10b981/g
s/#ffc107/#f59e0b/g

' "$FILE"

echo "Team Leader Dashboard updated with Agora theme"
