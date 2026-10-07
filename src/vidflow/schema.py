from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from vidflow.errors import ScriptError

Aspect = Literal["9:16", "16:9"]


StyleType = Literal["live_action", "anim_3d", "anim_2d", "ugc"]


class Profile(BaseModel):
    idea: str = ""
    audience: str = ""
    platform: str = "tiktok"
    style_type: StyleType = "anim_3d"
    palette: str = ""
    mood: str = ""
    film_look: str = ""
    reference: str = ""


class Character(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    description: str = ""  # tiếng Anh, ghép nguyên văn vào mọi prompt
    ref_image: str | None = None
    name: str = ""
    age: str = ""
    build: str = ""
    face: str = ""
    hair: str = ""
    accessories: str = ""
    wardrobe: str = ""
    expressions: str = ""
    voice_note: str = ""
    locked: bool = False


class Location(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    name: str = ""
    place: str = ""
    time_of_day: str = ""
    details: str = ""
    light_sources: str = ""
    ambience: str = ""


class Prop(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    name: str = ""
    description: str = ""  # tiếng Anh, cố định giữa các cảnh


class Voice(BaseModel):
    name: str = "Kore"
    style: str = ""
    speed: float = Field(1.0, gt=0.5, le=2.0)


class Music(BaseModel):
    file: str
    volume: float = Field(0.15, ge=0, le=1)


class Subtitles(BaseModel):
    enabled: bool = True
    max_chars_per_line: int = Field(32, ge=8)


class FlowSettings(BaseModel):
    """Cài đặt khi gen trong Google Flow; người dùng chọn ở cổng duyệt đầu tiên."""
    video_model: str = ""  # tên model trong Flow, vd "Veo 3.1 Fast"; rỗng = chưa chọn
    resolution: Literal["720p", "1080p"] = "720p"


class Review(BaseModel):
    """Kết quả agent kiểm duyệt prompt (hoặc người dùng bỏ qua kiểm duyệt)."""
    verdict: Literal["pass", "fail", "override"]
    score: float = Field(0, ge=0, le=10)
    issues: list[str] = []
    suggestion: str = ""
    prompt_hash: str = ""


Motion = Literal["zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "pan_down", "static"]
MAX_FRAMES = 60


class Frame(BaseModel):
    """Một ảnh trong cảnh dựng từ ảnh."""
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    description: str = ""  # tiếng Việt: trong khung có gì
    prompt: str = ""  # prompt riêng của khung (AI viết)
    seconds: float = Field(2.0, ge=0.5, le=10)
    motion: Motion = "zoom_in"
    caption: str = ""  # bong bóng thoại (comic)
    status: Literal["draft", "approved"] = "draft"
    locked: bool = False
    review: Review | None = None
    prompt_fields_hash: str = ""


class Scene(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    narration: str = ""
    veo_prompt: str = ""
    veo_prompt_vi: str = ""  # bản dịch tiếng Việt để người dùng duyệt; không gửi cho Veo
    characters: list[str] = []
    duration: Literal[4, 6, 8] = 8
    veo_audio: bool = False
    status: Literal["draft", "approved"] = "draft"
    # các ô chi tiết (người dùng điền tiếng Việt; job prompt viết veo_prompt tiếng Anh từ đây)
    purpose: str = ""
    dialogue: str = ""
    location: str = ""
    props: list[str] = []
    prop_state: str = ""
    action: str = ""
    beats: str = ""
    expression: str = ""
    shot_size: str = ""
    angle: str = ""
    camera_move: str = ""
    lens: str = ""
    dof: str = ""
    composition: str = ""
    light: str = ""
    light_quality: str = ""
    color_temp: str = ""
    atmosphere: str = ""
    sfx: str = ""
    ambient: str = ""
    avoid: list[str] = []
    anti_ai: list[str] = []
    locked: bool = False
    notes: str = ""
    prompt_fields_hash: str = ""  # hash các ô lúc veo_prompt được viết
    # cảnh dựng từ ảnh
    mode: Literal["veo", "slideshow", "stopmotion", "comic"] = "veo"
    frames: list[Frame] = []
    fps: int = Field(8, ge=6, le=12)
    transition: Literal["cut", "fade", "slide"] = "fade"
    assemble: Literal["ffmpeg", "capcut"] = "ffmpeg"  # cảnh ảnh: render mp4 bằng ffmpeg, hay ghép từng ảnh trong draft CapCut
    review: Review | None = None  # kiểm duyệt veo_prompt

    @model_validator(mode="after")
    def _check_frames(self) -> "Scene":
        ids = [f.id for f in self.frames]
        dup = sorted({i for i in ids if ids.count(i) > 1})
        if dup:
            raise ValueError(f"scene {self.id}: id khung trùng {dup}")
        if len(self.frames) > MAX_FRAMES:
            raise ValueError(f"scene {self.id}: tối đa {MAX_FRAMES} khung")
        if self.mode != "veo" and self.status == "approved" and not self.frames:
            raise ValueError(f"scene {self.id}: cảnh {self.mode} cần ít nhất 1 khung")
        return self

    def frame(self, frame_id: str) -> Frame:
        for f in self.frames:
            if f.id == frame_id:
                return f
        raise ScriptError(f"Cảnh {self.id} không có khung '{frame_id}'")


class Script(BaseModel):
    title: str
    aspect: Aspect = "9:16"
    style: str = ""
    profile: Profile = Profile()
    characters: list[Character] = []
    locations: list[Location] = []
    props: list[Prop] = []
    voice: Voice = Voice()
    music: Music | None = None
    subtitles: Subtitles = Subtitles()
    budget_usd: float = Field(20, gt=0)
    flow: FlowSettings = FlowSettings()
    prompt_language: Literal["vi", "en"] = "vi"
    scenes: list[Scene] = []

    @model_validator(mode="after")
    def _check_refs(self) -> "Script":
        ids = [s.id for s in self.scenes]
        dup = sorted({i for i in ids if ids.count(i) > 1})
        if dup:
            raise ValueError(f"scene id trùng: {dup}")
        char_ids = {c.id for c in self.characters}
        loc_ids = {l.id for l in self.locations}
        prop_ids = {p.id for p in self.props}
        for s in self.scenes:
            unknown = sorted(set(s.characters) - char_ids)
            if unknown:
                raise ValueError(f"scene {s.id}: nhân vật không tồn tại {unknown}")
            if s.location and s.location not in loc_ids:
                raise ValueError(f"scene {s.id}: bối cảnh không tồn tại '{s.location}'")
            unknown = sorted(set(s.props) - prop_ids)
            if unknown:
                raise ValueError(f"scene {s.id}: đạo cụ không tồn tại {unknown}")
        return self

    def scene(self, scene_id: str) -> Scene:
        for s in self.scenes:
            if s.id == scene_id:
                return s
        raise ScriptError(f"Không có cảnh '{scene_id}' trong script.yaml")

    def character(self, char_id: str) -> Character:
        for c in self.characters:
            if c.id == char_id:
                return c
        raise ScriptError(f"Không có nhân vật '{char_id}' trong script.yaml")

    def prop(self, prop_id: str) -> Prop:
        for p in self.props:
            if p.id == prop_id:
                return p
        raise ScriptError(f"Không có đạo cụ '{prop_id}' trong script.yaml")
