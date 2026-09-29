"use strict";
// vidflow Studio — quy trình 7 bước (trái) · nội dung bước (giữa) · Trợ lý AI (phải).

// ================= dữ liệu tĩnh =================
const OPT = {
  shot_size: ["Toàn cảnh (wide)", "Trung-rộng (medium wide)", "Trung (medium)", "Cận trung (medium close-up)", "Cận cảnh (close-up)", "Đặc tả (extreme close-up)", "Qua vai (over-the-shoulder)", "Góc nhìn nhân vật (POV)"],
  angle: ["Ngang tầm mắt", "Góc thấp (low angle)", "Góc cao (high angle)", "Từ trên xuống (top-down)", "Nghiêng (dutch angle)", "Selfie cầm tay"],
  camera_move: ["Đứng yên (static)", "Cầm tay nhẹ (handheld)", "Đẩy vào chậm (slow dolly-in)", "Kéo ra (dolly-out)", "Lia ngang (pan)", "Lia dọc (tilt)", "Bám theo (tracking)", "Zoom giật (snap zoom)", "Xoay quanh (orbit)"],
  lens: ["24mm", "35mm", "50mm", "85mm", "100mm macro"],
  dof: ["Xóa phông mạnh (f/1.4)", "Xóa phông vừa (f/2.8)", "Nét sâu (f/8)"],
  composition: ["Cân giữa", "Lệch tâm (1/3)", "Chừa khoảng trống phía trước", "Khung trong khung"],
  light_quality: ["Mềm, khuếch tán", "Cứng, bóng rõ", "Tương phản thấp", "Tương phản cao 4:1"],
  color_temp: ["Ấm (3200K)", "Trung tính (5600K)", "Lạnh (6500K+)", "Hỗn hợp ấm/lạnh"],
  purpose: ["Hook mở đầu", "Diễn biến", "Cao trào", "Punchline / twist", "Kêu gọi hành động"],
  style_type: [["anim_3d", "Hoạt hình 3D"], ["anim_2d", "Hoạt hình 2D"], ["live_action", "Người thật"], ["ugc", "Quay điện thoại (UGC)"]],
  platform: ["tiktok", "reels", "youtube_shorts", "youtube", "facebook"],
  voices: ["Puck", "Kore", "Charon", "Fenrir", "Aoede", "Leda", "Orus", "Zephyr"],
  models: ["", "Veo 3.1 Lite", "Veo 3.1 Fast", "Veo 3.1 Quality", "Omni 1.1 Flash"],
};
const ANTI_AI = [
  ["film_grain", "Hạt phim nhẹ"], ["handheld", "Máy cầm tay rung nhẹ"],
  ["imperfections", "Chi tiết không hoàn hảo"], ["practical_light", "Ánh sáng thực tế"],
  ["real_speed", "Tốc độ chuyển động thật"], ["micro_detail", "Chi tiết vi mô da/tóc/vải"],
  ["off_center", "Bố cục lệch tâm"], ["ugc_phone", "Kiểu quay điện thoại"],
];
const AVOID = ["no on-screen text", "no subtitles", "no watermark", "no name labels", "no warped hands or extra fingers", "no dialogue", "no music"];

// Hướng dẫn cho từng ô: gợi ý + ví dụ (bấm để điền)
const HELP = {
  title: { hint: "Tên video, ngắn, gây tò mò.", ex: ["Chưa có cà phê thì chưa phải người", "1 ngày làm barista", "Sáng thứ Hai của dân văn phòng"] },
  idea: { hint: "Một câu: chuyện gì, ai, cảm xúc gì, dài bao lâu. Càng cụ thể AI càng viết đúng.", ex: ["Video hài 20s: anh chàng đeo kính sáng dậy như zombie, thử cà phê sữa chua theo trend rồi tỉnh vì chua", "Review 30s quán cà phê nhỏ ở Hà Nội, tông ấm, người thật", "Kể chuyện 45s: cô gái mở tiệm trà chanh từ 0 đồng"] },
  audience: { hint: "Ai sẽ xem? Ảnh hưởng giọng văn và nhịp.", ex: ["Dân văn phòng 22–35 tuổi", "Sinh viên thích trend", "Người yêu cà phê"] },
  platform: { hint: "Nơi đăng. TikTok/Reels ưu tiên 9:16, hook 2 giây đầu.", ex: ["tiktok", "reels", "youtube_shorts"] },
  mood: { hint: "Cảm xúc chủ đạo.", ex: ["Hài, dí dỏm", "Ấm áp, thư thái", "Kịch tính, bất ngờ"] },
  palette: { hint: "3–4 màu chủ đạo của khung hình.", ex: ["Nâu cà phê, kem, xanh bạc hà", "Cam hoàng hôn, tím than", "Trắng, gỗ sáng, xanh lá"] },
  film_look: { hint: "Chất ảnh — giúp video bớt 'sạch như AI'.", ex: ["Hạt phim nhẹ, màu Kodak Portra 400", "Máy điện thoại, không chỉnh màu", "Hoạt hình 3D có texture, không bóng nhựa"] },
  reference: { hint: "Phim/quảng cáo/kênh có thẩm mỹ bạn thích (mô tả, không cần tên).", ex: ["Phim hoạt hình 3D gia đình, màu ấm", "Vlog đời thường quay cầm tay"] },
  name: { hint: "Tên gọi nhân vật / bối cảnh / đạo cụ.", ex: ["Tuấn", "Bếp chung cư", "Ly cà phê sữa chua"] },
  age: { hint: "Tuổi hoặc độ tuổi.", ex: ["khoảng 30", "ngoài 20", "trung niên"] },
  build: { hint: "Dáng người.", ex: ["gầy cao", "tròn trịa", "vừa người, vai rộng"] },
  face: { hint: "Nét mặt nổi bật, dễ nhận ra.", ex: ["mặt tròn, má phúng phính", "mặt dài, cằm nhọn, tàn nhang nhẹ"] },
  hair: { hint: "Kiểu, màu, chi tiết đặc trưng.", ex: ["đen, rẽ ngôi trái, một lọn dựng trên đỉnh", "búi cao, tóc con lòa xòa"] },
  accessories: { hint: "Kính, đồng hồ, khuyên tai…", ex: ["kính gọng tròn to màu đen", "khuyên tai bạc nhỏ"] },
  wardrobe: { hint: "Trang phục cố định qua các cảnh.", ex: ["áo thun navy, quần ngủ caro xanh trắng, dép lê xám", "sơ mi trắng xắn tay, tạp dề nâu"] },
  expressions: { hint: "Biểu cảm đặc trưng để hài/diễn.", ex: ["mắt lờ đờ khi buồn ngủ, trợn tròn khi bất ngờ"] },
  voice_note: { hint: "Tính cách / cách nói.", ex: ["lầy lội, hay tự nói một mình"] },
  place: { hint: "Nơi cụ thể, có chất Việt Nam nếu hợp.", ex: ["bếp chung cư nhỏ ở Hà Nội", "quán cà phê vỉa hè Sài Gòn"] },
  time_of_day: { hint: "Giờ trong ngày quyết định ánh sáng.", ex: ["7h sáng", "hoàng hôn", "đêm muộn"] },
  details: { hint: "Đồ vật cụ thể, hơi bừa bộn đời thường — chống 'chất AI'.", ex: ["bồn rửa còn bát, lịch treo tường, ấm siêu tốc, chậu trầu bà trên bệ cửa"] },
  light_sources: { hint: "Nguồn sáng có thật trong cảnh.", ex: ["nắng xiên qua cửa sổ trái, đèn trần vàng", "đèn neon biển hiệu, đèn đường"] },
  ambience: { hint: "Âm nền đặc trưng của nơi đó.", ex: ["xe máy xa xa, tủ lạnh ù, chim sẻ", "tiếng máy xay cà phê, nhạc nhỏ"] },
  purpose: { hint: "Vai trò cảnh trong câu chuyện.", ex: OPT.purpose },
  narration: { hint: "Lời dẫn đọc bằng giọng AI. ~2.5 từ/giây: ≤19 từ cho 8s, ≤14 cho 6s, ≤9 cho 4s.", ex: ["Bảy giờ sáng, anh Tuấn chính thức ở chế độ zombie.", "Nghe mạng rủ rê, anh thử ngay cà phê sữa chua."] },
  dialogue: { hint: "Câu nhân vật nói trong clip (tùy chọn, ngắn). Để trống nếu dùng lời dẫn.", ex: ["Ủa… sao nó chua vậy trời?"] },
  prop_state: { hint: "Trạng thái đạo cụ/trang phục ở cảnh này — giữ liền mạch.", ex: ["ly đã uống một nửa, kính lệch", "tóc còn ướt, áo nhăn"] },
  action: { hint: "MỘT hành động chính. Nhiều hành động = dễ lộ AI.", ex: ["lê bước vào bếp như zombie, suýt đâm vào tủ lạnh", "nhấp một ngụm rồi mặt nhăn vì chua"] },
  beats: { hint: "Chia hành động theo giây (tùy chọn) để kiểm soát nhịp.", ex: ["[0-2s] mở tủ lạnh\n[2-5s] nhìn hộp sữa chua nghi ngờ\n[5-6s] nhún vai"] },
  expression: { hint: "Biểu cảm nhân vật trong cảnh.", ex: ["mắt díp, miệng ngáp", "trợn mắt, lông mày nhướng cao"] },
  shot_size: { hint: "Cỡ cảnh.", ex: OPT.shot_size.slice(0, 5) },
  angle: { hint: "Góc máy.", ex: OPT.angle.slice(0, 4) },
  camera_move: { hint: "Chỉ MỘT chuyển động máy.", ex: OPT.camera_move.slice(0, 5) },
  lens: { hint: "Ống kính cụ thể thay cho chữ 'cinematic'.", ex: OPT.lens },
  dof: { hint: "Độ nét trước/sau.", ex: OPT.dof },
  composition: { hint: "Bố cục khung hình.", ex: OPT.composition },
  light: { hint: "Nguồn sáng + hướng, có lý do tồn tại.", ex: ["nắng sớm xiên qua cửa sổ bên trái", "ánh đèn tủ lạnh hắt lên mặt"] },
  light_quality: { hint: "Chất sáng.", ex: OPT.light_quality },
  color_temp: { hint: "Nhiệt màu.", ex: OPT.color_temp },
  atmosphere: { hint: "Thứ lơ lửng trong không khí làm ánh sáng thật hơn.", ex: ["bụi lơ lửng trong nắng", "hơi nước bốc từ ly"] },
  sfx: { hint: "Tiếng động gắn với hành động.", ex: ["tiếng muỗng chạm ly", "cửa tủ lạnh đóng cái rầm"] },
  ambient: { hint: "Âm nền — nếu bỏ trống Veo có thể tự thêm tiếng lạ.", ex: ["xe máy xa xa, chim sẻ", "tiếng quạt trần"] },
  notes: { hint: "Ghi chú riêng cho AI khi viết prompt.", ex: ["giữ ly cà phê y như cảnh trước", "nhân vật nhìn thẳng máy ở cuối"] },
  style: { hint: "Câu style tiếng Anh ghép vào đầu mọi prompt (AI viết ở bước 4).", ex: ["3D animated cartoon style, warm morning colors, soft film grain"] },
  voice_name: { hint: "Giọng Gemini TTS.", ex: OPT.voices.slice(0, 4) },
  voice_style: { hint: "Mô tả cách đọc.", ex: ["giọng nam dí dỏm, nhấn nhá như kể chuyện cười", "giọng nữ ấm, chậm rãi"] },
};

// 7 bước
const STEPS = [
  { id: "idea", title: "Ý tưởng & phong cách", icon: "💡",
    need: "Ý tưởng 1–2 câu, phong cách hình ảnh, model video Google Flow và độ phân giải.",
    why: "Đây là 'đề bài' để AI viết mọi thứ phía sau; model quyết định chất lượng và tín dụng tiêu tốn.",
    example: "“Video hài 20s: anh chàng đeo kính sáng dậy như zombie, thử cà phê sữa chua theo trend rồi tỉnh vì chua” · Hoạt hình 3D · Veo 3.1 Fast · 720p",
    done: d => !!(d.script.profile?.idea && d.script.flow?.video_model) },
  { id: "cast", title: "Nhân vật · Bối cảnh · Đạo cụ", icon: "🎭",
    need: "Ít nhất 1 nhân vật (hoặc bỏ qua nếu không có người), 1 bối cảnh; đạo cụ nào xuất hiện ≥2 cảnh.",
    why: "Mô tả cố định được lặp nguyên văn trong mọi prompt → nhân vật, căn bếp, chiếc ly giống nhau giữa các cảnh.",
    example: "Tuấn: ~30 tuổi, gầy cao, kính tròn đen, tóc rẽ ngôi trái… · Bếp chung cư Hà Nội 7h sáng · Ly cà phê sữa chua đá",
    done: d => (d.script.characters || []).length > 0 && (d.script.locations || []).length > 0 },
  { id: "story", title: "Kịch bản từng cảnh", icon: "📝",
    need: "Mỗi cảnh: vai trò, lời dẫn, MỘT hành động, nhân vật/bối cảnh/đạo cụ. Tích Duyệt khi ưng.",
    why: "Chỉ cảnh đã duyệt mới được gen video (tốn tín dụng).",
    example: "s01 · 8s · Hook · “Bảy giờ sáng, anh Tuấn chính thức ở chế độ zombie” · lê bước vào bếp suýt đâm tủ lạnh",
    done: d => (d.script.scenes || []).length > 0 && d.script.scenes.every(s => s.status === "approved") },
  { id: "shots", title: "Hình ảnh & prompt", icon: "🎬",
    need: "Góc máy, ánh sáng, âm thanh, tích chống 'chất AI'; bấm Viết prompt; tạo ảnh nhân vật trong Flow.",
    why: "Prompt càng cụ thể (ống kính, nguồn sáng, âm nền) video càng ít 'mùi AI'.",
    example: "Cận cảnh · 35mm f/2.8 · nắng sớm xiên cửa sổ trái · hạt phim nhẹ · SFX muỗng chạm ly",
    done: d => (d.script.scenes || []).length > 0 && d.script.scenes.every(s => !d.prompt_stale[s.id]) && (d.script.characters || []).every(c => (d.refs || []).some(f => f.startsWith(c.id + "."))) },
  { id: "voice", title: "Giọng đọc", icon: "🎙️",
    need: "Chọn giọng + cách đọc, tạo voice-over, nghe thử.",
    why: "Độ dài giọng đọc quyết định độ dài mỗi cảnh khi dựng.",
    example: "Puck · “giọng nam dí dỏm, nhấn nhá như kể chuyện cười”",
    done: d => (d.status || []).length > 0 && d.status.every(r => r.tts === "ok" || r.tts === "-") },
  { id: "video", title: "Video (Google Flow)", icon: "🎥",
    need: "Gen clip cho cảnh đã duyệt bằng tín dụng gói, xem và chọn take.",
    why: "Chạy trong Chrome đã đăng nhập Flow; mỗi clip tốn ~10–12 tín dụng (đo được với project cà phê).",
    example: "s01 take 1 ✓ · s03 gen lại vì đạo cụ sai",
    done: d => (d.status || []).length > 0 && d.status.filter(r => r.status === "approved").every(r => r.clip === "ok") },
  { id: "build", title: "Dựng CapCut", icon: "✂️",
    need: "Nhạc nền (tùy chọn), phụ đề, thoát CapCut rồi bấm Dựng.",
    why: "Tạo draft có clip + voice + phụ đề; bạn mở CapCut chỉnh nhẹ và export.",
    example: "draft vidflow_cafe-sang · 16s",
    done: d => !!d.state?.draft_path },
];
const STEP_JOBS = { idea: ["script", "✨ AI viết toàn bộ kịch bản chi tiết"], cast: ["script", "✨ AI điền nhân vật & bối cảnh"], story: ["script", "✨ AI viết/hoàn thiện các cảnh"],
  shots: ["prompts", "✨ AI viết prompt chi tiết"], voice: ["tts", "🎙️ Tạo giọng đọc"], video: ["flow", "🎥 Gen video trong Flow"], build: ["build", "✂️ Dựng draft CapCut"] };
const TEMPLATES = [
  { icon: "☕", title: "Hài đời thường", idea: "Video hài 20s: anh chàng đeo kính, tóc rẽ ngôi, sáng dậy như zombie, thử cà phê sữa chua theo trend rồi tỉnh vì chua", style: "anim_3d", aspect: "9:16" },
  { icon: "🏪", title: "Review quán", idea: "Review 30s một quán cà phê nhỏ ở Hà Nội: không gian, món signature, cảm nhận ngụm đầu; tông ấm, chân thực", style: "live_action", aspect: "9:16" },
  { icon: "📦", title: "Giới thiệu sản phẩm", idea: "Video 20s giới thiệu bình giữ nhiệt: vấn đề cà phê nguội, giải pháp, cảnh dùng thực tế, kêu gọi mua", style: "ugc", aspect: "9:16" },
  { icon: "📖", title: "Kể chuyện", idea: "Kể chuyện 40s: cô gái 25 tuổi mở tiệm trà chanh từ 0 đồng, thất bại lần đầu rồi đông khách", style: "anim_3d", aspect: "9:16" },
];

const S = { projects: [], name: null, data: null, dirty: false, step: "idea", job: null, poll: null, focus: null, sugg: null, suggLoading: false };

// ================= tiện ích =================
function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "class") el.className = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const k of kids.flat(Infinity)) if (k !== null && k !== undefined && k !== false) el.append(k.nodeType ? k : document.createTextNode(k));
  return el;
}
async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (r.status === 401) { location.href = "/login"; throw new Error("Cần đăng nhập"); }
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.detail || `Lỗi ${r.status}`);
  return body;
}
function toast(msg, err = false) {
  const t = document.getElementById("toast");
  t.textContent = msg; t.className = "toast" + (err ? " err" : ""); t.style.display = "block";
  clearTimeout(t._t); t._t = setTimeout(() => (t.style.display = "none"), err ? 8000 : 3000);
}
function markDirty() { S.dirty = true; const m = document.getElementById("dirtyMark"); m.textContent = "● Có thay đổi chưa lưu"; m.className = "dirty"; }
function media(path) { return `/media/${S.name}/${path}`; }
function slug(s) { return (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/g, "d").replace(/Đ/g, "d").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "") || "x"; }
const esc = s => String(s ?? "");

// ô nhập có: nhãn, gợi ý, ví dụ bấm-điền, nút ✨ AI gợi ý; focus → cập nhật Trợ lý AI
function F(label, obj, key, o = {}) {
  const help = HELP[o.help || key] || {};
  let input;
  if (o.type === "textarea") { input = h("textarea", { rows: o.rows || 2, placeholder: o.placeholder || help.ex?.[0] || "" }); input.value = obj[key] ?? ""; }
  else if (o.type === "select") { input = h("select", {}, o.options.map(x => Array.isArray(x) ? h("option", { value: x[0] }, x[1]) : h("option", { value: x }, x || "— chọn —"))); input.value = obj[key] ?? ""; }
  else if (o.type === "number") { input = h("input", { type: "number", step: "any" }); input.value = obj[key] ?? ""; }
  else {
    const listId = o.options ? "dl-" + key : null;
    input = h("input", { type: "text", list: listId, placeholder: o.placeholder || help.ex?.[0] || "" }); input.value = obj[key] ?? "";
    if (listId && !document.getElementById(listId)) document.body.append(h("datalist", { id: listId }, o.options.map(x => h("option", { value: x }))));
  }
  const ctx = { label, obj, key, help: o.help || key, scene: o.scene || null, input, ai: o.ai !== false && o.type !== "select" && o.type !== "number" };
  input.addEventListener("input", () => { obj[key] = o.type === "number" ? Number(input.value) : input.value; markDirty(); o.onInput && o.onInput(); });
  input.addEventListener("change", () => { if (o.type === "select") { obj[key] = input.value; markDirty(); } });
  input.addEventListener("focus", () => setFocus(ctx));
  const chips = o.chips !== false && help.ex && o.type !== "select" ? h("div", { class: "chips" }, help.ex.slice(0, 3).map(e => h("button", { class: "chip", type: "button", title: e, onclick: () => setValue(ctx, e) }, e.length > 42 ? e.slice(0, 40) + "…" : e))) : null;
  return h("label", { class: "f" + (o.wide ? " wide" : "") },
    h("span", { class: "flabel" }, label, ctx.ai ? h("button", { class: "spark", type: "button", title: "AI gợi ý cho ô này", onclick: e => { e.preventDefault(); setFocus(ctx); suggest(); } }, "✨") : null),
    help.hint && !o.noHint ? h("span", { class: "hint" }, help.hint) : null, input, chips);
}
function setValue(ctx, v) { ctx.obj[ctx.key] = v; ctx.input.value = v; markDirty(); ctx.input.dispatchEvent(new Event("input")); }
function checkGroup(items, arr) {
  return h("div", { class: "checks" }, items.map(([val, lab]) => {
    const cb = h("input", { type: "checkbox" }); cb.checked = arr.includes(val);
    cb.addEventListener("change", () => { const i = arr.indexOf(val); if (cb.checked && i < 0) arr.push(val); if (!cb.checked && i >= 0) arr.splice(i, 1); markDirty(); });
    return h("label", {}, cb, lab);
  }));
}
function checkbox(label, obj, key, onChange) {
  const cb = h("input", { type: "checkbox" }); cb.checked = !!obj[key];
  cb.addEventListener("change", () => { obj[key] = cb.checked; markDirty(); onChange && onChange(); });
  return h("label", {}, cb, label);
}
function guide(step) {
  return h("div", { class: "guide" },
    h("div", { class: "guide-title" }, `${step.icon} ${step.title}`),
    h("div", { class: "guide-grid" },
      h("div", {}, h("b", {}, "Cần gì"), h("p", {}, step.need)),
      h("div", {}, h("b", {}, "Vì sao"), h("p", {}, step.why)),
      h("div", {}, h("b", {}, "Ví dụ"), h("p", { class: "ex" }, step.example))),
    STEP_JOBS[step.id] ? h("div", { class: "row" }, h("button", { class: "primary", disabled: S.job?.state === "running", onclick: () => stepJob(step.id) }, STEP_JOBS[step.id][1]),
      h("span", { class: "hint" }, "hoặc tự điền các ô bên dưới — bấm ✨ ở từng ô để AI gợi ý")) : null);
}

// ================= tải / lưu =================
async function loadProjects() {
  S.projects = await api("/api/projects");
  const sel = document.getElementById("projectSel");
  sel.replaceChildren(h("option", { value: "" }, S.projects.length ? "— chọn project —" : "— chưa có project —"), ...S.projects.map(p => h("option", { value: p.name }, `${p.title} (${p.name})`)));
  sel.value = S.name || "";
}
async function openProject(name, jumpToCurrent = false) {
  if (S.dirty && !confirm("Có thay đổi chưa lưu. Bỏ qua?")) { document.getElementById("projectSel").value = S.name || ""; return; }
  S.name = name; S.dirty = false; S.focus = null; S.sugg = null;
  document.getElementById("projectSel").value = name || "";
  document.getElementById("dirtyMark").textContent = "";
  if (!name) { S.data = null; history.replaceState(null, "", location.pathname); render(); return; }
  location.hash = name;
  S.data = await api(`/api/projects/${name}`);
  if (jumpToCurrent) S.step = currentStep().id;
  render();
}
async function save() {
  if (!S.name) return;
  const sc = S.data.script; if (sc.music && !sc.music.file) sc.music = null;
  try { await api(`/api/projects/${S.name}/script`, { method: "PUT", body: JSON.stringify(sc) }); S.dirty = false; toast("Đã lưu"); await openProject(S.name); }
  catch (e) { toast(e.message, true); }
}
function currentStep() { return STEPS.find(s => !s.done(S.data)) || STEPS[STEPS.length - 1]; }

// ================= bố cục =================
function render() {
  document.getElementById("savebar").hidden = !S.name;
  const shell = document.getElementById("main");
  if (!S.name || !S.data) { shell.className = "home"; shell.replaceChildren(renderHome()); return; }
  shell.className = "app";
  const step = STEPS.find(s => s.id === S.step) || STEPS[0];
  const view = { idea: vIdea, cast: vCast, story: vStory, shots: vShots, voice: vVoice, video: vVideo, build: vBuild }[step.id]();
  shell.replaceChildren(renderSidebar(), h("section", { class: "content" }, h("h2", { class: "ptitle" }, S.data.script.title), guide(step), view, stepNav(step)), renderAssistant());
}
function renderSidebar() {
  const cur = currentStep();
  return h("aside", { class: "sidebar" },
    h("div", { class: "side-title" }, "Quy trình"),
    h("ol", { class: "stepper" }, STEPS.map((s, i) => {
      const done = s.done(S.data), isCur = s.id === cur.id;
      return h("li", { class: `stp ${S.step === s.id ? "active" : ""} ${done ? "done" : ""} ${isCur ? "current" : ""}`, onclick: () => { S.step = s.id; render(); } },
        h("span", { class: "dot" }, done ? "✓" : String(i + 1)), h("span", { class: "stp-t" }, s.title), isCur && !done ? h("span", { class: "now" }, "làm tiếp") : null);
    })),
    h("div", { class: "next" }, h("b", {}, "Bước tiếp theo"), h("p", {}, `${cur.icon} ${cur.title}: ${cur.need}`),
      h("button", { class: "primary", onclick: () => { S.step = cur.id; render(); } }, "Đi tới")));
}
function stepNav(step) {
  const i = STEPS.indexOf(step);
  return h("div", { class: "stepnav" },
    i > 0 ? h("button", { onclick: () => { S.step = STEPS[i - 1].id; render(); } }, `← ${STEPS[i - 1].title}`) : h("span"),
    i < STEPS.length - 1 ? h("button", { class: "primary", onclick: () => { S.step = STEPS[i + 1].id; render(); window.scrollTo({ top: 0, behavior: "smooth" }); } }, `${STEPS[i + 1].title} →`) : h("span"));
}

// ================= trang chủ =================
function renderHome() {
  return h("div", { class: "hero" },
    h("h2", { class: "hero-title" }, "Làm video AI trong 7 bước"),
    h("p", { class: "hero-sub" }, "Bạn đưa ý tưởng — AI viết kịch bản chi tiết, prompt chống “chất AI”, giọng đọc; Google Flow gen clip bằng tín dụng gói; vidflow dựng sẵn draft CapCut."),
    h("div", { class: "flow7" }, STEPS.map((s, i) => h("div", { class: "f7" }, h("div", { class: "f7i" }, s.icon), h("div", { class: "f7n" }, `${i + 1}. ${s.title}`)))),
    h("h3", { class: "sec" }, "Bắt đầu nhanh từ mẫu"),
    h("div", { class: "tpls" }, TEMPLATES.map(t => h("button", { class: "tpl", onclick: () => openNew(t) }, h("div", { class: "tpl-i" }, t.icon), h("b", {}, t.title), h("p", {}, t.idea)))),
    h("div", { class: "row center", style: "margin-top:18px" }, h("button", { class: "primary big", onclick: () => openNew() }, "+ Tự nhập ý tưởng")),
    S.projects.length ? h("div", {}, h("h3", { class: "sec" }, "Project của bạn"),
      h("div", { class: "tpls" }, S.projects.map(p => h("button", { class: "tpl", onclick: () => openProject(p.name, true) }, h("div", { class: "tpl-i" }, "🎞️"), h("b", {}, p.title), h("p", {}, `${p.scenes ?? 0} cảnh · ${p.approved ?? 0} đã duyệt · ${p.aspect ?? ""}`))))) : null);
}

// ================= các bước =================
function vIdea() {
  const s = S.data.script;
  s.profile = s.profile || {}; s.flow = s.flow || { video_model: "", resolution: "720p" };
  return h("div", {},
    h("div", { class: "card" }, h("h3", {}, "Ý tưởng"), h("div", { class: "grid" },
      F("Ý tưởng", s.profile, "idea", { type: "textarea", wide: true, rows: 3 }),
      F("Tựa video", s, "title"), F("Đối tượng xem", s.profile, "audience"), F("Nền tảng", s.profile, "platform", { options: OPT.platform }))),
    h("div", { class: "card" }, h("h3", {}, "Phong cách"), h("div", { class: "grid" },
      F("Loại hình ảnh", s.profile, "style_type", { type: "select", options: OPT.style_type }),
      F("Tỉ lệ khung hình", s, "aspect", { type: "select", options: ["9:16", "16:9"] }),
      F("Tâm trạng", s.profile, "mood"), F("Bảng màu", s.profile, "palette"),
      F("Chất ảnh / hạt phim", s.profile, "film_look", { wide: true }), F("Tham chiếu thẩm mỹ", s.profile, "reference", { wide: true }))),
    h("div", { class: "card" }, h("h3", {}, "Google Flow"), h("p", { class: "hint" }, "Chỉ dùng tín dụng gói. Model mạnh hơn tốn nhiều tín dụng hơn."), h("div", { class: "grid" },
      F("Model video", s.flow, "video_model", { type: "select", options: OPT.models }),
      F("Độ phân giải tải về", s.flow, "resolution", { type: "select", options: ["720p", "1080p"] }))));
}
function listEditor(title, arr, prefix, makeNew, body) {
  const add = () => { const id = slug(prompt(`Mã (không dấu):`, `${prefix}${arr.length + 1}`) || ""); if (!id || id === "x") return; arr.push(makeNew(id)); markDirty(); render(); };
  return h("div", { class: "card" }, h("div", { class: "row between" }, h("h3", {}, title), h("button", { onclick: add }, "+ Thêm")),
    arr.length ? null : h("p", { class: "hint" }, "Chưa có — bấm “+ Thêm” hoặc nút ✨ AI ở trên."),
    arr.map((it, i) => h("details", { open: arr.length <= 2, class: "item" },
      h("summary", {}, it.name || it.id, " ", h("span", { class: "badge" }, it.id)), body(it),
      h("button", { class: "danger small", onclick: () => { if (confirm("Xóa?")) { arr.splice(i, 1); markDirty(); render(); } } }, "Xóa"))));
}
function vCast() {
  const s = S.data.script; s.characters = s.characters || []; s.locations = s.locations || []; s.props = s.props || [];
  return h("div", {},
    listEditor("🧑 Nhân vật", s.characters, "nv", id => ({ id, name: "" }), c => h("div", { class: "grid" },
      F("Tên", c, "name"), F("Tuổi", c, "age"), F("Dáng người", c, "build"), F("Khuôn mặt", c, "face"), F("Tóc", c, "hair"),
      F("Kính / phụ kiện", c, "accessories"), F("Trang phục", c, "wardrobe", { wide: true }), F("Biểu cảm đặc trưng", c, "expressions", { wide: true }),
      F("Tính cách / cách nói", c, "voice_note", { wide: true }), h("div", { class: "checks wide" }, checkbox("🔒 Khóa (AI không sửa)", c, "locked")))),
    listEditor("🏠 Bối cảnh", s.locations, "bc", id => ({ id, name: "" }), l => h("div", { class: "grid" },
      F("Tên", l, "name"), F("Địa điểm", l, "place"), F("Thời gian", l, "time_of_day"), F("Chi tiết đồ vật", l, "details", { type: "textarea", wide: true }),
      F("Nguồn sáng thật", l, "light_sources", { wide: true }), F("Âm nền", l, "ambience", { wide: true }))),
    listEditor("🥤 Đạo cụ (giữ liền mạch giữa các cảnh)", s.props, "dc", id => ({ id, name: "" }), p => h("div", { class: "grid" },
      F("Tên", p, "name"), F("Mô tả cố định (tiếng Anh — AI viết ở bước 4)", p, "description", { type: "textarea", wide: true, ai: false, chips: false }))));
}
function sceneHead(sc, idx, extra = []) {
  const s = S.data.script;
  const ap = h("input", { type: "checkbox" }); ap.checked = sc.status === "approved";
  ap.addEventListener("change", () => { sc.status = ap.checked ? "approved" : "draft"; markDirty(); render(); });
  const move = d => { const j = idx + d; if (j < 0 || j >= s.scenes.length) return; [s.scenes[idx], s.scenes[j]] = [s.scenes[j], s.scenes[idx]]; markDirty(); render(); };
  return h("div", { class: "scene-head" }, h("span", { class: "sid" }, sc.id),
    h("select", { onchange: e => { sc.duration = Number(e.target.value); markDirty(); render(); } }, [4, 6, 8].map(d => h("option", { value: d, selected: sc.duration === d }, `${d}s`))),
    h("label", { class: "checks" }, ap, "Duyệt"), h("span", { class: "checks" }, checkbox("🔒 Khóa", sc, "locked", render)), extra,
    h("span", { style: "flex:1" }), h("button", { class: "small", onclick: () => move(-1) }, "↑"), h("button", { class: "small", onclick: () => move(1) }, "↓"),
    h("button", { class: "danger small", onclick: () => { if (confirm(`Xóa cảnh ${sc.id}?`)) { s.scenes.splice(idx, 1); markDirty(); render(); } } }, "Xóa"));
}
function vStory() {
  const s = S.data.script; s.scenes = s.scenes || [];
  const all = s.scenes.length && s.scenes.every(x => x.status === "approved");
  const total = s.scenes.reduce((a, x) => a + (x.duration || 0), 0);
  const addScene = () => { const n = s.scenes.length + 1; s.scenes.push({ id: "s" + String(n).padStart(2, "0"), duration: 6, status: "draft", characters: [], props: [], avoid: AVOID.slice(0, 4), anti_ai: ["film_grain", "imperfections", "practical_light"] }); markDirty(); render(); };
  return h("div", {},
    h("div", { class: "row", style: "margin-bottom:12px" }, h("button", { onclick: addScene }, "+ Thêm cảnh"),
      h("button", { onclick: () => { s.scenes.forEach(x => (x.status = all ? "draft" : "approved")); markDirty(); render(); } }, all ? "Bỏ duyệt tất cả" : "✓ Duyệt tất cả"),
      h("span", { class: "badge" }, `${s.scenes.length} cảnh · tổng ${total}s`)),
    s.scenes.map((sc, idx) => {
      sc.characters = sc.characters || []; sc.props = sc.props || [];
      const count = () => (sc.narration || "").trim().split(/\s+/).filter(Boolean).length, max = Math.floor(((sc.duration || 8) - 0.3) * 2.5);
      const wc = h("span", { class: "badge " + (count() > max ? "err" : "ok") }, `${count()}/${max} từ`);
      return h("div", { class: `card scene ${sc.status === "approved" ? "approved" : ""}` }, sceneHead(sc, idx, [wc]),
        h("div", { class: "grid" },
          F("Vai trò cảnh", sc, "purpose", { options: OPT.purpose, scene: sc.id }),
          F(`Lời dẫn (tối đa ${max} từ cho ${sc.duration}s)`, sc, "narration", { type: "textarea", wide: true, scene: sc.id,
            onInput: () => { wc.textContent = `${count()}/${max} từ`; wc.className = "badge " + (count() > max ? "err" : "ok"); } }),
          F("Lời thoại trong clip (tùy chọn)", sc, "dialogue", { wide: true, scene: sc.id }),
          h("div", { class: "f wide" }, h("span", { class: "flabel" }, "Nhân vật trong cảnh"), checkGroup((s.characters || []).map(c => [c.id, c.name || c.id]), sc.characters)),
          F("Bối cảnh", sc, "location", { type: "select", options: [["", "— không —"], ...(s.locations || []).map(l => [l.id, l.name || l.id])] }),
          h("div", { class: "f" }, h("span", { class: "flabel" }, "Đạo cụ"), checkGroup((s.props || []).map(p => [p.id, p.name || p.id]), sc.props)),
          F("Một hành động chính", sc, "action", { type: "textarea", wide: true, scene: sc.id }),
          F("Chia mốc thời gian (tùy chọn)", sc, "beats", { type: "textarea", wide: true, scene: sc.id }),
          F("Biểu cảm", sc, "expression", { scene: sc.id }), F("Trạng thái đạo cụ / trang phục", sc, "prop_state", { scene: sc.id })));
    }),
    s.scenes.length ? null : h("div", { class: "card empty-card" }, "Chưa có cảnh — bấm nút ✨ AI ở trên hoặc “+ Thêm cảnh”."));
}
function vShots() {
  const s = S.data.script, refs = S.data.refs || [];
  return h("div", {},
    h("div", { class: "card" }, h("div", { class: "row between" }, h("h3", {}, "🖼️ Ảnh tham chiếu nhân vật"),
      h("button", { onclick: () => confirmFlow(null, "refimg") }, "Tạo ảnh còn thiếu trong Flow")),
      h("p", { class: "hint" }, "Ảnh nền trơn, đủ mặt và trang phục — Flow dùng làm “nhân vật” để giữ nhất quán giữa các clip."),
      h("div", { class: "refs" }, (s.characters || []).map(c => { const f = refs.find(r => r.startsWith(c.id + ".")); return h("figure", {}, f ? h("img", { src: media("refs/" + f) }) : h("div", { class: "noimg" }, "Chưa có ảnh"), h("figcaption", {}, c.name || c.id)); }))),
    h("div", { class: "card" }, h("h3", {}, "Style chung gửi Veo"), F("Style (tiếng Anh)", s, "style", { type: "textarea", wide: true, ai: false })),
    (s.scenes || []).map((sc, idx) => {
      sc.avoid = sc.avoid || []; sc.anti_ai = sc.anti_ai || [];
      const stale = S.data.prompt_stale?.[sc.id];
      return h("div", { class: `card scene ${sc.status === "approved" ? "approved" : ""}` },
        sceneHead(sc, idx, [h("span", { class: "badge " + (stale ? "stale" : "ok") }, stale ? "Prompt cũ / chưa viết" : "Prompt khớp")]),
        h("p", { class: "mini" }, `🎯 ${sc.action || "(chưa có hành động — điền ở bước 3)"}`),
        h("details", { open: true }, h("summary", {}, "🎥 Máy quay"), h("div", { class: "grid" },
          F("Cỡ cảnh", sc, "shot_size", { options: OPT.shot_size, scene: sc.id }), F("Góc máy", sc, "angle", { options: OPT.angle, scene: sc.id }),
          F("Chuyển động máy (chỉ 1)", sc, "camera_move", { options: OPT.camera_move, scene: sc.id }), F("Ống kính", sc, "lens", { options: OPT.lens, scene: sc.id }),
          F("Độ sâu trường ảnh", sc, "dof", { options: OPT.dof, scene: sc.id }), F("Bố cục", sc, "composition", { options: OPT.composition, scene: sc.id }))),
        h("details", {}, h("summary", {}, "💡 Ánh sáng & không khí"), h("div", { class: "grid" },
          F("Nguồn sáng", sc, "light", { wide: true, scene: sc.id }), F("Chất sáng", sc, "light_quality", { options: OPT.light_quality, scene: sc.id }),
          F("Nhiệt màu", sc, "color_temp", { options: OPT.color_temp, scene: sc.id }), F("Không khí", sc, "atmosphere", { scene: sc.id }))),
        h("details", {}, h("summary", {}, "🔊 Âm thanh trong clip"), h("div", { class: "grid" },
          F("Tiếng động (SFX)", sc, "sfx", { scene: sc.id }), F("Âm nền", sc, "ambient", { scene: sc.id }),
          h("div", { class: "checks" }, (() => { const o = { mute: !sc.veo_audio }; return checkbox("Tắt tiếng clip (dùng giọng đọc)", o, "mute", () => { sc.veo_audio = !o.mute; }); })()))),
        h("details", {}, h("summary", {}, "🛡️ Chống “chất AI” & cần tránh"),
          h("div", { class: "f" }, h("span", { class: "flabel" }, "Chống chất AI"), checkGroup(ANTI_AI, sc.anti_ai)),
          h("div", { class: "f", style: "margin-top:8px" }, h("span", { class: "flabel" }, "Cần tránh"), checkGroup(AVOID.map(a => [a, a]), sc.avoid)),
          F("Ghi chú cho AI", sc, "notes", { type: "textarea", wide: true, scene: sc.id })),
        h("div", { class: "promptbox" }, h("div", { class: "row between" }, h("b", {}, "📜 Prompt"), h("button", { class: "small", onclick: () => runJob("prompts", [sc.id]) }, "✨ Viết lại prompt cảnh này")),
          sc.veo_prompt_vi ? h("div", { class: "prompt" }, sc.veo_prompt_vi) : h("p", { class: "hint" }, "Chưa có — bấm “✨ AI viết prompt chi tiết” ở trên."),
          sc.veo_prompt ? h("details", {}, h("summary", {}, "Bản tiếng Anh gửi Flow (sửa tay nếu cần)"), F("veo_prompt", sc, "veo_prompt", { type: "textarea", wide: true, rows: 5, ai: false, chips: false, noHint: true })) : null));
    }));
}
function vVoice() {
  const s = S.data.script, st = S.data.state.scenes || {};
  s.voice = s.voice || {};
  return h("div", {},
    h("div", { class: "card" }, h("h3", {}, "Giọng đọc"), h("div", { class: "grid" },
      F("Giọng", s.voice, "name", { options: OPT.voices, help: "voice_name" }), F("Cách đọc", s.voice, "style", { help: "voice_style", wide: true }),
      F("Tốc độ (0.5–2)", s.voice, "speed", { type: "number" }))),
    (s.scenes || []).map(sc => { const t = st[sc.id]?.tts; return h("div", { class: "card row between" },
      h("div", { style: "flex:1;min-width:220px" }, h("b", { class: "sid" }, sc.id), " ", h("span", {}, sc.narration || h("i", { class: "hint" }, "(không có lời dẫn)"))),
      t ? h("div", { class: "row" }, h("audio", { src: media(t.file), controls: true }), h("span", { class: "badge ok" }, `${t.duration_s}s / ${sc.duration}s`)) : h("span", { class: "badge" }, "chưa có"),
      sc.narration ? h("button", { class: "small", onclick: () => runJob("tts", [sc.id]) }, "Tạo lại") : null); }));
}
function vVideo() {
  const s = S.data.script, st = S.data.state.scenes || {};
  s.flow = s.flow || { video_model: "", resolution: "720p" };
  return h("div", {},
    h("div", { class: "card" }, h("h3", {}, "Cài đặt Flow"), h("div", { class: "grid" },
      F("Model video", s.flow, "video_model", { type: "select", options: OPT.models }), F("Độ phân giải", s.flow, "resolution", { type: "select", options: ["720p", "1080p"] })),
      h("p", { class: "hint" }, "Trước khi chạy: Chrome đã đăng nhập Flow, tắt “Hỏi nơi lưu mỗi tệp”, không thao tác Chrome khi đang gen.")),
    (s.scenes || []).map(sc => { const x = st[sc.id] || {}; const takes = x.takes || [];
      return h("div", { class: `card scene ${sc.status === "approved" ? "approved" : ""}` },
        h("div", { class: "row between" }, h("span", {}, h("b", { class: "sid" }, sc.id), " ", h("span", { class: "mini" }, sc.action || "")),
          sc.status === "approved" ? h("button", { class: "small", onclick: () => confirmFlow([sc.id]) }, takes.length ? "🔁 Gen lại" : "🎥 Gen cảnh này") : h("span", { class: "badge stale" }, "chưa duyệt")),
        h("div", { class: "media" }, takes.length ? takes.map((t, i) => h("figure", { class: x.picked === i ? "picked" : "" },
          h("video", { src: media(t.file), controls: true, preload: "metadata" }),
          h("figcaption", {}, `take ${i + 1}${x.picked === i ? " ✓ đang dùng" : ""} `, x.picked === i ? null : h("button", { class: "small", onclick: () => pickTake(sc.id, i + 1) }, "Dùng take này"))))
          : h("span", { class: "hint" }, "Chưa có clip"))); }));
}
function vBuild() {
  const s = S.data.script; s.subtitles = s.subtitles || { enabled: true, max_chars_per_line: 32 };
  const music = s.music || (s.music = { file: "", volume: 0.15 });
  return h("div", {},
    h("div", { class: "card" }, h("h3", {}, "Âm thanh & phụ đề"), h("div", { class: "grid" },
      F("Nhạc nền (đường dẫn trong project, vd music/bg.mp3)", music, "file", { ai: false, chips: false }),
      F("Âm lượng nhạc (0–1)", music, "volume", { type: "number" }),
      h("div", { class: "checks" }, checkbox("Bật phụ đề", s.subtitles, "enabled")), F("Ký tự mỗi dòng phụ đề", s.subtitles, "max_chars_per_line", { type: "number" })),
      h("p", { class: "hint" }, "Không có file nhạc? Thêm nhạc từ thư viện CapCut sau khi mở draft (được phép dùng trên TikTok).")),
    h("div", { class: "card" }, h("h3", {}, "Trạng thái"), h("table", {}, h("tr", {}, ["Cảnh", "Duyệt", "Voice", "Take", "Clip", "Lỗi"].map(x => h("th", {}, x))),
      (S.data.status || []).map(r => h("tr", {}, [r.id, r.status, r.tts, r.picked, r.clip, r.error].map(x => h("td", {}, esc(x))))))),
    S.data.state?.draft_path ? h("div", { class: "card" }, h("h3", {}, "✅ Draft đã dựng"), h("p", {}, S.data.state.draft_path), h("p", { class: "hint" }, "Mở CapCut → project này → chỉnh nhẹ → Export.")) : null);
}

// ================= Trợ lý AI (cột phải) =================
function renderAssistant() {
  const f = S.focus, help = f ? HELP[f.help] || {} : null;
  const box = h("aside", { class: "assistant" }, h("div", { class: "side-title" }, "✨ Trợ lý AI"));
  if (f) {
    box.append(h("div", { class: "as-card" }, h("div", { class: "as-field" }, f.label, f.scene ? h("span", { class: "badge" }, f.scene) : null),
      help.hint ? h("p", { class: "hint" }, help.hint) : null,
      help.ex?.length ? h("div", {}, h("div", { class: "as-sub" }, "Ví dụ — bấm để điền"), h("div", { class: "chips col" }, help.ex.map(e => h("button", { class: "chip", onclick: () => setValue(f, e) }, e)))) : null,
      f.ai ? h("button", { class: "primary wide-btn", disabled: S.suggLoading, onclick: suggest }, S.suggLoading ? "AI đang nghĩ… (~15–20s)" : "✨ Gợi ý 3 phương án") : null,
      S.suggLoading ? h("div", { class: "shimmer" }, h("div"), h("div"), h("div")) : null,
      S.sugg && S.sugg.key === f.key && S.sugg.obj === f.obj ? h("div", {}, h("div", { class: "as-sub" }, "Chọn rồi sửa tiếp nếu muốn"),
        S.sugg.items.map(it => { const t = h("textarea", { rows: 3 }); t.value = it; return h("div", { class: "sugg" }, t, h("button", { class: "ok small", onclick: () => { setValue(f, t.value); toast("Đã điền — nhớ Lưu"); } }, "Dùng")); })) : null));
  } else {
    box.append(h("div", { class: "as-card" }, h("p", { class: "hint" }, "Bấm vào một ô bất kỳ để xem hướng dẫn, ví dụ và nhờ AI gợi ý cho ô đó.")));
  }
  const ask = h("textarea", { rows: 3, placeholder: "vd: làm cảnh 2 hài hơn, thêm một cảnh twist ở cuối" });
  const quick = ["Làm kịch bản hài hơn", "Rút lời dẫn ngắn lại", "Thêm 1 cảnh twist ở cuối", "Tăng chi tiết chống chất AI cho mọi cảnh"];
  box.append(h("div", { class: "as-card" }, h("div", { class: "as-field" }, "💬 Nhờ AI sửa kịch bản"),
    h("p", { class: "hint" }, "AI sửa trực tiếp kịch bản (bỏ qua phần đã khóa 🔒). Lưu trước khi gửi."),
    h("div", { class: "chips col" }, quick.map(q => h("button", { class: "chip", onclick: () => { ask.value = q; } }, q))), ask,
    h("button", { class: "primary wide-btn", disabled: S.job?.state === "running", onclick: () => { if (!ask.value.trim()) return toast("Nhập yêu cầu", true); runJob("assist", null, ask.value.trim()); } }, "Gửi cho AI")));
  if (S.job) box.append(h("div", { class: "as-card" }, h("div", { class: "as-field" }, `⚙️ ${S.job.label}`, h("span", { class: "badge " + (S.job.state === "done" ? "ok" : S.job.state === "failed" ? "err" : "stale") }, S.job.state)),
    h("pre", { class: "log", id: "log" }, S.job.log || "(đang chạy…)")));
  return box;
}
function setFocus(ctx) {
  const same = S.focus && S.focus.obj === ctx.obj && S.focus.key === ctx.key;
  S.focus = ctx; if (!same) S.sugg = null;
  const old = document.querySelector(".assistant"); if (old) old.replaceWith(renderAssistant());
}
async function suggest() {
  const f = S.focus; if (!f || !f.ai) return;
  S.suggLoading = true; setFocus(f);
  try {
    const r = await api("/api/suggest", { method: "POST", body: JSON.stringify({ project: S.name, field: f.key, label: f.label, current: f.obj[f.key] || "", scene_id: f.scene }) });
    S.sugg = { key: f.key, obj: f.obj, items: r.suggestions };
  } catch (e) { toast(e.message, true); }
  S.suggLoading = false; if (S.focus === f) setFocus(f);
}

// ================= việc nền =================
async function pickTake(scene, take) {
  try { await api(`/api/projects/${S.name}/pick`, { method: "POST", body: JSON.stringify({ scene, take }) }); toast(`${scene}: dùng take ${take}`); openProject(S.name); }
  catch (e) { toast(e.message, true); }
}
function stepJob(id) {
  const [kind] = STEP_JOBS[id];
  if (kind === "flow") return confirmFlow(null);
  if (kind === "script" && (S.data.script.scenes || []).length && !confirm("AI sẽ viết/hoàn thiện kịch bản (giữ nguyên phần 🔒 khóa). Tiếp tục?")) return;
  runJob(kind);
}
function confirmFlow(scenes, kind = "flow") {
  const s = S.data.script;
  if (!s.flow?.video_model) { toast("Chọn model video Google Flow ở bước 1 trước.", true); S.step = "idea"; render(); return; }
  const what = kind === "refimg" ? "tạo ảnh nhân vật còn thiếu" : `gen video ${scenes ? scenes.join(", ") : "các cảnh đã duyệt"} bằng ${s.flow.video_model}, tải ${s.flow.resolution}`;
  if (confirm(`Sẽ ${what} trong Google Flow (tốn tín dụng gói). Chrome phải đăng nhập Flow; đừng thao tác Chrome khi đang chạy. Tiếp tục?`)) runJob(kind, scenes);
}
async function runJob(kind, scenes = null, instruction = "") {
  if (S.dirty) { toast("Lưu thay đổi trước (Cmd+S).", true); return; }
  try {
    S.job = await api(`/api/projects/${S.name}/jobs`, { method: "POST", body: JSON.stringify({ kind, scenes, instruction }) });
    toast(`Bắt đầu: ${S.job.label}`); render(); startPolling();
  } catch (e) { toast(e.message, true); }
}
function startPolling() {
  clearInterval(S.poll);
  S.poll = setInterval(async () => {
    const j = await api("/api/jobs/current").catch(() => null); if (!j) return;
    S.job = j.state === "idle" ? null : j;
    const pill = document.getElementById("jobPill");
    pill.className = "pill " + (j.state || "");
    pill.textContent = j.state === "running" ? `⚙️ ${j.label}…` : j.state === "done" ? `✓ ${j.label}` : j.state === "failed" ? `✗ ${j.label}` : "Rảnh";
    const log = document.getElementById("log");
    if (log && j.log !== undefined) { const end = log.scrollTop + log.clientHeight >= log.scrollHeight - 20; log.textContent = j.log || "(đang chạy…)"; if (end) log.scrollTop = log.scrollHeight; }
    if (j.state !== "running") {
      clearInterval(S.poll);
      if (j.project === S.name && !S.dirty) await openProject(S.name);
      if (j.state === "done") toast(`Xong: ${j.label}`); else if (j.state === "failed") toast(`Lỗi: ${j.label} — xem log bên phải`, true);
    }
  }, 2000);
}

// ================= video mới =================
function openNew(tpl = null) {
  if (S.dirty && !confirm("Có thay đổi chưa lưu. Bỏ qua?")) return;
  const dlg = document.getElementById("newDlg"), f = document.getElementById("newForm");
  f.reset();
  const el = n => f.elements.namedItem(n);
  delete el("name").dataset.touched;
  el("title").oninput = () => { if (!el("name").dataset.touched) el("name").value = slug(el("title").value).replace(/_/g, "-"); };
  el("name").oninput = () => (el("name").dataset.touched = "1");
  document.getElementById("ideaEx").replaceChildren(...HELP.idea.ex.map(e => h("button", { type: "button", class: "chip", onclick: () => { el("idea").value = e; } }, e.length > 60 ? e.slice(0, 58) + "…" : e)));
  if (tpl) { el("idea").value = tpl.idea; el("title").value = tpl.title; el("title").oninput(); el("aspect").value = tpl.aspect; el("style_type").value = tpl.style; }
  dlg.showModal();
  dlg.onclose = async () => {
    if (dlg.returnValue !== "ok") return;
    const body = Object.fromEntries(new FormData(f)); const start = !!body.start; const style = body.style_type; delete body.start; delete body.style_type;
    try {
      await api("/api/projects", { method: "POST", body: JSON.stringify(body) });
      S.dirty = false; await loadProjects(); await openProject(body.name);
      S.data.script.profile.style_type = style;
      await api(`/api/projects/${S.name}/script`, { method: "PUT", body: JSON.stringify(S.data.script) });
      S.step = "idea"; await openProject(S.name);
      if (start) runJob("script");
    } catch (e) { toast(e.message, true); }
  };
}

// ================= khởi động =================
document.getElementById("projectSel").addEventListener("change", e => openProject(e.target.value, true));
document.getElementById("newBtn").addEventListener("click", () => openNew());
document.getElementById("homeBtn").addEventListener("click", () => openProject(""));
document.getElementById("saveBtn").addEventListener("click", save);
document.getElementById("reloadBtn").addEventListener("click", () => { S.dirty = false; openProject(S.name); });
document.addEventListener("keydown", e => { if ((e.metaKey || e.ctrlKey) && e.key === "s") { e.preventDefault(); save(); } });
window.addEventListener("beforeunload", e => { if (S.dirty) { e.preventDefault(); e.returnValue = ""; } });
(async () => {
  await loadProjects();
  const want = decodeURIComponent(location.hash.slice(1));
  if (want && S.projects.some(p => p.name === want)) await openProject(want, true); else render();
  const j = await api("/api/jobs/current").catch(() => null);
  if (j && j.state === "running") { S.job = j; startPolling(); }
})();
