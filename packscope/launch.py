"""Discover and launch desktop applications associated with installed items."""
from dataclasses import dataclass
import logging
import os
from pathlib import Path
import shutil
import subprocess

from packscope.actions import APT_ID, FLAT_ID, SNAP_ID, _validate
from packscope.inventory import command


@dataclass(frozen=True)
class LaunchTarget:
    label: str
    kind: str
    path: str = ''
    argv: tuple = ()


def _desktop_info(path):
    try:
        from gi.repository import Gio
    except ImportError as exc:
        raise RuntimeError('找不到桌面啟動元件 python3-gi。') from exc
    return Gio.DesktopAppInfo.new_from_filename(str(path))


def _desktop_target(path):
    path = Path(path)
    if not path.is_absolute() or path.suffix.lower() != '.desktop' or not path.is_file():
        return None
    info = _desktop_info(path)
    if not info or info.get_is_hidden() or not info.should_show():
        return None
    return LaunchTarget(info.get_display_name() or info.get_name() or path.stem, 'desktop', str(path))


def _snap_apps(name):
    from bauh.gems.snap.snapd import SnapdClient, URL_BASE
    client = SnapdClient(logging.getLogger('packscope'))
    response = client.session.get(f'{URL_BASE}/apps', params={'names':name}, timeout=5)
    if response.status_code == 404:
        return []
    response.raise_for_status()
    data = response.json()
    if data.get('status-code') != 200 or not isinstance(data.get('result'),list):
        raise RuntimeError('無法讀取 Snap 啟動項目。')
    return data['result']


def find_targets(package):
    """Find launchers only; never execute the installed program here."""
    targets = []
    if package.manager == 'APT / dpkg':
        name = _validate(APT_ID, package.ident)
        listing = command(['dpkg-query','-L','--',name], timeout=15).stdout
        for line in listing.splitlines():
            if line.endswith('.desktop'):
                item = _desktop_target(line)
                if item: targets.append(item)
    elif package.manager == 'Snap':
        name = _validate(SNAP_ID, package.ident)
        for item in _snap_apps(name):
            if item.get('snap') == name and not item.get('daemon') and item.get('desktop-file'):
                target = _desktop_target(item['desktop-file'])
                if target: targets.append(target)
    elif package.manager == 'Flatpak':
        ident = _validate(FLAT_ID, package.ident)
        scope = {'系統':'--system','使用者':'--user'}.get(package.scope)
        if not scope: return []
        ref = command(['flatpak','info',scope,'--show-ref',ident], timeout=10).stdout.strip()
        parts = ref.split('/')
        if len(parts) == 4 and parts[0] == 'app' and '/'.join(parts[1:]) == ident:
            binary = shutil.which('flatpak')
            if binary:
                targets.append(LaunchTarget(package.name,'command',argv=(binary,'run',scope,
                                             '--arch='+parts[2],'--branch='+parts[3],parts[1])))
    elif package.manager == 'AppImage':
        if not package.location: return []
        path = Path(package.location)
        if path.is_file(): candidates = [path]
        elif path.is_dir(): candidates = sorted(p for p in path.iterdir() if p.suffix.lower() == '.appimage')
        else: candidates = []
        for file in candidates:
            if file.is_file() and file.suffix.lower() == '.appimage' and os.access(file,os.X_OK):
                targets.append(LaunchTarget(file.stem,'command',argv=(str(file),)))
    # Console-only tools and libraries are not assumed to be GUI programs.
    unique = {}
    for target in targets:
        unique[(target.kind,target.path,target.argv)] = target
    return list(unique.values())


def start_target(target):
    """Launch a previously discovered desktop entry or exact argument vector."""
    if target.kind == 'desktop':
        info = _desktop_info(target.path)
        if not info or not info.launch([], None):
            raise RuntimeError('無法啟動此桌面程式。')
    elif target.kind == 'command' and target.argv:
        subprocess.Popen(target.argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    else:
        raise ValueError('無法判定啟動方式。')
    return '已送出開啟要求。'
