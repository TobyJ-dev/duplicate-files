"""
Tests for hash_file().
"""

from pathlib import Path
import pytest
from dupfinder import hash_file


def test_same_content_produces_same_hash(tmp_path):
    """Two files with identical content must produce the same hash."""
    file_a = tmp_path / "file_a.jpg"
    file_b = tmp_path / "file_b.jpg"
    content = b"some image content"
    file_a.write_bytes(content)
    file_b.write_bytes(content)

    assert hash_file(file_a) == hash_file(file_b)


def test_different_content_produces_different_hash(tmp_path):
    """Two files with different content must produce different hashes."""
    # tmp_path is a Path object pointing to a temporary folder that pytest 
    # creates for you automatically before the test runs and deletes automatically after it finishes.
    # It is a real folder on disk, already created, ready to use.

    # This creates a Path object pointing to a file inside that temp folder.
    # The file does not exist yet, this is just a path.
    file_a = tmp_path / "file_a.jpg"
    file_b = tmp_path / "file_b.jpg"
    
    # write_bytes() creates the file and writes raw bytes into it.
    # b"some image content" is a bytes literal, same as you would write
    # when opening a file in binary mode with open(path, 'rb').
    file_a.write_bytes(b"content version one")
    file_b.write_bytes(b"content version two")

    assert hash_file(file_a) != hash_file(file_b)
    

def test_returns_none_for_nonexistent_file(tmp_path):
    """hash_file() must return None for a file that does not exist, not raise an exception."""
    missing = tmp_path / "does_not_exist.jpg"

    result = hash_file(missing)

    assert result is None


def test_empty_file_produces_known_hash(tmp_path):
    """hash_file() on an empty file must return the known MD5 of empty content."""
    empty_file = tmp_path / "empty.jpg"
    empty_file.write_bytes(b"")

    result = hash_file(empty_file)

    assert result == "d41d8cd98f00b204e9800998ecf8427e"