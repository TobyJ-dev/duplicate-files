"""
Tests for find_duplicates().
"""

from pathlib import Path
import pytest
from dupfinder import find_duplicates


def test_duplicate_files_are_grouped_together(tmp_path):
    """Two files with identical content must appear in the same group."""
    dup_a = tmp_path / "dup_a.jpg"
    dup_b = tmp_path / "dup_b.jpg"
    dup_a.write_bytes(b"duplicate content")
    dup_b.write_bytes(b"duplicate content")

    duplicates = find_duplicates([dup_a, dup_b])

    assert len(duplicates) == 1
    group = list(duplicates.values())[0]
    assert set(group) == {dup_a, dup_b}


def test_unique_files_are_not_in_results(tmp_path):
    """A file with no duplicate must not appear in the results at all."""
    dup_a = tmp_path / "dup_a.jpg"
    dup_b = tmp_path / "dup_b.jpg"
    unique = tmp_path / "unique.jpg"
    dup_a.write_bytes(b"duplicate content")
    dup_b.write_bytes(b"duplicate content")
    unique.write_bytes(b"completely different content")

    duplicates = find_duplicates([dup_a, dup_b, unique])

    all_found_paths = [p for paths in duplicates.values() for p in paths]
    assert unique not in all_found_paths
    

def test_all_unique_files_returns_empty_dict(tmp_path):
    """find_duplicates() must return an empty dict when no files share content."""
    file_a = tmp_path / "file_a.jpg"
    file_b = tmp_path / "file_b.jpg"
    file_c = tmp_path / "file_c.jpg"
    file_a.write_bytes(b"content one")
    file_b.write_bytes(b"content two")
    file_c.write_bytes(b"content three")

    duplicates = find_duplicates([file_a, file_b, file_c])

    assert duplicates == {}