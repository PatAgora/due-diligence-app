# utils.py
from enum import Enum
from datetime import date, datetime
import pandas as pd


class ReviewStatus(str, Enum):
    UNASSIGNED        = "Unassigned"
    PENDING_REVIEW    = "Pending Review"
    SME_REFERRED      = "Referred to SME"
    REFERRED_TO_AI_SME = "Referred to AI SME"
    SME_RETURNED      = "Returned from SME – Awaiting Review"
    IR_COMP           = "Initial Review Complete - Awaiting Outreach"
    OUTREACH          = "Outreach"
    OUTREACH_COMPLETE = "Outreach Complete"
    OUTREACH_RET      = "Outreach Response Received"
    CHASER1_DUE       = "7 Day Chaser Due"
    CHASER2_DUE       = "14 Day Chaser Due"
    CHASER3_DUE       = "21 Day Chaser Due"
    NTC_DUE           = "NTC Due"
    RESTRICTIONS_DUE  = "NTC Issued - Restrictions Due"
    AWAITING_QC       = "Awaiting QC"
    AWAITING_QC_REWORK = "Awaiting QC Rework"
    QC_WAITING_ASSIGNMENT = "QC Waiting Assignment"
    QC_PENDING_REVIEW = "QC Pending Review"
    QC_UNASSIGNED     = "QC – Awaiting Assignment"
    QC_IN_PROGRESS    = "QC – In Progress"
    QC_REWORK         = "QC – Rework Required"
    QC_REWORK_COMPLETE = "QC - Rework Complete"
    REWORK_REQUIRED   = "Rework Required"
    COMPLETED         = "Completed"

    def __str__(self) -> str:
        # Ensure templates / APIs show the human-readable label
        return self.value


# ---------- Helpers ----------
def is_blank(v) -> bool:
    # Treat None, empty string, 0, "0", and pandas NA as blank
    if v is None:
        return True
    if v == "":
        return True
    if v == 0 or v == "0":
        return True
    if pd.isna(v):
        return True
    return False

def not_blank(v) -> bool:
    return not is_blank(v)

def parse_d(val):
    """Return date or None from common formats / date/datetime/None."""
    if is_blank(val):
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        s = val.strip()
        for fmt in (
            "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y",
            "%m/%d/%Y", "%Y/%m/%d",
            "%d %b %Y", "%d %B %Y",
            "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f",
        ):
            try:
                return datetime.strptime(s, fmt).date()
            except Exception:
                continue
    return None


# ---------- Core ----------
def derive_case_status(rec: dict) -> ReviewStatus:
    """
    Prescriptive mapping (SIMPLIFIED - Single Level):

    Unassigned = assigned_to blank
    Pending Review = assigned_to not blank, referred_to_sme blank, InitialReviewCompleteDate blank
    Referred to SME = referred_to_sme not blank, sme_returned_date blank
    Returned from SME – Awaiting Review = sme_returned_date not blank, InitialReviewCompleteDate not blank
    Initial Review Complete - Awaiting Outreach = InitialReviewCompleteDate not blank (and no Outreach1Date)
    Outreach = Outreach1Date not blank AND outreach_response_received_date blank
    Outreach Response Received = outreach_response_received_date not blank AND date_completed blank
    7/14/21 Day Chaser Due = Chaser{1/2/3}DueDate <= today AND outreach_response_received_date blank
    NTC Due = NTCDueDate <= today AND outreach_response_received_date blank
    NTC Issued - Restrictions Due = NTCIssuedDate <= today AND RestrictionsAppliedDate blank
    
    QC WORKFLOW (Task goes to QC if in qc_sampling_log):
    - If date_completed AND in qc_sampling_log AND qc_check_date blank → QC_UNASSIGNED/QC_IN_PROGRESS
    - If qc_rework_required AND NOT qc_rework_completed → QC_REWORK
    - If qc_check_date exists AND (qc_outcome = Pass OR NOT qc_rework_required) → COMPLETED
    
    Completed = date_completed not blank AND (QC done OR NOT in qc_sampling_log)
    """
    r = dict(rec or {})
    today = date.today()

    # Normalize dates we reference
    d = {
        "InitialReviewCompleteDate": parse_d(r.get("InitialReviewCompleteDate")),
        "Chaser1IssuedDate":         parse_d(r.get("Chaser1IssuedDate")),
        "Chaser1DueDate":            parse_d(r.get("Chaser1DueDate")),
        "Chaser2DueDate":            parse_d(r.get("Chaser2DueDate")),
        "Chaser3DueDate":            parse_d(r.get("Chaser3DueDate")),
        "NTCDueDate":                parse_d(r.get("NTCDueDate")),
        "NTCIssuedDate":             parse_d(r.get("NTCIssuedDate")),
        "RestrictionsAppliedDate":   parse_d(r.get("RestrictionsAppliedDate")),
        "outreach_response_received_date": parse_d(r.get("outreach_response_received_date")),
        "Outreach1Date": parse_d(r.get("Outreach1Date") or r.get("OutreachDate1")) or parse_d(r.get("OutreachDate1")),
        "date_completed":            parse_d(r.get("date_completed")),
        "qc_check_date":             parse_d(r.get("qc_check_date")),
        "qc_end_time":               parse_d(r.get("qc_end_time")),
        "sme_returned_date":         parse_d(r.get("sme_returned_date")) or parse_d(r.get("SMEReturnedDate")),
    }

    # Non-date flags/IDs
    # Handle assigned_to: treat 0, None, empty string as unassigned
    assigned_to_raw = r.get("assigned_to")
    assigned_to = None if (assigned_to_raw is None or assigned_to_raw == 0 or assigned_to_raw == "" or (isinstance(assigned_to_raw, str) and assigned_to_raw.strip() == "0")) else assigned_to_raw
    referred_to_sme    = r.get("referred_to_sme")
    qc_assigned_to     = r.get("qc_assigned_to")
    qc_rework_required = r.get("qc_rework_required")
    qc_rework_completed = r.get("qc_rework_completed")  # Boolean/integer field, not a date
    in_qc_sampling     = r.get("_in_qc_sampling")  # Set by caller if needed
    outreach_complete   = r.get("outreach_complete")

    # ---- PRIORITY ORDER ----
    
    # Get status string once for reuse
    low_status = (str(r.get('status')) or '').strip().lower()
    
    # Returned from SME – Awaiting Review (check this first if sme_returned_date is set)
    # This applies to both manual and AI SME referrals
    if not_blank(d["sme_returned_date"]):
        # If it was an AI SME referral (status contains "referred to ai sme"), return SME_RETURNED
        if 'referred to ai sme' in low_status:
            return ReviewStatus.SME_RETURNED
        # For manual referrals, check if InitialReviewCompleteDate and Chaser1IssuedDate are set
        if not_blank(d["InitialReviewCompleteDate"]) and not_blank(d["Chaser1IssuedDate"]):
            return ReviewStatus.SME_RETURNED
    
    # Referred to AI SME (check this to preserve the AI SME status when no response yet)
    if 'referred to ai sme' in low_status and is_blank(d['sme_returned_date']):
        return ReviewStatus.REFERRED_TO_AI_SME
    
    # Referred to SME
    if ((not_blank(referred_to_sme) or 'referred to sme' in low_status) and is_blank(d['sme_returned_date'])):
        return ReviewStatus.SME_REFERRED

    # QC WORKFLOW - New flow: completed → awaiting_qc → qc_waiting_assignment → qc_pending_review → completed/rework_required
    if not_blank(d["date_completed"]):
        # Get QC outcome and related fields
        qc_outcome = (str(r.get("qc_outcome") or "")).strip().lower()
        qc_rework_required_val = r.get("qc_rework_required")
        
        # Check if rework is required
        # Only consider rework required if the flag is explicitly set (not 0)
        # If qc_rework_required is 0 or None, even if qc_outcome is "fail", 
        # it means the reviewer has resubmitted after rework and we should move forward
        is_rework_required = (not_blank(qc_rework_required_val) and qc_rework_required_val != 0)
        # qc_rework_completed is a boolean/integer field (0 or 1), not a date
        is_rework_completed = (qc_rework_completed is not None and qc_rework_completed != 0 and qc_rework_completed != "0" and str(qc_rework_completed).strip() != "")
        
        # Check if status is explicitly set to "QC - Rework Complete" (reviewer marked rework as done)
        current_status = (str(r.get("status", "") or "")).strip()
        if current_status == "QC - Rework Complete":
            # Task is waiting for QC to confirm rework completion
            if in_qc_sampling:
                if is_blank(qc_assigned_to):
                    return ReviewStatus.QC_WAITING_ASSIGNMENT
                else:
                    return ReviewStatus.QC_PENDING_REVIEW
            # If not in QC sampling, it should still go to QC
            return ReviewStatus.AWAITING_QC
        
        # If rework is required and not completed, return Rework Required
        if is_rework_required and not is_rework_completed:
            return ReviewStatus.QC_REWORK
        
        # If rework is completed but QC hasn't reviewed it yet, return Awaiting QC Rework
        # This check must come BEFORE the generic QC pending check to prioritize rework status
        if is_rework_completed and is_blank(d["qc_check_date"]):
            # Reviewer has completed rework, waiting for QC to review
            if in_qc_sampling:
                if is_blank(qc_assigned_to):
                    return ReviewStatus.QC_WAITING_ASSIGNMENT
                else:
                    return ReviewStatus.AWAITING_QC_REWORK
            # If not in QC sampling, it should still show as awaiting QC rework
            return ReviewStatus.AWAITING_QC_REWORK
        
        # If QC check has been done
        if not_blank(d["qc_check_date"]):
            # If rework was required, check if it's completed
            if is_rework_required:
                if is_rework_completed:
                    # Rework completed and QC confirmed, task is done
                    return ReviewStatus.COMPLETED
                else:
                    # Still waiting for rework
                    return ReviewStatus.QC_REWORK
            # No rework required and QC passed
            if qc_outcome in ("pass", "pass with feedback"):
                return ReviewStatus.COMPLETED
            # If QC outcome is "fail" but rework_required is 0, it means reviewer resubmitted after rework
            # Check if task is in QC sampling to determine next status
            if qc_outcome == "fail" and not is_rework_required:
                # Check if QC has completed their review of the rework (qc_end_time is set)
                # If qc_end_time is set AND rework_completed is true, QC has confirmed rework is OK
                if not_blank(d["qc_end_time"]) and is_rework_completed:
                    # QC has confirmed rework completion, task is done
                    return ReviewStatus.COMPLETED
                # Reviewer resubmitted after rework - check if it needs to go back to QC
                if in_qc_sampling:
                    if is_blank(qc_assigned_to):
                        return ReviewStatus.QC_WAITING_ASSIGNMENT
                    else:
                        return ReviewStatus.QC_PENDING_REVIEW
                # Not in QC sampling, task is completed
                return ReviewStatus.COMPLETED
        
        # Task is completed but QC hasn't been done yet
        # If QC check date is blank, check if task is in QC sampling
        if is_blank(d["qc_check_date"]):
            # If in QC sampling, check assignment status
            if in_qc_sampling:
                if is_blank(qc_assigned_to):
                    return ReviewStatus.QC_WAITING_ASSIGNMENT
                else:
                    return ReviewStatus.QC_PENDING_REVIEW
            # If NOT in QC sampling (e.g., reviewer has 0% sampling rate), task is completed
            # Tasks not in QC sampling should go directly to Completed status
            return ReviewStatus.COMPLETED
        
        # QC has been done - check if rework is required
        # If rework is required and not completed, return rework status
        if is_rework_required and not is_rework_completed:
            return ReviewStatus.QC_REWORK
        
        # QC passed or rework completed - task is completed
        return ReviewStatus.COMPLETED

    # Unassigned - Check this FIRST before any Outreach or other status checks
    # An unassigned task should never show as Outreach, Pending Review, etc.
    if is_blank(assigned_to):
        return ReviewStatus.UNASSIGNED

    # Initial Review Complete - Awaiting Outreach (only if not in QC rework)
    if not_blank(d["InitialReviewCompleteDate"]) and is_blank(d["Chaser1IssuedDate"]) and is_blank(d["Outreach1Date"]) and is_blank(d["date_completed"]) and str(r.get("status","")).strip().lower() not in ("complete","completed"):
        return ReviewStatus.IR_COMP

    # Outreach Complete - if outreach_complete flag is set, status is "Outreach Complete"
    # Check this before other outreach states
    if outreach_complete and outreach_complete != 0 and is_blank(d["date_completed"]):
        return ReviewStatus.OUTREACH_COMPLETE
    
    # Outreach Response Received
    if not_blank(d["outreach_response_received_date"]) and is_blank(d["date_completed"]):
        return ReviewStatus.OUTREACH_RET
    
    # Outreach - First outreach sent; waiting for response
    # Task is already confirmed as assigned (checked above)
    if not_blank(d["Outreach1Date"]) and is_blank(d["outreach_response_received_date"]):
        return ReviewStatus.OUTREACH
    
    # Due states (only if response not received)
    # Task is already confirmed as assigned (checked above)
    if is_blank(d["outreach_response_received_date"]):
        if d["NTCDueDate"] and d["NTCDueDate"] <= today:
            return ReviewStatus.NTC_DUE
        if d["Chaser3DueDate"] and d["Chaser3DueDate"] <= today:
            return ReviewStatus.CHASER3_DUE
        if d["Chaser2DueDate"] and d["Chaser2DueDate"] <= today:
            return ReviewStatus.CHASER2_DUE
        if d["Chaser1DueDate"] and d["Chaser1DueDate"] <= today:
            return ReviewStatus.CHASER1_DUE
        if d["NTCIssuedDate"] and d["NTCIssuedDate"] <= today and is_blank(d["RestrictionsAppliedDate"]):
            return ReviewStatus.RESTRICTIONS_DUE

    # Pending Review
    if is_blank(referred_to_sme) and is_blank(d["InitialReviewCompleteDate"]) and is_blank(d["Chaser1IssuedDate"]):
        return ReviewStatus.PENDING_REVIEW

    # Fallback
    return ReviewStatus.PENDING_REVIEW


# ---- Raw status normalization & override (added) ----
from typing import Optional

def _norm_status_text(s: str) -> str:
    s = (s or "").strip().lower()
    s = s.replace("—", "-").replace("–", "-")  # normalize dashes
    s = " ".join(s.split())
    return s

def map_raw_status_to_enum(raw_status: Optional[str]) -> Optional[ReviewStatus]:
    s = _norm_status_text(raw_status or "")
    if not s:
        return None

    # Completed first
    if "completed" in s or s == "complete":
        return ReviewStatus.COMPLETED

    # QC states
    if "awaiting qc rework" in s:
        return ReviewStatus.AWAITING_QC_REWORK
    if "qc" in s and "rework" in s:
        return ReviewStatus.QC_REWORK
    if "qc" in s and ("in progress" in s or "in-progress" in s or "inprogress" in s):
        return ReviewStatus.QC_IN_PROGRESS
    if "qc" in s and ("awaiting assignment" in s or "unassigned" in s):
        return ReviewStatus.QC_UNASSIGNED
    if "awaiting qc" in s and "rework" not in s:
        return ReviewStatus.AWAITING_QC

    # SME
    if "referred to ai sme" in s:
        # Return a custom status for AI SME referrals - we'll handle this specially
        # For now, map it to SME_REFERRED but we need to preserve the "AI SME" text
        return ReviewStatus.SME_REFERRED  # Will be overridden by raw status
    if "referred to sme" in s:
        return ReviewStatus.SME_REFERRED
    if "returned from sme" in s:
        return ReviewStatus.SME_RETURNED

    # Initial review complete / awaiting outreach
    if "awaiting outreach" in s or "initial review complete" in s:
        return ReviewStatus.IR_COMP

    # Outreach
    if "outreach response received" in s:
        return ReviewStatus.OUTREACH_RET
    if "outreach" in s:
        return ReviewStatus.OUTREACH

    # Chasers
    if "21 day chaser" in s or "chaser 3" in s or "chaser3" in s:
        return ReviewStatus.CHASER3_DUE
    if "14 day chaser" in s or "chaser 2" in s or "chaser2" in s:
        return ReviewStatus.CHASER2_DUE
    if "7 day chaser" in s or "chaser 1" in s or "chaser1" in s:
        return ReviewStatus.CHASER1_DUE

    # NTC
    if "ntc issued" in s and "restrictions" in s:
        return ReviewStatus.NTC_ISSUED_RESTRICTIONS_DUE
    if "ntc due" in s:
        return ReviewStatus.NTC_DUE

    # Assignment / review
    if "pending review" in s:
        return ReviewStatus.PENDING_REVIEW
    if "unassigned" in s:
        return ReviewStatus.UNASSIGNED

    return None

def best_status_with_raw_override(rec: dict) -> ReviewStatus:
    """
    Prefer derived status, but if the raw DB status clearly indicates a known state,
    return that raw state so MI reflects operational intent.
    Special case: 'Awaiting Outreach' should not be up-bucketed to 'Outreach'.
    Special case: 'Referred to AI SME' should be preserved as-is.
    Special case: 'Outreach Complete' should be preserved as-is.
    """
    try:
        derived = derive_case_status(rec)
    except Exception:
        derived = None
    
    raw_status = rec.get("status", "").strip()
    raw_status_lower = raw_status.lower()
    
    # Preserve "Referred to AI SME" status exactly as it is
    if "referred to ai sme" in raw_status_lower:
        return ReviewStatus.REFERRED_TO_AI_SME
    
    # Preserve "Awaiting QC Rework" status exactly as it is
    if "awaiting qc rework" in raw_status_lower:
        return ReviewStatus.AWAITING_QC_REWORK
    
    # Preserve "Outreach Complete" status exactly as it is
    if "outreach complete" in raw_status_lower:
        return ReviewStatus.OUTREACH_COMPLETE
    
    raw_enum = map_raw_status_to_enum(raw_status)

    if raw_enum is None:
        return derived

    return raw_enum
