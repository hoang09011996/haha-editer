# vidflow — Nhân vật @TÊN, clip động, xuất MP4 và giao diện mới

Ngày: 2026-10-12 · Trạng thái: người dùng duyệt thiết kế, chờ duyệt spec.
Mockup: https://claude.ai/artifact/94mb9nfWitwdRCLiY7SDvh (Bảng mốc, Nhân vật, Xem thử & Xuất, Tạo video nhanh).

## Mục tiêu

Quy trình nhanh (`vidflow quick`, video doodle ~100–200 mốc) hiện thiếu: nhân vật nhất quán giữa các mốc, chuyển động, xuất video không cần CapCut, và giao diện để theo dõi hàng trăm mốc. Spec này thêm:

1. Nhân vật `@TÊN` (của bộ kênh và của từng video), ảnh nhân vật tự đính khi gen trong Flow.
2. Nối cảnh: mốc đánh dấu `cont` được đính ảnh mốc trước làm tham chiếu.
3. Clip động: một số mốc (tối đa N) được gen clip Veo từ ảnh của mốc.
4. Xuất MP4 bằng Remotion (mặc định); draft CapCut thành tùy chọn và nhận được clip.
5. Giao diện mới cho toàn bộ `vidflow ui` theo mockup, thêm 4 màn của quy trình nhanh.

Ràng buộc giữ nguyên: chỉ dùng tín dụng gói Google Flow (không `vidflow gen/estimate/refimg`); không sửa `state.json`, `quick.yaml`, `beats.json` bằng tay — mọi ghi qua CLI; prompt phải qua kiểm duyệt mới được gen; model video và độ phân giải (mặc định 720p) chọn ở bước tạo video.

Ngoài phạm vi: app Flow "Smart Ref Binding" (chạy thử riêng sau), nghiên cứu đối thủ, SFX/nhạc ElevenLabs, video dọc 9:16 riêng.

## Giai đoạn 1 — Dữ liệu, CLI, agent

### Nhân vật

```python
class Character(BaseModel):
    id: str            # IN HOA, [A-Z][A-Z0-9_]{1,23}, ví dụ MODERNYOU
    name: str = ""     # tên tiếng Việt hiển thị
    desc: str          # mô tả cố định (tiếng Anh, dùng trong prompt sheet và prompt mốc)
    color: str = ""    # màu đặc trưng #RRGGBB
    image: str | None = None  # đường dẫn tương đối tới ảnh sheet
```

- Bộ kênh: `presets/<id>.yaml` thêm `characters: [Character]`; ảnh ở `presets/refs/<preset-id>/<CHAR>.png|jpg`.
- Video: `quick.yaml` thêm `characters: [Character]`; ảnh ở `projects/<tên>/refs/<CHAR>.png|jpg`.
- `quick.yaml` thêm `channel_chars: [str]` — các nhân vật bộ kênh được dùng trong video này (mặc định: tất cả).
- Tên tra cứu = hợp của `channel_chars` và `characters`; trùng `id` giữa hai nơi → lỗi.

### Cài đặt video nhanh (`quick.yaml`)

```yaml
flow: {image_model: "Nano Banana 2", video_model: "Veo 3.1 Lite", resolution: "720p"}
max_clips: 12        # 0 = chỉ ảnh tĩnh
allow_cont: true     # cho phép quick-writer đánh dấu nối cảnh
```
`video_model` rỗng khi `max_clips > 0` → `quick flow --clips` từ chối chạy và yêu cầu chọn model.

### Mốc (`beats.json`)

```python
class Clip(BaseModel):
    enabled: bool = False
    prompt: str = ""
    review: Review | None = None
    file: str | None = None            # clips/NNN_MM-SS.mp4
    status: Literal["pending", "ok", "redo", "error"] = "pending"
    error: str = ""

class Beat(BaseModel):          # thêm trường mới, trường cũ giữ nguyên
    refs: list[str] = []         # CLI tự tách từ @TÊN trong prompt
    cont: bool = False           # nối cảnh với mốc liền trước
    clip: Clip = Clip()
    error: str = ""              # lý do Flow từ chối ảnh gần nhất
```
`beats.json` cũ (không có trường mới) vẫn đọc được.

`refs` không do agent khai: `set-prompt(s)` tách `@([A-Z][A-Z0-9_]+)` từ prompt ảnh (và prompt clip), kiểm tra từng tên có trong danh sách tra cứu; tên lạ → từ chối cả lô, báo tên. Mốc 1 không được `cont`.

### Luật được gen (dùng chung cho CLI và UI)

Ảnh mốc cần gen khi: `status ∈ {pending, redo}`, prompt đạt, đã có thời gian, VÀ
- mọi nhân vật trong `refs` đã có ảnh — thiếu → mốc "bị chặn: thiếu @X";
- nếu `cont`: mốc trước đã có ảnh — chưa có → "chờ mốc trước".

Clip cần gen khi: `clip.enabled`, ảnh mốc `ok`, prompt clip đạt, `clip.status ∈ {pending, redo, error}`, và `flow.video_model` đã chọn. Số mốc `clip.enabled` không vượt `max_clips` (CLI từ chối bật thêm).

### Lệnh CLI mới / thay đổi (`vidflow quick ...`)

| Lệnh | Việc |
|---|---|
| `set-chars --json` | quick-writer ghi nhân vật riêng của video `[{id,name,desc,color}]` |
| `char-image <CHAR> <file> [--channel]` | gắn ảnh sheet cho nhân vật video (hoặc bộ kênh) |
| `chars [--json]` | liệt kê nhân vật + có ảnh chưa + số mốc dùng + số mốc bị chặn |
| `set-prompts` | nhận thêm `cont` cho mỗi mốc; tự tách `refs` |
| `set-clip-prompts --json` | `[{n, prompt, verdict, score, issues}]`, bật `clip.enabled` |
| `clip on|off <n...>` | người dùng bật/tắt clip (giới hạn `max_clips`) |
| `set-clip <n> <file>` | nhập clip đã gen → `clips/NNN_MM-SS.mp4`, `clip.status=ok` |
| `fail <n> --reason ... [--clip]` | ghi lỗi Flow từ chối cho ảnh hoặc clip |
| `beats --todo` | thêm `attach: [đường dẫn tuyệt đối]` = ảnh nhân vật theo `refs` + ảnh mốc trước nếu `cont`; thêm `blocked: [{n, reason}]` |
| `beats --todo-clips` | danh sách clip cần gen, kèm `image` (ảnh nguồn), `prompt`, model, độ phân giải |
| `settings --video-model ... --resolution ... --max-clips ... --allow-cont/--no-allow-cont` | ghi cài đặt Flow |

### Agent

- **quick-writer**
  - Sau bước kịch bản: đề xuất nhân vật riêng của video (mô tả theo mẫu character sheet: bố cục toàn thân trước/nghiêng/sau, đầu 3 góc, 4 biểu cảm, đạo cụ; nền trắng lưới mờ; câu neo phong cách của bộ kênh) → `set-chars`.
  - Bước prompt: mọi nhân vật trong ảnh phải nhắc bằng `@TÊN`; đánh dấu `cont` khi mốc tiếp nối cùng khoảnh khắc (chỉ khi `allow_cont`); đề xuất tối đa `max_clips` mốc có hành động rõ làm clip, viết prompt clip (câu neo phong cách + "frame-by-frame doodle motion" + chuyển động + máy quay + dòng `Sound:`), tự kiểm duyệt như prompt ảnh → `set-clip-prompts`.
  - Bảng kiểm thêm: nhân vật nhắc bằng `@TÊN` và không mô tả lại ngoại hình mâu thuẫn với sheet; prompt clip mô tả MỘT chuyển động ≤ 8 giây.
- **flow-operator** (cập nhật `flow-operator.md` và phần "Gen ảnh mốc" của `quick-writer.md`):
  - Character sheet: nhân vật chưa có ảnh → gen trong Flow từ `desc` → `char-image`.
  - Ảnh mốc: trước khi dán prompt, bấm "+" đính từng file trong `attach` (theo thứ tự nhân vật rồi ảnh mốc trước); mốc bị chặn thì bỏ qua và báo.
  - Clip: chế độ tạo video từ ảnh, đính `image`, model/độ phân giải theo `--todo-clips`, thời lượng ngắn nhất ≥ độ dài mốc → `set-clip`.
  - Flow từ chối → `fail` kèm nguyên văn thông báo, tiếp mốc sau; điều kiện dừng giữ như cũ.
- Job UI/CLI mới: `chars` (gen sheet), `clips` (gen clip). `flow` giữ nguyên tên cho ảnh mốc.

## Giai đoạn 2 — Xuất video

### `vidflow quick render` (Remotion, mặc định)

```
vidflow quick render -p <project> [--resolution 1080p|720p] [--transition scene|cut|fade]
  [--clip-fit trim|speed] [--zoom/--no-zoom] [--subtitles/--no-subtitles]
  [--clip-audio/--no-clip-audio] [--logo/--no-logo] [--music/--no-music]
```
- Sinh `projects/<tên>/tmp/render-props.json`: mỗi mốc `{src, kind: image|video, start, end, cont}`, `audio`, `subtitles`, `logo`, `music`, `fps`, kích thước.
- Mốc có clip `ok` dùng clip; còn lại dùng ảnh; mốc chưa có ảnh → khung trống (cảnh báo số mốc).
- `clip-fit`: `trim` cắt clip theo độ dài mốc (clip ngắn hơn mốc → giữ khung cuối); `speed` đổi tốc độ cho vừa.
- `transition=scene` (mặc định): mốc `cont` cắt thẳng, mốc mở cảnh mới mờ chéo 0.3 giây.
- Logo: `presets/<id>.yaml` thêm `logo: <đường dẫn>`. Nhạc: `audio/music.(mp3|wav)` nếu có, âm lượng thấp dưới giọng.
- Gọi `npx remotion render` trong `remotion/` với `--public-dir` trỏ vào project và `--props`; ra `projects/<tên>/out/<tên>-vN.mp4`.
- Nâng `remotion/src/DoodleVideo.tsx` từ bản thử: thêm `<OffthreadVideo>` cho clip, chuyển cảnh, logo, nhạc; khóa phiên bản `remotion` cụ thể thay cho `latest`.

### Draft CapCut (tùy chọn)

`vidflow quick build` giữ nguyên; `assemble` nhận thêm clip (đoạn video thay cho ảnh ở mốc có clip `ok`, cắt theo độ dài mốc). Ràng buộc sandbox `~/Movies` và "CapCut phải đóng" giữ như cũ.

## Giai đoạn 3 — Giao diện

### Phong cách (áp dụng toàn bộ `src/vidflow/ui/static`)

- Bỏ nền sao/tinh vân (`galaxy.js`, `#stars`, `.nebula`), gradient, glow, emoji trong UI.
- Token màu trên `:root`: nền `#E3EBE2`, mặt khung `#F2F6F1`, đường kẻ `#CCD8CB`, ô nhập `#EAF1E9`, viền nút `#B8C7B7`, chữ `#0E1238`, chữ phụ `#4A4F6E`; chính `#000080`, phụ `#0069ba`, thành công `#1fba00` (chữ xanh lá `#157A00`), lỗi `#C8283E`, cảnh báo `#8A4B00` trên `#FDEBD2`.
- Phông: Be Vietnam Pro (chữ), JetBrains Mono (số mốc, thời gian, `@TÊN`) qua Google Fonts.
- Khung 3 vùng: thanh trái (logo, video đang mở, điều hướng, tiến độ, trạng thái Flow + tín dụng), vùng giữa, khung phải (chi tiết / xuất). Dưới ~900px các vùng xếp dọc.
- Trạng thái luôn có chữ (Có ảnh / Đang gen / Lỗi / Chờ / Gen lại / Bị chặn), không chỉ dựa vào màu.
- Màn của quy trình đầy đủ (kịch bản, cảnh, khung, prompt, kiểm duyệt) giữ chức năng, chỉ đổi giao diện; vẫn bắt đăng nhập.

### Màn quy trình nhanh

1. **Bảng mốc**: thanh tiến độ (có ảnh / đang gen / lỗi / chờ / bị chặn); nút Tạm dừng, Chạy lại mốc lỗi, Gen clip; bộ lọc (Tất cả, Lỗi, Chưa có ảnh, Bị chặn, Clip, Nối cảnh); mốc gom theo cảnh (cảnh = chuỗi mốc nối bằng `cont`; mốc không `cont` mở cảnh mới), màu cảnh lấy từ màu nhân vật chính hoặc bảng màu cố định; thẻ mốc: ảnh, số, thời gian, lời đọc, `@TÊN`, nhãn CLIP, trạng thái; khung phải: lời đọc, ảnh sẽ đính kèm, prompt ảnh + điểm, công tắc clip + prompt clip, Gen lại ảnh / AI viết lại / Lưu.
2. **Nhân vật**: hai nhóm (bộ kênh, video này); thẻ có ảnh sheet, `@TÊN`, màu, mô tả, số mốc dùng; thiếu ảnh → nổi bật "chặn N mốc" + Gen sheet trong Flow / Tải ảnh lên; Đưa vào bộ kênh.
3. **Xem thử & Xuất**: trình phát trên trình duyệt (ảnh/`<video>` theo mốc + `<audio>` giọng đọc + phụ đề), dòng thời gian tô màu theo cảnh, đánh dấu clip/lỗi/chưa có ảnh, sóng âm; bấm mốc để nhảy tới. Khung Xuất MP4 (các tùy chọn của `quick render`), Draft CapCut, danh sách bản đã xuất có link tải. Kéo mép mốc để đổi thời lượng: KHÔNG làm ở bản này (thời lượng do giọng đọc quyết định).
4. **Tạo video nhanh**: bộ kênh, chủ đề gợi ý, nhân vật bộ kênh dùng, tỉ lệ, model ảnh, model clip (bắt buộc khi `max_clips > 0`), độ phân giải, số clip tối đa, cho phép nối cảnh.

### API mới (`server.py`)

- `GET /api/quick/{name}`: quick.yaml + beats + nhân vật + tóm tắt trạng thái (kể cả `blocked`).
- `POST /api/quick` (tạo), `POST /api/quick/{name}/settings`, `/pick`, `/redo`, `/clip` (on/off), `/prompt` (sửa prompt ảnh/clip của một mốc — đánh dấu review trống để phải kiểm duyệt lại).
- `POST /api/quick/{name}/chars/{id}/image` (tải ảnh lên), `POST /api/quick/{name}/chars/{id}/promote`.
- `POST /api/quick/{name}/jobs` với `kind ∈ {ideas, script, prompts, chars, flow, clips, voice, render, build}`; dùng `JobRunner` hiện có (mỗi lúc một job).
- `GET /media/...` phục vụ cả `clips/`, `refs/`, `out/`, `presets/refs/`.
- Mọi ghi đi qua hàm trong `vidflow.quick.ops` (cùng luật với CLI).

## Kiểm thử

- pytest: mô hình (đọc beats.json cũ), tách `@TÊN` + từ chối tên lạ, luật bị chặn/chờ mốc trước, giới hạn `max_clips`, `attach` đúng thứ tự, `set-clip`/`fail`, `char-image` cả hai phạm vi, `promote`.
- pytest: sinh `render-props.json` (ảnh/clip/khung trống, trim/speed, chuyển cảnh theo `cont`); `assemble` với clip.
- pytest (TestClient): các API mới, có bắt đăng nhập.
- Thủ công: render Remotion một project nhỏ; chạy toàn quy trình với ~10 mốc, 2 nhân vật, 2 clip trong Flow.

## Thứ tự làm

Giai đoạn 1 → 2 → 3; mỗi giai đoạn một kế hoạch triển khai và một lần duyệt. Giai đoạn 3 có thể tách đổi phong cách chung (3a) và 4 màn mới (3b).
