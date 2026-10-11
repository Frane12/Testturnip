#!/usr/bin/env python3
"""Publish packaging ONLY: preserve the audited S Ultimate RC1 driver binary.
Input: GitHub Actions artifact from successful run 38127891483.
Fails closed on any binary, RC archive, source or metadata mismatch.
"""
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys
import zipfile

EXPECTED_RC_ZIP = "8b5ba062aee721ecec29c9aa80a062bdbb1feecd23f916e3e6a0fb84799adc9c"
EXPECTED_RC_SOURCE = "ce6ab127c43d1c370a3b30fd173577711e6bf000d76a1953a9b32133b4d1a52c"
EXPECTED_LIB = "55d05eb150d40121770c74fe9c90c3f79b92ea4de28611f2cfce53602e019f80"
RC_NAME = "Drnas-Turnip-A810-S-Ultimate-v1.0-RC1.zip"
SRC_NAME = "A810-S-Ultimate-v1.0-RC1-Source.zip"
RELEASE_NAME = "Drnas-Turnip-A810-S-Ultimate-v1.0.zip"
RELEASE_SOURCE = "Drnas-Turnip-A810-S-Ultimate-v1.0-Source.zip"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check(cond, msg):
    if not cond:
        raise SystemExit("Release packaging FAIL: " + msg)


def main():
    check(len(sys.argv) == 3, "usage: pack.py <RC artifact folder> <out>")
    incoming, dest = map(Path, sys.argv[1:])
    dest.mkdir(parents=True, exist_ok=True)
    rc = incoming / RC_NAME
    src = incoming / SRC_NAME
    check(rc.is_file() and src.is_file(), "audited input ZIP or source absent")
    check(sha(rc.read_bytes()) == EXPECTED_RC_ZIP, "RC ZIP sha256 differs")
    check(sha(src.read_bytes()) == EXPECTED_RC_SOURCE, "source archive sha256 differs")
    with zipfile.ZipFile(rc) as z:
        check(z.testzip() is None, "RC zip corrupted")
        check(sorted(z.namelist()) == ["libvulkan_freedreno.so", "meta.json"], "unexpected RC ZIP layout")
        binary = z.read("libvulkan_freedreno.so")
        meta = json.loads(z.read("meta.json"))
    check(sha(binary) == EXPECTED_LIB, "audited Vulkan driver bytes changed")
    check(binary[:4] == b"\x7fELF" and binary[4] == 2 and binary[5] == 1,
          "not ELF64 little-endian")
    check(struct.unpack_from("<H", binary, 18)[0] == 183, "not AArch64 ELF")
    check(meta["packageVersion"] == "1.0-rc1", "unexpected metadata version")
    check(meta["name"] == "Drnas-Turnip A810 S Ultimate v1.0 (RC1 Test)",
          "unexpected source driver label")
    check(meta["libraryName"] == "libvulkan_freedreno.so" and meta["minApi"] == 34,
          "unexpected RC package compatibility")
    with zipfile.ZipFile(src) as z:
        check(z.testzip() is None, "source ZIP corrupt")
        check("A810-S-Ultimate-v1-RC1-complete.patch" in z.namelist(),
              "audited source patch missing")
    meta["name"] = "Drnas-Turnip A810 S Ultimate v1.0"
    meta["description"] = (
        "Adreno 810 / Android KGSL; ATUltimate Dynamic V3 measured context learner, "
        "stability fixes and optional diagnostics"
    )
    meta["packageVersion"] = "1.0"

    driver = dest / RELEASE_NAME
    with zipfile.ZipFile(driver, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9) as z:
        z.writestr("libvulkan_freedreno.so", binary)
        z.writestr("meta.json", json.dumps(meta, indent=2) + "\n")
    with zipfile.ZipFile(driver) as z:
        check(z.testzip() is None, "release ZIP corrupt")
        check(sha(z.read("libvulkan_freedreno.so")) == EXPECTED_LIB,
              "release does not contain audited binary")
        m = json.loads(z.read("meta.json"))
        check(m["packageVersion"] == "1.0" and
              m["name"] == "Drnas-Turnip A810 S Ultimate v1.0", "final metadata mismatch")
    source = dest / RELEASE_SOURCE
    shutil.copyfile(src, source)
    sums = dest / "SHA256SUMS.txt"
    sums.write_text(
        "".join(sha(p.read_bytes()) + "  " + p.name + "\n" for p in [driver, source]),
        encoding="utf-8"
    )
    print("RELEASE PACKAGE PASS: AArch64 binary unchanged", EXPECTED_LIB)
    print("RELEASE PACKAGE PASS: ZIP layout, source patch, Winlator metadata, checksums")
    print(sums.read_text())


if __name__ == "__main__":
    main()
