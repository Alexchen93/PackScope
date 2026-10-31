"""PackScope operations. Commands run without a shell; pkexec uses system UI."""
from dataclasses import dataclass
from collections import deque
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from packscope.inventory import Package

APT_ID = re.compile(r'^[a-z0-9][a-z0-9+.-]*(?::[a-z0-9][a-z0-9-]*)?$')
SNAP_ID = re.compile(r'^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$')
FLAT_ID = re.compile(r'^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)?$')
NPM_ID = re.compile(r'^(?:@[a-z0-9._~-]+/)?[a-z0-9._~-]+$')
PY_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]*$')

@dataclass(frozen=True)
class Operation:
    action: str
    package: Package
    argv: tuple
    needs_auth: bool


def search_apt(query):
    query = query.strip()
    if not query or len(query) > 100:
        raise ValueError('請輸入有效的軟體名稱。')
    env = dict(os.environ, LC_ALL='C', LANGUAGE='C')
    result = subprocess.run([_binary('apt-cache'), 'search', '--names-only', '--', re.escape(query)],
                            stdin=subprocess.DEVNULL, capture_output=True, text=True, errors='replace',
                            env=env, timeout=30, check=True)
    found = []
    for line in result.stdout.splitlines():
        name, sep, desc = line.partition(' - ')
        if sep and APT_ID.fullmatch(name):
            found.append((name, desc))
            if len(found) == 100: break
    return found


def _validate(pattern, text):
    if not isinstance(text, str) or not pattern.fullmatch(text):
        raise ValueError('套件識別碼格式不正確。')
    return text


def _binary(name):
    path = shutil.which(name)
    if not path:
        raise ValueError(f'找不到 {name}，請先安裝對應的套件管理器。')
    return path


def _privileged(argv):
    return (_binary('pkexec'), *argv)


def make_file_install(filename: str) -> Operation:
    """Prepare an install from a local file, based on its file extension."""
    path = Path(filename).expanduser().resolve()
    if not path.is_file():
        raise ValueError('找不到安裝檔，請重新選擇。')
    suffix = path.suffix.lower()
    managers = {'.deb': 'APT / dpkg', '.snap': 'Snap', '.flatpak': 'Flatpak',
                '.flatpakref': 'Flatpak', '.appimage': 'AppImage'}
    manager = managers.get(suffix)
    if not manager:
        raise ValueError('不支援這個檔案類型。請選擇 DEB、Snap、Flatpak、Flatpakref 或 AppImage 檔案。')
    package = Package(path.stem, str(path), '未知', manager,
                      '使用者' if manager in ('Flatpak', 'AppImage') else '系統', location=str(path))
    if suffix == '.deb':
        argv = _privileged([_binary('apt-get'), '-y', '-o', 'Dpkg::Use-Pty=0',
                            '-o', 'APT::Status-Fd=1', 'install', '--', str(path)])
        return Operation('install', package, argv, True)
    if suffix == '.snap':
        argv = _privileged([_binary('snap'), 'install', '--dangerous', '--', str(path)])
        return Operation('install', package, argv, True)
    if suffix in ('.flatpak', '.flatpakref'):
        flag = '--bundle' if suffix == '.flatpak' else '--from'
        return Operation('install', package,
                         (_binary('flatpak'), 'install', '--user', '-y', flag, '--', str(path)), False)
    return make_operation(package, 'install')


def make_operation(package: Package, action: str, remote: str = 'flathub') -> Operation:
    if action not in ('install', 'update', 'remove'):
        raise ValueError('不支援的操作。')
    manager = package.manager
    auth = False
    if manager == 'APT / dpkg':
        name = _validate(APT_ID, package.ident)
        apt = _binary('apt-get')
        subcommand = 'remove' if action == 'remove' else 'install'
        args = [apt, '-y', '-o', 'Dpkg::Use-Pty=0', '-o', 'APT::Status-Fd=1', subcommand]
        if action == 'update': args.append('--only-upgrade')
        args.extend(['--', name])
        argv, auth = _privileged(args), True
    elif manager == 'Snap':
        name = _validate(SNAP_ID, package.ident)
        subcommand = {'install':'install', 'update':'refresh', 'remove':'remove'}[action]
        argv, auth = _privileged([_binary('snap'), subcommand, '--', name]), True
    elif manager == 'Flatpak':
        name = _validate(FLAT_ID, package.ident)
        scope = {'系統':'--system', '使用者':'--user'}.get(package.scope)
        if scope is None: raise ValueError('無法判定 Flatpak 安裝範圍。')
        flatpak = _binary('flatpak')
        subcommand = {'install':'install', 'update':'update', 'remove':'uninstall'}[action]
        # Keep polkit interaction available for system installations; -y
        # answers the package manager's ordinary confirmation prompts.
        args = [flatpak, subcommand, scope, '-y']
        if action == 'install':
            if not re.fullmatch(r'[A-Za-z0-9._-]+', remote): raise ValueError('Flatpak 來源名稱不正確。')
            args.extend(['--', remote, name])
        else:
            args.extend(['--', name])
        # Flatpak's system service requests authorisation through polkit itself.
        argv, auth = tuple(args), package.scope == '系統'
    elif manager == 'pipx':
        # pipx operates on the environment name, which can differ from its
        # distribution name when a suffix was used at installation time.
        venv = Path(package.location) if package.location else None
        name = _validate(PY_ID, venv.name if venv and venv.parent.name == 'venvs' else package.ident)
        subcommand = {'install':'install', 'update':'upgrade', 'remove':'uninstall'}[action]
        argv = (_binary('pipx'), subcommand, name)
    elif manager == 'npm global':
        name = _validate(NPM_ID, package.ident)
        subcommand = {'install':'install', 'update':'update', 'remove':'uninstall'}[action]
        argv = (_binary('npm'), subcommand, '--global', '--', name)
    elif manager == 'Cargo':
        name = _validate(PY_ID, package.ident)
        if action == 'remove': argv = (_binary('cargo'), 'uninstall', '--', name)
        elif action == 'update': argv = (_binary('cargo'), 'install', '--force', '--', name)
        else: argv = (_binary('cargo'), 'install', '--', name)
    elif manager == 'AppImage':
        if action == 'update': raise ValueError('此 AppImage 沒有統一的更新方式。')
        path = Path(package.location)
        if not package.location or not path.is_file() or path.suffix.lower() != '.appimage':
            raise ValueError('找不到對應的 AppImage 檔案。')
        if action == 'install':
            argv = ()  # Copy and desktop integration are performed by Python below.
        else:
            argv_list = [_binary('gio'), 'trash', '--', str(path)]
            desktop = _appimage_desktop(path)
            try:
                marker = 'X-PackScope-Target=' + json.dumps(str(path), ensure_ascii=True)
                if desktop.is_file() and marker in desktop.read_text(encoding='utf-8').splitlines():
                    argv_list.append(str(desktop))
            except OSError:
                pass
            argv = tuple(argv_list)
    else:
        raise ValueError('這個來源尚未支援此操作。')
    return Operation(action, package, tuple(argv), auth)


def _appimage_desktop(path):
    digest = hashlib.sha256(str(path).encode('utf-8')).hexdigest()[:16]
    return Path.home()/'.local/share/applications'/f'packscope-{digest}.desktop'


def install_appimage(source, on_progress=None):
    source = Path(source)
    if not source.is_file() or source.suffix.lower() != '.appimage':
        raise ValueError('找不到對應的 AppImage 檔案。')
    if any(ord(c) < 32 for c in source.name):
        raise ValueError('檔案名稱包含無法使用的控制字元。')
    directory = Path.home()/'Applications'
    directory.mkdir(parents=True, exist_ok=True)
    dest = directory/source.name
    same = source.resolve() == dest.resolve()
    if not same and (dest.exists() or dest.is_symlink()):
        raise ValueError('Applications 資料夾中已有同名檔案。')
    desktop = _appimage_desktop(dest)
    desktop.parent.mkdir(parents=True, exist_ok=True)
    if desktop.exists() or desktop.is_symlink():
        raise ValueError('此 AppImage 已有 PackScope 桌面捷徑。')
    created = False
    try:
        if not same:
            with source.open('rb') as inp, dest.open('xb') as out:
                created = True
                total = source.stat().st_size
                copied = 0
                while True:
                    chunk = inp.read(1024 * 1024)
                    if not chunk: break
                    out.write(chunk)
                    copied += len(chunk)
                    if on_progress and total: on_progress(min(99, int(copied * 100 / total)))
        os.chmod(dest, dest.stat().st_mode | 0o100)
        quoted = str(dest).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%')
        name = source.stem.replace('\n', ' ').replace('\r', ' ')
        marker = json.dumps(str(dest), ensure_ascii=True)
        entry = (f'[Desktop Entry]\nType=Application\nName={name}\nExec="{quoted}"\n'
                 f'Icon=application-x-executable\nTerminal=false\nCategories=Utility;\nX-PackScope-Target={marker}\n')
        with desktop.open('x', encoding='utf-8') as out: out.write(entry)
    except Exception:
        if created:
            try: dest.unlink()
            except OSError: pass
        raise
    return f'已建立 AppImage：{dest}\n已建立桌面捷徑：{desktop}'


ANSI_ESCAPE = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
APT_PROGRESS = re.compile(r'^pmstatus:.*?:(\d+(?:\.\d+)?):')
PERCENT_PROGRESS = re.compile(r'(?<![\d.])(100(?:\.0+)?|\d{1,2}(?:\.\d+)?)%')


def progress_value(line, manager):
    """Parse actual tool-reported progress; never invent a percentage."""
    if manager == 'APT / dpkg':
        match = APT_PROGRESS.search(line)
    elif manager in ('Flatpak', 'Snap'):
        match = PERCENT_PROGRESS.search(line)
    else:
        match = None
    if not match: return None
    return max(0, min(99, int(float(match.group(1)))))


def execute(operation: Operation, on_output=None, on_progress=None) -> str:
    """Run one user-confirmed operation; system authentication is handled by polkit."""
    if operation.package.manager == 'AppImage' and operation.action == 'install':
        output = install_appimage(operation.package.location, on_progress)
        if on_output: on_output(output)
        return output
    env = dict(os.environ)
    # A package manager must never wait for an invisible terminal prompt.
    env['DEBIAN_FRONTEND'] = 'noninteractive'
    lines = deque(maxlen=1500)
    process = subprocess.Popen(operation.argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, errors='replace', env=env,
                               bufsize=1)
    assert process.stdout is not None
    try:
        for raw in process.stdout:
            line = ANSI_ESCAPE.sub('', raw).rstrip('\r\n')
            lines.append(line)
            if on_output: on_output(line)
            value = progress_value(line, operation.package.manager)
            if value is not None and on_progress: on_progress(value)
    finally:
        process.stdout.close()
    code = process.wait()
    output = '\n'.join(lines).strip()
    if code != 0:
        raise RuntimeError(f'操作未完成（代碼 {code}）。\n\n{output[-40000:]}')
    return output[-40000:] or '操作已完成。'
