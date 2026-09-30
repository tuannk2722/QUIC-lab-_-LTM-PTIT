# Bằng chứng P0 (2026-09-30)

Các file này là logs/metadata thực từ lượt P0; không phải benchmark dataset. Baseline git 7e54ad6, working tree dirty=true. Không lưu cert/private key, PCAP hoặc số liệu performance giả. Whitespace của log được chuẩn hóa (tab thành spaces, bỏ dòng trắng cuối) để diff sạch; nội dung và exit codes giữ nguyên.

- toolchain.json: metadata official download và checksum đã so bằng sha256sum trước giải nén.
- modules.txt / modules-verify.txt: go list -m all / go mod verify, exit 0.
- tests.log: make test, exit 0; config/CLI/TLS tests và compile-only API smoke.
- g00-commands.log: lệnh subprocess, stdout/stderr và expected/actual exit; bao gồm build, help/version, SAN và negative cases.
- doctor.txt: lần inventory trong sandbox bị netlink permission (doctor 3, Make 2); giữ lại để không che failure.
- doctor-host.txt: inventory cuối cùng ngoài sandbox, UID 1000, exit 0. Không sudo, không network mutation.
- permission-attempts.txt: lịch sử lỗi quyền ban đầu, giữ nguyên; không còn là blocker G00 sau lần probe thành công.
- network-probe.log: log người dùng chạy trong WSL2 lúc 2026-09-30T04:48:25Z; có netem 50ms, mirred→ifb0, PASS sau xóa namespace. Không có traffic, counters bằng 0 là đúng scope primitive probe.
- network-probe-provenance.json: đường dẫn/hash log gốc, bản chuẩn hóa và script được đối chiếu. Log không ghi numeric exit code riêng; không bịa exit 0 từ shell. Người dùng xác nhận thành công, control flow của script và PASS corroborate kết quả. G00 đã PASS; G01–G12 NOT_RUN.
- api-*.txt: go doc/source đúng cache v0.63.0. Lệnh go doc chạy từ repo với GOPATH local có thể in import path chứa `.tools/gopath/pkg/mod`; module chính thức được xác nhận riêng trong go.mod/modules.txt và compile smoke. api-congestion.txt trích internal/ackhandler/sent_packet_handler.go đúng tag v0.63.0 (nguồn trong VERSIONS).

Mọi lệnh Go dùng GOTOOLCHAIN=local, GOPATH=$PWD/.tools/gopath, GOCACHE=$PWD/.tools/gocache. Sau dependency download, API doc/module verification được chạy GOPROXY=off. Không chạy workload, application network tests hoặc G01–G12. Các nguồn/trạng thái/giới hạn chi tiết ở VERSIONS và ACCEPTANCE_RESULTS.
