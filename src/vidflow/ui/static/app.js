"use strict";
// vidflow Studio — UI cục bộ. Dữ liệu: /api/projects/<name> (script.yaml + state.json).

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
};
const ANTI_AI = [
  ["film_grain", "Hạt phim nhẹ"], ["handheld", "Máy cầm tay rung nhẹ"],
  ["imperfections", "Chi tiết không hoàn hảo (bụi, nếp vải, bừa bộn)"], ["practical_light", "Ánh sáng thực tế, không bão hòa"],
  ["real_speed", "Chuyển động tốc độ thật"], ["micro_detail", "Chi tiết vi mô (da, tóc, vải)"],
  ["off_center", "Bố cục lệch tâm"], ["ugc_phone", "Kiểu quay điện thoại (UGC)"],
];
const AVOID = ["no on-screen text", "no subtitles", "no watermark", "no name labels", "no warped hands or extra fingers", "no dialogue", "no music"];
const STEPS = [
  ["script", "1. Viết kịch bản chi tiết", "Claude điền mọi ô (bỏ qua cảnh/nhân vật đã khóa)."],
  ["prompts", "2. Viết prompt chi tiết", "Claude viết prompt tiếng Anh + bản dịch cho cảnh có prompt cũ/trống."],
  ["refimg", "2b. Tạo ảnh nhân vật (Flow)", "Tạo ảnh tham chiếu trong Google Flow — tốn tín dụng, cần Chrome đăng nhập Flow."],
  ["tts", "3. Tạo voice-over", "Gemini TTS (free tier) cho các cảnh có lời dẫn."],
  ["flow", "4. Gen video (Flow)", "Gen trong Google Flow bằng tín dụng gói cho cảnh đã duyệt — không thao tác Chrome khi đang chạy."],
  ["build", "5. Dựng draft CapCut", "Cần thoát CapCut trước. Dựng clip + voice + phụ đề + nhạc."],
  ["export_prompts", "Xuất prompts.md", "Để tự dán vào Flow bằng tay."],
];

const S = { projects: [], name: null, data: null, dirty: false, tab: "scenes", job: null, poll: null };

// ---------- tiện ích ----------
function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "class") el.className = v;
    else if (k === "html") el.innerHTML = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const k of kids.flat()) if (k !== null && k !== undefined && k !== false) el.append(k.nodeType ? k : document.createTextNode(k));
  return el;
}
async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.detail || `Lỗi ${r.status}`);
  return body;
}
function toast(msg, err = false) {
  const t = document.getElementById("toast");
  t.textContent = msg; t.className = "toast" + (err ? " err" : ""); t.style.display = "block";
  clearTimeout(t._t); t._t = setTimeout(() => (t.style.display = "none"), err ? 8000 : 3000);
}
function markDirty() { S.dirty = true; document.getElementById("dirtyMark").textContent = "● Có thay đổi chưa lưu"; document.getElementById("dirtyMark").className = "dirty"; }
function media(path) { return `/media/${S.name}/${path}`; }

// ô nhập gắn vào obj[key]
function field(label, obj, key, { type = "text", options = null, wide = false, rows = 2, placeholder = "", disabled = false } = {}) {
  let input;
  if (type === "textarea") {
    input = h("textarea", { rows, placeholder, disabled });
    input.value = obj[key] ?? "";
  } else if (type === "select") {
    input = h("select", { disabled }, options.map(o => Array.isArray(o) ? h("option", { value: o[0] }, o[1]) : h("option", { value: o }, o)));
    input.value = obj[key] ?? "";
  } else if (type === "number") {
    input = h("input", { type: "number", disabled }); input.value = obj[key] ?? "";
  } else {
    const listId = options ? "dl-" + key : null;
    input = h("input", { type: "text", list: listId, placeholder, disabled }); input.value = obj[key] ?? "";
    if (options && !document.getElementById(listId)) document.body.append(h("datalist", { id: listId }, options.map(o => h("option", { value: o }))));
  }
  input.addEventListener("input", () => { obj[key] = type === "number" ? Number(input.value) : input.value; markDirty(); });
  return h("label", { class: "f" + (wide ? " wide" : "") }, label, input);
}
function checkGroup(items, arr, onChange) {
  return h("div", { class: "checks" }, items.map(([val, lab]) => {
    const cb = h("input", { type: "checkbox" }); cb.checked = arr.includes(val);
    cb.addEventListener("change", () => { const i = arr.indexOf(val); if (cb.checked && i < 0) arr.push(val); if (!cb.checked && i >= 0) arr.splice(i, 1); markDirty(); onChange && onChange(); });
    return h("label", {}, cb, lab);
  }));
}
function checkbox(label, obj, key, onChange) {
  const cb = h("input", { type: "checkbox" }); cb.checked = !!obj[key];
  cb.addEventListener("change", () => { obj[key] = cb.checked; markDirty(); onChange && onChange(); });
  return h("label", {}, cb, label);
}
function slug(s) { return (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/g, "d").replace(/Đ/g, "d").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "") || "x"; }

// ---------- tải dữ liệu ----------
async function loadProjects() {
  S.projects = await api("/api/projects");
  const sel = document.getElementById("projectSel");
  sel.replaceChildren(h("option", { value: "" }, S.projects.length ? "— chọn project —" : "— chưa có project —"),
    ...S.projects.map(p => h("option", { value: p.name }, `${p.title} (${p.name})`)));
  sel.value = S.name || "";
}
async function openProject(name, keepTab = true) {
  if (S.dirty && !confirm("Có thay đổi chưa lưu. Bỏ qua?")) { document.getElementById("projectSel").value = S.name || ""; return; }
  S.name = name; S.dirty = false;
  document.getElementById("projectSel").value = name || "";
  if (!name) { render(); return; }
  location.hash = name;
  S.data = await api(`/api/projects/${name}`);
  if (!keepTab) S.tab = "scenes";
  document.getElementById("dirtyMark").textContent = "";
  render();
}
async function save() {
  if (!S.name) return;
  const sc = S.data.script;
  if (sc.music && !sc.music.file) sc.music = null;
  try {
    await api(`/api/projects/${S.name}/script`, { method: "PUT", body: JSON.stringify(S.data.script) });
    S.dirty = false; toast("Đã lưu script.yaml");
    await openProject(S.name);
  } catch (e) { toast(e.message, true); }
}

// ---------- render ----------
function render() {
  const main = document.getElementById("main");
  document.getElementById("savebar").hidden = !S.name;
  if (!S.name || !S.data) {
    main.replaceChildren(h("div", { class: "empty" }, h("p", {}, "Chọn một project ở trên, hoặc bấm “+ Video mới”."),
      h("button", { class: "primary", onclick: () => openNew() }, "+ Video mới")));
    return;
  }
  const tabs = [["profile", "Hồ sơ"], ["cast", "Nhân vật · Bối cảnh · Đạo cụ"], ["scenes", "Cảnh"], ["run", "Chạy & Dựng"]];
  const bar = h("div", { class: "tabs" }, tabs.map(([k, l]) => h("button", { class: S.tab === k ? "active" : "", onclick: () => { S.tab = k; render(); } }, l)));
  const body = { profile: renderProfile, cast: renderCast, scenes: renderScenes, run: renderRun }[S.tab]();
  main.replaceChildren(h("h2", { style: "margin:0 0 12px" }, S.data.script.title), bar, body);
}

function renderProfile() {
  const s = S.data.script;
  s.profile = s.profile || {}; s.flow = s.flow || { video_model: "", resolution: "720p" };
  s.voice = s.voice || {}; s.subtitles = s.subtitles || { enabled: true, max_chars_per_line: 32 };
  return h("div", {},
    h("div", { class: "card" }, h("h3", {}, "Thông tin"), h("div", { class: "grid" },
      field("Tựa", s, "title"),
      field("Ý tưởng", s.profile, "idea", { type: "textarea", wide: true, rows: 3 }),
      field("Đối tượng xem", s.profile, "audience"),
      field("Nền tảng", s.profile, "platform", { options: OPT.platform }),
      field("Tỉ lệ khung hình", s, "aspect", { type: "select", options: ["9:16", "16:9"] }),
      field("Model video (Google Flow)", s.flow, "video_model", { type: "select", options: ["", "Veo 3.1 Lite", "Veo 3.1 Fast", "Veo 3.1 Quality", "Omni 1.1 Flash"] }),
      field("Độ phân giải tải về", s.flow, "resolution", { type: "select", options: ["720p", "1080p"] }))),
    h("div", { class: "card" }, h("h3", {}, "Phong cách chung"), h("div", { class: "grid" },
      field("Loại hình ảnh", s.profile, "style_type", { type: "select", options: OPT.style_type }),
      field("Tâm trạng", s.profile, "mood", { placeholder: "hài, ấm áp, dí dỏm" }),
      field("Bảng màu", s.profile, "palette", { placeholder: "nâu cà phê, kem, xanh bạc hà" }),
      field("Hạt phim / chất màu", s.profile, "film_look", { placeholder: "hạt phim nhẹ, Kodak Portra 400" }),
      field("Tham chiếu thẩm mỹ", s.profile, "reference", { wide: true }),
      field("Style gửi cho Veo (tiếng Anh, Claude viết)", s, "style", { type: "textarea", wide: true }))),
    h("div", { class: "card" }, h("h3", {}, "Âm thanh chung"), h("div", { class: "grid" },
      field("Giọng đọc (Gemini TTS)", s.voice, "name", { options: OPT.voices }),
      field("Cách đọc", s.voice, "style", { placeholder: "giọng nam dí dỏm, nhấn nhá" }),
      field("Tốc độ", s.voice, "speed", { type: "number" }),
      field("Nhạc nền (đường dẫn trong project, vd music/bg.mp3)", s.music || (s.music = { file: "", volume: 0.15 }), "file"),
      field("Âm lượng nhạc (0–1)", s.music, "volume", { type: "number" }),
      h("div", { class: "checks" }, checkbox("Bật phụ đề", s.subtitles, "enabled")),
      field("Số ký tự mỗi dòng phụ đề", s.subtitles, "max_chars_per_line", { type: "number" }))));
}

function listEditor(title, arr, makeNew, renderItem, prefix) {
  const wrap = h("div", { class: "card" }, h("div", { class: "row", style: "justify-content:space-between" }, h("h3", {}, title),
    h("button", { onclick: () => { const id = prompt(`Mã ${title.toLowerCase()} (không dấu):`, `${prefix}${arr.length + 1}`); if (!id) return; arr.push(makeNew(slug(id))); markDirty(); render(); } }, "+ Thêm")));
  if (!arr.length) wrap.append(h("p", { class: "badge" }, "Chưa có"));
  arr.forEach((item, i) => wrap.append(h("details", { open: arr.length <= 2 },
    h("summary", {}, `${item.name || item.id} `, h("span", { class: "badge" }, item.id)),
    renderItem(item),
    h("button", { class: "danger", style: "margin-top:8px", onclick: () => { if (confirm("Xóa?")) { arr.splice(i, 1); markDirty(); render(); } } }, "Xóa"))));
  return wrap;
}

function renderCast() {
  const s = S.data.script;
  s.characters = s.characters || []; s.locations = s.locations || []; s.props = s.props || [];
  const refs = S.data.refs || [];
  return h("div", {},
    listEditor("Nhân vật", s.characters, id => ({ id, name: "", description: "" }), c => {
      const imgs = refs.filter(f => f.startsWith(c.id + ".") || f.startsWith(c.id + "_"));
      return h("div", {}, h("div", { class: "grid" },
        field("Tên", c, "name"), field("Tuổi", c, "age"), field("Dáng người", c, "build"),
        field("Khuôn mặt", c, "face"), field("Tóc", c, "hair", { placeholder: "đen, rẽ ngôi trái, lọn dựng" }),
        field("Kính / phụ kiện", c, "accessories"), field("Trang phục", c, "wardrobe", { wide: true }),
        field("Biểu cảm đặc trưng", c, "expressions", { wide: true }), field("Giọng / tính cách", c, "voice_note", { wide: true }),
        field("Mô tả gửi Veo (tiếng Anh, Claude viết, lặp nguyên văn mọi cảnh)", c, "description", { type: "textarea", wide: true, rows: 3 })),
        h("div", { class: "checks" }, checkbox("Khóa (AI không sửa)", c, "locked")),
        h("div", { class: "refs", style: "margin-top:8px" }, imgs.length ? imgs.map(f => h("img", { src: media("refs/" + f), alt: f, title: f })) : h("span", { class: "badge" }, "Chưa có ảnh tham chiếu — chạy bước 2b")));
    }, "nv"),
    listEditor("Bối cảnh", s.locations, id => ({ id, name: "" }), l => h("div", { class: "grid" },
      field("Tên", l, "name"), field("Địa điểm", l, "place", { placeholder: "bếp chung cư nhỏ ở Hà Nội" }),
      field("Thời gian trong ngày", l, "time_of_day", { placeholder: "7h sáng" }),
      field("Chi tiết đồ vật", l, "details", { type: "textarea", wide: true }),
      field("Nguồn sáng thật", l, "light_sources", { placeholder: "nắng xiên qua cửa sổ, đèn trần vàng" }),
      field("Âm nền đặc trưng", l, "ambience", { placeholder: "xe máy xa xa, tủ lạnh ù" })), "bc"),
    listEditor("Đạo cụ (giữ liền mạch giữa các cảnh)", s.props, id => ({ id, name: "" }), p => h("div", { class: "grid" },
      field("Tên", p, "name"),
      field("Mô tả cố định (tiếng Anh, Claude viết)", p, "description", { type: "textarea", wide: true })), "dc"));
}

function sceneCard(sc, idx) {
  const s = S.data.script, st = (S.data.state.scenes || {})[sc.id] || {}, row = (S.data.status || []).find(r => r.id === sc.id) || {};
  const stale = S.data.prompt_stale?.[sc.id];
  sc.avoid = sc.avoid || []; sc.anti_ai = sc.anti_ai || []; sc.characters = sc.characters || []; sc.props = sc.props || [];
  const cbApprove = h("input", { type: "checkbox" }); cbApprove.checked = sc.status === "approved";
  cbApprove.addEventListener("change", () => { sc.status = cbApprove.checked ? "approved" : "draft"; markDirty(); render(); });
  const move = d => { const j = idx + d; if (j < 0 || j >= s.scenes.length) return; [s.scenes[idx], s.scenes[j]] = [s.scenes[j], s.scenes[idx]]; markDirty(); render(); };
  const words = (sc.narration || "").trim().split(/\s+/).filter(Boolean).length;
  const maxWords = Math.floor(((sc.duration || 8) - 0.3) * 2.5);

  const takes = (st.takes || []).map((t, i) => h("figure", { class: st.picked === i ? "picked" : "" },
    h("video", { src: media(t.file), controls: true, preload: "metadata" }),
    h("figcaption", {}, `take ${i + 1}${st.picked === i ? " ✓" : ""} `, st.picked === i ? null : h("button", { onclick: () => pickTake(sc.id, i + 1) }, "Chọn"))));

  return h("div", { class: `card scene ${sc.status === "approved" ? "approved" : ""} ${sc.locked ? "locked" : ""}` },
    h("div", { class: "scene-head" },
      h("span", { class: "sid" }, sc.id),
      h("select", { onchange: e => { sc.duration = Number(e.target.value); markDirty(); render(); } }, [4, 6, 8].map(d => h("option", { value: d, selected: sc.duration === d }, `${d}s`))),
      h("label", { class: "checks" }, cbApprove, "Duyệt"),
      h("span", { class: "checks" }, checkbox("Khóa", sc, "locked", render)),
      h("span", { class: "badge " + (stale ? "stale" : "ok") }, stale ? "Prompt cũ / chưa viết" : "Prompt khớp"),
      row.tts ? h("span", { class: "badge " + (row.tts === "ok" ? "ok" : row.tts === "-" ? "" : "stale") }, `Voice: ${row.tts}`) : null,
      row.clip ? h("span", { class: "badge " + (row.clip === "ok" ? "ok" : "stale") }, `Clip: ${row.clip}`) : null,
      row.error ? h("span", { class: "badge err", title: row.error }, "Lỗi") : null,
      h("span", { style: "flex:1" }),
      h("button", { onclick: () => move(-1), title: "Lên" }, "↑"), h("button", { onclick: () => move(1), title: "Xuống" }, "↓"),
      h("button", { class: "danger", onclick: () => { if (confirm(`Xóa cảnh ${sc.id}?`)) { s.scenes.splice(idx, 1); markDirty(); render(); } } }, "Xóa")),
    h("div", { class: "grid" },
      field("Mục đích cảnh", sc, "purpose", { options: OPT.purpose }),
      h("label", { class: "f wide" }, `Lời dẫn (${words}/${maxWords} từ tối đa cho ${sc.duration}s)`,
        (() => { const t = h("textarea", { rows: 2 }); t.value = sc.narration || ""; t.addEventListener("input", () => { sc.narration = t.value; markDirty(); }); return t; })()),
      field("Lời thoại nhân vật trong clip (tùy chọn, ≤8s)", sc, "dialogue", { wide: true })),
    h("details", { open: true }, h("summary", {}, "Ai & ở đâu"),
      h("div", { class: "grid" },
        h("div", { class: "f wide" }, "Nhân vật", checkGroup((s.characters || []).map(c => [c.id, c.name || c.id]), sc.characters)),
        field("Bối cảnh", sc, "location", { type: "select", options: [["", "— không —"], ...(s.locations || []).map(l => [l.id, l.name || l.id])] }),
        h("div", { class: "f wide" }, "Đạo cụ", checkGroup((s.props || []).map(p => [p.id, p.name || p.id]), sc.props)),
        field("Trạng thái trang phục / đạo cụ trong cảnh", sc, "prop_state", { wide: true, placeholder: "ly đã uống một nửa, kính lệch" }))),
    h("details", { open: true }, h("summary", {}, "Hành động"),
      h("div", { class: "grid" },
        field("Một hành động chính", sc, "action", { type: "textarea", wide: true }),
        field("Chia mốc thời gian (tùy chọn)", sc, "beats", { type: "textarea", wide: true, placeholder: "[0-2s] …\n[2-5s] …" }),
        field("Biểu cảm", sc, "expression", { wide: true }))),
    h("details", {}, h("summary", {}, "Máy quay"),
      h("div", { class: "grid" },
        field("Cỡ cảnh", sc, "shot_size", { options: OPT.shot_size }), field("Góc máy", sc, "angle", { options: OPT.angle }),
        field("Chuyển động máy (chỉ 1)", sc, "camera_move", { options: OPT.camera_move }), field("Ống kính", sc, "lens", { options: OPT.lens }),
        field("Độ sâu trường ảnh", sc, "dof", { options: OPT.dof }), field("Bố cục", sc, "composition", { options: OPT.composition }))),
    h("details", {}, h("summary", {}, "Ánh sáng & chất ảnh"),
      h("div", { class: "grid" },
        field("Nguồn sáng (có lý do)", sc, "light", { wide: true, placeholder: "nắng sớm xiên qua cửa sổ bên trái" }),
        field("Chất sáng", sc, "light_quality", { options: OPT.light_quality }), field("Nhiệt màu", sc, "color_temp", { options: OPT.color_temp }),
        field("Bầu không khí", sc, "atmosphere", { placeholder: "bụi lơ lửng trong nắng, hơi nước bốc" }))),
    h("details", {}, h("summary", {}, "Âm thanh trong clip"),
      h("div", { class: "grid" },
        field("Tiếng động (SFX)", sc, "sfx"), field("Âm nền", sc, "ambient"),
        h("div", { class: "checks" }, (() => { const o = { mute: !sc.veo_audio }; return checkbox("Tắt tiếng clip (dùng voice-over)", o, "mute", () => { sc.veo_audio = !o.mute; }); })()))),
    h("details", {}, h("summary", {}, "Chống “chất AI” & cần tránh"),
      h("div", { class: "f" }, "Chống chất AI", checkGroup(ANTI_AI, sc.anti_ai)),
      h("div", { class: "f", style: "margin-top:8px" }, "Cần tránh", checkGroup(AVOID.map(a => [a, a]), sc.avoid)),
      field("Ghi chú cho AI", sc, "notes", { type: "textarea", wide: true })),
    h("details", { open: !!sc.veo_prompt }, h("summary", {}, "Prompt (Claude viết từ các ô trên)"),
      sc.veo_prompt_vi ? h("div", { class: "prompt" }, h("b", {}, "Bản dịch: "), sc.veo_prompt_vi) : h("span", { class: "badge" }, "Chưa có — bấm “Viết prompt chi tiết”"),
      h("details", {}, h("summary", {}, "Prompt tiếng Anh (sửa tay nếu cần)"), field("veo_prompt", sc, "veo_prompt", { type: "textarea", wide: true, rows: 5 })),
      h("div", { class: "row", style: "margin-top:8px" },
        h("button", { onclick: () => runJob("prompts", [sc.id]) }, "Viết lại prompt cảnh này"))),
    h("details", { open: !!(st.tts || (st.takes || []).length) }, h("summary", {}, "Media"),
      h("div", { class: "media" },
        st.tts ? h("figure", {}, h("audio", { src: media(st.tts.file), controls: true }), h("figcaption", {}, `voice ${st.tts.duration_s}s`)) : h("span", { class: "badge" }, "Chưa có voice"),
        takes.length ? takes : h("span", { class: "badge" }, "Chưa có clip")),
      h("div", { class: "row", style: "margin-top:8px" },
        h("button", { onclick: () => runJob("tts", [sc.id]) }, "Tạo lại voice"),
        h("button", { onclick: () => confirmFlow([sc.id]) }, "Gen lại cảnh này (Flow)"))));
}

function renderScenes() {
  const s = S.data.script; s.scenes = s.scenes || [];
  const allApproved = s.scenes.length && s.scenes.every(x => x.status === "approved");
  const total = s.scenes.reduce((a, x) => a + (x.duration || 0), 0);
  return h("div", {},
    h("div", { class: "row", style: "margin-bottom:10px" },
      h("button", { onclick: () => { const n = s.scenes.length + 1; s.scenes.push({ id: "s" + String(n).padStart(2, "0"), duration: 6, status: "draft", characters: [], props: [], avoid: [...AVOID.slice(0, 4)], anti_ai: ["film_grain", "imperfections", "practical_light"] }); markDirty(); render(); } }, "+ Thêm cảnh"),
      h("button", { onclick: () => { s.scenes.forEach(x => (x.status = allApproved ? "draft" : "approved")); markDirty(); render(); } }, allApproved ? "Bỏ duyệt tất cả" : "Duyệt tất cả"),
      h("span", { class: "badge" }, `${s.scenes.length} cảnh · tổng ${total}s`)),
    s.scenes.length ? s.scenes.map(sceneCard) : h("div", { class: "empty" }, "Chưa có cảnh. Bấm “1. Viết kịch bản chi tiết” ở tab Chạy & Dựng, hoặc “+ Thêm cảnh”."));
}

function renderRun() {
  const busy = S.job && S.job.state === "running";
  const rows = S.data.status || [];
  return h("div", {},
    h("div", { class: "steps" }, STEPS.map(([k, t, d]) => h("div", { class: "step" }, h("b", {}, t), h("p", {}, d),
      h("button", { class: "primary", disabled: busy || S.dirty, title: S.dirty ? "Lưu trước khi chạy" : "", onclick: () => (k === "flow" || k === "refimg") ? confirmFlow(null, k) : runJob(k) }, "Chạy")))),
    S.dirty ? h("p", { class: "dirty" }, "Lưu thay đổi trước khi chạy các bước.") : null,
    h("div", { class: "card", style: "margin-top:14px" }, h("h3", {}, "Trạng thái từng cảnh"),
      h("table", {}, h("tr", {}, ["Cảnh", "Duyệt", "Voice", "Số take", "Take chọn", "Clip", "Lỗi gần nhất"].map(x => h("th", {}, x))),
        rows.map(r => h("tr", {}, [r.id, r.status, r.tts, r.takes, r.picked, r.clip, r.error].map(x => h("td", {}, x ?? "")))))),
    h("div", { class: "card" }, h("h3", {}, S.job ? `Việc: ${S.job.label} — ${S.job.state}` : "Chưa chạy việc nào"),
      h("pre", { class: "log", id: "log" }, S.job ? (S.job.log || "(chưa có log)") : "")));
}

// ---------- hành động ----------
async function pickTake(scene, take) {
  try { await api(`/api/projects/${S.name}/pick`, { method: "POST", body: JSON.stringify({ scene, take }) }); toast(`${scene}: dùng take ${take}`); openProject(S.name); }
  catch (e) { toast(e.message, true); }
}
function confirmFlow(scenes, kind = "flow") {
  const s = S.data.script;
  if (!s.flow?.video_model) { toast("Chọn model video Google Flow ở tab Hồ sơ trước.", true); S.tab = "profile"; render(); return; }
  const what = kind === "refimg" ? "tạo ảnh nhân vật" : `gen video ${scenes ? scenes.join(", ") : "các cảnh đã duyệt"} bằng ${s.flow.video_model}, tải ${s.flow.resolution}`;
  if (confirm(`Sẽ ${what} trong Google Flow (tốn tín dụng gói). Chrome phải đang đăng nhập Flow và bạn không thao tác Chrome khi đang chạy. Tiếp tục?`)) runJob(kind, scenes);
}
async function runJob(kind, scenes = null) {
  if (S.dirty) { toast("Lưu thay đổi trước khi chạy.", true); return; }
  try {
    S.job = await api(`/api/projects/${S.name}/jobs`, { method: "POST", body: JSON.stringify({ kind, scenes }) });
    toast(`Bắt đầu: ${S.job.label}`); S.tab = "run"; render(); startPolling();
  } catch (e) { toast(e.message, true); }
}
function startPolling() {
  clearInterval(S.poll);
  S.poll = setInterval(async () => {
    const j = await api("/api/jobs/current").catch(() => null);
    if (!j) return;
    S.job = j.state === "idle" ? null : j;
    const pill = document.getElementById("jobPill");
    pill.className = "pill " + (j.state || "");
    pill.textContent = j.state === "running" ? `Đang chạy: ${j.label}` : j.state === "done" ? `Xong: ${j.label}` : j.state === "failed" ? `Lỗi: ${j.label}` : "Rảnh";
    const log = document.getElementById("log");
    if (log && j.log !== undefined) { const atEnd = log.scrollTop + log.clientHeight >= log.scrollHeight - 20; log.textContent = j.log; if (atEnd) log.scrollTop = log.scrollHeight; }
    if (j.state !== "running") {
      clearInterval(S.poll);
      if (j.project === S.name && !S.dirty) { await openProject(S.name); }
      if (j.state === "done") toast(`Xong: ${j.label}`); else if (j.state === "failed") toast(`Lỗi: ${j.label} — xem log`, true);
    }
  }, 2000);
}
function openNew() {
  if (S.dirty && !confirm("Có thay đổi chưa lưu. Bỏ qua?")) return;
  const dlg = document.getElementById("newDlg"), f = document.getElementById("newForm");
  f.reset();
  const title = f.elements.namedItem("title"), nameIn = f.elements.namedItem("name");
  delete nameIn.dataset.touched;
  title.oninput = () => { if (!nameIn.dataset.touched) nameIn.value = slug(title.value).replace(/_/g, "-"); };
  nameIn.oninput = () => (nameIn.dataset.touched = "1");
  dlg.showModal();
  dlg.onclose = async () => {
    if (dlg.returnValue !== "ok") return;
    const body = Object.fromEntries(new FormData(f)); const start = !!body.start; delete body.start;
    try {
      await api("/api/projects", { method: "POST", body: JSON.stringify(body) });
      S.dirty = false; await loadProjects(); await openProject(body.name, false);
      if (start) runJob("script");
    } catch (e) { toast(e.message, true); }
  };
}

// ---------- khởi động ----------
document.getElementById("projectSel").addEventListener("change", e => openProject(e.target.value, false));
document.getElementById("newBtn").addEventListener("click", openNew);
document.getElementById("saveBtn").addEventListener("click", save);
document.getElementById("reloadBtn").addEventListener("click", () => { S.dirty = false; openProject(S.name); });
document.addEventListener("keydown", e => { if ((e.metaKey || e.ctrlKey) && e.key === "s") { e.preventDefault(); save(); } });
window.addEventListener("beforeunload", e => { if (S.dirty) { e.preventDefault(); e.returnValue = ""; } });
(async () => {
  await loadProjects();
  const want = decodeURIComponent(location.hash.slice(1));
  if (want && S.projects.some(p => p.name === want)) await openProject(want);
  else render();
  const j = await api("/api/jobs/current").catch(() => null);
  if (j && j.state === "running") { S.job = j; startPolling(); }
})();
