#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime, time as dtime, timedelta
import pathlib
from pathlib import Path, PurePosixPath
from typing import Any
from zoneinfo import ZoneInfo


TZ = ZoneInfo("Asia/Shanghai")
SKILL_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_ROOT = Path(
    os.environ.get(
        "TL_DAILY_REVIEW_RUNTIME_ROOT",
        str(Path.home() / ".codex" / "runtime" / "tl-daily-review"),
    )
)
VAULT_ROOT = Path(
    os.environ.get(
        "TL_DAILY_REVIEW_VAULT_ROOT",
        "/Users/wuzhigang/Library/Mobile Documents/iCloud~md~obsidian/Documents/icloud-ob",
    )
)
NOTEBOOKLM_ROOT = VAULT_ROOT / "00_收件箱" / "NotebookLM"
DEFAULT_REPO_ROOTS = [
    "/Users/wuzhigang/Code",
    "/Users/wuzhigang/code",
    "/Users/wuzhigang/Workspace",
    "/Users/wuzhigang/workspace",
]
_repo_roots_env = os.environ.get("TL_DAILY_REVIEW_REPO_ROOTS", "")
REPO_ROOTS = [
    Path(item)
    for item in (_repo_roots_env.split(":") if _repo_roots_env else DEFAULT_REPO_ROOTS)
    if item
]

STATE_DIR = RUNTIME_ROOT / "state"
REPORT_DIR = RUNTIME_ROOT / "reports"
STAGING_DIR = RUNTIME_ROOT / "staging" / "NotebookLM"
FIRST_SEEN_FILE = STATE_DIR / "notebooklm_first_seen.json"
CARD_INDEX_FILE = STATE_DIR / "notebooklm_card_index.json"
REPORT_JSON = REPORT_DIR / "latest.json"
REPORT_MD = REPORT_DIR / "latest.md"
REMOTE_REPO_ALLOWLIST = Path(
    os.environ.get("TL_DAILY_REVIEW_ALLOWLIST", str(SKILL_ROOT / "repo_allowlist.txt"))
)
DIR_ALLOWLIST_PATH = Path(
    os.environ.get("TL_DAILY_REVIEW_DIR_ALLOWLIST", str(SKILL_ROOT / "dir_allowlist.txt"))
)
# 扫描时跳过的目录名（精确匹配）和文件后缀（glob 匹配）
DISK_IGNORE_DIR_NAMES = {
    ".git", ".svn", ".hg", "__pycache__", "node_modules",
    ".obsidian", ".trash", "venv", ".venv", "env",
    ".next", ".nuxt", "dist", "build", ".cache", ".pytest_cache",
    "DerivedData", ".gradle", ".idea",
}
DISK_IGNORE_FILE_SUFFIXES = {
    ".pyc", ".pyo", ".class", ".o", ".so", ".dylib",
    ".lock", ".DS_Store", ".swp", ".swo",
}
GH_CONFIG_DIR = Path(
    os.environ.get(
        "TL_DAILY_REVIEW_GH_CONFIG_DIR", str(Path.home() / ".config" / "gh")
    )
).expanduser()
GH_ENV_OVERRIDE_KEYS = (
    "GH_TOKEN",
    "GITHUB_TOKEN",
    "GH_ENTERPRISE_TOKEN",
    "GITHUB_ENTERPRISE_TOKEN",
)

# Agent History Bank (ahb) 集成
AHB_CONFIG = Path(
    os.environ.get(
        "TL_DAILY_REVIEW_AHB_CONFIG", str(Path.home() / ".ahb" / "config.toml")
    )
).expanduser()
AGENT_HISTORY_ROOT = VAULT_ROOT / "Agent History"
AGENT_HISTORY_DAILY_DIR = AGENT_HISTORY_ROOT / "Daily"


class CommandError(RuntimeError):
    pass


@dataclass
class Window:
    start: datetime
    end: datetime

    @property
    def gh_since(self) -> str:
        return self.start.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")

    @property
    def gh_until(self) -> str:
        return self.end.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")

    @property
    def git_since(self) -> str:
        return self.start.strftime("%Y-%m-%d %H:%M:%S %Z")

    @property
    def git_until(self) -> str:
        return self.end.strftime("%Y-%m-%d %H:%M:%S %Z")


def ensure_dirs() -> None:
    for path in (STATE_DIR, REPORT_DIR, STAGING_DIR):
        path.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_lines(path: Path) -> set[str]:
    if not path.exists():
        return set()
    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            lines.append(line)
    return set(lines)


def run_cmd(
    args: list[str],
    *,
    timeout: int = 180,
    retries: int = 1,
    retry_delay: float = 2.0,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> str:
    last_err = None
    for attempt in range(1, retries + 1):
        proc = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        if proc.returncode == 0:
            return proc.stdout
        last_err = (
            f"cmd={shlex.join(args)} rc={proc.returncode} "
            f"stdout={proc.stdout.strip()} stderr={proc.stderr.strip()}"
        )
        if attempt < retries:
            time.sleep(retry_delay * attempt)
    raise CommandError(last_err or shlex.join(args))


def is_transient_network_error(message: str) -> bool:
    lowered = message.lower()
    patterns = (
        "error connecting to",
        "temporary failure in name resolution",
        "nodename nor servname provided",
        "connection reset by peer",
        "connection refused",
        "connection timed out",
        "operation timed out",
        "network is unreachable",
        "no route to host",
        "tls handshake timeout",
        "eof",
    )
    return any(pattern in lowered for pattern in patterns)


def build_gh_env() -> tuple[dict[str, str], list[str]]:
    env = os.environ.copy()
    stripped_keys = [key for key in GH_ENV_OVERRIDE_KEYS if env.pop(key, None)]
    env.pop("XDG_CONFIG_HOME", None)
    env["GH_CONFIG_DIR"] = str(GH_CONFIG_DIR)
    return env, stripped_keys


GH_ENV, GH_STRIPPED_KEYS = build_gh_env()


def run_gh_cmd(
    args: list[str],
    *,
    timeout: int = 180,
    retries: int = 1,
    retry_delay: float = 2.0,
    cwd: Path | None = None,
) -> str:
    last_exc: CommandError | None = None
    attempts = max(retries, 1)
    for attempt in range(1, attempts + 1):
        try:
            return run_cmd(
                ["gh", *args],
                timeout=timeout,
                retries=1,
                retry_delay=retry_delay,
                cwd=cwd,
                env=GH_ENV,
            )
        except CommandError as exc:
            last_exc = exc
            if attempt >= attempts or not is_transient_network_error(str(exc)):
                break
            time.sleep(retry_delay * attempt)
    raise CommandError(str(last_exc) if last_exc else shlex.join(["gh", *args]))


def check_gh_auth() -> dict[str, Any]:
    diagnostics: dict[str, Any] = {
        "gh_path": shutil.which("gh") or "",
        "gh_config_dir": str(GH_CONFIG_DIR),
        "gh_config_exists": GH_CONFIG_DIR.exists(),
        "stripped_env_overrides": GH_STRIPPED_KEYS,
        "status_ok": False,
        "api_ok": False,
    }
    try:
        status_output = run_gh_cmd(["auth", "status"], retries=2)
        diagnostics["status_ok"] = True
        diagnostics["status_output"] = status_output.strip()
    except CommandError as exc:
        diagnostics["status_error"] = str(exc)

    try:
        login = run_gh_cmd(["api", "user", "--jq", ".login"], timeout=30, retries=2).strip()
        diagnostics["api_ok"] = True
        diagnostics["api_login"] = login
    except CommandError as exc:
        diagnostics["api_error"] = str(exc)

    return diagnostics


def check_url(url: str, timeout: int = 10, retries: int = 3) -> dict[str, Any]:
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                return {"ok": True, "status": resp.status, "url": url}
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            if attempt < retries:
                time.sleep(attempt)
    return {"ok": False, "url": url, "error": last_error}


def resolve_host(host: str) -> dict[str, Any]:
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "host": host, "error": str(exc)}
    addresses = []
    for info in infos:
        addr = info[4][0]
        if addr not in addresses:
            addresses.append(addr)
    return {"ok": True, "host": host, "addresses": addresses}


def wait_for_service(
    *,
    name: str,
    url: str,
    host: str,
    timeout: int = 90,
    interval: int = 5,
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    deadline = time.time() + timeout
    while True:
        resolved = resolve_host(host)
        reachable = check_url(url, timeout=10, retries=1)
        attempt = {
            "at": datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S %Z"),
            "resolve": resolved,
            "url": reachable,
        }
        attempts.append(attempt)
        if resolved.get("ok") and reachable.get("ok"):
            return {
                "ok": True,
                "name": name,
                "host": host,
                "url": url,
                "attempts": attempts,
            }
        if time.time() >= deadline:
            return {
                "ok": False,
                "name": name,
                "host": host,
                "url": url,
                "attempts": attempts,
            }
        time.sleep(interval)


def summarize_service_wait(wait_result: dict[str, Any]) -> dict[str, Any]:
    attempts = wait_result.get("attempts", [])
    last = attempts[-1] if attempts else {}
    last_resolve = last.get("resolve")
    last_url = last.get("url")
    summary = {
        "ok": wait_result.get("ok", False),
        "host": wait_result.get("host", ""),
        "url": wait_result.get("url", ""),
        "attempt_count": len(attempts),
        "last_resolve": last_resolve,
        "last_url": last_url,
    }
    if not wait_result.get("ok", False):
        errors = []
        if last_resolve and not last_resolve.get("ok", False):
            errors.append(f"DNS: {last_resolve.get('error', 'unknown')}")
        if last_url and not last_url.get("ok", False):
            errors.append(f"URL: {last_url.get('error', 'unknown')}")
        if errors:
            summary["failure_summary"] = " | ".join(errors)
    return summary


def collect_network_context() -> dict[str, Any]:
    context: dict[str, Any] = {
        "resolved_hosts": {
            "api.github.com": resolve_host("api.github.com"),
            "notebooklm.google.com": resolve_host("notebooklm.google.com"),
        },
    }
    try:
        dns_output = run_cmd(["scutil", "--dns"], timeout=20, retries=1)
        context["dns_excerpt"] = "\n".join(dns_output.splitlines()[:40])
    except Exception as exc:  # noqa: BLE001
        context["dns_excerpt_error"] = str(exc)
    return context


def compute_window(now: datetime | None = None) -> Window:
    end = now or datetime.now(TZ)
    yesterday = (end - timedelta(days=1)).date()
    start = datetime.combine(yesterday, dtime.min, TZ)
    return Window(start=start, end=end)


def repo_slug_from_remote(remote: str) -> str | None:
    remote = remote.strip()
    patterns = [
        r"git@github\.com:(?P<slug>[^ ]+?)(?:\.git)?$",
        r"https://github\.com/(?P<slug>[^ ]+?)(?:\.git)?$",
        r"https://[^@]+@github\.com/(?P<slug>[^ ]+?)(?:\.git)?$",
    ]
    for pattern in patterns:
        match = re.search(pattern, remote)
        if match:
            return match.group("slug")
    return None


def discover_repos() -> list[Path]:
    repos: list[Path] = []
    seen: set[tuple[int, int]] = set()
    for root in REPO_ROOTS:
        if not root.exists():
            continue
        out = run_cmd(
            ["find", str(root), "-maxdepth", "3", "-name", ".git", "-type", "d"],
            retries=1,
        )
        for line in out.splitlines():
            repo = Path(line).parent.resolve()
            stat = repo.stat()
            key = (stat.st_dev, stat.st_ino)
            if key not in seen:
                seen.add(key)
                repos.append(repo)
    repos.sort()
    return repos


def collect_git_data(window: Window, *, gh_api_enabled: bool) -> dict[str, Any]:
    repos = discover_repos()
    remote_results: list[dict[str, Any]] = []
    local_results: list[dict[str, Any]] = []
    remote_failures: list[dict[str, Any]] = []
    checked_slugs: set[str] = set()
    allowlist = load_lines(REMOTE_REPO_ALLOWLIST)
    repo_local_commit_count: dict[str, int] = {}

    for repo in repos:
        try:
            local_out = run_cmd(
                [
                    "git",
                    "-C",
                    str(repo),
                    "log",
                    f"--since={window.git_since}",
                    f"--until={window.git_until}",
                    "--pretty=format:%H\t%h\t%ai\t%s",
                ],
                retries=1,
            )
        except CommandError as exc:
            if "does not have any commits yet" in str(exc):
                local_out = ""
            else:
                raise
        if local_out.strip():
            for line in local_out.splitlines():
                full_sha, short_sha, authored_at, subject = line.split("\t", 3)
                local_results.append(
                    {
                        "repo_path": str(repo),
                        "short_sha": short_sha,
                        "sha": full_sha,
                        "authored_at": authored_at,
                        "subject": subject,
                    }
                )
            repo_local_commit_count[str(repo)] = len(local_out.splitlines())

        try:
            remote = run_cmd(
                ["git", "-C", str(repo), "remote", "get-url", "origin"], retries=1
            ).strip()
        except CommandError:
            continue
        slug = repo_slug_from_remote(remote)
        if not slug or slug in checked_slugs:
            continue
        has_local_activity = repo_local_commit_count.get(str(repo), 0) > 0
        if not has_local_activity and slug not in allowlist:
            continue
        checked_slugs.add(slug)
        if not gh_api_enabled:
            remote_failures.append(
                {
                    "repo_slug": slug,
                    "error": "GitHub API unavailable during this run; remote verification skipped",
                }
            )
            continue
        try:
            payload = run_gh_cmd(
                [
                    "api",
                    f"repos/{slug}/commits?since={window.gh_since}&until={window.gh_until}&per_page=100",
                ],
                timeout=30,
                retries=5,
                retry_delay=3.0,
            )
            data = json.loads(payload)
            commits = []
            for item in data:
                message = item["commit"]["message"].splitlines()[0]
                commits.append(
                    {
                        "repo_slug": slug,
                        "sha": item["sha"],
                        "short_sha": item["sha"][:7],
                        "authored_at": item["commit"]["author"]["date"],
                        "subject": message,
                    }
                )
            if commits:
                remote_results.extend(commits)
        except Exception as exc:  # noqa: BLE001
            remote_failures.append({"repo_slug": slug, "error": str(exc)})

    return {
        "repo_count": len(repos),
        "remote_checked_repo_count": len(checked_slugs),
        "local_commits": local_results,
        "remote_commits": remote_results,
        "remote_failures": remote_failures,
    }


def collect_obsidian_changes(window: Window) -> dict[str, Any]:
    new_files: list[dict[str, Any]] = []
    modified_files: list[dict[str, Any]] = []
    start_ts = window.start.timestamp()
    end_ts = window.end.timestamp()
    for path in VAULT_ROOT.rglob("*.md"):
        if ".obsidian" in path.parts:
            continue
        stat = path.stat()
        birth = getattr(stat, "st_birthtime", stat.st_ctime)
        mtime = stat.st_mtime
        rel = str(path.relative_to(VAULT_ROOT))
        if start_ts <= birth <= end_ts:
            new_files.append(
                {
                    "path": rel,
                    "birth": datetime.fromtimestamp(birth, TZ).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    "mtime": datetime.fromtimestamp(mtime, TZ).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                }
            )
        elif birth < start_ts <= mtime <= end_ts:
            modified_files.append(
                {
                    "path": rel,
                    "birth": datetime.fromtimestamp(birth, TZ).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    "mtime": datetime.fromtimestamp(mtime, TZ).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                }
            )
    new_files.sort(key=lambda item: item["birth"])
    modified_files.sort(key=lambda item: item["mtime"])
    return {"new_files": new_files, "modified_files": modified_files}


def collect_disk_changes(window: Window) -> dict[str, Any]:
    """扫描 dir_allowlist 中的目录，返回时间窗口内有变更的文件。

    与 collect_obsidian_changes / collect_git_data 互补：
    覆盖 vault 和 git 仓库之外的工作产出（PPT、文档、代码等）。
    """
    allowlist_path = DIR_ALLOWLIST_PATH
    scan_roots = sorted(load_lines(allowlist_path))
    if not scan_roots:
        return {"scanned": False, "scan_roots": [], "groups": [], "total_files": 0}

    start_ts = window.start.timestamp()
    end_ts = window.end.timestamp()
    new_files: list[dict[str, Any]] = []
    modified_files: list[dict[str, Any]] = []

    for root_str in scan_roots:
        root = Path(root_str).expanduser()
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            # 原地修改 dirnames 可以阻止 os.walk 递归进去
            dirnames[:] = [
                d for d in dirnames
                if d not in DISK_IGNORE_DIR_NAMES and not d.startswith("~$")
            ]
            for fname in filenames:
                if fname.startswith("~$") or fname in DISK_IGNORE_FILE_SUFFIXES:
                    continue
                fpath = Path(dirpath) / fname
                suffix = fpath.suffix.lower()
                if suffix in DISK_IGNORE_FILE_SUFFIXES:
                    continue
                try:
                    stat = fpath.stat()
                except OSError:
                    continue
                birth = getattr(stat, "st_birthtime", stat.st_ctime)
                mtime = stat.st_mtime
                try:
                    rel = str(fpath.relative_to(root))
                except ValueError:
                    rel = str(fpath)
                if start_ts <= birth <= end_ts:
                    new_files.append({
                        "root": root_str,
                        "path": rel,
                        "birth": datetime.fromtimestamp(birth, TZ).strftime("%Y-%m-%d %H:%M:%S"),
                        "mtime": datetime.fromtimestamp(mtime, TZ).strftime("%Y-%m-%d %H:%M:%S"),
                        "suffix": suffix or "(none)",
                        "size": stat.st_size,
                    })
                elif birth < start_ts <= mtime <= end_ts:
                    modified_files.append({
                        "root": root_str,
                        "path": rel,
                        "birth": datetime.fromtimestamp(birth, TZ).strftime("%Y-%m-%d %H:%M:%S"),
                        "mtime": datetime.fromtimestamp(mtime, TZ).strftime("%Y-%m-%d %H:%M:%S"),
                        "suffix": suffix or "(none)",
                        "size": stat.st_size,
                    })

    new_files.sort(key=lambda x: x["birth"], reverse=True)
    modified_files.sort(key=lambda x: x["mtime"], reverse=True)

    # 按 root + 一级子目录分组汇总
    groups: list[dict[str, Any]] = []
    group_map: dict[str, dict[str, Any]] = {}
    all_changes = new_files + modified_files
    for item in all_changes:
        parts = PurePosixPath(item["path"]).parts
        if len(parts) >= 2:
            group_key = f"{Path(item['root']).name}/{parts[0]}"
        else:
            group_key = pathlib.Path(item["root"]).name
        if group_key not in group_map:
            group_map[group_key] = {"group": group_key, "count": 0, "suffixes": {}}
        g = group_map[group_key]
        g["count"] += 1
        g["suffixes"][item["suffix"]] = g["suffixes"].get(item["suffix"], 0) + 1
    for g in group_map.values():
        g["suffixes"] = dict(sorted(g["suffixes"].items(), key=lambda x: -x[1]))
        groups.append(g)
    groups.sort(key=lambda x: -x["count"])

    return {
        "scanned": True,
        "scan_roots": scan_roots,
        "groups": groups,
        "new_files": new_files,
        "modified_files": modified_files,
        "total_files": len(new_files) + len(modified_files),
    }


def sanitize_title(title: str) -> str:
    title = re.sub(r"[\\/:*?\"<>|]+", "-", title).strip()
    title = re.sub(r"\s+", " ", title)
    return title or "未命名"


def is_writable_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except Exception:  # noqa: BLE001
        return False


def find_existing_card(card_index: dict[str, str], notebook_id: str) -> Path | None:
    indexed = card_index.get(notebook_id)
    if indexed:
        path = Path(indexed)
        if path.exists():
            return path
    for path in NOTEBOOKLM_ROOT.rglob("*.md"):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if f"notebooklm_id: {notebook_id}" in text:
            return path
    return None


def stable_time_from_existing_card(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None
    match = re.search(
        r"\|\s*创建时间（`notebooklm list --json`，归档依据）\s*\|\s*`([^`]+)`",
        text,
    )
    if match:
        return match.group(1).strip()
    match = re.search(r'^created:\s*"([^"]+)"', text, re.M)
    if match:
        return f"{match.group(1)}T00:00:00"
    return None


def parse_note_ids(raw: str) -> list[str]:
    if "No notes found" in raw:
        return []
    ids: list[str] = []
    for match in re.finditer(r"\b[0-9a-f]{8}(?:-[0-9a-f]{4,12})?", raw, re.I):
        note_id = match.group(0)
        if note_id not in ids:
            ids.append(note_id)
    return ids


def split_first_sentence(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return "待补写。"
    parts = re.split(r"(?<=[。！？.!?])\s*", text, maxsplit=1)
    sentence = parts[0].strip()
    return sentence if sentence.endswith(("。", "！", "？", ".", "!", "?")) else f"{sentence}。"


def render_card(
    *,
    notebook_id: str,
    title: str,
    stable_created_at: str,
    observed_created_ats: list[str],
    source_items: list[dict[str, Any]],
    notes: list[dict[str, str]],
    summary_text: str,
    card_date: str,
) -> str:
    source_titles = ", ".join(item["title"] for item in source_items) or "未知"
    note_value = "无" if not notes else f"{len(notes)} 条"
    observed_text = " / ".join(observed_created_ats) or "无"
    source_lines = "\n".join(
        f"- `{item['title']}`（{item.get('type', 'unknown')}，created_at: {item.get('created_at', 'unknown')}）"
        for item in source_items
    )
    if not source_lines:
        source_lines = "- 无"
    note_lines = "无"
    if notes:
        blocks = []
        for note in notes:
            blocks.append(f"### Note {note['id']}\n\n{note['content'].strip()}")
        note_lines = "\n\n".join(blocks)
    first_sentence = split_first_sentence(summary_text)
    return f"""---
created: "{card_date}"
updated: "{datetime.now(TZ).strftime("%Y-%m-%d")}"
tags:
  - NotebookLM
  - 收件箱
type: notebooklm-import
status: inbox
notebooklm_id: {notebook_id}
---

# {title}

## 元数据

| 字段 | 内容 |
| --- | --- |
| NotebookLM ID | `{notebook_id}` |
| 首次稳定时间（本地缓存） | `{stable_created_at}` |
| 本次 `list --json` 观测时间 | `{observed_text}` |
| 来源文件 | `{source_titles}` |
| NotebookLM note | {note_value} |

## 一句话核心观点

{first_sentence}

## NotebookLM 摘要

{summary_text.strip() or "暂无摘要。"}

## Source 列表

{source_lines}

## NotebookLM Notes

{note_lines}
"""


def collect_notebooklm(window: Window, *, service_ready: bool) -> dict[str, Any]:
    first_seen = load_json(FIRST_SEEN_FILE, {})
    card_index = load_json(CARD_INDEX_FILE, {})
    if not service_ready:
        save_json(FIRST_SEEN_FILE, first_seen)
        save_json(CARD_INDEX_FILE, card_index)
        return {
            "imported_items": [],
            "failures": [
                {
                    "id": "__service_wait__",
                    "title": "NotebookLM service readiness",
                    "error": "NotebookLM network preflight did not become ready within timeout",
                }
            ],
        }
    imported_items: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    try:
        raw = run_cmd(["notebooklm", "list", "--json"], retries=3)
        notebooks = json.loads(raw)["notebooks"]
    except (CommandError, json.JSONDecodeError, KeyError) as exc:
        save_json(FIRST_SEEN_FILE, first_seen)
        save_json(CARD_INDEX_FILE, card_index)
        return {
            "imported_items": imported_items,
            "failures": [
                {
                    "id": "__notebooklm_list__",
                    "title": "NotebookLM list",
                    "error": str(exc),
                }
            ],
        }

    for nb in notebooks:
        notebook_id = nb["id"]
        title = nb["title"]
        observed_created_at = nb["created_at"]
        cached = first_seen.get(notebook_id)
        existing_card = find_existing_card(card_index, notebook_id)
        existing_card_time = (
            stable_time_from_existing_card(existing_card) if existing_card else None
        )
        if not cached:
            cached = {
                "title": title,
                "first_seen_created_at": existing_card_time or observed_created_at,
                "observed_created_ats": [observed_created_at],
                "card_path": str(existing_card) if existing_card else None,
                "first_seen_at": datetime.now(TZ).isoformat(),
            }
            first_seen[notebook_id] = cached
        else:
            cached["title"] = title
            if existing_card_time:
                cached["first_seen_created_at"] = existing_card_time
            observed = cached.setdefault("observed_created_ats", [])
            if observed_created_at not in observed:
                observed.append(observed_created_at)
            if existing_card and not cached.get("card_path"):
                cached["card_path"] = str(existing_card)

        stable_created_at = cached["first_seen_created_at"]
        try:
            stable_dt = datetime.fromisoformat(stable_created_at)
        except ValueError:
            failures.append(
                {"id": notebook_id, "title": title, "error": "invalid first_seen_created_at"}
            )
            continue
        if cached.get("card_path"):
            card_index[notebook_id] = cached["card_path"]
            continue
        if not (window.start <= stable_dt.astimezone(TZ) <= window.end):
            continue

        try:
            metadata_raw = run_cmd(
                ["notebooklm", "metadata", "-n", notebook_id, "--json"],
                retries=3,
            )
            metadata = json.loads(metadata_raw)
            source_list_raw = run_cmd(
                ["notebooklm", "source", "list", "-n", notebook_id, "--json"],
                retries=3,
            )
            source_list = json.loads(source_list_raw)["sources"]
            note_list_raw = run_cmd(
                ["notebooklm", "note", "list", "-n", notebook_id],
                retries=3,
            )
            note_ids = parse_note_ids(note_list_raw)
            notes = []
            for note_id in note_ids:
                content = run_cmd(
                    ["notebooklm", "note", "get", note_id, "-n", notebook_id],
                    retries=3,
                )
                notes.append({"id": note_id, "content": content.strip()})
            summary_text = run_cmd(
                ["notebooklm", "summary", "-n", notebook_id],
                retries=3,
            )
            if summary_text.startswith("Summary:"):
                summary_text = summary_text.split("Summary:", 1)[1].strip()

            card_day = stable_dt.astimezone(TZ).strftime("%Y-%m-%d")
            month_key = card_day[:7]
            preferred_dir = NOTEBOOKLM_ROOT / month_key
            use_staging = not is_writable_dir(preferred_dir)
            target_dir = STAGING_DIR / month_key if use_staging else preferred_dir
            target_dir.mkdir(parents=True, exist_ok=True)
            card_path = target_dir / f"{card_day}-{sanitize_title(title)}.md"
            card_content = render_card(
                notebook_id=notebook_id,
                title=title,
                stable_created_at=stable_created_at,
                observed_created_ats=cached["observed_created_ats"],
                source_items=source_list or metadata.get("sources", []),
                notes=notes,
                summary_text=summary_text,
                card_date=card_day,
            )
            card_path.write_text(card_content, encoding="utf-8")
            cached["card_path"] = str(card_path)
            card_index[notebook_id] = str(card_path)
            imported_items.append(
                {
                    "id": notebook_id,
                    "title": title,
                    "stable_created_at": stable_created_at,
                    "observed_created_ats": cached["observed_created_ats"],
                    "source_titles": [item["title"] for item in source_list],
                    "note_count": len(notes),
                    "card_path": str(card_path),
                    "used_staging": use_staging,
                    "summary_first_sentence": split_first_sentence(summary_text),
                }
            )
        except Exception as exc:  # noqa: BLE001
            failures.append({"id": notebook_id, "title": title, "error": str(exc)})

    save_json(FIRST_SEEN_FILE, first_seen)
    save_json(CARD_INDEX_FILE, card_index)
    return {"imported_items": imported_items, "failures": failures}


def find_ahb_bin() -> str | None:
    """按优先级探测 ahb 二进制路径。"""
    candidates = [
        os.environ.get("TL_DAILY_REVIEW_AHB_BIN", ""),
        shutil.which("ahb") or "",
        str(Path.home() / "Code" / "bradenwu" / "agent-history-bank" / "ahb"),
    ]
    for item in candidates:
        if item and Path(item).exists() and os.access(item, os.X_OK):
            return item
    return None


def run_ahb_sync(ahb_bin: str) -> tuple[bool, str]:
    """运行 ahb sync 增量归档最新 Agent 对话。

    接受退出码 0（成功）与 3（partial，部分会话含无法解析类型但不影响归档）。
    """
    try:
        proc = subprocess.run(
            [ahb_bin, "sync", "--config", str(AHB_CONFIG)],
            text=True,
            capture_output=True,
            timeout=600,
        )
        if proc.returncode in (0, 3):
            return True, (proc.stdout or proc.stderr).strip()
        detail = f"rc={proc.returncode} stderr={proc.stderr.strip()}"
        return False, detail[:300]
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:300]


_AHB_DAILY_LINE = re.compile(
    r"^-\s+\[\[(?P<link>[^\]|]+)(?:\|(?P<title>[^\]]+))?\]\]\s*·\s*(?P<ts>\S+)"
)


def _to_local_ts(raw: str) -> str:
    """把 ahb 透传的 ISO UTC 时间戳(带 ``Z``)换算为 CST 可读串。

    ahb Daily 笔记里的时间戳是 UTC(如 ``2026-08-10T00:07:05.684Z``);
    若直接用于叙事会把 UTC 当本地时间,造成"凌晨高密度协作"之类的时区误读。
    复用文件顶部的 ``TZ`` 常量(与其它 ``datetime.fromtimestamp(..., TZ)`` 一致)。
    解析失败时回退为原值,不阻断采集。
    """
    try:
        iso = raw.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso).astimezone(TZ)
        return dt.strftime("%Y-%m-%d %H:%M:%S %Z")
    except Exception:  # noqa: BLE001
        return raw


def parse_ahb_daily(path: Path) -> list[dict[str, Any]]:
    """解析 ahb Daily 笔记，提取会话条目。

    每行格式: ``- [[Sessions/…/id|标题]] · ISO 时间戳``
    """
    sessions: list[dict[str, Any]] = []
    if not path.exists():
        return sessions
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _AHB_DAILY_LINE.match(line)
        if not match:
            continue
        link = match.group("link")
        title = match.group("title") or link.rsplit("/", 1)[-1]
        raw_ts = match.group("ts")
        sessions.append(
            {
                "title": title,
                "link": link,
                "timestamp": _to_local_ts(raw_ts),
                "timestamp_utc": raw_ts,
            }
        )
    return sessions


def collect_agent_history(window: Window) -> dict[str, Any]:
    """先运行 ahb sync 归档最新 Agent 对话，再汇总时间窗口内每日的会话清单。

    ahb sync 是增量幂等的，每次运行只处理新增历史。
    采集后读取 ``Agent History/Daily/<日期>.md`` 中窗口内每一天的会话索引，
    作为每日复盘的 AI 对话事实基线。
    """
    ahb_bin = find_ahb_bin()
    sync_ok = False
    sync_detail = ""

    if ahb_bin:
        sync_ok, sync_detail = run_ahb_sync(ahb_bin)
    else:
        sync_detail = "ahb 二进制未找到（PATH 或 ~/Code/bradenwu/agent-history-bank/ahb 均不存在）"

    daily_entries: list[dict[str, Any]] = []
    day = window.start.date()
    end_day = window.end.date()
    while day <= end_day:
        daily_file = AGENT_HISTORY_DAILY_DIR / f"{day.isoformat()}.md"
        sessions = parse_ahb_daily(daily_file)
        if sessions:
            try:
                rel = str(daily_file.relative_to(VAULT_ROOT))
            except ValueError:
                rel = str(daily_file)
            daily_entries.append(
                {
                    "date": day.isoformat(),
                    "file": rel,
                    "session_count": len(sessions),
                    "sessions": sessions,
                }
            )
        day += timedelta(days=1)

    total = sum(item["session_count"] for item in daily_entries)
    return {
        "ahb_bin": ahb_bin or "",
        "ahb_config": str(AHB_CONFIG),
        "sync_ok": sync_ok,
        "sync_detail": sync_detail,
        "total_sessions": total,
        "daily_entries": daily_entries,
    }


def build_report(window: Window) -> dict[str, Any]:
    github_wait = wait_for_service(
        name="github_api",
        url="https://api.github.com",
        host="api.github.com",
    )
    notebooklm_wait = wait_for_service(
        name="notebooklm",
        url="https://notebooklm.google.com",
        host="notebooklm.google.com",
    )
    preflight = {
        "github_api": summarize_service_wait(github_wait),
        "notebooklm": summarize_service_wait(notebooklm_wait),
    }
    gh_auth = (
        check_gh_auth()
        if github_wait.get("ok")
        else {
            "status_ok": False,
            "api_ok": False,
            "skipped_due_to_network": True,
            "reason": "GitHub preflight did not become ready within timeout",
            "gh_path": shutil.which("gh") or "",
            "gh_config_dir": str(GH_CONFIG_DIR),
            "gh_config_exists": GH_CONFIG_DIR.exists(),
            "stripped_env_overrides": GH_STRIPPED_KEYS,
        }
    )
    try:
        notebooklm_status = run_cmd(["notebooklm", "status"], retries=1).strip()
    except Exception as exc:  # noqa: BLE001
        notebooklm_status = f"ERROR: {exc}"
    gh_api_enabled = gh_auth.get("api_ok", False)
    git_data = collect_git_data(window, gh_api_enabled=gh_api_enabled)
    obsidian_data = collect_obsidian_changes(window)
    disk_data = collect_disk_changes(window)
    notebooklm_data = collect_notebooklm(
        window,
        service_ready=notebooklm_wait.get("ok", False),
    )
    agent_history_data = collect_agent_history(window)
    return {
        "generated_at": datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S %Z"),
        "window": {
            "start": window.start.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "end": window.end.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "gh_since": window.gh_since,
            "gh_until": window.gh_until,
        },
        "preflight": preflight,
        "gh_auth_status": gh_auth.get("status_output", gh_auth.get("status_error", "")).strip(),
        "gh_auth_diagnostics": gh_auth,
        "notebooklm_status": notebooklm_status,
        "network_context": collect_network_context(),
        "git": git_data,
        "obsidian": obsidian_data,
        "disk": disk_data,
        "notebooklm": notebooklm_data,
        "agent_history": agent_history_data,
    }


def render_report_md(report: dict[str, Any]) -> str:
    gh_diag = report.get("gh_auth_diagnostics", {})
    gh_auth_mode = "OK" if gh_diag.get("api_ok") else "WARN"
    gh_auth_source = "keyring" if gh_diag.get("status_ok") else "diagnostic-only"
    github_preflight = report["preflight"]["github_api"]
    notebooklm_preflight = report["preflight"]["notebooklm"]
    lines = [
        "# Daily Review Report",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- 窗口：{report['window']['start']} -> {report['window']['end']}",
        "",
        "## 预检",
        f"- GitHub API：{'OK' if github_preflight['ok'] else 'FAIL'}（尝试 {github_preflight['attempt_count']} 次）",
        f"- NotebookLM：{'OK' if notebooklm_preflight['ok'] else 'FAIL'}（尝试 {notebooklm_preflight['attempt_count']} 次）",
        f"- GitHub Auth：{gh_auth_mode} ({gh_auth_source}, {gh_diag.get('gh_config_dir', '')})",
        "",
        "## Git",
        f"- 扫描仓库数：{report['git']['repo_count']}",
        f"- 远端校验仓库数：{report['git']['remote_checked_repo_count']}",
        f"- 本地 commits：{len(report['git']['local_commits'])}",
        f"- 远端 commits：{len(report['git']['remote_commits'])}",
        f"- 远端失败：{len(report['git']['remote_failures'])}",
        "",
        "## Obsidian",
        f"- 新增：{len(report['obsidian']['new_files'])}",
        f"- 修改：{len(report['obsidian']['modified_files'])}",
        "",
        "## 磁盘文件变更（vault 外）",
        f"- 扫描目录：{', '.join(report.get('disk', {}).get('scan_roots', [])) or '未配置'}",
        f"- 新增：{len(report.get('disk', {}).get('new_files', []))}",
        f"- 修改：{len(report.get('disk', {}).get('modified_files', []))}",
        "",
        "## NotebookLM",
        f"- 新导入：{len(report['notebooklm']['imported_items'])}",
        f"- 导入失败：{len(report['notebooklm']['failures'])}",
        "",
    ]
    ahb_data = report.get("agent_history", {})
    if ahb_data:
        lines.extend(
            [
                "## Agent History（AI 对话）",
                f"- ahb：{ahb_data.get('ahb_bin') or '未找到'}",
                f"- ahb sync：{'OK' if ahb_data.get('sync_ok') else 'FAIL'}",
            ]
        )
        if not ahb_data.get("sync_ok") and ahb_data.get("sync_detail"):
            lines.append(f"- sync 详情：{ahb_data['sync_detail'][:200]}")
        lines.append(
            f"- 窗口内会话总数：{ahb_data.get('total_sessions', 0)}"
        )
        lines.append("")
    if github_preflight.get("failure_summary") or notebooklm_preflight.get("failure_summary"):
        lines.append("### 预检失败摘要")
        if github_preflight.get("failure_summary"):
            lines.append(f"- GitHub API：{github_preflight['failure_summary']}")
        if notebooklm_preflight.get("failure_summary"):
            lines.append(f"- NotebookLM：{notebooklm_preflight['failure_summary']}")
        lines.append("")
    if report["notebooklm"]["imported_items"]:
        lines.append("### 新导入卡片")
        for item in report["notebooklm"]["imported_items"]:
            lines.append(
                f"- {item['title']} -> {item['card_path']} "
                f"（来源：{', '.join(item['source_titles']) or '无'}）"
            )
        lines.append("")
    if report["git"]["remote_failures"]:
        lines.append("### 远端失败")
        for item in report["git"]["remote_failures"]:
            lines.append(f"- {item['repo_slug']}: {item['error']}")
        lines.append("")
    if report["notebooklm"]["failures"]:
        lines.append("### NotebookLM 失败")
        for item in report["notebooklm"]["failures"]:
            lines.append(f"- {item['title']} ({item['id']}): {item['error']}")
        lines.append("")
    ahb_data = report.get("agent_history", {})
    for entry in ahb_data.get("daily_entries", []):
        lines.append(f"### Agent History · {entry['date']}（{entry['session_count']} 个会话）")
        for sess in entry["sessions"]:
            lines.append(f"- {sess['title']} · {sess['timestamp']}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--print-json", action="store_true")
    args = parser.parse_args()

    ensure_dirs()
    report = build_report(compute_window())
    save_json(REPORT_JSON, report)
    REPORT_MD.write_text(render_report_md(report), encoding="utf-8")
    if args.print_json:
        json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        print(REPORT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
