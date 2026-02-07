# Requirements Document: MiniWoW Streamlit Dashboard & Runtime Monitor

## 1. Executive Summary
The goal is to expand the existing Streamlit dashboard (`view_progress_streamlit.py`) into a comprehensive control center. This dashboard will not only visualize historical dungeon progress (SQLite) but also provide real-time visibility into the automation system's health by monitoring emulator connectivity (`adb`), parsing active execution logs, and displaying configuration status (`emulators.json`).

## 2. Scope
- Target Platform: Web browser (via Streamlit)
- Core Functions:
  1. Runtime Monitoring: Real-time status of emulator sessions (Online/Offline, Last Action, Errors)
  2. Progress Tracking: Visualization of daily/weekly dungeon completion (leveraging existing logic)
  3. Log Inspection: Live tailing of application logs for debugging
- Exclusions: This phase focuses on monitoring. Remote control (Start/Stop/Restart actions) is out of scope, but the UI should be designed to accommodate it later.

## 3. User Stories
1. System Health Check: As a user, I want to see a high-level status for each configured emulator so I know immediately if a device has disconnected or crashed.
2. Live Activity: As a user, I want to see the last 3-5 log lines for each session to understand what the bot is currently doing.
3. Progress Verification: As a user, I want to see how many dungeons are left for the day without checking the game client.
4. Error Discovery: As a user, I want the dashboard to highlight sessions that have logged ERROR/CRITICAL messages recently.
5. Configuration Audit: As a user, I want to see which character configuration (`mage`, `rogue`, etc.) is assigned to which emulator instance.

## 4. Data Sources
| Source | Purpose | Access Method |
| --- | --- | --- |
| `emulators.json` | Source of truth for session names, emulator addresses, assigned configs, and log paths | JSON file read |
| ADB (`adb devices`) | Verify emulator instances are connected/online | Shell command (`subprocess`) |
| Logs (`log/*.log`) | Real-time activity status, error detection, debugging | File read (tail) |
| `database/dungeon_progress.db` | Historical completion data and today's progress stats | SQLite (Peewee ORM) |

## 5. UI/UX Requirements

### 5.1 Layout Structure
Use a Sidebar for navigation and global settings, and a Main Area divided into sections:

- Sidebar:
  - Auto-refresh toggle (On/Off)
  - Refresh rate setting (default 5s)
  - Path inputs (DB path, config dir, emulators.json path)

- Section 1: Runtime Monitor (Top Priority)
  - Display a grid/table of sessions, one per entry in `emulators.json`
  - For each session show:
    - Session name + emulator address
    - Status badge:
      - Online: ADB connected + log updated recently
      - Idle: ADB connected + log stale
      - Offline: ADB disconnected
    - Current config/职业 (from latest relevant log patterns)
    - Current dungeon progress position (name + [i/total] if available)
    - Recent error indicator (if ERROR/CRITICAL present in recent log tail)

- Section 2: Progress Dashboard (Existing)
  - Retain existing progress charts and tables

- Section 3: Log Inspector
  - Select a session/log file
  - Show last N lines in a scrollable area
  - Handle missing logs gracefully

### 5.2 Interaction & Behavior
- Auto-Refresh: Must refresh automatically (default every 5 seconds) without manual page reload
- Responsiveness: Works on typical desktop browser; avoid heavy reads on each redraw

## 6. Non-Functional Requirements

### 6.1 Performance
- Cache ADB results briefly (5-10s) to avoid spamming the system shell
- Tail logs efficiently (read last N bytes/lines), avoid reading entire files

### 6.2 Error Handling
- Missing files: show friendly warnings instead of crashing
- ADB failure: show global error banner but keep DB stats functional
- DB locked: handle gracefully (retry or skip update)

### 6.3 Security
- Read-only in this iteration (no writes to emulators.json, no destructive actions)
- Assume local/VPN usage; no built-in auth required for now

## 7. Acceptance Checklist
- [ ] Reads `emulators.json` and lists all sessions
- [ ] Correctly identifies connected vs disconnected emulators via ADB
- [ ] Displays latest activity from logs and updates near real-time
- [ ] Existing progress view still works
- [ ] Highlights sessions with recent errors
- [ ] Remains responsive with auto-refresh enabled
- [ ] Robust to missing log files while running
