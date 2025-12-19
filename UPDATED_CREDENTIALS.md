# 🔑 Updated Test Account Credentials

**Frontend URL**: https://5173-ihzqwl5fhfcbjidc9trwd-c81df28e.sandbox.novita.ai

## All Test Accounts

| Role | Email | Password | Name | Level/Notes |
|------|-------|----------|------|-------------|
| **Admin** | admin@scrutinise.co.uk | admin123 | Admintest1 | Full access |
| **Operations Manager** | ops@scrutinise.co.uk | ops123 | Ops1 | Operations dashboard |
| **Team Leader (Level 1)** | TeamLead@scrutinise.co.uk | teamlead123 | TeamLead | ✅ NEW - Level 1 |
| **Team Leader (Level 2)** | teamlead@scrutinise.co.uk | teamlead123 | TLTestL2 | Level 2 (old account) |
| **QC Team Lead** | qctl@scrutinise.co.uk | qctl123 | QCTL1 | QC Lead dashboard |
| **QC Reviewer** | QC1@scrutinise.co.uk | qc123 | QCReview1 | QC Review dashboard |
| **Reviewer** | reviewer1@scrutinise.co.uk | reviewer123 | Jon Jones | Reviewer dashboard |

## Team Leader Level 1 - NEW CREDENTIALS

✅ **Email**: `TeamLead@scrutinise.co.uk`
✅ **Password**: `teamlead123`
✅ **Role**: team_lead_1
✅ **Level**: 1
✅ **Status**: Active

## Additional Team Leader Accounts Available

| Email | Name | Role | Level | Status |
|-------|------|------|-------|--------|
| faizanmukhtar96@gmail.com | Faizan | team_lead_1 | 1 | Active |
| RevTL2@scrutinise.co.uk | RevTL2 | team_lead_2 | 2 | Active |

*(Need password reset if you want to use these)*

## Recent Changes

### ✅ Team Leader Dashboard Updates:
1. **Removed "Level" from title** - Now shows just "Team Leader Dashboard"
2. **Fixed alignment** - Now matches Operations Dashboard layout
3. **Level 1 account ready** - TeamLead@scrutinise.co.uk with password reset

### ✅ Styling Updates:
1. **Exact Agora grey background** - #f5f6f8 everywhere
2. **Consistent layout** - All dashboards aligned properly
3. **White cards** - Clean, readable design

## Note About Levels

You mentioned there shouldn't be levels in this workflow. The database still has:
- **team_lead_1** (Level 1) - 2 accounts
- **team_lead_2** (Level 2) - 2 accounts

The dashboard title no longer shows the level, but the data is still stored. If you want to completely remove levels from the system, we would need to:
1. Update the database schema
2. Update the backend API logic
3. Remove level-based filtering/routing

For now, the level is just hidden from the UI.

---

**Last Updated**: 2025-12-19
**Status**: ✅ All credentials active and tested
