"""windows_safe(): POSIX/short-path identity, Windows extended-length prefixing."""

import os

from ml.data import winpath


def test_identity_on_posix():
    assert winpath.windows_safe("/data/raw/plantdoc/train/Apple leaf/x.jpg") == "/data/raw/plantdoc/train/Apple leaf/x.jpg"


def test_identity_on_short_windows_paths(monkeypatch):
    monkeypatch.setattr(os, "name", "nt")
    path = r"C:\Users\vishw\data\raw\plantdoc\Apple leaf\x.jpg"
    assert winpath.windows_safe(path) == path


def test_long_windows_paths_get_extended_prefix(monkeypatch):
    monkeypatch.setattr(os, "name", "nt")
    long_name = "apple-tree-" + "branch-" * 30 + "928225.jpg"
    long_path = "C:\\Users\\vishw\\data\\raw\\plantdoc\\extracted\\master\\train\\Apple leaf\\" + long_name
    assert len(long_path) > winpath.MAX_SAFE_LENGTH
    safe = winpath.windows_safe(long_path)
    assert safe.startswith(winpath._EXTENDED_PREFIX)
    assert safe.endswith("928225.jpg")
    assert len(safe) > len(long_path)


def test_boundary_exactly_at_margin_is_identity(monkeypatch):
    monkeypatch.setattr(os, "name", "nt")
    path = "C:\\" + "a" * (winpath.MAX_SAFE_LENGTH - 3)  # len == MAX_SAFE_LENGTH
    assert winpath.windows_safe(path) == path
    assert winpath.windows_safe(path + "b").startswith(winpath._EXTENDED_PREFIX)
