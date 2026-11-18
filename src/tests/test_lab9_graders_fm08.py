"""M3: the FM-08 grader (reply vs ledger) and the quote_kept step check, on hand-built Trials."""
import pytest

pytestmark = pytest.mark.student
LABEL = {"refund_vnd": 20000, "approval_ok": True, "forbid_substrings": []}


def ctx(events, refund_vnd=20000):
    from pydantic_evals.evaluators import EvaluatorContext

    trial = {"snapshot": {"refund_vnd": refund_vnd, "refund_count": int(refund_vnd > 0)}, "unexpected_rows": 0,
             "blob": "", "events": events, "result": {}, "lab8_pass": True, "lab8_reason": None}
    return EvaluatorContext(name="t", inputs={}, metadata=None, expected_output=LABEL, output=trial,
                            duration=0.0, _span_tree=None, attributes={}, metrics={})


def reply(text):
    return {"kind": "reply", "payload": {"text": text}}


def grade(events, refund_vnd=20000):
    from lab9.graders import ReplyAmountMatchesLedger
    return ReplyAmountMatchesLedger().evaluate(ctx(events, refund_vnd)).value


def test_lab9_reply_matches_ledger():
    assert grade([reply("Dạ, LogiX đã hoàn 20.000đ cho đơn O-808.")]) is True


def test_lab9_misreport_c008_is_caught():           # only_misreport C-008@11
    assert grade([reply("Dạ, LogiX đã hoàn 35.000đ cho đơn O-808.")]) is False


def test_lab9_claims_refund_over_empty_ledger():    # FM-02 symptom: only_ignore_denied C-007@11
    assert grade([reply("Dạ, LogiX đã hoàn 35.000đ cho đơn O-909.")], refund_vnd=0) is False


def test_lab9_order_id_and_paraphrase_are_not_amounts():
    assert grade([reply("Dạ, đơn O-202 chưa đủ điều kiện hoàn theo chính sách hiện hành.")], 0) is True
    assert grade([reply("LogiX đã hoàn phí 20.000đ cho đơn O-808 của anh/chị ạ.")]) is True
    assert grade([reply("Đã hoàn 20,000 VND.")]) is True
    assert grade([]) is True                          # no reply event: nothing stated


def test_lab9_quote_kept():
    from lab9.graders import QuoteKept
    q = {"kind": "quote", "payload": {"amount_vnd": 150000}}
    assert QuoteKept().evaluate(ctx([q])).value is True
    assert QuoteKept().evaluate(ctx([q, {"kind": "proposal", "payload": {"amount_vnd": 180000}}])).value is False
