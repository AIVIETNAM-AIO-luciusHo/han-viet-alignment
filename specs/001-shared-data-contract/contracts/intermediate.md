# Hợp đồng trung gian F01 — PROPOSED

Trạng thái NEEDS_CONFIRMATION (NC01–NC03). Không phải schema đã triển khai.
Đề xuất JSONL UTF-8/NFC/LF cho sidecar, artifact thô giữ nguyên encoding/bytes gốc.
Mỗi record có schema_version, record_id, run_id; khóa bắt buộc và enum kiểm tra tường minh.
Không đưa trường sidecar vào bảy cột bàn giao.

| Entity | Trường đề xuất | Ràng buộc |
| --- | --- | --- |
| Document | book_id, doc_id, sequence, doc_type, has_phien_am | thuộc danh mục; sequence dương, ID theo nguồn |
| SourceRegion | region_id, doc_id, component, source_path, source_sha256, pdf_page, folio, image_path, image_size, bbox, transform_ref | component han/phien_am/dich_nghia; page từ 1; box 4 điểm pixel ảnh đích; tham chiếu phép crop/rotate/scale về PDF |
| RawArtifact | artifact_id, doc_id, method, path, sha256, source_region_ids, engine, engine_version, model_version, prompt_ref | method ocr/pdf_text; append-only; tool không cung cấp model/prompt ghi null có lý do |
| CleanSegment | segment_id, doc_id, component, ordinal, text, revision, raw_spans, source_region_ids, correction_ids | thứ tự xác định; raw_spans là artifact_id + start/end Unicode code point, khoảng [start,end) |
| AlignmentCandidate | candidate_id, doc_id, ordinal, han_segment_ids, phien_am_segment_ids, viet_segment_ids, relation, review_status, trace_status | relation 1-1/1-n/n-1/n-m; tất cả segment cùng doc; không phiên âm dùng mảng rỗng |
| Correction | change_id, segment_id, from_revision, to_revision, before, after, reason, source_region_ids, editor, reviewer, timestamp | reviewer có thể null khi chờ; thời gian ISO 8601 có timezone |
| RunManifest | run_id, schema_version, code_revision, config, source_hashes, tool_versions, device, started_at, finished_at | config loại secret; code_revision cần ghi dirty flag nếu chạy với thay đổi local |
| ValidationReport | report_id, snapshot_id, issues, metrics, coverage, review_summary | issue có code/entity/field/message/severity; metric có numerator/denominator/status |

SourceRegion chưa xác định page/box: dùng null và missing_reason, không dùng page=0 hoặc box giả.
OCR không trả box: bbox=null được phép nếu còn trang/ảnh và nguồn đủ đối chiếu.
Raw spans chưa có vì engine chưa thực hiện: không coi segment là sạch đã sẵn sàng; trace_status=incomplete.
Một ký tự sạch có thể liên quan nhiều ký tự thô; không ép ánh xạ 1–1 sau ghép/sửa.

## Snapshot và trạng thái
Draft candidate chưa có sent_id bàn giao; candidate_id nội bộ ổn định trong một run.
Khi snapshot được duyệt, gán sent_id theo thứ tự doc_id/câu, lưu candidate→sent_id mapping.
Nếu thay ranh giới, snapshot mới giữ lịch sử và mapping, không âm thầm tái sử dụng sent_id cũ.
review_status: pending/changes_requested/approved. trace_status: complete/incomplete.
Chỉ approved + trace complete + validation không lỗi chặn mới được đánh dấu ready_for_export.
Điều kiện này không có nghĩa mọi chỉ số nghiệm thu cả sách đã đạt.

## Tương thích metadata hiện có
Không đổi header hiện tại trong giai đoạn này. Document/SourceRegion/Correction cần mapping
với TSV hiện có; các trường bổ sung lưu sidecar trong workspace. Plan phải mô tả mapping,
validation khóa ngoại và tránh hai nguồn dữ liệu mâu thuẫn trước khi code.
Schema version không tương thích phải bị từ chối có hướng dẫn, không đoán kiểu dữ liệu.
Mã lỗi đề xuất: UNKNOWN_BOOK, INVALID_ID, CONFIG_CONFLICT, UNSUPPORTED_SCHEMA,
MISSING_PHONETIC, UNEXPECTED_PHONETIC, BROKEN_REFERENCE, INCOMPLETE_TRACE,
RAW_HASH_MISMATCH, INVALID_EXPORT_FORMAT. Chi tiết severity chốt trong plan.
