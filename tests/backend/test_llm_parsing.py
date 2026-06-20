"""Tests for tolerant LLM JSON extraction."""

import json

import pytest

from backend.llm.parsing import extract_json


def test_plain_json():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_json_with_surrounding_whitespace():
    assert extract_json('\n  {"a": 1}\n ') == {"a": 1}


def test_fenced_json_with_language_tag():
    raw = '```json\n{"cv": {"name": "Jane"}}\n```'
    assert extract_json(raw) == {"cv": {"name": "Jane"}}


def test_fenced_json_without_language_tag():
    raw = '```\n{"a": 1}\n```'
    assert extract_json(raw) == {"a": 1}


def test_leading_prose_before_object():
    raw = 'Here is the JSON you requested:\n{"a": 1, "b": 2}'
    assert extract_json(raw) == {"a": 1, "b": 2}


def test_trailing_prose_after_object():
    raw = '{"a": 1}\n\nLet me know if you want changes.'
    assert extract_json(raw) == {"a": 1}


def test_nested_object_recovered_from_prose():
    raw = 'Sure!\n{"cv": {"sections": {"x": ["y"]}}}\nDone.'
    assert extract_json(raw) == {"cv": {"sections": {"x": ["y"]}}}


def test_empty_string_raises():
    with pytest.raises(json.JSONDecodeError):
        extract_json("")


def test_no_json_raises():
    with pytest.raises(json.JSONDecodeError):
        extract_json("I could not complete this request.")
