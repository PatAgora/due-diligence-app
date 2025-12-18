# Database Cleanup Plan

## Primary Databases (KEEP)
1. `./DueDiligenceBackend/Due Diligence/scrutinise_workflow.db` (336K) - **MAIN DATABASE**
   - Used by Flask app (app.py line 333: DB_PATH = 'scrutinise_workflow.db')
   - Most recently modified (Dec 17 20:53)
   - Contains all workflow data

2. `./DueDiligenceBackend/Transaction Review/tx.db` (116K)
   - Used by Transaction Review module
   - Keep as separate module database

## Duplicate/Stale Databases (SAFE TO REMOVE)
1. `./DueDiligenceFrontend/scrutinise_workflow.db` (336K)
   - Duplicate in frontend directory (frontend should not have DB)
   - Older version (Dec 3 13:29)
   - **REMOVE**

2. `./DueDiligenceBackend/scrutinise_workflow.db` (12K)
   - Duplicate in parent directory
   - Much smaller, likely incomplete
   - **REMOVE**

3. `./DueDiligenceBackend/AI SME/scrutinise_workflow.db` (176K)
   - Duplicate in AI SME directory
   - AI SME should connect to main DB
   - **REMOVE**

4. `./DueDiligenceBackend/Due Diligence/database.db` (40K)
   - Old database file, replaced by scrutinise_workflow.db
   - **REMOVE**

## Action
Remove 4 duplicate/stale database files, keep 2 primary databases.
