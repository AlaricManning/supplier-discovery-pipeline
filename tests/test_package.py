"""Smoke tests: the package and all pipeline stage subpackages import cleanly."""

import importlib

import pytest

import supplier_discovery


def test_version() -> None:
    assert supplier_discovery.__version__


@pytest.mark.parametrize(
    "stage",
    ["ingestion", "extraction", "normalization", "indexing", "matching"],
)
def test_stage_subpackages_import(stage: str) -> None:
    importlib.import_module(f"supplier_discovery.{stage}")
