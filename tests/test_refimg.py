import dataclasses

import pytest

from vidflow.errors import ConfigError
from vidflow.refimg import run_refimg

PNG = b"\x89PNG\r\n\x1a\nfake"
JPG = b"\xff\xd8\xfffake"


class FakeImage:
    def __init__(self, data=PNG):
        self.data = data
        self.prompts = []

    def generate(self, *, prompt, model):
        self.prompts.append((prompt, model))
        return self.data


def test_creates_png(project, cfg):
    fake = FakeImage()
    assert run_refimg(project, cfg, fake, sleep=lambda s: None) == ["refs/an.png"]
    prompt, model = fake.prompts[0]
    assert "cô gái 25 tuổi" in prompt and "cinematic, warm tone" in prompt
    assert model == "test-image-model"
    assert (project.refs_dir / "an.png").read_bytes() == PNG


def test_jpeg_gets_jpg_extension(project, cfg):
    assert run_refimg(project, cfg, FakeImage(JPG), sleep=lambda s: None) == ["refs/an.jpg"]


def test_skips_existing_unless_force(project, cfg):
    (project.refs_dir / "an.png").write_bytes(b"mine")
    assert run_refimg(project, cfg, FakeImage(), sleep=lambda s: None) == []
    assert (project.refs_dir / "an.png").read_bytes() == b"mine"
    assert run_refimg(project, cfg, FakeImage(), force=True, sleep=lambda s: None) == ["refs/an.png"]


def test_force_replaces_other_extension(project, cfg):
    (project.refs_dir / "an.jpg").write_bytes(JPG)
    run_refimg(project, cfg, FakeImage(PNG), force=True, sleep=lambda s: None)
    assert not (project.refs_dir / "an.jpg").exists()
    assert (project.refs_dir / "an.png").exists()


def test_requires_image_model(project, cfg):
    with pytest.raises(ConfigError, match="image_model"):
        run_refimg(project, dataclasses.replace(cfg, image_model=None), FakeImage())
