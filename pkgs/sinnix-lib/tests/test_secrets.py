"""The shared secret-name rule and offset-preserving value masks."""

from __future__ import annotations

from sinnix_lib.secrets import (
    env_name_is_secret,
    mask_secret_values,
    masked_window,
    secret_values,
)

SECRET = b"sk-fixture-0123456789abcdef"


def test_secret_names_are_word_tokens() -> None:
    assert env_name_is_secret("OPENAI_API_KEY")
    assert env_name_is_secret("GH_TOKEN")
    assert not env_name_is_secret("KEYBOARD")
    assert not env_name_is_secret("GIT_CONFIG_KEY_0")
    assert not env_name_is_secret("PATH")


def test_only_long_secret_named_values_are_masked() -> None:
    values = secret_values(
        {
            "GH_TOKEN": SECRET.decode(),
            "PASS": "1",
            "PATH": "/bin:/x",
            "SSH_AUTH_SOCK": "/run/user/1000/ssh-agent",
        }
    )
    assert values == (SECRET,)


def test_a_mask_keeps_the_length_and_hides_the_value() -> None:
    masked = mask_secret_values(b"a " + SECRET + b" b", (SECRET,))
    assert SECRET not in masked and len(masked) == len(SECRET) + 4
    assert masked.startswith(b"a [REDACTED")


def test_a_window_masks_a_value_split_across_pages() -> None:
    """Fails if paging at an offset inside a secret returns part of it."""
    data = b"head " + SECRET + b" tail"

    def read(start: int, length: int) -> bytes:
        return data[start : start + length]

    cut = 5 + 7
    first = masked_window(read, 0, cut, (SECRET,))
    second = masked_window(read, cut, 100, (SECRET,))
    assert first + second == mask_secret_values(data, (SECRET,))
    assert SECRET[:7] not in first and SECRET[7:] not in second
