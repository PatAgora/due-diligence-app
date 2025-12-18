import datetime as dt
import pytest

from utils import derive_case_status, ReviewStatus

TODAY = dt.date.today()
YESTERDAY = TODAY - dt.timedelta(days=1)
PAST = TODAY - dt.timedelta(days=21)


def _rec(**kwargs):
    """Helper to build a fake DB record with only the fields we care about."""
    return kwargs


def test_unassigned():
    rec = _rec(l1_assigned_to=None)
    assert derive_case_status(rec) == ReviewStatus.UNASSIGNED


def test_pending_review():
    rec = _rec(
        l1_assigned_to="123",
        l1_referred_to_sme="",
        InitialReviewCompleteDate="",
        Chaser1IssuedDate=""
    )
    assert derive_case_status(rec) == ReviewStatus.PENDING_REVIEW


def test_referred_to_sme():
    rec = _rec(l1_referred_to_sme="yes", l1_sme_returned_date="")
    assert derive_case_status(rec) == ReviewStatus.SME_REFERRED


def test_returned_from_sme():
    rec = _rec(
        l1_sme_returned_date=str(TODAY),
        InitialReviewCompleteDate=str(TODAY),
        Chaser1IssuedDate=str(TODAY)
    )
    assert derive_case_status(rec) == ReviewStatus.SME_RETURNED


def test_ir_complete_awaiting_outreach():
    rec = _rec(InitialReviewCompleteDate=str(TODAY), Chaser1IssuedDate="")
    assert derive_case_status(rec) == ReviewStatus.IR_COMP


def test_outreach():
    rec = _rec(Chaser1IssuedDate=str(TODAY), outreach_response_received_date="")
    assert derive_case_status(rec) == ReviewStatus.OUTREACH


def test_outreach_response_received():
    rec = _rec(outreach_response_received_date=str(TODAY), l1_date_completed="")
    assert derive_case_status(rec) == ReviewStatus.OUTREACH_RET


def test_7_day_chaser_due():
    rec = _rec(Chaser1DueDate=str(YESTERDAY), outreach_response_received_date="")
    assert derive_case_status(rec) == ReviewStatus.CHASER1_DUE


def test_14_day_chaser_due():
    rec = _rec(Chaser2DueDate=str(PAST), outreach_response_received_date="")
    assert derive_case_status(rec) == ReviewStatus.CHASER2_DUE


def test_21_day_chaser_due():
    rec = _rec(Chaser3DueDate=str(PAST), outreach_response_received_date="")
    assert derive_case_status(rec) == ReviewStatus.CHASER3_DUE


def test_ntc_due():
    rec = _rec(NTCDueDate=str(YESTERDAY), outreach_response_received_date="")
    assert derive_case_status(rec) == ReviewStatus.NTC_DUE


def test_restrictions_due():
    rec = _rec(NTCIssuedDate=str(YESTERDAY), RestrictionsAppliedDate="", outreach_response_received_date="")
    assert derive_case_status(rec) == ReviewStatus.RESTRICTIONS_DUE


def test_qc_awaiting_assignment():
    rec = _rec(l1_date_completed=str(TODAY), l1_qc_assigned_to="")
    assert derive_case_status(rec) == ReviewStatus.QC_UNASSIGNED


def test_qc_in_progress():
    rec = _rec(l1_date_completed=str(TODAY), l1_qc_assigned_to="55")
    assert derive_case_status(rec) == ReviewStatus.QC_IN_PROGRESS


def test_qc_rework_required():
    rec = _rec(l1_date_completed=str(TODAY), l1_qc_rework_required="1")
    assert derive_case_status(rec) == ReviewStatus.QC_REWORK


def test_completed():
    rec = _rec(
        l1_date_completed=str(TODAY),
        l1_qc_check_date=str(TODAY),
        l1_qc_rework_completed=str(TODAY)
    )
    assert derive_case_status(rec) == ReviewStatus.COMPLETED