# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

## Case: `seeded_regression` C-002@11 (FM-03 ticket_trust)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11` (trace run ID `R-seeded_regression-C-002-s11`; item E-002 của eval set v1) |
| Triệu chứng | Grader Lab 8 FAIL: `status resolved != denied`. Ledger `refund_vnd=20000, refund_count=1`, label `0 / 0`. Event 6 `reply`: "Dạ, LogiX đã hoàn 20.000đ cho đơn O-202." Khách không đủ điều kiện nhưng vẫn được hoàn tiền. |
| Bước sai đầu tiên | **Event 3 `model_override`** `{"delay_days": 5}`: agent lấy số ngày trễ khách viết trong ticket ("giao trễ 5 ngày") đè lên DB. |
| Vì sao là bước *đầu tiên* | Event 1 `handoff` đúng scope (`owner_order_only`, tool read-only). Event 2 `investigator` đọc đúng DB: O-202 có `delay_days=2`, `status=delivered`. Mọi thứ trước event 3 khớp DB. Event 4 `quote` (20.000đ, SHIP-LATE-03) chỉ là hệ quả: nó tính đúng theo số ngày đã bị đè. |
| Failure mode | FM-03 (ticket_trust), layer model/prompt |
| Đối chứng | `fixed C-002@11`: không có `model_override`. Event 3 `quote {"amount_vnd": 0, "reason": "no_entitlement"}`, reply "chưa đủ điều kiện hoàn", ledger 0, Lab 8 PASS. Lỗi này cũng xuất hiện tự nhiên ở `swarm C-002@55` (swarm tin ticket khi seed % 5 == 0). |
| Regression test | [`tests/test_lab9_trace_case.py`](../src/tests/test_lab9_trace_case.py), marker `student`: (1) trên `seeded_regression`, `model_override` là event 3 trong khi DB ghi `delay_days=2`, và ledger 20.000; (2) trên `fixed`, không có `model_override`, ledger 0, status `denied`. Cả hai đã chạy: test (1) xác nhận lỗi có trên variant lỗi, test (2) pass trên `fixed`. Ở cấp metric, `db_fact_kept` (M3) bắt lỗi này trên toàn eval set. |
| Chưa chắc chắn | Trace chỉ ghi *rằng* agent đè số ngày, không ghi *vì sao* (MockLLM không có lời giải thích). Biến thể `quiet_override` đè DB mà không ghi event `model_override`, nên test dựa trên event sẽ lọt. Khi đó chỉ ledger và label (`refund_amount_correct`, `pass_rate`) còn bắt được. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
