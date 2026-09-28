import pytest

from vidflow.config import Config, load_config
from vidflow.errors import ConfigError


def test_missing_file_gives_defaults(tmp_path):
    assert load_config(tmp_path / "none.toml") == Config()


def test_loads_values(tmp_path):
    f = tmp_path / "vidflow.toml"
    f.write_text('veo_price_per_second = 0.4\nimage_model = "m"\ndraft_folder = "~/drafts"\n'
                 'media_folder = "~/Movies/x"\n', encoding="utf-8")
    c = load_config(f)
    assert c.veo_price_per_second == 0.4
    assert c.image_model == "m"
    assert str(c.draft_folder).endswith("/drafts") and "~" not in str(c.draft_folder)
    assert str(c.media_folder).endswith("/Movies/x") and "~" not in str(c.media_folder)


def test_empty_strings_mean_unset(tmp_path):
    f = tmp_path / "vidflow.toml"
    f.write_text('image_model = ""\nveo_price_per_second = 0.0\n', encoding="utf-8")
    c = load_config(f)
    assert c.image_model is None
    assert c.veo_price_per_second is None


def test_unknown_key(tmp_path):
    f = tmp_path / "vidflow.toml"
    f.write_text("foo = 1\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="foo"):
        load_config(f)


def test_bad_resolution(tmp_path):
    f = tmp_path / "vidflow.toml"
    f.write_text('veo_resolution = "480p"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="veo_resolution"):
        load_config(f)
