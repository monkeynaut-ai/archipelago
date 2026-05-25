"""Tests for the shared workspace-provisioning helpers."""

from __future__ import annotations

import re

from archipelago.systems._workspace import BASE_IMAGE_TAG, generate_volume_name


class TestGenerateVolumeName:
    def test_given_slug_when_generate_then_name_matches_expected_pattern(self):
        name = generate_volume_name("run-observability")
        assert re.match(r"^archipelago-ws-run-observability-\d{19}$", name), name

    def test_given_slug_with_unsafe_chars_when_generate_then_sanitized(self):
        name = generate_volume_name("my weird/slug!")
        assert re.match(r"^archipelago-ws-[a-zA-Z0-9._-]+-\d{19}$", name), name

    def test_given_two_calls_when_generate_then_names_differ(self):
        # time_ns() suffix makes same-second collisions astronomically rare.
        a = generate_volume_name("demo")
        b = generate_volume_name("demo")
        assert a != b


class TestBaseImageTag:
    def test_given_constant_when_read_then_is_nonempty_string(self):
        assert isinstance(BASE_IMAGE_TAG, str) and BASE_IMAGE_TAG
