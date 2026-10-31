"""Read-only inventory. No installation, privilege escalation or updates."""
from dataclasses import dataclass
import glob
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


@dataclass(frozen=True)
class Package:
    name: str
    ident: str
    version: str
    manager: str
    scope: str = "未知"
    description: str = ""
    evidence: str = ""
    location: str = ""


@dataclass
class ScanResult:
    manager: str
    packages: list
    status: str
    detail: str = ""


def command(args, timeout=15):
    env = dict(os.environ, LC_ALL="C", LANGUAGE="C")
    return subprocess.run(args, capture_output=True, text=True, check=True,
                          timeout=timeout, env=env)


def debian():
    if not shutil.which("dpkg-query"):
        return ScanResult("APT / dpkg", [], "unavailable", "找不到 dpkg-query")
    # Prefer bauh's Debian adapter if its aptitude dependency is present.
    if shutil.which("aptitude"):
        from bauh.gems.debian.aptitude import Aptitude
        packages = list(Aptitude(logging.getLogger("packscope")).read_installed())
        rows = [Package(p.name, p.name, p.version or "未知", "APT / dpkg", "系統",
                        p.description or "", "bauh 的 Debian 模組 / aptitude 套件資料庫")
                for p in packages]
        return ScanResult("APT / dpkg", rows, "ok", "使用 bauh 的 aptitude 介面")
    result = command(["dpkg-query", "-W", "-f=${db:Status-Status}\t${binary:Package}\t${Version}\t${binary:Summary}\n"])
    rows = []
    for line in result.stdout.splitlines():
        fields = line.split("\t", 3)
        if len(fields) == 4 and fields[0] == "installed":
            _, name, version, desc = fields
            rows.append(Package(name, name, version or "未知", "APT / dpkg", "系統", desc,
                                "dpkg 套件資料庫（目前管理狀態）"))
    return ScanResult("APT / dpkg", rows, "ok", "aptitude 未安裝；使用 dpkg 唯讀備援")


def flatpak():
    if not shutil.which("flatpak"):
        return ScanResult("Flatpak", [], "unavailable", "未安裝 Flatpak")
    # Check exit status explicitly: bauh's list_installed does not report command errors.
    command(["flatpak", "list", "--columns=application"], timeout=15)
    from bauh.gems.flatpak import flatpak as backend
    version = backend.get_version()
    if not version:
        raise RuntimeError("無法讀取 Flatpak 版本")
    entries = backend.list_installed(version)
    rows = []
    for item in entries:
        ident = item.get("ref") or item.get("id") or "未知"
        scope = {"system": "系統", "user": "使用者"}.get(item.get("installation"), item.get("installation") or "未知")
        origin = item.get("origin") or "未知"
        kind = "執行環境" if item.get("runtime") else "應用程式"
        rows.append(Package(item.get("name") or ident, ident, item.get("version") or "未知", "Flatpak", scope,
                            item.get("description") or kind,
                            f"bauh Flatpak 模組：目前記錄的遠端來源 {origin}；不代表最初安裝方式"))
    return ScanResult("Flatpak", rows, "ok", "包含應用程式與執行環境")


def snap():
    if not shutil.which("snap"):
        return ScanResult("Snap", [], "unavailable", "未安裝 Snap")
    from bauh.gems.snap.snapd import SnapdClient, URL_BASE
    client = SnapdClient(logging.getLogger("packscope"))
    if not client.session:
        raise RuntimeError("無法建立 snapd 連線")
    # Reuse bauh's snapd transport, but check errors and impose a timeout.
    response = client.session.get(f"{URL_BASE}/snaps", timeout=5)
    response.raise_for_status()
    data = response.json()
    if data.get("status-code") != 200 or not isinstance(data.get("result"), list):
        raise RuntimeError("snapd 回傳無效結果")
    rows = []
    for item in data["result"]:
        name = item.get("name") or "未知"
        rows.append(Package(item.get("title") or name, name, item.get("version") or "未知", "Snap", "系統",
                            item.get("summary") or "", "bauh snapd 介面：目前已安裝的 Snap"))
    return ScanResult("Snap", rows, "ok")


def appimage():
    directories = [Path.home() / "Applications", Path.home() / "AppImages", Path.home() / "Downloads"]
    rows, seen = [], set()
    for directory in directories:
        if not directory.is_dir():
            continue
        for path in directory.iterdir():
            if path.suffix.lower() != ".appimage" or not path.is_file():
                continue
            resolved = str(path.resolve())
            if resolved in seen:
                continue
            seen.add(resolved)
            rows.append(Package(path.stem, resolved, "未知", "AppImage", "使用者", "偵測到 AppImage 檔案",
                                "依檔案副檔名偵測；不代表已安裝或經過驗證", str(path)))
    # bauh stores its managed AppImages as metadata; do not execute the file.
    for item in glob.glob(str(Path.home() / ".local/share/bauh/appimage/installed/*/data.json")):
        # Managed metadata may contain richer details, but it is not a file path guarantee.
        try:
            with open(item, encoding="utf-8") as source:
                metadata = json.load(source)
            name = str(metadata.get("name") or Path(item).parent.name)
            location = str(metadata.get("install_dir") or "")
            if location and any(location == r.location or r.location.startswith(location + os.sep) for r in rows):
                continue
            rows.append(Package(name, item, str(metadata.get("version") or "未知"), "AppImage", "使用者",
                                "bauh 管理的 AppImage", "bauh 的 AppImage 安裝紀錄", location))
        except (OSError, ValueError, TypeError):
            continue
    return ScanResult("AppImage", rows, "ok", "掃描 ~/Applications、~/AppImages、~/Downloads 與 bauh 安裝紀錄；結果可能不完整")


def pipx():
    if not shutil.which('pipx'):
        return ScanResult('pipx', [], 'unavailable', '未安裝 pipx')
    configured = os.environ.get('PIPX_HOME')
    homes = [Path(configured).expanduser()] if configured else [Path.home()/'.local/share/pipx', Path.home()/'.local/pipx']
    rows, seen, errors = [], set(), 0
    for home in homes:
        directory = home / 'venvs'
        if not directory.is_dir():
            continue
        for metadata in directory.glob('*/pipx_metadata.json'):
            try:
                data = json.loads(metadata.read_text(encoding='utf-8'))
                main = data.get('main_package') or {}
                name = main.get('package') or metadata.parent.name
                location = str(metadata.parent)
                if location in seen:
                    continue
                seen.add(location)
                rows.append(Package(name, name, main.get('package_version') or '未知', 'pipx', '使用者',
                                    'pipx 管理的獨立 Python 應用程式', 'pipx 虛擬環境的本機 metadata', location))
            except (OSError, ValueError, TypeError, AttributeError):
                errors += 1
    note = '僅讀取 pipx 的本機中繼資料，不掃描其他 Python 虛擬環境。'
    if errors: note += f' {errors} 個環境無法讀取。'
    return ScanResult('pipx', rows, 'ok', note)


def npm():
    if not shutil.which('npm'):
        return ScanResult('npm global', [], 'unavailable', '未安裝 npm')
    # npm may write logs or cache even for list; keep those in a temporary directory.
    with tempfile.TemporaryDirectory(prefix='packscope-npm-') as cache:
        out = command(['npm', 'list', '--global', '--depth=0', '--json', '--loglevel=silent', '--cache', cache], timeout=30)
    data = json.loads(out.stdout)
    dependencies = data.get('dependencies', {})
    if not isinstance(dependencies, dict):
        raise ValueError('npm 回傳的套件清單格式不正確。')
    rows = []
    for name, item in dependencies.items():
        if not isinstance(item, dict): continue
        rows.append(Package(name, name, item.get('version') or '未知', 'npm global', '目前使用者環境',
                            '目前 npm 環境中的全域套件', 'npm list --global 的本機結果', item.get('path') or ''))
    return ScanResult('npm global', rows, 'ok', '僅目前 PATH 的 npm 全域環境。')


def cargo():
    if not shutil.which('cargo'):
        return ScanResult('Cargo', [], 'unavailable', '未安裝 Cargo')
    try:
        import tomllib
    except ImportError:
        return ScanResult('Cargo', [], 'unavailable', '讀取 Cargo 紀錄需要 Python 3.11 或更新版本。')
    home = Path(os.environ.get('CARGO_HOME') or Path.home()/'.cargo').expanduser()
    metadata = home / '.crates.toml'
    if not metadata.is_file():
        return ScanResult('Cargo', [], 'ok', '沒有 Cargo 全域安裝紀錄。')
    with metadata.open('rb') as source:
        data = tomllib.load(source)
    entries = data.get('v1', {})
    if not isinstance(entries, dict):
        raise ValueError('Cargo 安裝紀錄格式不正確。')
    rows = []
    for key in entries:
        fields = key.split(' ', 2)
        if len(fields) < 2: continue
        name, version = fields[:2]
        rows.append(Package(name, name, version, 'Cargo', '使用者', 'cargo install 安裝的工具',
                            'Cargo 本機安裝紀錄 .crates.toml', str(home/'bin')))
    return ScanResult('Cargo', rows, 'ok', '僅讀取目前 CARGO_HOME 的安裝紀錄。')


def scan_all():
    results = []
    for name, fn in [("APT / dpkg", debian), ("Snap", snap), ("Flatpak", flatpak), ("AppImage", appimage),
                     ('pipx', pipx), ('npm global', npm), ('Cargo', cargo)]:
        try:
            results.append(fn())
        except Exception as error:
            detail = str(error).splitlines()[0][:200] if str(error) else type(error).__name__
            results.append(ScanResult(name, [], "error", f"讀取失敗：{detail}"))
    return results
