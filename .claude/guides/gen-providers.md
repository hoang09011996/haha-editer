# Nguồn gen ảnh/clip (flow / gemini / aistudio)

Hướng dẫn thao tác các nguồn gen ảnh/clip qua phiên Chrome đã đăng nhập của người dùng. Agent gen (job sheets/flow/clips của `vidflow quick`) đọc đúng mục của nguồn được giao.

Quy tắc chung cho mọi nguồn:
- Dùng công cụ Claude in Chrome trên trình duyệt của người dùng; không có công cụ trình duyệt → DỪNG, báo "Cần mở phiên bằng `claude --chrome`".
- Chưa đăng nhập → nhờ người dùng tự đăng nhập; không nhập mật khẩu hộ.
- KHÔNG gọi API, KHÔNG tạo API key, KHÔNG bật thanh toán, KHÔNG nhập thẻ. Mọi màn hình nhắc phí/thanh toán/nâng cấp trả tiền = hết lượt: chạy `uv run vidflow quick limit -p <project> --provider <nguồn> --kind image|video --reason "<nguyên văn>"` rồi DỪNG.
- Dấu hiệu hết lượt (mọi nguồn): thông báo đạt giới hạn/hạn mức ngày, hết tín dụng, "try again tomorrow", nút tạo bị khóa kèm lời nhắc nâng cấp → `quick limit ...` rồi DỪNG.
- Tải file: Chrome phải tắt "Ask where to save each file before downloading". File không xuất hiện trong ~/Downloads sau 15 giây → DỪNG và nhờ người dùng tắt tùy chọn đó.
- Dịch vụ từ chối một prompt (vi phạm chính sách, lỗi một lần) KHÔNG phải hết lượt: `quick fail ...` rồi làm mốc tiếp.
- Giao diện khác hẳn mô tả dưới đây → làm theo giao diện thật nếu chắc chắn, ghi lại ngắn gọn giao diện quan sát được (vị trí nút, tên model, cách đính ảnh, cách tải) trong báo cáo để cập nhật file này; không chắc → DỪNG và báo.

## flow
Theo `flow-operator.md` (giao diện Flow, cài đặt tác nhân, tải 1K/2K, điều kiện dừng) cùng các mục gen trong `quick-writer.md`. Đính ảnh tham chiếu bằng nút "+" ở ô "Bạn muốn tạo gì?".

## gemini
Trang: https://gemini.google.com (tài khoản gói Google AI của người dùng; hạn mức theo ngày, tách khỏi tín dụng Flow).
- Mỗi mốc/clip: mở cuộc trò chuyện MỚI để ảnh trước không ảnh hưởng (trừ khi chính `attach` yêu cầu ảnh mốc trước).
- Ảnh: chọn công cụ/chế độ tạo ảnh (Nano Banana / "Create image"); đính các file trong `attach` bằng nút tải tệp/"+" của ô nhập; dán prompt nguyên văn, thêm câu "Aspect ratio <tỉ lệ>." ở cuối nếu giao diện không có nút chọn tỉ lệ; tạo 1 ảnh.
- Clip: chọn công cụ video (Veo); tải ảnh nguồn `image` lên làm khung đầu; dán prompt nguyên văn; chờ (kiểm tra mỗi ~20 giây, tối đa 10 phút).
- Tải: dùng nút tải xuống của ảnh/video (bản chất lượng cao nhất có), lấy file mới nhất trong ~/Downloads.
- Hạn mức video ở Gemini thường rất thấp (vài video/ngày): gặp thông báo giới hạn → `quick limit ... --kind video` rồi DỪNG.

## aistudio
Trang: https://aistudio.google.com (đăng nhập bằng tài khoản Google của người dùng, chỉ dùng giao diện web).
- Chọn model tạo ảnh (Nano Banana / Gemini image) hoặc model video (Veo) trong danh sách model của giao diện; đặt tỉ lệ khung hình trong phần cài đặt chạy nếu có.
- Đính ảnh tham chiếu (`attach` / `image`) bằng nút thêm tệp của ô prompt; dán prompt nguyên văn; chạy (Run).
- Tải ảnh/video bằng nút tải xuống của kết quả.
- AI Studio có thể yêu cầu dự án có thanh toán hoặc API key cho một số model (đặc biệt video): gặp bất kỳ yêu cầu nào như vậy → `quick limit ... --reason "cần trả phí"` rồi DỪNG. Không chọn "Get API key", không liên kết billing.
