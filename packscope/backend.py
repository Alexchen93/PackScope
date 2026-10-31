"""Read-only package queries and export functions for PackScope."""
from dataclasses import asdict
from datetime import datetime
import csv
import gzip
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import tempfile

from packscope.inventory import Package, command

APT_NAME = re.compile(r'^[a-z0-9][a-z0-9+.-]*(?::[a-z0-9][a-z0-9-]*)?$')
SNAP_NAME = re.compile(r'^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$')
FLATPAK_REF = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')


def safe_name(pattern, value):
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError('套件識別碼格式不正確，已取消操作。')
    return value


def details(package: Package):
    """Fetch locally installed metadata; never run the selected application."""
    if package.manager == 'APT / dpkg':
        name = safe_name(APT_NAME, package.ident)
        status = command(['dpkg-query', '-s', '--', name], timeout=10).stdout
        try:
            policy = command(['apt-cache', 'policy', '--', name], timeout=10).stdout
        except (OSError, subprocess.SubprocessError):
            policy = '無法讀取目前套件庫資訊。'
        return ('dpkg 已安裝資料\n\n' + status + '\n目前 APT 套件庫資訊（不代表最初安裝來源）\n\n' + policy).strip()
    if package.manager == 'Flatpak':
        ref = safe_name(FLATPAK_REF, package.ident)
        scope = {'系統': '--system', '使用者': '--user'}.get(package.scope)
        if not scope:
            raise ValueError('無法確定 Flatpak 的安裝範圍。')
        info = command(['flatpak', 'info', scope, ref], timeout=10).stdout
        return 'Flatpak 已安裝資料\n\n' + info.strip()
    if package.manager == 'Snap':
        name = safe_name(SNAP_NAME, package.ident)
        from bauh.gems.snap.snapd import SnapdClient, URL_BASE
        client = SnapdClient(logging.getLogger('packscope'))
        response = client.session.get(f'{URL_BASE}/snaps/{name}', timeout=8)
        response.raise_for_status()
        data = response.json()
        if data.get('status-code') != 200 or not isinstance(data.get('result'), dict):
            raise ValueError('snapd 回傳無效結果。')
        fields = data['result']
        keys = [('名稱','name'), ('版本','version'), ('修訂版','revision'), ('發布者','publisher'),
                ('追蹤頻道','tracking-channel'), ('授權','license'), ('類型','type'),
                ('摘要','summary'), ('描述','description')]
        lines = ['Snap 已安裝資料', '']
        for label, key in keys:
            value = fields.get(key)
            if isinstance(value, dict): value = value.get('display-name') or value.get('username')
            if value: lines.append(f'{label}：{value}')
        return '\n'.join(lines)
    if package.manager == 'AppImage':
        lines = ['AppImage 檔案資訊', '', '檔案僅以唯讀方式檢查，未執行。']
        if package.location:
            path = Path(package.location)
            lines.append(f'位置：{path}')
            try:
                info = path.stat()
                lines.append(f'大小：{info.st_size:,} 位元組')
                lines.append(f'最後修改：{datetime.fromtimestamp(info.st_mtime).strftime("%Y-%m-%d %H:%M:%S")}')
            except OSError:
                lines.append('無法讀取檔案資訊。')
        else:
            lines.append('檔案位置未知。')
        return '\n'.join(lines)
    if package.manager in ('pipx', 'npm global', 'Cargo'):
        return (f'名稱：{package.name}\n套件 ID：{package.ident}\n版本：{package.version}\n'
                f'管理器：{package.manager}\n安裝範圍：{package.scope}\n'
                f'位置：{package.location or "未知"}\n證據：{package.evidence}')
    raise ValueError('這個來源尚未支援詳細資料查詢。')


def check_updates():
    """Use local APT/Flatpak data and query Snap's available refreshes."""
    sections = []
    try:
        result = command(['apt-get', '-s', '-o', 'Debug::NoLocking=1', 'upgrade'], timeout=90)
        updates = []
        for line in result.stdout.splitlines():
            match = re.match(r'^Inst\s+(\S+)(?:\s+\[([^\]]+)\])?\s+\((\S+)', line)
            if match:
                name, current, candidate = match.groups()
                updates.append(f'{name}  {current or "未知"} → {candidate}')
        note = ('根據本機 APT 套件清單模擬一般升級；不會刷新套件清單。'
                '被保留、分階段發布或需要額外套件的更新可能未列出。')
        sections.append(('APT / dpkg', note, updates, None))
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        sections.append(('APT / dpkg', '', [], str(exc)))
    try:
        # --cached avoids updating remote metadata; results may be stale.
        result = command(['flatpak', 'remote-ls', '--updates', '--cached', '--columns=ref,origin'], timeout=30)
        updates = [line.strip().replace('\t', '  ·  ') for line in result.stdout.splitlines() if line.strip()]
        sections.append(('Flatpak', '依本機快取查詢，資訊可能不是最新。', updates, None))
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        sections.append(('Flatpak', '', [], str(exc)))
    try:
        result = command(['snap', 'refresh', '--list'], timeout=45)
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if lines and lines[0].lower().startswith('name '):
            lines = lines[1:]
        if len(lines) == 1 and lines[0].lower().startswith(('all snaps up to date', 'no updates available')):
            lines = []
        sections.append(('Snap', '向 Snap 商店查詢可用更新；不會執行更新。', lines, None))
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        sections.append(('Snap', '', [], str(exc)))
    sections.append(('AppImage', 'AppImage 沒有統一的更新查詢方式；尚未檢查。', [], None))
    sections.append(('開發工具', 'pipx、npm 和 Cargo 尚未檢查更新。', [], None))
    return sections


def package_history(package: Package, log_dir=Path('/var/log')):
    """Find bounded dpkg events without claiming why or how they occurred."""
    if package.manager != 'APT / dpkg':
        raise ValueError('目前只支援 APT / dpkg 的本機變更紀錄。')
    name = safe_name(APT_NAME, package.ident)
    base, _, arch = name.partition(':')
    paths = [Path(log_dir)/'dpkg.log', Path(log_dir)/'dpkg.log.1',
             Path(log_dir)/'dpkg.log.2.gz', Path(log_dir)/'dpkg.log.3.gz']
    matches, failures = [], 0
    for path in paths:
        if not path.is_file():
            continue
        try:
            if path.suffix == '.gz':
                with gzip.open(path, 'rt', encoding='utf-8', errors='replace') as source:
                    text = source.read(4_000_000)
            else:
                with path.open('rb') as source:
                    source.seek(0, os.SEEK_END)
                    source.seek(max(0, source.tell() - 4_000_000))
                    text = source.read().decode('utf-8', errors='replace')
            for line in text.splitlines():
                fields = line.split()
                if len(fields) < 5 or fields[2] not in ('install','upgrade','remove','purge'):
                    continue
                found_base, _, found_arch = fields[3].partition(':')
                if found_base == base and (not arch or found_arch == arch):
                    matches.append(line)
        except (OSError, EOFError):
            failures += 1
    matches.sort(reverse=True)
    note = ('資料來自最近幾份 dpkg 紀錄，可能因權限、輪替或截斷而不完整；'
            '這些紀錄無法單獨證明使用者最初使用哪種安裝方式。')
    if failures: note += f'\n有 {failures} 份紀錄無法讀取。'
    return note + '\n\n' + ('\n'.join(matches[:100]) if matches else '在已讀取的紀錄中找不到相關事件。')


def export_inventory(path, packages, fmt):
    """Export exactly the currently filtered inventory selected by the user."""
    if fmt not in ('json', 'csv', 'md'):
        raise ValueError('不支援的匯出格式。')
    records = [asdict(p) for p in packages]
    destination = Path(path)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='',
                                         dir=destination.parent, prefix='.packscope-', delete=False) as out:
            temp_path = out.name
            if fmt == 'json':
                json.dump({'exported_at': datetime.now().astimezone().isoformat(), 'packages': records}, out, ensure_ascii=False, indent=2)
                out.write('\n')
            elif fmt == 'csv':
                fields = list(Package.__dataclass_fields__)
                writer = csv.DictWriter(out, fieldnames=fields)
                writer.writeheader()
                for record in records:
                    # Prevent data from being interpreted as spreadsheet formulas.
                    cleaned = {k: ("'" + v if isinstance(v, str) and v.lstrip().startswith(('=', '+', '-', '@')) else v)
                               for k, v in record.items()}
                    writer.writerow(cleaned)
            else:
                from html import escape
                def cell(value):
                    return escape(str(value or '')).replace('\\', '\\\\').replace('|', '\\|').replace('\n', ' ')
                out.write('# PackScope 軟體清單\n\n')
                out.write('| 名稱 | 套件 ID | 版本 | 管理器 | 範圍 |\n| --- | --- | --- | --- | --- |\n')
                for record in records:
                    out.write('| ' + ' | '.join(cell(record[k]) for k in ('name','ident','version','manager','scope')) + ' |\n')
        os.replace(temp_path, destination)
        temp_path = None
    finally:
        if temp_path:
            try: os.unlink(temp_path)
            except OSError: pass
