# Result schema v1

`result-records.schema.json` định nghĩa từng typed record dưới `$defs.run`, `$defs.stream`, `$defs.progress`. Validate bằng đúng `$ref` tương ứng (root là container schema, không tự chọn record). `x-csv-columns` là thứ tự cột bắt buộc. CSV strings được convert kiểu; ô rỗng chỉ map null với field nullable, error_message/error_code thành chuỗi rỗng khi không có lỗi.

Các ràng buộc chéo (N rows, FK, formula, successful checksums, total bytes, correct cohort counts) do analysis/validate.py thực hiện theo METRICS_AND_RESULTS. JSON Schema không thể chứng minh 0-RTT hoặc network condition thật. Không có sample measured row trong thư mục này.
