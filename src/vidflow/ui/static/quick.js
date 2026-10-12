"use strict";
// vidflow — quy trình nhanh: Bảng mốc · Nhân vật · Xem thử & Xuất · Tạo video nhanh (spec 2026-10-12, Giai đoạn 3).
// Dùng chung tiện ích của app.js (nạp trước): h, api, toast, S, setCurrent, startPolling, openProject, loadProjects.

const Q = {
  name: null, data: null, screen: "board", filter: "all", sel: null, fresh: false, provider: null,
  drafts: {}, reviewing: {}, timer: null, wave: null, player: null,
  exportOpts: { resolution: "1080p", transition: "scene", clip_fit: "trim", zoom: true, subtitles: true, logo: true, clip_audio: false, music: false },
};
const QSCREENS = {}; // id màn → hàm trả [vùng giữa, khung phải | null]; mỗi màn tự đăng ký
const QNAV = [["board", "Bảng mốc"], ["chars", "Nhân vật"], ["preview", "Xem thử & Xuất"]];
const QST = { ok: ["Có ảnh", "st-ok"], gen: ["Đang gen", "st-gen"], error: ["Lỗi", "st-error"], pending: ["Chờ", "st-pending"], redo: ["Gen lại", "st-redo"], blocked: ["Bị chặn", "st-blocked"] };
const QCLIP = { pending: "chưa gen", ok: "đã có clip", redo: "chờ gen lại", error: "lỗi" };
const QJOB = { running: "đang chạy", done: "xong", failed: "lỗi", stopped: "đã dừng" };
const QSTAGE = { new: "mới tạo", ideas: "chờ chọn ý tưởng", picked: "đã chọn ý tưởng", script: "đã có kịch bản", voiced: "đã có giọng đọc", prompted: "đã có prompt", imaged: "đủ ảnh", built: "đã dựng" };
const SCENE_COLORS = ["#3557D6", "#E09A2D", "#8B5E3C", "#2E8B6E", "#7A4FB5", "#0069ba"];
const PROVIDERS = [["flow", "Flow"], ["gemini", "Gemini"], ["aistudio", "AI Studio"]];
const VIDEO_MODELS = ["", "Veo 3.1 Lite", "Veo 3.1 Fast", "Veo 3.1 Quality", "Omni 1.1 Flash"];
const IMAGE_MODELS = ["Nano Banana 2"];
const FLOW_JOBS = { flow: "gen ảnh mốc", clips: "gen clip động", sheets: "gen character sheet" };
const QFILTERS = [
  ["all", "Tất cả", () => true],
  ["error", "Lỗi", b => b.state === "error" || b.clip.status === "error"],
  ["noimg", "Chưa có ảnh", b => b.state !== "ok"],
  ["blocked", "Bị chặn", b => b.state === "blocked"],
  ["clip", "Clip", b => b.clip.enabled],
  ["cont", "Nối cảnh", b => b.cont],
];

// ================= tiện ích =================
function fmtT(s) { if (s == null) return "--:--"; const m = Math.floor(s / 60), x = Math.floor(s % 60); return `${String(m).padStart(2, "0")}:${String(x).padStart(2, "0")}`; }
function fmtT1(s) { s = Math.max(0, s || 0); const m = Math.floor(s / 60); return `${String(m).padStart(2, "0")}:${(s - m * 60).toFixed(1).padStart(4, "0")}`; }
function pad3(n) { return String(n).padStart(3, "0"); }
function qBeat(n) { return (Q.data?.beats || []).find(b => b.n === n) || null; }
function qChar(id) { return (Q.data?.characters || []).find(c => c.id === id) || null; }
// video nhanh `name` còn đang mở? Phản hồi chậm (kiểm duyệt tới 300 s) về sau khi người dùng đã chuyển video/trang chủ
// thì bỏ qua: không vẽ đè #main, không toast, không gọi API theo tên mới.
function qActive(name = Q.name) { return S.kind === "quick" && S.name === name && Q.name === name; }
function qSay(name, msg, err = false) { if (qActive(name)) toast(msg, err); }
async function qPost(path, body, name = Q.name) { return api(`/api/quick/${name}${path}`, { method: "POST", body: JSON.stringify(body || {}) }); }
async function qReload() {
  const name = Q.name, d = await api(`/api/quick/${name}`);
  if (Q.name !== name) return; // đã mở video khác trong lúc chờ
  Q.data = d; if (d.job) S.job = d.job;
}
// sau mỗi thao tác: tải lại + vẽ lại nếu video `name` còn mở; lỗi tải → toast
async function qRefresh(name, opts = {}) {
  if (!qActive(name)) return;
  try { await qReload(); } catch (e) { qSay(name, e.message, true); }
  if (qActive(name)) Q.render(opts);
}
function qColor(c, fallback) { return typeof c === "string" && /^#[0-9A-Fa-f]{6}$/.test(c) ? c : fallback; } // màu vào style: chỉ #RRGGBB
function provLabel(p) { return (PROVIDERS.find(x => x[0] === p) || [p, p || "Flow"])[1]; }
// nguồn gen cho việc gen: ô "Nguồn" (ghi đè một lần) hoặc cài đặt video (ảnh/sheet: image_provider; clip: video_provider)
function qProvider(kind) { const f = Q.data.quick.flow; return Q.provider || (kind === "clips" ? f.video_provider : f.image_provider) || "flow"; }

// ================= mở / vẽ =================
Q.open = async function (name) {
  if (Q.name !== name) Object.assign(Q, { name, data: null, screen: "board", filter: "all", sel: null, fresh: true, drafts: {}, reviewing: {} });
  Q.wave = null;
  try { await qReload(); } catch (e) { qSay(name, e.message, true); return; }
  if (!qActive(name)) return;
  if (Q.fresh) { Q.sel = Q.data.beats.length ? Q.data.beats[0].n : null; Q.fresh = false; }
  if (Q.sel != null && !qBeat(Q.sel)) Q.sel = Q.data.beats.length ? Q.data.beats[0].n : null;
  Q.render();
  qAutoRefresh();
};
// đang chọn/gõ trong ô của thanh đầu hoặc khung phải (ô "Nguồn", cài đặt...) → không vẽ lại kẻo mất lựa chọn dở
function qFormFocus() {
  const ae = document.activeElement;
  return !!ae && /^(SELECT|INPUT|TEXTAREA)$/.test(ae.tagName) && !!ae.closest("#main .qhead, #main .panel");
}
function qAutoRefresh() {
  clearInterval(Q.timer);
  Q.timer = setInterval(async () => {
    const running = Q.data?.job && Q.data.job.state === "running";
    if (S.kind !== "quick" || S.name !== Q.name || (!running && !Q.stale)) { clearInterval(Q.timer); return; }
    if (Q.screen === "preview") return; // không làm gián đoạn trình phát
    if (running) { try { await qReload(); } catch { return; } }
    if (qFormFocus()) { Q.stale = true; return; } // dữ liệu đã tải lặng lẽ; vẽ ở lượt sau khi rời ô
    Q.render({ keepPanel: true });
  }, 5000);
}
Q.render = function (opts = {}) {
  const d = Q.data; if (!d || !qActive()) return; // không vẽ đè khi đang mở video chi tiết / trang chủ
  Q.stale = false;
  document.getElementById("savebar").hidden = true; document.body.classList.remove("has-savebar");
  const main = document.getElementById("main");
  const oldPanel = opts.keepPanel ? main.querySelector(".panel") : null;
  const keep = oldPanel && oldPanel.contains(document.activeElement) ? oldPanel : null; // đang gõ trong khung phải → giữ nguyên
  // vẽ lại khung phải trong lúc đang gõ (vd. kết quả kiểm duyệt cùng mốc): nhớ ô + con trỏ để trả lại sau khi vẽ
  const ae = document.activeElement, focusKey = !keep && ae && main.querySelector(".panel")?.contains(ae) ? ae.getAttribute("aria-label") : null;
  const caret = focusKey && "selectionStart" in ae ? [ae.selectionStart, ae.selectionEnd, ae.scrollTop] : null;
  // trình phát Xem thử bị vẽ lại / rời màn: dừng tiếng + vòng vẽ (phần tử cũ tách khỏi trang vẫn phát nếu không dừng)
  main.querySelectorAll("audio, video").forEach(m => { if (!keep || !keep.contains(m)) m.pause(); });
  if (Q.player) { cancelAnimationFrame(Q.player.raf); Q.player = null; }
  setCurrent(d.preset.name, d.quick.title || d.name, [d.status.voice_s ? fmtT(d.status.voice_s) : null, `${d.beats.length} mốc`, d.aspect].filter(Boolean).join(" · "));
  document.getElementById("railNav").replaceChildren(qRail());
  const [center, panel] = (QSCREENS[Q.screen] || QSCREENS.board)();
  main.className = panel ? "app" : "app single";
  main.replaceChildren(...[center, panel ? (keep || panel) : null].filter(Boolean));
  const back = focusKey ? [...main.querySelectorAll(".panel [aria-label]")].find(x => x.getAttribute("aria-label") === focusKey) : null;
  if (back) { back.focus(); if (caret) try { back.setSelectionRange(caret[0], caret[1]); back.scrollTop = caret[2]; } catch { /* ô không có con trỏ */ } }
};
function qSteps() {
  const d = Q.data, st = d.status, b = st.beats;
  const idx = ["new", "ideas", "picked", "script", "voiced", "prompted", "imaged", "built"].indexOf(st.stage);
  const steps = [
    ["Ý tưởng", st.ideas ? `${st.ideas} ý` : "", idx >= 2],
    ["Kịch bản · mốc", b.total ? String(b.total) : "", idx >= 3 && b.total > 0],
    ["Giọng đọc", st.voice_s ? fmtT(st.voice_s) : "", b.total > 0 && b.timed],
    ["Prompt", b.total ? `${b.prompted}/${b.total}` : "", b.total > 0 && b.prompted === b.total],
    ["Ảnh · clip", b.total ? `${b.imaged}/${b.total}` : "", b.total > 0 && b.imaged === b.total],
    ["Xuất video", d.renders.length ? String(d.renders.length) : "", d.renders.length > 0],
  ];
  const now = steps.findIndex(s => !s[2]);
  return steps.map(([label, meta, done], i) => ({ label, meta, state: done ? "done" : i === now ? "now" : "todo" }));
}
function qRail() {
  const d = Q.data, missing = d.characters.filter(c => !c.image_url && c.uses > 0).length;
  const link = (id, label) => h("button", { class: "navlink" + (Q.screen === id ? " active" : ""), onclick: () => { Q.screen = id; Q.render(); } },
    label, id === "chars" && missing ? h("span", { class: "tag warn" }, `${missing} thiếu`) : null);
  return h("div", {},
    h("div", { class: "navlist" }, QNAV.filter(([id]) => QSCREENS[id]).map(([id, label]) => link(id, label))),
    h("div", { class: "psteps" }, h("span", { class: "eyebrow" }, "Tiến độ"),
      h("ol", {}, qSteps().map((s, i) => h("li", { class: s.state },
        h("span", { class: "pdot " + s.state }, s.state === "done" ? "✓" : String(i + 1)), h("span", { class: "plabel" }, s.label), h("span", { class: "pmeta" }, s.meta))))));
}

// ================= việc nền =================
// job clip cần model clip; false → đã báo và mở Cài đặt
function qClipModelOk(kind) {
  if (kind !== "clips" || Q.data.quick.flow.video_model) return true;
  toast("Chọn model clip trong Cài đặt trước.", true); Q.screen = "board"; Q.sel = null; Q.render(); return false;
}
function qConfirmGen(kind) {
  return confirm(`Sẽ ${FLOW_JOBS[kind]} trong ${provLabel(qProvider(kind))} (phiên Chrome đã đăng nhập, tốn lượt/tín dụng gói). Đừng thao tác Chrome khi đang chạy. Tiếp tục?`);
}
async function qJob(kind, { instruction = "", options = null, confirmText = null, confirmed = false } = {}) {
  const name = Q.name, gen = !!FLOW_JOBS[kind];
  if (!qClipModelOk(kind)) return;
  if (gen && !confirmed && !qConfirmGen(kind)) return;
  if (confirmText && !confirm(confirmText)) return;
  try {
    const job = await qPost("/jobs", { kind, instruction, options: options || {}, provider: gen && Q.provider ? Q.provider : null }, name);
    S.job = job; startPolling(); // việc nền là chung cả máy: luôn theo dõi
    if (!qActive(name)) return;
    Q.data.job = job;
    toast(`Bắt đầu: ${job.label}`); Q.render(); qAutoRefresh();
  } catch (e) { qSay(name, e.message, true); }
}
async function qStop() {
  const name = Q.name;
  if (!confirm("Dừng việc đang chạy? Ảnh/clip đã gen giữ nguyên.")) return;
  try { await qPost("/jobs/stop", {}, name); qSay(name, "Đã dừng"); } catch (e) { qSay(name, e.message, true); }
  if (qActive(name)) await Q.open(name);
}
async function qRetryErrors() {
  const name = Q.name, kind = Q.data.beats.some(b => b.error) ? "flow" : "clips";
  if (!qClipModelOk(kind) || !qConfirmGen(kind)) return; // hỏi trước: bấm Hủy thì lỗi vẫn giữ nguyên
  try {
    const img = await qPost("/retry", { ns: null, clip: false }, name);
    const clip = await qPost("/retry", { ns: null, clip: true }, name);
    if (!qActive(name)) return;
    toast(`Đã đưa ${img.count + clip.count} mốc lỗi về hàng chờ`);
    await qReload();
    if (qActive(name)) await qJob(kind, { confirmed: true });
    // một hàng chạy duy nhất: không nối job clip sau job ảnh được — nhắc người dùng tự bấm
    if (kind === "flow" && clip.count && qActive(name)) toast("Đã đưa lại clip lỗi vào hàng chờ — bấm Gen clip sau khi gen ảnh xong.");
  } catch (e) { qSay(name, e.message, true); }
}
async function qPick(n) {
  const name = Q.name;
  try { const r = await qPost("/pick", { n }, name); qSay(name, `Đã chọn: ${r.title}`); } catch (e) { qSay(name, e.message, true); }
  if (qActive(name)) await Q.open(name);
}

// ================= Bảng mốc — vùng giữa =================
function qCounts() {
  const c = { ok: 0, gen: 0, error: 0, pending: 0, redo: 0, blocked: 0 };
  for (const b of Q.data.beats) c[b.state]++;
  return c;
}
function qBoardHead() {
  const d = Q.data, c = qCounts(), total = d.beats.length || 1;
  const job = d.job && d.job.state === "running" ? d.job : null, busy = S.job?.state === "running";
  const errs = d.beats.filter(b => b.error).length + d.beats.filter(b => b.clip.status === "error").length;
  const clipTodo = d.beats.filter(b => b.clip.enabled && b.clip.status !== "ok").length;
  const seg = (k, color) => h("span", { style: `width:${(c[k] / total) * 100}%;background:${color}` });
  const provSel = h("select", { class: "prov-sel", "aria-label": "Nguồn gen (ghi đè một lần)" }, h("option", { value: "" }, "Nguồn: theo cài đặt"),
    PROVIDERS.map(([v, l]) => h("option", { value: v }, "Nguồn: " + l)));
  provSel.value = Q.provider || ""; provSel.onchange = () => { Q.provider = provSel.value || null; Q.render({ keepPanel: true }); };
  const stats = [["ok", "có ảnh"], ["gen", "đang gen"], ["error", "lỗi"], ["pending", "chờ"], ["redo", "gen lại"], ["blocked", "bị chặn"]];
  return h("header", { class: "qhead" }, h("h1", {}, "Bảng mốc"),
    h("div", { class: "qprog" },
      h("div", { class: "qstats" }, stats.map(([k, l]) => h("span", { class: "qstat " + k }, h("strong", {}, String(c[k])), " " + l))),
      h("div", { class: "qbar", role: "img", "aria-label": `${c.ok} trên ${d.beats.length} mốc có ảnh` },
        seg("ok", "var(--success)"), seg("gen", "var(--secondary)"), seg("error", "var(--error)"), seg("blocked", "var(--warn)"))),
    h("div", { class: "row" }, provSel,
      job ? h("button", { onclick: qStop }, "Tạm dừng")
        : h("button", { class: "primary", disabled: !d.beats.length || busy, onclick: () => qJob("flow") }, `Gen ảnh (${provLabel(qProvider("flow"))})`),
      errs ? h("button", { class: "danger", disabled: busy, onclick: qRetryErrors }, `Chạy lại ${errs} lỗi`) : null,
      clipTodo ? h("button", { class: "primary", disabled: busy, onclick: () => qJob("clips") }, `Gen ${clipTodo} clip (${provLabel(qProvider("clips"))})`) : null,
      h("button", { onclick: () => { Q.sel = null; Q.render(); } }, "Cài đặt")));
}
function qNext() {
  const d = Q.data, st = d.status, q = d.quick, busy = S.job?.state === "running";
  const btn = (label, fn, primary = true) => h("button", { class: primary ? "primary" : "", disabled: busy, onclick: fn }, label);
  const box = (title, text, ...actions) => h("div", { class: "card next-card" }, h("h3", {}, title), text ? h("p", { class: "hint" }, text) : null, h("div", { class: "row" }, actions));
  if (st.stage === "new") return box("Bước 1 · Ý tưởng", "AI đề xuất 5 ý tưởng theo brief của bộ kênh.",
    btn("Đề xuất 5 ý tưởng", () => qJob("ideas", { instruction: q.title ? `Chủ đề người dùng gợi ý: ${q.title}` : "" })));
  if (st.stage === "ideas") return h("div", { class: "card next-card" }, h("h3", {}, "Bước 1 · Chọn một ý tưởng"),
    h("ol", { class: "ideas" }, q.ideas.map((it, i) => h("li", {}, h("div", { class: "idea" },
      h("div", {}, h("b", {}, it.title), it.hook ? h("p", { class: "hint" }, it.hook) : null, it.why_viral ? h("p", { class: "hint" }, "Vì sao: " + it.why_viral) : null),
      h("button", { class: "primary small", disabled: busy, onclick: () => qPick(i + 1) }, "Chọn"))))),
    h("div", { class: "row" }, btn("Đề xuất lại", () => qJob("ideas"), false)));
  if (st.stage === "picked") return box("Bước 2 · Kịch bản", `Ý tưởng: ${st.picked_title}. AI viết lời dẫn, tách mốc và đề xuất nhân vật riêng.`, btn("Viết kịch bản + tách mốc", () => qJob("script")));
  if (st.stage === "script") return box("Bước 3 · Giọng đọc", "Đọc từng mốc bằng Gemini TTS (gói miễn phí) và điền thời gian.", btn("Tạo giọng đọc", () => qJob("voice")));
  if (st.beats.prompted < st.beats.total) return box("Bước 4 · Prompt", `${st.beats.prompted}/${st.beats.total} mốc có prompt đạt kiểm duyệt.`, btn("Viết prompt ảnh + clip", () => qJob("prompts")));
  if (st.chars_missing.length) return box("Nhân vật thiếu ảnh", `${st.chars_missing.map(c => "@" + c).join(", ")} chưa có character sheet — ${st.blocked} mốc đang bị chặn.`,
    btn(`Gen sheet (${provLabel(qProvider("sheets"))})`, () => qJob("sheets")), QSCREENS.chars ? btn("Mở Nhân vật", () => { Q.screen = "chars"; Q.render(); }, false) : null);
  return null;
}
function qFilters() {
  return h("div", { class: "seg-group", role: "group", "aria-label": "Lọc mốc" }, QFILTERS.map(([k, label, fn]) =>
    h("button", { class: Q.filter === k ? "on" : "", "aria-pressed": Q.filter === k ? "true" : "false", onclick: () => { Q.filter = k; Q.render({ keepPanel: true }); } },
      label, " ", h("span", { class: "mono count" }, String(Q.data.beats.filter(fn).length)))));
}
function qSceneList(beats) {
  const scenes = [];
  for (const b of beats) {
    if (!b.cont || !scenes.length) scenes.push({ beats: [] });
    scenes[scenes.length - 1].beats.push(b);
  }
  scenes.forEach((s, i) => {
    const lead = s.beats.flatMap(b => b.refs).map(qChar).find(c => c && qColor(c.color));
    s.color = lead ? lead.color : SCENE_COLORS[i % SCENE_COLORS.length];
    s.index = i + 1;
  });
  return scenes;
}
function qRefChip(id) {
  const c = qColor(qChar(id)?.color, "#4A4F6E");
  return h("span", { class: "ref mono", style: `background:${c}1F;color:color-mix(in srgb, ${c} 70%, #0E1238)` }, "@" + id);
}
function qThumbLabel(b) {
  return { gen: "Flow đang vẽ…", error: "Flow từ chối prompt", blocked: "Bị chặn: " + (b.blocked || ""), redo: "Chờ gen lại",
    pending: b.blocked ? "Chờ: " + b.blocked : b.prompt ? "Chưa có ảnh" : "Chưa có prompt" }[b.state] || "";
}
function qCard(b, color) {
  const [label, cls] = QST[b.state];
  const clipTag = b.clip.enabled ? h("span", { class: "cliptag" }, b.clip.status === "ok" ? "CLIP" : b.clip.status === "error" ? "CLIP lỗi" : "CLIP chờ") : null;
  return h("div", { class: "beat-wrap" },
    b.cont ? h("span", { class: "contline", title: "Nối cảnh với mốc trước", style: `background:${color}` }) : null,
    h("button", { class: "beat" + (Q.sel === b.n ? " sel" : "") + (b.state === "error" ? " err" : ""), "aria-pressed": Q.sel === b.n ? "true" : "false", onclick: () => { Q.sel = b.n; Q.render(); } },
      h("div", { class: "thumb" }, b.image_url ? h("img", { src: b.image_url, alt: `Ảnh mốc ${b.n}`, loading: "lazy" }) : h("span", { class: "thumb-ph" }, qThumbLabel(b))),
      h("div", { class: "beat-body" },
        h("div", { class: "beat-meta" }, h("span", { class: "mono bn" }, pad3(b.n)), h("span", { class: "mono bt" }, fmtT(b.start)), b.image_url && b.provider ? h("span", { class: "prov" }, provLabel(b.provider)) : null, h("span", { class: "grow" }), clipTag, h("span", { class: "st " + cls }, label)),
        h("div", { class: "beat-text" }, b.text),
        h("div", { class: "refs-row" }, b.refs.map(qRefChip)))));
}
function qScenes() {
  const fn = QFILTERS.find(f => f[0] === Q.filter)[2];
  const out = qSceneList(Q.data.beats).map(sc => {
    const shown = sc.beats.filter(fn);
    if (!shown.length) return null;
    const first = sc.beats[0], last = sc.beats[sc.beats.length - 1];
    return h("section", { class: "scene-sec" },
      h("div", { class: "scene-h" }, h("span", { class: "swatch", style: `background:${sc.color}` }), h("h2", {}, `Cảnh ${sc.index}`),
        h("span", { class: "mono muted" }, `${pad3(first.n)}–${pad3(last.n)} · ${fmtT(first.start)}`), h("span", { class: "rule" })),
      h("div", { class: "beats-row" }, shown.map(b => qCard(b, sc.color))));
  }).filter(Boolean);
  return out.length ? h("div", { class: "scenes" }, out) : h("p", { class: "hint" }, "Không có mốc nào khớp bộ lọc.");
}
function qQuotaBanner() {
  const j = Q.data.job;
  if (!j || !j.quota_exhausted) return null;
  return h("div", { class: "notice warn banner", role: "alert" }, h("strong", {}, `Hết lượt ở ${provLabel(j.provider)}. `),
    "Chọn nguồn khác ở ô “Nguồn” phía trên (Flow, Gemini hoặc AI Studio) rồi bấm Gen lại, hoặc đổi nguồn mặc định trong Cài đặt.");
}
function qBoard() {
  const d = Q.data, job = d.job;
  // Log việc nền đặt ngay dưới đầu trang (trước danh sách mốc dài) để thấy ngay khi bấm chạy
  const center = h("section", { class: "content" }, qBoardHead(), qQuotaBanner(),
    job ? h("details", { class: "joblog", open: job.state !== "done" }, h("summary", {}, `${job.label} · ${QJOB[job.state] || job.state}`),
      h("pre", { class: "log", id: "log" }, job.log || "(đang chạy…)")) : null,
    qNext(), d.beats.length ? qFilters() : null,
    d.beats.length ? qScenes() : h("p", { class: "hint" }, "Chưa có mốc — làm theo thẻ Bước tiếp theo ở trên."));
  return [center, qPanel()];
}

// ================= Bảng mốc — khung phải =================
function qPanel() {
  const b = Q.sel != null ? qBeat(Q.sel) : null;
  return h("aside", { class: "panel", "aria-label": b ? `Chi tiết mốc ${b.n}` : "Cài đặt video" }, b ? qDetail(b) : qSettings());
}
function qReviewLabel(rv, key) {
  if (Q.reviewing[key]) return h("span", { class: "rv busy" }, "Đang kiểm duyệt…");
  if (!rv) return h("span", { class: "rv none" }, "Chưa kiểm duyệt");
  if (rv.verdict === "override") return h("span", { class: "rv ok" }, "Duyệt tay");
  return h("span", { class: "rv " + (rv.verdict === "pass" ? "ok" : "bad") }, `${rv.verdict === "pass" ? "Đạt" : "Trượt"} · ${rv.score}/10`);
}
function qIssues(rv) { return rv && rv.verdict === "fail" && rv.issues.length ? h("ul", { class: "issues-list" }, rv.issues.map(x => h("li", {}, x))) : null; }
function qDraft(b, kind) { const k = `${b.n}:${kind}`; return k in Q.drafts ? Q.drafts[k] : (kind === "clip" ? b.clip.prompt : b.prompt); }
function qAttach(a) {
  const pic = a.url ? h("img", { src: a.url, alt: "" }) : h("span", { class: "att-ph" });
  if (a.kind === "prev") return h("span", { class: "att prev" }, pic, h("span", {}, `Ảnh mốc ${pad3(a.n)} · nối cảnh${a.url ? "" : " (chưa có)"}`));
  return h("span", { class: "att" + (a.url ? "" : " missing") }, pic, h("span", { class: "mono" }, "@" + a.id), a.url ? null : h("span", { class: "st st-blocked" }, "Thiếu ảnh"));
}
function qDetail(b) {
  const d = Q.data, q = d.quick, [label, cls] = QST[b.state], busy = S.job?.state === "running";
  const rvImg = !!Q.reviewing[`${b.n}:img`], rvClip = !!Q.reviewing[`${b.n}:clip`]; // đang kiểm duyệt → khóa nút + ô prompt
  const imgTa = h("textarea", { class: "prompt-area", rows: 6, "aria-label": "Prompt ảnh", readonly: rvImg });
  imgTa.value = qDraft(b, "img"); imgTa.oninput = () => { Q.drafts[`${b.n}:img`] = imgTa.value; };
  const clipOn = h("input", { type: "checkbox", "aria-label": "Làm clip động", disabled: rvClip });
  clipOn.checked = b.clip.enabled; clipOn.onchange = () => qToggleClip(b.n, clipOn.checked);
  let clipBlock = null;
  if (b.clip.enabled) {
    const clipTa = h("textarea", { class: "prompt-area", rows: 4, "aria-label": "Prompt clip", readonly: rvClip });
    clipTa.value = qDraft(b, "clip"); clipTa.oninput = () => { Q.drafts[`${b.n}:clip`] = clipTa.value; };
    clipBlock = h("div", { class: "clip-inner" },
      h("div", { class: "lbl" }, h("span", { class: "eyebrow" }, "Prompt clip"), qReviewLabel(b.clip.review, `${b.n}:clip`)), clipTa, qIssues(b.clip.review),
      b.clip.error ? h("p", { class: "notice err" }, "Flow từ chối clip: " + b.clip.error) : null,
      b.clip_url ? h("video", { src: b.clip_url, controls: true, preload: "metadata", class: "clip-prev" }) : null,
      h("span", { class: "hint" }, `${provLabel(q.flow.video_provider)} · ${q.flow.video_model || "Chưa chọn model clip"} · ${q.flow.resolution} · gen từ ảnh mốc này · ${d.status.clips.enabled}/${q.max_clips} clip đã chọn · ${QCLIP[b.clip.status]}${b.clip.provider ? " · clip gen bằng " + provLabel(b.clip.provider) : ""}`),
      h("div", { class: "row" },
        h("button", { class: "small", disabled: rvClip, onclick: () => qOverride(b.n, true) }, "Duyệt tay"),
        b.clip.status === "ok" ? h("button", { class: "small", disabled: rvClip, onclick: () => qRedo(b.n, true) }, "Gen lại clip") : null,
        h("button", { class: "small secondary", disabled: rvClip, onclick: () => qSaveReview(b.n, true) }, "Lưu & kiểm duyệt clip")));
  }
  return h("div", { class: "detail" },
    h("div", { class: "detail-h" }, h("h2", {}, `Mốc ${pad3(b.n)}`), h("span", { class: "mono muted" }, `${fmtT(b.start)} → ${fmtT(b.end)}`), h("span", { class: "grow" }), h("span", { class: "st " + cls }, label)),
    h("p", { class: "quote" }, `“${b.text}”`),
    b.image_url ? h("img", { class: "detail-img", src: b.image_url, alt: `Ảnh mốc ${b.n}` }) : null,
    b.image_url && b.provider ? h("span", { class: "hint" }, "Ảnh gen bằng " + provLabel(b.provider)) : null,
    b.error ? h("p", { class: "notice err" }, "Flow từ chối ảnh: " + b.error) : null,
    b.blocked && b.state !== "ok" ? h("p", { class: "notice warn" }, (b.state === "blocked" ? "Bị chặn: " : "Chờ: ") + b.blocked) : null,
    h("div", { class: "group" }, h("span", { class: "eyebrow" }, "Ảnh đính kèm khi gen"),
      b.attach.length ? h("div", { class: "attach" }, b.attach.map(qAttach)) : h("span", { class: "hint" }, "Không đính ảnh nào")),
    h("label", { class: "group" }, h("span", { class: "lbl" }, h("span", { class: "eyebrow" }, "Prompt ảnh"), qReviewLabel(b.review, `${b.n}:img`)), imgTa),
    qIssues(b.review),
    h("div", { class: "clipbox" }, h("label", { class: "switch" }, h("span", {}, "Làm clip động"), clipOn), clipBlock),
    h("div", { class: "actions" },
      h("button", { disabled: b.status !== "ok" || rvImg, onclick: () => qRedo(b.n, false) }, "Gen lại ảnh"),
      h("button", { disabled: busy || rvImg || rvClip, onclick: () => qJob("prompts", { instruction: `Chỉ viết lại prompt ảnh (và prompt clip nếu bật) của mốc ${b.n}; không đụng mốc khác.`, confirmText: `AI sẽ viết lại prompt mốc ${b.n}. Tiếp tục?` }) }, "AI viết lại"),
      h("button", { disabled: rvImg, onclick: () => qOverride(b.n, false) }, "Duyệt tay"),
      h("button", { class: "secondary grow", disabled: rvImg, onclick: () => qSaveReview(b.n, false) }, "Lưu & kiểm duyệt")));
}
function qSettings() {
  const q = Q.data.quick, f = { ...q.flow, max_clips: q.max_clips, allow_cont: q.allow_cont };
  const sel = (key, opts) => {
    const all = [...new Set([...opts, f[key] ?? ""])];
    const s = h("select", {}, all.map(o => h("option", { value: o }, o || "— chọn —")));
    s.value = f[key] ?? ""; s.onchange = () => { f[key] = s.value; }; return s;
  };
  const psel = key => { const s = h("select", {}, PROVIDERS.map(([v, l]) => h("option", { value: v }, l))); s.value = f[key] || "flow"; s.onchange = () => { f[key] = s.value; }; return s; };
  const max = h("input", { type: "number", min: 0, max: 200 }); max.value = f.max_clips; max.oninput = () => { f.max_clips = Number(max.value); };
  const cont = h("input", { type: "checkbox" }); cont.checked = f.allow_cont; cont.onchange = () => { f.allow_cont = cont.checked; };
  const name = Q.name;
  const save = async () => {
    if (f.max_clips > 0 && !f.video_model) { toast("Chọn model clip (bắt buộc khi số clip > 0).", true); return; }
    try {
      await qPost("/settings", { image_model: f.image_model, video_model: f.video_model, resolution: f.resolution, image_provider: f.image_provider || "flow", video_provider: f.video_provider || "flow", max_clips: f.max_clips, allow_cont: f.allow_cont }, name);
      qSay(name, "Đã lưu cài đặt"); await qRefresh(name);
    } catch (e) { qSay(name, e.message, true); }
  };
  return h("div", { class: "detail" }, h("h2", {}, "Cài đặt video"), h("p", { class: "hint" }, "Bấm một mốc trên bảng để xem chi tiết."),
    h("label", { class: "f" }, h("span", { class: "flabel" }, "Model ảnh"), sel("image_model", IMAGE_MODELS)),
    h("label", { class: "f" }, h("span", { class: "flabel" }, "Model clip động"), sel("video_model", VIDEO_MODELS)),
    h("label", { class: "f" }, h("span", { class: "flabel" }, "Độ phân giải clip"), sel("resolution", ["720p", "1080p"])),
    h("label", { class: "f" }, h("span", { class: "flabel" }, "Nguồn gen ảnh (và sheet)"), psel("image_provider")),
    h("label", { class: "f" }, h("span", { class: "flabel" }, "Nguồn gen clip"), psel("video_provider")),
    h("label", { class: "f" }, h("span", { class: "flabel" }, "Số clip tối đa (0 = chỉ ảnh)"), max),
    h("label", { class: "checks" }, cont, "Cho phép nối cảnh"),
    h("button", { class: "primary", onclick: save }, "Lưu cài đặt"));
}
async function qSaveReview(n, clip) {
  const name = Q.name, key = `${n}:${clip ? "clip" : "img"}`, b = qBeat(n), saved = clip ? b.clip.prompt : b.prompt;
  const text = (key in Q.drafts ? Q.drafts[key] : saved).trim();
  if (!text) { toast("Prompt rỗng.", true); return; }
  try { if (text !== saved) await qPost("/prompt", { n, prompt: text, clip }, name); } catch (e) { qSay(name, e.message, true); return; }
  if (!qActive(name)) return;
  delete Q.drafts[key];
  Q.reviewing[key] = true;
  await qRefresh(name);
  try {
    const r = await qPost("/review", { n, clip }, name);
    qSay(name, `Mốc ${n}: ${r.review.verdict === "pass" ? "đạt" : "trượt"} ${r.review.score}/10`, r.review.verdict !== "pass");
  } catch (e) { qSay(name, e.message, true); }
  if (Q.name === name) delete Q.reviewing[key];
  await qRefresh(name, { keepPanel: Q.sel !== n }); // đang sửa mốc khác → giữ nguyên khung phải (con trỏ, chữ đang gõ)
}
async function qOverride(n, clip) {
  const name = Q.name, key = `${n}:${clip ? "clip" : "img"}`, b = qBeat(n), saved = clip ? b.clip.prompt : b.prompt;
  if (!confirm(`Duyệt tay prompt ${clip ? "clip" : "ảnh"} mốc ${n} (cho phép gen dù chưa đạt kiểm duyệt)?`)) return;
  try {
    const text = key in Q.drafts ? Q.drafts[key].trim() : "";
    if (text && text !== saved) await qPost("/prompt", { n, prompt: text, clip }, name);
    if (Q.name === name) delete Q.drafts[key];
    await qPost("/override", { n, clip }, name); qSay(name, `Mốc ${n}: đã duyệt tay`);
  } catch (e) { qSay(name, e.message, true); }
  await qRefresh(name);
}
async function qRedo(n, clip) {
  const name = Q.name;
  try { await qPost("/redo", { ns: [n], clip }, name); qSay(name, `Mốc ${n}: chờ gen lại ${clip ? "clip" : "ảnh"}`); } catch (e) { qSay(name, e.message, true); }
  await qRefresh(name);
}
async function qToggleClip(n, on) {
  const name = Q.name;
  try { await qPost("/clip", { ns: [n], on }, name); } catch (e) { qSay(name, e.message, true); }
  await qRefresh(name);
}
QSCREENS.board = qBoard;

// ================= Nhân vật =================
function qChars() {
  const d = Q.data;
  const group = (scope, title, sub, empty) => {
    const list = d.characters.filter(c => c.scope === scope);
    return h("section", { class: "char-group" },
      h("div", { class: "scene-h" }, h("h2", {}, title), h("span", { class: "muted" }, sub), h("span", { class: "rule" })),
      list.length ? h("div", { class: "chars-grid" }, list.map(qCharCard)) : h("p", { class: "hint" }, empty));
  };
  return [h("section", { class: "content" },
    h("header", { class: "qhead" }, h("div", {}, h("h1", {}, "Nhân vật"),
      h("p", { class: "hint" }, "Prompt nhắc ", h("span", { class: "mono" }, "@TÊN"), " thì ảnh nhân vật đó được đính kèm khi gen trong Flow. Nhân vật chưa có ảnh sẽ chặn các mốc dùng nó."))),
    group("channel", "Của bộ kênh", `${d.preset.name} — dùng lại ở mọi video`, "Bộ kênh chưa có nhân vật, hoặc video này không dùng."),
    group("video", "Riêng video này", "AI đề xuất từ kịch bản, bạn duyệt trước khi gen ảnh mốc", "Chưa có — AI đề xuất sau bước kịch bản.")), null];
}
function qCharCard(c) {
  // thiếu ảnh: cảnh báo chỉ khi có mốc dùng (cùng quy tắc số "N thiếu" trên thanh trái); không mốc nào dùng → nhãn trung tính
  const busy = S.job?.state === "running", missing = !c.image_url, warn = missing && c.uses > 0;
  const file = h("input", { type: "file", accept: "image/png,image/jpeg,image/webp", hidden: true, "aria-label": `Ảnh @${c.id}` });
  file.onchange = () => { const f = file.files[0]; file.value = ""; if (f) qUpload(c.id, f); };
  return h("article", { class: "char-card" + (warn ? " missing" : "") },
    warn ? h("div", { class: "missing-box" }, h("strong", {}, "Chưa có character sheet"),
      h("span", {}, c.blocked ? `${c.blocked} mốc đang bị chặn gen` : "Chưa mốc nào bị chặn"))
      : missing ? h("div", { class: "missing-box neutral" }, h("strong", {}, "Chưa có ảnh"), h("span", {}, "Chưa mốc nào dùng nhân vật này"))
      : h("img", { class: "sheet", src: c.image_url, alt: `Character sheet @${c.id}` }),
    h("div", { class: "char-body" },
      h("div", { class: "char-h" }, h("span", { class: "swatch", style: `background:${qColor(c.color, "var(--muted)")}` }), h("span", { class: "mono cid" }, "@" + c.id),
        c.name ? h("span", { class: "muted" }, c.name) : null, h("span", { class: "grow" }), h("span", { class: "mono muted" }, `${c.uses} mốc`)),
      h("p", { class: "char-desc" }, c.desc || ""),
      h("div", { class: "row" }, file,
        missing ? h("button", { class: "primary small", disabled: busy, onclick: () => qJob("sheets") }, `Gen sheet (${provLabel(qProvider("sheets"))})`) : null,
        h("button", { class: "small", disabled: busy, onclick: () => file.click() }, missing ? "Tải ảnh lên" : "Thay ảnh"),
        c.scope === "video" ? h("button", { class: "small", disabled: busy, onclick: () => qPromote(c.id) }, "Đưa vào bộ kênh") : null)));
}
async function qUpload(id, f) {
  const name = Q.name, fd = new FormData(); fd.append("file", f);
  try { // multipart: không qua api() (api() đặt Content-Type JSON)
    const r = await fetch(`/api/quick/${name}/chars/${id}/image`, { method: "POST", body: fd });
    if (r.status === 401) { location.href = "/login"; return; }
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof body.detail === "string" && body.detail ? body.detail : `Lỗi ${r.status}`);
    qSay(name, `Đã gắn ảnh @${id}`);
  } catch (e) { qSay(name, e.message, true); }
  await qRefresh(name);
}
async function qPromote(id) {
  const name = Q.name;
  if (!confirm(`Đưa @${id} vào bộ kênh? Mọi video sau của kênh dùng được nhân vật này.`)) return;
  try { await qPost(`/chars/${id}/promote`, {}, name); qSay(name, `@${id} đã vào bộ kênh`); } catch (e) { qSay(name, e.message, true); }
  await qRefresh(name);
}
QSCREENS.chars = qChars;

// ================= Tạo video nhanh =================
Q.openNew = async function () {
  let presets;
  try { presets = await api("/api/presets"); } catch (e) { toast(e.message, true); return; }
  if (!presets.length) { toast("Chưa có bộ kênh — tạo bằng lệnh `vidflow preset import`.", true); return; }
  const f = { preset: presets[0].id, chars: [], image_model: IMAGE_MODELS[0], video_model: "", resolution: "720p", image_provider: "flow", video_provider: "flow", max_clips: 12, allow_cont: true };
  const presetSel = h("select", {}, presets.map(p => h("option", { value: p.id }, p.name)));
  const topic = h("input", { type: "text", placeholder: "vd: một ngày bình thường của tổ tiên 50.000 năm trước" });
  const charsBox = h("div", { class: "pick-list" }), aspect = h("span", { class: "mono" });
  const fillPreset = () => {
    const p = presets.find(x => x.id === presetSel.value);
    f.preset = p.id; f.chars = p.characters.map(c => c.id); aspect.textContent = p.aspect;
    charsBox.replaceChildren(...(p.characters.length ? p.characters.map(c => {
      const cb = h("input", { type: "checkbox" }); cb.checked = true;
      cb.onchange = () => { f.chars = cb.checked ? [...f.chars, c.id] : f.chars.filter(x => x !== c.id); };
      return h("label", { class: "pick-char" }, cb, h("span", { class: "swatch", style: `background:${qColor(c.color, "var(--muted)")}` }),
        h("span", {}, h("span", { class: "mono cid" }, "@" + c.id), " ", h("span", { class: "hint" }, c.name || c.desc)));
    }) : [h("span", { class: "hint" }, "Bộ kênh chưa có nhân vật.")]));
  };
  presetSel.onchange = fillPreset; fillPreset();
  const pick = (key, opts) => { const s = h("select", {}, opts.map(o => h("option", { value: o }, o || "— chọn —"))); s.value = f[key]; s.onchange = () => { f[key] = s.value; }; return s; };
  const psel = key => { const s = h("select", {}, PROVIDERS.map(([v, l]) => h("option", { value: v }, l))); s.value = f[key]; s.onchange = () => { f[key] = s.value; }; return s; };
  const maxOut = h("span", { class: "mono" }, String(f.max_clips));
  const range = h("input", { type: "range", min: 0, max: 40, value: f.max_clips, "aria-label": "Số clip động tối đa" });
  const vidLabel = h("label", { class: "f req" }, h("span", { class: "flabel" }, "Model clip động · bắt buộc"), pick("video_model", VIDEO_MODELS));
  range.oninput = () => { f.max_clips = Number(range.value); maxOut.textContent = range.value; vidLabel.classList.toggle("req", f.max_clips > 0); };
  const cont = h("input", { type: "checkbox" }); cont.checked = true; cont.onchange = () => { f.allow_cont = cont.checked; };
  const sec = (n, title, ...kids) => h("section", { class: "qsec" }, h("span", { class: "stepnum" }, String(n)), h("div", {}, h("h2", {}, title), kids));
  const dlg = h("dialog", { class: "qdlg", "aria-label": "Video nhanh mới" });
  dlg.addEventListener("close", () => dlg.remove());
  const okBtn = h("button", { type: "button", class: "primary" }, "Tạo và đề xuất ý tưởng");
  const submit = async () => {
    if (okBtn.disabled) return;
    if (f.max_clips > 0 && !f.video_model) { toast("Chọn model clip động (bắt buộc khi số clip tối đa > 0).", true); return; }
    const p = presets.find(x => x.id === f.preset);
    const body = { preset: f.preset, topic: topic.value.trim(), channel_chars: f.chars.length === p.characters.length ? null : f.chars,
      image_model: f.image_model, video_model: f.video_model, resolution: f.resolution, image_provider: f.image_provider, video_provider: f.video_provider,
      max_clips: f.max_clips, allow_cont: f.allow_cont, start: true };
    okBtn.disabled = true; // tên thư mục tự sinh theo giây: bấm hai lần sẽ trùng (409)
    try {
      const r = await api("/api/quick", { method: "POST", body: JSON.stringify(body) });
      dlg.close();
      await loadProjects(); await openProject(r.name);
      if (r.job) { S.job = r.job; startPolling(); toast(`Bắt đầu: ${r.job.label}`); } else if (r.warning) toast(r.warning, true);
    } catch (e) { okBtn.disabled = false; toast(e.message, true); }
  };
  okBtn.onclick = submit;
  dlg.append(
    h("div", { class: "qdlg-h" }, h("h1", {}, "Video nhanh mới"), h("p", { class: "hint" }, "AI đề xuất 5 ý tưởng, viết kịch bản, tách mốc và viết prompt. Bạn duyệt ở từng bước.")),
    h("div", { class: "qdlg-b" },
      sec(1, "Bộ kênh và chủ đề", h("label", { class: "f" }, h("span", { class: "flabel" }, "Bộ kênh"), presetSel),
        h("label", { class: "f" }, h("span", { class: "flabel" }, "Chủ đề gợi ý · không bắt buộc"), topic)),
      sec(2, "Nhân vật của kênh dùng trong video", charsBox, h("span", { class: "hint" }, "Nhân vật riêng của video do AI đề xuất sau bước kịch bản.")),
      sec(3, "Google Flow", h("div", { class: "grid2" },
        h("div", { class: "f" }, h("span", { class: "flabel" }, "Tỉ lệ (theo bộ kênh)"), aspect),
        h("label", { class: "f" }, h("span", { class: "flabel" }, "Model ảnh"), pick("image_model", IMAGE_MODELS)),
        vidLabel,
        h("label", { class: "f" }, h("span", { class: "flabel" }, "Độ phân giải clip"), pick("resolution", ["720p", "1080p"])),
        h("label", { class: "f" }, h("span", { class: "flabel" }, "Nguồn gen ảnh"), psel("image_provider")),
        h("label", { class: "f" }, h("span", { class: "flabel" }, "Nguồn gen clip"), psel("video_provider"))),
        h("span", { class: "hint" }, "Flow, Gemini (gemini.google.com) hoặc AI Studio (aistudio.google.com) qua Chrome đã đăng nhập. Hết lượt ở nguồn nào thì đổi nguồn trên Bảng mốc.")),
      sec(4, "Chuyển động",
        h("label", { class: "f" }, h("span", { class: "flabel row between" }, "Số clip động tối đa", maxOut), range,
          h("span", { class: "hint" }, "AI đề xuất tối đa ngần này mốc làm clip; bạn bật/tắt từng mốc trên Bảng mốc. 0 = chỉ ảnh tĩnh.")),
        h("label", { class: "checks" }, cont, h("span", {}, "Cho phép AI đánh dấu ", h("strong", {}, "nối cảnh"), " — mốc tiếp nối cùng khoảnh khắc được đính ảnh mốc trước làm tham chiếu.")))),
    h("div", { class: "qdlg-f" }, h("button", { type: "button", onclick: () => dlg.close() }, "Hủy"),
      okBtn));
  document.body.append(dlg);
  dlg.showModal();
};

// ================= Xem thử & Xuất =================
// clip được dùng khi xuất (giống clips.ready_clips): bật + đã có file
function qHasClip(b) { return !!(b.clip.enabled && b.clip.status === "ok" && b.clip_url); }
function qPreview() {
  const d = Q.data, beats = d.beats.filter(b => b.start != null && b.end != null);
  const center = h("section", { class: "content" }, h("h1", { class: "page-h" }, "Xem thử"));
  if (!beats.length || !d.voice_url) center.append(h("div", { class: "card" }, h("p", {}, "Chưa có giọng đọc và thời gian mốc — chạy bước Giọng đọc trên Bảng mốc trước.")));
  else center.append(qPlayer(beats), qTimeline(beats));
  return [center, qExport()];
}
function qPlayer(beats) {
  const d = Q.data, total = Math.max(0.1, beats[beats.length - 1].end);
  const audio = h("audio", { src: d.voice_url, preload: "auto" });
  const img = h("img", { alt: "" }), vid = h("video", { playsinline: true, preload: "auto" });
  vid.muted = true; // clip phát không tiếng: giọng đọc là <audio>
  const ph = h("div", { class: "stage-ph" }), sub = h("div", { class: "subtitle" });
  const ratio = /^\d+:\d+$/.test(d.aspect || "") ? d.aspect.replace(":", " / ") : "16 / 9";
  const stage = h("div", { class: "stage", style: `aspect-ratio:${ratio}` }, img, vid, ph, sub);
  const time = h("span", { class: "mono" }), cur = h("span", { class: "mono now-tag" });
  const subOn = h("input", { type: "checkbox" }); subOn.checked = true;
  const playBtn = h("button", { class: "play" }, "Phát");
  let idx = -1;
  const find = t => { let lo = 0, hi = beats.length - 1; while (lo < hi) { const m = (lo + hi + 1) >> 1; if (beats[m].start <= t) lo = m; else hi = m - 1; } return lo; };
  const show = (i, t) => {
    const b = beats[i];
    if (i !== idx) {
      idx = i;
      const clip = qHasClip(b);
      img.hidden = !(b.image_url && !clip); vid.hidden = !clip; ph.hidden = !!(b.image_url || clip);
      if (!img.hidden) img.src = b.image_url;
      if (clip) vid.src = b.clip_url; else vid.removeAttribute("src");
      ph.textContent = `Mốc ${pad3(b.n)} chưa có ảnh`;
      sub.textContent = b.text;
      cur.textContent = `${pad3(b.n)}${clip ? " · CLIP" : ""}`;
      P.mark(b.n);
    }
    if (!vid.hidden) {
      const want = Math.max(0, Math.min(t - b.start, (vid.duration || 99) - 0.05)); // clip ngắn hơn mốc → giữ khung cuối
      if (Math.abs(vid.currentTime - want) > 0.3) vid.currentTime = want;
      if (!audio.paused && vid.paused) vid.play().catch(() => {});
      if (audio.paused && !vid.paused) vid.pause();
    }
    sub.hidden = !subOn.checked;
    time.textContent = `${fmtT1(t)} / ${fmtT1(total)}`;
  };
  const tick = () => {
    if (Q.player !== P) return; // trình phát cũ (đã vẽ lại / rời màn): không ghi đè trình phát mới
    show(find(audio.currentTime), audio.currentTime);
    P.head(audio.currentTime / total);
    if (!audio.paused) P.raf = requestAnimationFrame(tick);
  };
  const P = { seek: t => { audio.currentTime = t; tick(); }, head: () => {}, mark: () => {}, raf: 0 };
  Q.player = P;
  audio.onplay = () => { playBtn.textContent = "Dừng"; cancelAnimationFrame(P.raf); tick(); };
  audio.onpause = () => { playBtn.textContent = "Phát"; vid.pause(); cancelAnimationFrame(P.raf); tick(); };
  audio.onseeked = tick;
  audio.onerror = () => { if (Q.player === P) qSay(Q.name, "Không tải được giọng đọc", true); };
  subOn.onchange = tick;
  playBtn.onclick = () => (audio.paused ? audio.play().catch(() => {}) : audio.pause());
  const step = dir => { const i = Math.max(0, Math.min(beats.length - 1, find(audio.currentTime) + dir)); P.seek(beats[i].start + 0.01); };
  setTimeout(tick, 0);
  return h("div", { class: "player" }, stage, audio,
    h("div", { class: "controls" }, h("button", { onclick: () => step(-1) }, "Mốc trước"), playBtn, h("button", { onclick: () => step(1) }, "Mốc sau"),
      time, cur, h("span", { class: "grow" }), h("label", { class: "row" }, subOn, "Phụ đề")));
}
function qTimeline(beats) {
  const total = beats[beats.length - 1].end, scenes = qSceneList(beats), colorOf = new Map();
  scenes.forEach(sc => sc.beats.forEach(b => colorOf.set(b.n, sc.color)));
  const segs = beats.map(b => {
    const color = colorOf.get(b.n), kind = b.state === "ok" ? "ok" : b.state === "gen" ? "gen" : b.state === "error" ? "error" : "none";
    const clip = qHasClip(b), label = QST[b.state][0];
    const style = `flex:${Math.max(0.05, b.end - b.start)};` + (kind === "ok" ? `background:${color}` : kind === "gen" ? `background:${color};opacity:.45` : "");
    return h("button", { class: `seg ${kind}${clip ? " clip" : ""}`, style, title: `Mốc ${pad3(b.n)} · ${fmtT(b.start)} · ${label}${clip ? " · clip" : ""}`,
      "aria-label": `Mốc ${b.n}: ${label}${clip ? ", có clip" : ""}`, onclick: () => Q.player && Q.player.seek(b.start + 0.01) });
  });
  const head = h("span", { class: "playhead" });
  if (Q.player) {
    Q.player.head = frac => { head.style.left = `${Math.min(100, Math.max(0, frac * 100))}%`; };
    Q.player.mark = n => segs.forEach((s, i) => s.classList.toggle("cur", beats[i].n === n));
  }
  const wave = h("div", { class: "wave", role: "img", "aria-label": "Sóng âm giọng đọc" });
  qLoadWave(wave);
  const key = (style, label) => h("span", {}, h("i", { style }), label);
  return h("section", { class: "timeline", "aria-label": "Dòng thời gian" },
    h("div", { class: "row between" }, h("h2", {}, "Dòng thời gian"), h("span", { class: "hint" }, `bấm mốc để nhảy tới · ${fmtT(total)}`)),
    h("div", { class: "scene-labels" }, scenes.map(sc => h("span", { style: `flex:${Math.max(0.05, sc.beats[sc.beats.length - 1].end - sc.beats[0].start)}`, title: `Cảnh ${sc.index}` }, `Cảnh ${sc.index}`))),
    h("div", { class: "segs-wrap" }, h("div", { class: "segs" }, segs, head)),
    wave,
    h("div", { class: "legend" }, key("background:#3557D6", "có ảnh (màu theo cảnh)"), key("background:var(--track);border-bottom:4px solid var(--primary)", "clip động"),
      key("background:#F4C7CF;border:1px solid var(--error)", "lỗi"), key("background:#3557D6;opacity:.45", "đang gen"), key("background:var(--track)", "chưa có ảnh")));
}
async function qLoadWave(el) {
  const name = Q.name;
  try {
    if (!Q.wave) {
      const peaks = (await api(`/api/quick/${name}/waveform?bins=300`)).peaks;
      if (Q.name !== name) return; // đã mở video khác
      Q.wave = peaks;
    }
    el.replaceChildren(...Q.wave.map(p => h("span", { style: `height:${Math.max(2, p * 28).toFixed(1)}px` })));
  } catch { el.replaceChildren(h("span", { class: "hint" }, "Không đọc được sóng âm")); }
}
function qExport() {
  const d = Q.data, o = Q.exportOpts, busy = S.job?.state === "running";
  const sel = (key, label, opts) => { const s = h("select", { "aria-label": label }, opts.map(([v, l]) => h("option", { value: v }, l))); s.value = o[key]; s.onchange = () => { o[key] = s.value; }; return h("label", { class: "f" }, h("span", { class: "flabel" }, label), s); };
  const tog = (key, label) => { const c = h("input", { type: "checkbox" }); c.checked = o[key]; c.onchange = () => { o[key] = c.checked; }; return h("label", { class: "switch" }, h("span", {}, label), c); };
  const noimg = d.beats.filter(b => b.state !== "ok").length;
  const job = d.job && ["render", "build"].includes(d.job.kind) ? d.job : null;
  return h("aside", { class: "panel", "aria-label": "Xuất video" }, h("div", { class: "detail" },
    h("div", { class: "detail-h" }, h("h2", {}, "Xuất MP4"), h("span", { class: "grow" }), h("span", { class: "badge" }, "Remotion · mặc định")),
    h("div", { class: "grid2" },
      sel("resolution", "Độ phân giải", [["1080p", "1080p"], ["720p", "720p"]]),
      sel("transition", "Chuyển cảnh", [["scene", "Theo cảnh"], ["cut", "Cắt thẳng"], ["fade", "Mờ chéo"]])),
    sel("clip_fit", "Clip dài hơn mốc", [["trim", "Cắt bớt cho vừa mốc"], ["speed", "Tăng tốc cho vừa mốc"]]),
    h("div", { class: "toggles" }, tog("zoom", "Zoom chậm trên ảnh tĩnh"), tog("subtitles", "Phụ đề theo giọng"), tog("logo", "Logo kênh"),
      tog("clip_audio", "Âm thanh trong clip Veo"), tog("music", "Nhạc nền")),
    noimg ? h("p", { class: "notice warn" }, `Còn ${noimg} mốc chưa có ảnh sẽ hiện khung trống. Nên gen xong trước khi xuất bản cuối.`) : null,
    h("button", { class: "primary", disabled: busy || !d.beats.length, onclick: () => qJob("render", { options: { ...o } }) }, "Xuất MP4"),
    h("div", { class: "subcard" }, h("b", {}, "Draft CapCut"), h("span", { class: "hint" }, "Tùy chọn, khi cần chỉnh tay. Phải đóng CapCut trước khi dựng."),
      h("button", { disabled: busy || !d.beats.length, onclick: () => qJob("build", { options: { zoom: o.zoom, subtitles: o.subtitles } }) }, "Dựng draft CapCut")),
    h("div", { class: "subcard" }, h("b", {}, "Bản đã xuất"),
      d.renders.length ? d.renders.map(r => { const f = r.file.replace(/^out\//, ""); return h("div", { class: "row between" }, h("span", { class: "mono" }, `${f} · ${r.size_mb} MB`), h("a", { href: r.url, download: f }, "Tải")); })
        : h("span", { class: "hint" }, "Chưa có bản nào.")),
    job ? h("div", { class: "subcard" }, h("b", {}, `${job.label}: ${QJOB[job.state] || job.state}`), h("pre", { class: "log", id: "log" }, job.log || "(đang chạy…)")) : null));
}
QSCREENS.preview = qPreview;
