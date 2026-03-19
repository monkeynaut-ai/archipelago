"""Canonical artifact models for the Archipelago pipeline."""

from pydantic import BaseModel


class CodePatch(BaseModel):
    feature_name: str
    files_changed: list[str]
    diff_summary: str
    branch_name: str


class TestResults(BaseModel):
    __test__ = False

    feature_name: str
    tests_passed: int
    tests_failed: int
    test_output: str
    all_green: bool
