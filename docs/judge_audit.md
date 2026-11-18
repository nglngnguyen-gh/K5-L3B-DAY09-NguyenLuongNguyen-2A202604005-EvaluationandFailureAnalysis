# Judge audit

Chạy trong `src/`: `python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 10` (và `judge_helpful_public.csv`). Lớp positive là **FAIL**, vì việc của judge là tìm lỗi.

| Tiêu chí | n | κ | Precision | Recall | Ma trận (tp/fp/fn/tn) | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | 24 / 4 / 6 / 66 | **PASS** (exit 0) | **dùng**, chỉ cho metric tone, không blocking cho tiền |
| helpful | 100 | 0.375 | 1.000 | **0.300** | 9 / 0 / 21 / 70 | **FAIL** (exit 1): κ và R dưới sàn | **loại**, không được dùng làm gate |

Tỉ lệ FAIL sau hiệu chỉnh Rogan-Gladen, `(p_obs + spec − 1) / (sens + spec − 1)`:
- **tone**: quan sát 0.28, sens 0.8, spec 66/70 = 0.943, hiệu chỉnh ra **0.30**. Con số này khớp tỉ lệ FAIL theo người (30/100).
- **helpful**: quan sát 0.09, sens 0.3, spec 1.0, hiệu chỉnh ra **0.30**. Con số tổng thể được sửa đúng, nhưng judge vẫn bỏ sót 7/10 lỗi trên từng reply cụ thể (xem kết luận).

## Audit thủ công: tone_ok (cả 10 bất đồng)

| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú / sửa rubric |
|---|---|---|---|---|---|
| 1 | H-008 "Em đã hoàn tiền cho anh rồi nha…" | PASS | FAIL | **Người** | Xưng "em" và dùng "nha" là suồng sã với khách khiếu nại. Rubric thêm: *xưng hô phải là "LogiX" – "anh/chị"; FAIL nếu dùng em/bạn/mình*. |
| 2 | H-017 "Dạ, bạn ơi LogiX đã hoàn…" | PASS | FAIL | **Người** | Cùng lỗi xưng hô "bạn". Judge hiểu "thân thiện" là "đạt tone". Dùng chung quy tắc xưng hô ở #1. |
| 3 | H-029 "Dạ, vui lòng chờ… không cần nhắn thêm." | PASS | FAIL | **Người** | Judge chỉ thấy từ lịch sự "Dạ, vui lòng" mà bỏ qua giọng ra lệnh. Rubric thêm: *FAIL nếu có câu mệnh lệnh hoặc cấm khách liên hệ, dù mở đầu lịch sự*. Kèm ví dụ few-shot. |
| 4 | H-042 "Dạ, đơn O-808 đã hoàn 120.000đ…" (không xin lỗi) | FAIL | PASS | **Người** | Judge phạt vì "thiếu xin lỗi". Rubric thêm: *xin lỗi KHÔNG bắt buộc; ngắn mà đủ ý vẫn PASS*. |
| 5 | H-051 "LogiX đã refund 90.000đ…" | FAIL | PASS | **Người** | Style guide CS của LogiX cho phép từ "refund". Rubric thêm danh sách từ tiếng Anh được phép (refund, ship, voucher). |
| 6 | H-063 "…đã hoàn 20.000đ và sẽ hoàn thêm…" | PASS | FAIL | **Người** (nhưng không phải lỗi tone) | Đây là lời hứa vượt quá kết quả của hệ thống, gần với FM-08. Lỗi kiểu này phải chấm bằng code (so reply với ledger), không giao cho judge tone. Rubric: ghi rõ *ngoài phạm vi tone*. |
| 7 | H-070 "…ạ 😂😂" | PASS | FAIL | **Người** | Emoji cười không hợp với ngữ cảnh khiếu nại. Rubric thêm: *FAIL nếu có emoji trong khiếu nại / hoàn tiền*. |
| 8 | H-081 "Dạ, đơn O-107 chưa đủ điều kiện…" | FAIL | PASS | **Judge** | Note của file: người gán nhãn đọc nhầm ticket. Mình **không sửa CSV** (đây là dữ liệu calibration công khai, test tham chiếu phụ thuộc vào nó). Đề xuất sửa nhãn ở phiên bản nhãn tiếp theo và cho nhãn đi qua 2 người duyệt. |
| 9 | H-088 "Dạ, dạ, LogiX đã hoàn…" | FAIL | PASS | **Người** (tranh cãi được) | Lặp chữ do gõ nhầm, khách vẫn hiểu. Rubric thêm: *lỗi gõ nhẹ không làm đổi nghĩa thì không FAIL tone*. |
| 10 | H-094 "Da, LogiX da hoan… xin loi vi su bat tien." | PASS | FAIL | **Người** | Tiếng Việt mất dấu trông như dịch máy, thiếu chuyên nghiệp. Rubric thêm: *FAIL nếu mất dấu tiếng Việt*. |

Tổng kết tone: trong 10 case, judge sai 9 (6 FN, 3 FP), người sai 1 (H-081). Lỗi của judge rơi vào hai nhóm: (a) coi "thân thiện" hoặc từ lịch sự bề mặt là đạt tone (#1, #2, #3, #7, #10); (b) quá khắt khe với chuẩn không có trong style guide (#4, #5, #9). Cả hai nhóm đều sửa được bằng rubric cụ thể kèm few-shot.

## Audit thủ công: helpful (5 case đại diện trong 21 FN)

| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú |
|---|---|---|---|---|---|
| 1 | HL-015 "Dạ, LogiX đã hoàn 55.000đ cho đơn O-112 ạ." | PASS | FAIL | **Người** | Ledger ghi 40.000đ. Judge chỉ thấy reply, không thấy ledger, nên **không thể** biết số sai. Đây là FM-08. |
| 2 | HL-016 reply dài: xin lỗi 2 lần + "đã hoàn 55.000đ" | PASS | FAIL | **Người** | Ledger ghi 35.000đ. Reply càng nhiều lời xin lỗi thì judge càng chấm PASS (**verbosity / politeness bias**). 13/18 case sai số tiền có dạng này. |
| 3 | HL-043 "rất tiếc… đã hoàn 35.000đ cho O-202… rất tiếc…" | PASS | FAIL | **Người** | Ledger ghi 20.000đ. Câu xin lỗi lặp nguyên văn hai lần mà judge không phạt. |
| 4 | HL-087 "Dạ, LogiX đã hoàn 60.000đ cho đơn O-202 ạ." | PASS | FAIL | **Người** | Ledger ghi 90.000đ, reply nói *ít hơn*. Đây vẫn là FM-08: khách nhận thông tin sai về số tiền. |
| 5 | HL-047 "Ok bạn, đơn O-515 xử lý rồi nhé." | PASS | FAIL | **Người** | Không nói kết quả là gì (hoàn bao nhiêu hay bị từ chối) nên không giúp được khách. 3 case "Ok bạn… xử lý rồi nhé" đều bị judge bỏ sót. |

Phân loại 21 FN: **18 case** reply nói số tiền khác ledger (13 reply dài nhiều lời xin lỗi, 5 reply ngắn), và **3 case** reply mơ hồ không nêu kết quả. Judge không có một false positive nào (P = 1.0), nghĩa là nó gần như chỉ bắt được reply thô lỗ hoặc rỗng ("Bạn gửi lại thông tin đi.").

Sửa rubric helpful (để calibrate lại, chưa được dùng làm gate):
1. *Bỏ hẳn tiêu chí số tiền khỏi judge.* Số tiền trong reply so với ledger được chấm bằng code: metric FM-08 ở M3.
2. *FAIL nếu reply không nêu kết quả cụ thể* (đã hoàn X đ / bị từ chối vì lý do Y / cần thêm thông tin Z).
3. *Không cộng điểm cho lời xin lỗi; FAIL nếu một câu bị lặp nguyên văn.* Kèm few-shot gồm 1 reply dài sai và 1 reply ngắn đúng, để khử verbosity bias.

## Kết luận

- **helpful bị loại**: κ = 0.375 < 0.6 và R = 0.30 < 0.7. Ma trận cho thấy fn = 21 so với tp = 9, tức judge bỏ sót 70% reply không hữu ích. Precision 1.0 không cứu được: dùng judge này làm gate thì 7/10 regression về độ hữu ích sẽ lọt qua mà vẫn "xanh". Nguyên nhân gốc là 18/21 lỗi bị sót là **sai số tiền**, loại thông tin judge không có (judge không đọc ledger). Vì vậy tiền phải chấm bằng code. Rogan-Gladen kéo được tỉ lệ tổng thể về 0.30, nhưng đó chỉ là ước lượng *trung bình* trên cả tập, không cho biết *reply nào* sai. Gate cần quyết định trên từng PR và từng item, nên con số hiệu chỉnh không thay được recall.
- **tone được dùng** (κ = 0.757, P = 0.857, R = 0.8): dùng như metric chất lượng, không blocking cho các quyết định liên quan đến tiền hay approval. Khi báo cáo tỉ lệ lỗi tone nên dùng số đã hiệu chỉnh (0.30), không dùng số quan sát (0.28).
- **Rủi ro còn lại**:
  - Judge mới chỉ được kiểm trên dữ liệu replay công khai (100 dòng cho mỗi tiêu chí). Nhãn và rubric đã sửa ở đây đều nhìn thấy chính tập này, nên cần một bộ nhãn người mới làm held-out trước khi tin các con số.
  - Ít nhất một nhãn người sai (H-081). Nhãn người cũng cần được audit.
  - Với LLM thật, verdict của judge dao động giữa các lần chạy. Replay che mất dải nhiễu đó.
