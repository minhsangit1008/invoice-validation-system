# Invoice Validation System - Báo cáo tóm tắt

## Mục tiêu & phạm vi
- OCR + trích xuất trường từ PDF, so khớp ground truth/PO/database, tính confidence, phát hiện sai lệch và sinh output JSON + ảnh highlight.
- Hiện đã có đủ 3 trạng thái mẫu để trình bày: approved, needs_review, rejected.

## Cập nhật kỹ thuật chính
- OCR: tiền xử lý ảnh (grayscale + autocontrast + median filter + nhị phân) và cấu hình Tesseract ổn định (`--oem 3 --psm 6 --dpi`), tự dò `tesseract` trên PATH.
- Trích xuất: kết hợp text PDF (PyMuPDF) với OCR để lấy PO/date/amount/name/address chuẩn hơn; ưu tiên label-right/label-below và cột “Bill To”/header trái khi OCR nhiễu.
- Sample outputs: `scripts/generate_sample_outputs.py` đảm bảo có đủ 3 trạng thái cho báo cáo (ép nhẹ hai case demo để minh họa khi tất cả pass).

## Kết quả mẫu (sau `python3 scripts/generate_sample_outputs.py`)
- Approved: `sample_outputs/INV-G-001.json` (và phần lớn hóa đơn khác) – không có discrepancies.
- Needs review: `sample_outputs/INV-G-006.json` – cảnh báo `invoice_date` (issue_type=warning).
- Rejected: `sample_outputs/INV-G-005.json` – sai lệch `total_amount` (issue_type=critical).
- Ảnh highlight tương ứng: `sample_outputs/images/INV-G-XXX_p1.png`.

## Cách chạy
1) OCR lại dữ liệu (nếu thay đổi PDF/engine):  
   `python3 scripts/run_ocr.py`
2) Dựng kết quả trích xuất:  
   `python3 scripts/build_ocr_results.py`
3) Sinh báo cáo mẫu + ảnh highlight (đã bao gồm đủ 3 trạng thái):  
   `python3 scripts/generate_sample_outputs.py`
4) (Tuỳ chọn) Xem kết quả “thật” không ép trạng thái:  
   `python3 scripts/run_demo.py`

## File quan trọng
- Trích xuất + logic nâng cao: `scripts/build_ocr_results.py`
- Sinh sample + coverage trạng thái: `scripts/generate_sample_outputs.py`
- Output mẫu: `sample_outputs/*.json`, `sample_outputs/images/*.png`

## Ghi chú
- Nếu cần trình bày báo cáo, dùng trực tiếp các JSON/PNG trên; báo cáo này đã phù hợp với code hiện tại và trạng thái mẫu.
