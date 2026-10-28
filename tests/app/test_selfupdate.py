"""In-app updates: picking this system's file from a release, checking it against the
release's checksums, and handing over to the new version (macOS swap script, Linux AppImage
replacement). The download itself needs a published release, so it isn't run here."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from asterism.app import selfupdate as SU

RELEASE = {"tag_name": "v0.2.0", "assets": [
    {"name": "ASTERISM-0.2.0-mac.dmg", "browser_download_url": SU.DOWNLOAD_PREFIX + "v0.2.0/ASTERISM-0.2.0-mac.dmg"},
    {"name": "ASTERISM-0.2.0-mac.zip", "browser_download_url": SU.DOWNLOAD_PREFIX + "v0.2.0/ASTERISM-0.2.0-mac.zip"},
    {"name": "ASTERISM-0.2.0-windows-setup.exe", "browser_download_url": SU.DOWNLOAD_PREFIX + "v0.2.0/x.exe"},
    {"name": "ASTERISM-0.2.0-linux-x86_64.AppImage", "browser_download_url": SU.DOWNLOAD_PREFIX + "v0.2.0/x"},
    {"name": "SHA256SUMS.txt", "browser_download_url": SU.DOWNLOAD_PREFIX + "v0.2.0/SHA256SUMS.txt"}]}


@pytest.mark.parametrize("plat, name", [("darwin", "ASTERISM-0.2.0-mac.zip"),
                                        ("win32", "ASTERISM-0.2.0-windows-setup.exe"),
                                        ("linux", "ASTERISM-0.2.0-linux-x86_64.AppImage")])
def test_pick_asset(monkeypatch, plat, name):
    monkeypatch.setattr(sys, "platform", plat)
    mine, sums = SU.pick_asset(RELEASE)
    assert mine["name"] == name and sums["name"] == "SHA256SUMS.txt"


def test_checksums(tmp_path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"asterism")
    h = SU.sha256(str(f))
    sums = SU.parse_sums(f"{h}  a.bin\n{'0' * 64} *b.exe\nnot a line\n")
    assert sums == {"a.bin": h, "b.exe": "0" * 64}


def test_only_github_release_files_are_downloaded(app):
    from PySide6.QtNetwork import QNetworkAccessManager
    assert SU._download(QNetworkAccessManager(), "https://example.com/evil.zip", None) is None


def test_from_source_nothing_to_replace():
    assert not getattr(sys, "frozen", False)
    assert SU.install_target() is None and not SU.can_install()


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS swap")
def test_mac_swap_script_replaces_the_app(tmp_path):
    old = tmp_path / "Applications" / "ASTERISM.app"
    (old / "Contents").mkdir(parents=True)
    (old / "Contents" / "version.txt").write_text("old")
    new_src = tmp_path / "build" / "ASTERISM.app" / "Contents"
    new_src.mkdir(parents=True)
    (new_src / "version.txt").write_text("new")
    z = tmp_path / "ASTERISM-0.2.0-mac.zip"
    subprocess.run(["ditto", "-c", "-k", "--keepParent", str(tmp_path / "build" / "ASTERISM.app"), str(z)], check=True)
    unpacked = tmp_path / "dl" / "new"
    subprocess.run(["ditto", "-x", "-k", str(z), str(unpacked)], check=True)
    dead = subprocess.Popen(["true"])
    dead.wait()
    opened = tmp_path / "opened.txt"
    script = SU.mac_script(dead.pid, str(unpacked / "ASTERISM.app"), str(old),
                           open_cmd=f"echo >> {opened} ")
    subprocess.run(["/bin/bash", "-c", script], check=True, timeout=20)
    assert (old / "Contents" / "version.txt").read_text() == "new"
    assert opened.exists()


def test_linux_appimage_is_replaced(tmp_path, monkeypatch):
    target = tmp_path / "ASTERISM.AppImage"
    target.write_bytes(b"old")
    new = tmp_path / "dl" / "ASTERISM-0.2.0-linux-x86_64.AppImage"
    new.parent.mkdir()
    new.write_bytes(b"new")
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("APPIMAGE", str(target))
    cmd = SU.prepare(str(new))
    assert cmd == [str(target)] and target.read_bytes() == b"new"
    assert os.access(target, os.X_OK)
