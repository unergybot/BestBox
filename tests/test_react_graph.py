"""Tests for ReAct graph integration."""

from agents.graph import react_app


def test_react_app_compiles():
    assert react_app is not None
