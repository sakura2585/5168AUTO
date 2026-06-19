# -*- mode: python ; coding: utf-8 -*-
# 5168AUTO 發布用單檔 EXE（PyInstaller）
# 執行：python -m PyInstaller --noconfirm 5168AUTO.spec

import os
import re
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

_spec_dir = os.path.dirname(os.path.abspath(SPEC))


def _read_app_version() -> tuple[tuple[int, int, int, int], str, str]:
    app_py = os.path.join(_spec_dir, "app.py")
    raw = "v0.0.0"
    try:
        with open(app_py, encoding="utf-8") as f:
            m = re.search(
                r'^\s*_APP_VERSION\s*=\s*["\']([^"\']+)["\']',
                f.read(),
                re.M,
            )
            if m:
                raw = (m.group(1) or "").strip()
    except OSError:
        pass
    s = raw.lower().lstrip("v")
    nums = [int(x) for x in re.findall(r"\d+", s)]
    while len(nums) < 4:
        nums.append(0)
    ft = tuple(nums[:4])
    vs_display = ".".join(str(x) for x in ft[:4])
    return ft, vs_display, raw


def _write_win_version_info(
    path: str, filevers: tuple, vs_display: str, exe_filename: str
) -> None:
    if sys.platform != "win32":
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    content = f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={filevers},
    prodvers={filevers},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u''),
        StringStruct(u'FileDescription', u'5168AUTO'),
        StringStruct(u'FileVersion', u'{vs_display}'),
        StringStruct(u'InternalName', u'5168AUTO'),
        StringStruct(u'LegalCopyright', u''),
        StringStruct(u'OriginalFilename', u'{exe_filename}'),
        StringStruct(u'ProductName', u'5168AUTO'),
        StringStruct(u'ProductVersion', u'{vs_display}')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


_filevers, _vs_display, _app_version = _read_app_version()
_exe_stem = f"5168AUTO_{_app_version}"
_exe_filename = f"{_exe_stem}.exe"
_version_info_path = os.path.join(_spec_dir, "build", "_file_version_info.txt")
_write_win_version_info(_version_info_path, _filevers, _vs_display, _exe_filename)

_hidden = [
    "browser_actions",
    "browser_core",
    "browser_session",
    "config_store",
    "credentials_store",
    "inventory_workflow",
    "login_worker",
    "paths",
    "popup_guard",
    "session_guard",
    "workflow_worker",
]
_hidden += collect_submodules("selenium")
_hidden += collect_submodules("PySide6")

_datas = collect_data_files("certifi")
for _fname in ("config.example.json", "credentials.example.json"):
    _src = os.path.join(_spec_dir, _fname)
    if os.path.isfile(_src):
        _datas.append((_src, "."))

a = Analysis(
    [os.path.join(_spec_dir, "app.py")],
    pathex=[_spec_dir],
    binaries=[],
    datas=_datas,
    hiddenimports=_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

_exe_options = dict(
    name=_exe_stem,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
if sys.platform == "win32" and os.path.isfile(_version_info_path):
    _exe_options["version"] = _version_info_path

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    **_exe_options,
)
