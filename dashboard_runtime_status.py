#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""Runtime status helpers for the Streamlit dashboard."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

@dataclass(frozen=True)
class EmulatorSession:
    name: str
    emulator: str
    configs: List[str]
    log_path: Optional[str] = None

@dataclass(frozen=True)
class LogStatus:
    current_config: Optional[str]
    current_dungeon: Optional[str]
    progress: Optional[str]
    last_completed: Optional[str]
    has_error: bool
    last_activity: Optional[str]

def load_emulator_sessions(emulators_path: str) -> List[EmulatorSession]:
    if not os.path.exists(emulators_path):
        return []
    try:
        with open(emulators_path, 'r', encoding='utf-8') as fh:
            payload = json.load(fh)
    except Exception:
        return []

    sessions: List[EmulatorSession] = []
    for raw in payload.get('sessions', []) or []:
        name = str(raw.get('name') or '').strip() or 'unknown'
        emulator = str(raw.get('emulator') or '').strip()
        configs = list(raw.get('configs') or [])
        log_path = raw.get('log')
        sessions.append(
            EmulatorSession(
                name=name,
                emulator=emulator,
                configs=[str(c).strip() for c in configs if str(c).strip()],
                log_path=str(log_path).strip() if log_path else None,
            )
        )
    return sessions

def resolve_log_path(session: EmulatorSession, repo_root: str) -> Optional[str]:
    if not session.log_path:
        return os.path.join(repo_root, 'log', f'autodungeon_{session.name}.log')
    p = session.log_path
    if os.path.isabs(p):
        return p
    return os.path.join(repo_root, p)

def parse_adb_devices_output(stdout: str) -> Set[str]:
    devices: Set[str] = set()
    for line in stdout.splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and parts[1] == 'device':
            devices.add(parts[0])
    return devices

def get_connected_adb_devices(timeout_sec: float = 5.0) -> Set[str]:
    try:
        result = subprocess.run(
            ['adb', 'devices'],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        if result.returncode != 0:
            return set()
        return parse_adb_devices_output(result.stdout)
    except Exception:
        return set()

def read_last_n_lines(file_path: str, n: int = 200, chunk_size: int = 4096) -> str:
    if not file_path or not os.path.exists(file_path):
        return ''
    try:
        with open(file_path, 'rb') as fh:
            fh.seek(0, os.SEEK_END)
            end = fh.tell()
            if end <= 0:
                return ''
            blocks: List[bytes] = []
            lines_found = 0
            pos = end
            while pos > 0 and lines_found < n:
                step = chunk_size if pos >= chunk_size else pos
                pos -= step
                fh.seek(pos)
                chunk = fh.read(step)
                blocks.append(chunk)
                lines_found += chunk.count(b'\n')
            content = b''.join(reversed(blocks))
            text = content.decode('utf-8', errors='ignore')
            return '\n'.join(text.splitlines()[-n:])
    except Exception:
        return ''

_ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

def strip_ansi(text: str) -> str:
    return _ANSI_ESCAPE.sub('', text)

_PAT_PROGRESS = re.compile(r'🎯\s*\[(\d+)\s*/\s*(\d+)\]\s*处理副本[:：]\s*(.+)')
_PAT_COMPLETE = re.compile(r'✅\s*完成[:：]\s*(.+)')
_PAT_CONFIG = re.compile(r'当前配置[:：]?\s*([^\s\x1b]+)')

def parse_log_status(log_content: str) -> LogStatus:
    current_config: Optional[str] = None
    current_dungeon: Optional[str] = None
    progress: Optional[str] = None
    last_completed: Optional[str] = None
    has_error = False
    last_activity: Optional[str] = None

    if not log_content:
        return LogStatus(None, None, None, None, False, None)

    lines = [ln for ln in log_content.splitlines() if ln is not None]
    if lines:
        last_activity = strip_ansi(lines[-1].strip()) or None

    for line in reversed(lines):
        clean_line = strip_ansi(line)
        
        if not has_error and ('ERROR' in clean_line or 'CRITICAL' in clean_line):
            has_error = True

        if current_config is None:
            m = _PAT_CONFIG.search(clean_line)
            if m:
                current_config = m.group(1).strip()

        if current_dungeon is None:
            m = _PAT_PROGRESS.search(clean_line)
            if m:
                current_dungeon = m.group(3).strip()
                progress = f'{m.group(1)}/{m.group(2)}'

        if last_completed is None:
            m = _PAT_COMPLETE.search(clean_line)
            if m:
                last_completed = m.group(1).strip()

        if (current_config and current_dungeon and last_completed and has_error):
            break

    return LogStatus(
        current_config=current_config,
        current_dungeon=current_dungeon,
        progress=progress,
        last_completed=last_completed,
        has_error=has_error,
        last_activity=last_activity,
    )

def get_file_mtime_iso(path: str) -> Optional[str]:
    try:
        ts = os.path.getmtime(path)
        return datetime.fromtimestamp(ts).strftime('%m-%d %H:%M:%S')
    except Exception:
        return None

def load_config_meta(config_dir: str) -> Dict[str, Dict[str, Any]]:
    meta: Dict[str, Dict[str, Any]] = {}
    if not os.path.isdir(config_dir):
        return meta
    for fn in sorted(os.listdir(config_dir)):
        if not fn.endswith('.json'):
            continue
        name = fn[:-5]
        path = os.path.join(config_dir, fn)
        try:
            with open(path, 'r', encoding='utf-8') as fh:
                payload = json.load(fh)
        except Exception:
            continue
        class_name = payload.get('class', '未知')
        planned = 0
        for zone, dungeons in (payload.get('zone_dungeons') or {}).items():
            for d in dungeons or []:
                if not isinstance(d, dict) or 'name' not in d:
                    continue
                if bool(d.get('selected', True)):
                    planned += 1
        meta[name] = {'class_name': class_name, 'planned_count': planned}
    return meta

def get_today_completed_count(db_path: str, config_name: str, include_special: bool = False) -> int:
    try:
        from database import DungeonProgressDB
        with DungeonProgressDB(db_path=db_path, config_name=config_name) as db:
            return int(db.get_today_completed_count(include_special=include_special))
    except Exception:
        return 0

def build_runtime_rows(
    *,
    repo_root: str,
    emulators_path: str,
    config_dir: str,
    db_path: str,
    log_tail_lines: int = 200,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    errors: List[str] = []
    sessions = load_emulator_sessions(emulators_path)
    if not sessions:
        return ([], errors)

    config_meta = load_config_meta(config_dir)
    config_meta_lower = {k.lower(): v for k, v in config_meta.items()}

    connected = get_connected_adb_devices()

    rows: List[Dict[str, Any]] = []
    for s in sessions:
        log_path = resolve_log_path(s, repo_root)
        log_text = read_last_n_lines(log_path or '', n=log_tail_lines)
        log_status = parse_log_status(log_text)

        is_connected = bool(s.emulator) and (s.emulator in connected)
        status = '🟢 在线' if is_connected else '🔴 离线'

        active_cfg = log_status.current_config
        active_class = None
        if active_cfg:
            if active_cfg in config_meta:
                active_class = config_meta[active_cfg].get('class_name')
            elif active_cfg.lower() in config_meta_lower:
                active_class = config_meta_lower[active_cfg.lower()].get('class_name')

        planned_sum = 0
        completed_sum = 0
        for cfg in s.configs:
            cfg_stripped = cfg.strip()
            meta = config_meta.get(cfg_stripped)
            if not meta:
                meta = config_meta_lower.get(cfg_stripped.lower())
            
            if meta:
                planned_sum += int(meta.get('planned_count', 0))
            
            completed_sum += get_today_completed_count(db_path, cfg_stripped, include_special=True)

        progress_str = f'{completed_sum}/{planned_sum}'

        rows.append(
            {
                '会话': s.name,
                '模拟器': s.emulator,
                '状态': status,
                '运行职业': active_class or '-',
                '运行配置': active_cfg or '-',
                '当前副本': log_status.current_dungeon or '-',
                '进度': log_status.progress or '-',
                '最近完成': log_status.last_completed or '-',
                '今日完成/计划': progress_str,
                '错误': '⚠️' if log_status.has_error else '',
                '日志更新时间': get_file_mtime_iso(log_path) if log_path else None,
                '最新日志': log_status.last_activity or '',
                '_log_path': log_path or '',
                '_log_text': log_text,
            }
        )

    return rows, errors

def render_runtime_monitor(
    *,
    emulators_path: str,
    config_dir: str,
    db_path: str,
    refresh_interval_ms: int = 5000,
    log_tail_lines: int = 200,
) -> None:
    import pandas as pd
    import streamlit as st

    repo_root = os.path.dirname(os.path.abspath(__file__))
    st.subheader('运行时监控')

    if not os.path.exists(emulators_path):
        st.warning(f'未找到模拟器配置文件: {emulators_path}')
        return

    rows, errors = build_runtime_rows(
        repo_root=repo_root,
        emulators_path=emulators_path,
        config_dir=config_dir,
        db_path=db_path,
        log_tail_lines=log_tail_lines,
    )

    if errors:
        for err in errors:
            st.warning(err)

    if not rows:
        st.info('未发现任何模拟器会话')
        return

    total = len(rows)
    online = sum(1 for r in rows if str(r.get('状态', '')).startswith('🟢'))
    st.caption(f'会话数: {total} | 在线: {online}')

    df = pd.DataFrame(rows)
    display_cols = [
        '会话',
        '模拟器',
        '状态',
        '运行职业',
        '运行配置',
        '当前副本',
        '进度',
        '今日完成/计划',
        '错误',
        '日志更新时间',
        '最新日志',
    ]
    st.dataframe(df[display_cols], hide_index=True, width='stretch')

    with st.expander('🔍 日志检查器'):
        names = [f"{r['会话']} ({r['模拟器']})" for r in rows]
        selected = st.selectbox('选择会话', names)
        idx = names.index(selected) if selected in names else 0
        r = rows[idx]
        st.text(f"Log: {r.get('_log_path', '')}")
        st.text_area(
            f'最后 {log_tail_lines} 行',
            value=r.get('_log_text', ''),
            height=320,
            disabled=True,
        )
