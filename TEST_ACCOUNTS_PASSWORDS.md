# Test Account Passwords

**Frontend Login URL**: https://5173-ihzqwl5fhfcbjidc9trwd-c81df28e.sandbox.novita.ai

## Test Account Credentials

| Role | Email | Password | Name | Dashboard |
|------|-------|----------|------|-----------|
| **Admin** | admin@scrutinise.co.uk | admin123 | Admintest1 | /list_users |
| **Operations Manager** | ops@scrutinise.co.uk | ops123 | Ops1 | /operations_dashboard |
| **Team Leader Level 1** | TeamLead@scrutinise.co.uk | teamlead1 | TeamLead | /team_leader_dashboard |
| **Team Leader Level 2** | teamlead@scrutinise.co.uk | teamlead123 | TLTestL2 | /team_leader_dashboard |
| **QC Team Lead** | qctl@scrutinise.co.uk | qctl123 | QCTL1 | /qc_lead_dashboard |
| **QC Reviewer** | QC1@scrutinise.co.uk | qc123 | QCReview1 | /qc_dashboard |
| **Reviewer** | reviewer1@scrutinise.co.uk | reviewer123 | Jon Jones | /reviewer_dashboard |

## Additional Team Leader Accounts Available

| Email | Name | Role | Level |
|-------|------|------|-------|
| faizanmukhtar96@gmail.com | Faizan | team_lead_1 | 1 |
| RevTL2@scrutinise.co.uk | RevTL2 | team_lead_2 | 2 |

*(Use password reset script if you need credentials for these accounts)*

## Notes

- **All passwords are test passwords** - change them after first login
- **All accounts are active** and ready to use
- **2FA is disabled** for all test accounts for easier testing
- **Team Leader dashboard**: No longer displays level (removed as per workflow)
- **Admin user** has access to all areas

## Quick Login Test

```bash
# Test Team Leader Level 1 login
curl -X POST https://5050-ihzqwl5fhfcbjidc9trwd-c81df28e.sandbox.novita.ai/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "email=TeamLead@scrutinise.co.uk&password=teamlead1"
```

---
*Generated: 2025-12-19*
*Backend: Port 5050 | Frontend: Port 5173*
*Updated: Removed level display from Team Leader Dashboard*
