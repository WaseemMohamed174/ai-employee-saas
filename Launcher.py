#!/usr/bin/env python3
"""Project Launcher - a standalone, project-agnostic terminal launcher for full-stack projects.

This file is a template: copy it into the root of any project, edit the CONFIG section below (name, environments, services, questions...)
and leave the rest of the file as is. No external libraries: standard Python only.

What it does
    1. Libraries   Python virtual environments, missing/outdated package detection (name + version + markers),
                   install from PyPI or from an offline "central library" of .whl files. Cached by requirements hash.
    2. Selection   Config-driven questions (choice / workers / number / bool / text), saved and reusable.
                   A choice can require API keys: asked hidden and saved in .env (chmod 600).
    3. Prepare     .env schema (required, generated secrets, defaults), data folders, frontend install + build.
                   Node.js is downloaded privately (sha256-checked) when missing; npm / pnpm / yarn / bun auto-detected.
    4. Launch      Starts every service of the profile (dev or prod), waits for health checks, supervises them
                   (auto-restart with backoff, prefixed live logs, graceful Ctrl+C) and runs hooks (migrations, seed...).

Usage
    python Launcher.py [command] [options]

Commands
    run        (default) full flow: libraries -> selection -> prepare -> launch, with the default profile
    dev        same as run --profile dev
    prod       same as run --profile prod
    setup      steps 1-3 only (install + prepare), nothing is launched. Good for CI / Docker builds
    doctor     diagnose this machine and this project (python, node, ports, .env, disk, network ...)
    status     show what is running right now
    stop       stop the running instance (services are stopped gracefully)
    logs [svc] list log files, or print the tail of one (-n LINES, -f to follow)
    clean      remove generated things (venvs, logs, node, frontend build, saved selection)
    init       create .env.example from the CONFIG schema and add the usual .gitignore lines
    config     print the resolved configuration
    demo       show every terminal component with sample data, changes nothing
    prompt     print the ready-made prompt to give an AI assistant so it configures this file for your project

Options
    --profile NAME     dev | prod | any profile you define (default: CONFIG["default_profile"])
    --auto             never ask, use saved or recommended choices (or <PREFIX>_AUTO=1)
    --reselect         ask the selection questions again even if a saved selection exists
    --recheck          re-verify installed libraries even if requirements did not change
    --central PATH     take missing libraries from this folder of .whl files (or <PREFIX>_CENTRAL=PATH)
    --no-frontend      do not install / build the frontend
    --no-venv          do not use virtual environments, use the current Python (handy for CI / testing)
    --no-browser       do not open the browser
    --quiet            do not stream service logs to the terminal (they are still written to files)
    --host H --port P  override host / main port
    -e KEY=VALUE       set an environment variable for this run (repeatable)
    --force            init: overwrite .env.example / run: start even if another instance is running
    -h, --help         show this text

Environment (PREFIX = CONFIG["slug"] upper-cased, or CONFIG["env_prefix"])
    <PREFIX>_HOST  <PREFIX>_PORT  <PREFIX>_PORT_<NAME>  <PREFIX>_DATA_DIR  <PREFIX>_AUTO  <PREFIX>_CENTRAL
    <PREFIX>_NODE_MIRROR   alternative to https://nodejs.org/dist for the Node.js download
    NO_COLOR=1             no colors at all

Config precedence (highest first):  real environment  >  .env.<profile>  >  .env.local  >  .env  >  defaults in CONFIG.
Per-machine tweaks of CONFIG itself can go in an optional launcher.json next to this file (deep-merged).

Placeholders usable in commands / env / urls / health checks:
    {host} {port} {port.NAME} {profile} {root} {data} {runtime} {logs} {py} {py.ENVNAME} {pm} {node}
    {sel.QUESTION_ID} {env.ANY_ENV_VAR} {i} (instance number when a service has "count")
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import http.client
import importlib
import json
import os
import platform
import re
import secrets
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import threading
import time
import unicodedata
import urllib.error
import urllib.request
import uuid
import webbrowser
import zipfile
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace


# =====================================================================================================
# AI_PROMPT  -  Copy this text and give it to any AI along with this file so it configures it for your project. (Or run: python Launcher.py prompt)
# =====================================================================================================
AI_PROMPT = """\
The attached file Launcher.py is a general launcher for any fullstack project (not tied to any previous project).
The task: configure it for my current project.

Rules:
- Edit the CONFIG dictionary only (or create launcher.json beside the file), and never touch the rest of the file. The rest of the file is the engine.
- The examples in CONFIG (FastAPI / Vite / uvicorn / sqlite) are only illustrative samples, not assumptions about my project.
- Build the configuration from the actual project structure: read the requirements files, package.json, and how each service is started.
- Define: name and slug, environments (a venv for each Python part), env_vars (the variables that must go in .env),
  questions (if there are user choices such as the database or provider), services (start commands and the health check),
  hooks (migrations and others), and urls (the links shown after launch).
- Use placeholders like {port}, {host}, {py.ENVNAME}, {pm}, and {sel.ID} instead of writing fixed values.
- If something isn't clear from the project, ask me and don't guess.
- At the end tell me to run: python Launcher.py doctor , and then: python Launcher.py setup
"""


# =====================================================================================================
# CONFIG  -  This is the only part you edit for each new project. Everything below it is generic and must not change.
# (You can also put a partial override in launcher.json beside the file instead of editing here.)
# =====================================================================================================
CONFIG = {
    # ------------------------------------------------------------------ identity
    "name": "AI Employee",
    "slug": "shop-assistant",       # lowercase, no spaces. Env-var prefix: SHOP_ASSISTANT_PORT ...
    "version": "0.1.0",
    "tagline": "AI assistant SaaS for e-commerce stores",
    "env_prefix": None,             # None = slug upper-cased
    "python_min": (3, 10),

    # ------------------------------------------------------------------ run settings
    "profiles": ["dev", "prod"],
    "default_profile": "dev",
    "host": "127.0.0.1",
    "ports": {"main": 8000, "web": 5173},
    "data_dir": ".venv",            # runtime files live in <data_dir>/runtime (venvs, logs, state, node)
    "data_subdirs": ["database/data"],   # tenant_<slug>.db and platform.db files live here
    "open_browser": True,
    "stream_logs": True,
    "log_max_mb": 5,
    "show_hardware": True,
    "run_inside_env": None,
    "central_hint": None,
    "node_mirror": None,

    # ------------------------------------------------------------------ python environments (one venv each)
    "environments": [
        {"name": "database", "requirements": "database/requirements.txt", "component": "Database", "required": True},
        {"name": "backend", "requirements": "backend/requirements.txt", "component": "Backend", "required": True},
    ],

    # ------------------------------------------------------------------ .env schema
    "env_vars": [
        {"name": "SECRET_KEY", "desc": "Signing key for sessions and tokens", "secret": True,
         "generate": "hex32", "required": True},
        {"name": "DATABASE_URL", "desc": "Platform DB connection string (tenant DBs auto-discovered in database/data/)",
         "default": "sqlite:///{root}/database/data/platform.db"},
        {"name": "API_PORT", "desc": "Main port the backend opens on (written by the Launcher from your port selection)",
         "default": "8000"},
        {"name": "AI_PROVIDER", "desc": "AI provider: mock (default, sandbox) | gemini | openai | anthropic",
         "default": "mock"},
        {"name": "GEMINI_API_KEY", "desc": "Google Gemini API key (optional, needed for real AI)",
         "secret": True},
        {"name": "OPENAI_API_KEY", "desc": "OpenAI API key (optional)",
         "secret": True},
        {"name": "ANTHROPIC_API_KEY", "desc": "Anthropic API key (optional)",
         "secret": True},
        {"name": "JWT_ALGORITHM", "desc": "JWT signing algorithm", "default": "HS256"},
        {"name": "JWT_EXPIRE_MINUTES", "desc": "JWT token expiry in minutes (default 7 days)", "default": "10080"},
        {"name": "CORS_ORIGINS", "desc": "Comma-separated allowed CORS origins", "default": "*"},
        {"name": "RATE_LIMIT_PER_MINUTE", "desc": "API rate limit per key per minute", "default": "60"},
        {"name": "SMTP_HOST", "desc": "SMTP server host for email verification (optional)", "default": ""},
        {"name": "SMTP_PORT", "desc": "SMTP server port", "default": "587"},
        {"name": "SMTP_USER", "desc": "SMTP username", "default": ""},
        {"name": "SMTP_PASSWORD", "desc": "SMTP password", "secret": True},
        {"name": "SMTP_FROM_EMAIL", "desc": "From email for outgoing messages", "default": "noreply@shop-assistant.local"},
        {"name": "GOOGLE_OAUTH_CLIENT_ID", "desc": "Google OAuth client ID (optional)", "default": ""},
        {"name": "GOOGLE_OAUTH_CLIENT_SECRET", "desc": "Google OAuth client secret (optional)", "secret": True},
        {"name": "STRIPE_SECRET_KEY", "desc": "Stripe secret key (optional, for paid plans)", "secret": True},
        {"name": "STRIPE_WEBHOOK_SECRET", "desc": "Stripe webhook secret (optional)", "secret": True},
    ],

    # ------------------------------------------------------------------ selection questions (step 2)
    "questions": [
        {"id": "port", "type": "number", "title": "Main port", "min": 1024, "max": 65535, "default": 8000,
         "explain": "The port the project opens on. Examples: 8000 (default) · 8080 · 5000 — type any port "
                    "from 1024 to 65535; if the port is busy the launcher picks the next free one. "
                    "The final port is recorded in .env as API_PORT so integrations can find the backend."},
        {"id": "workers", "type": "workers", "title": "Server workers", "per_worker_gb": 0.3,
         "explain": "Each worker is a separate process that answers requests. More workers handle more users at the same moment; each uses about 0.3 GB of RAM."},
        {"id": "ai_provider", "type": "choice", "title": "AI provider",
         "prefer_configured": True,
         "explain": "Which AI service answers chat messages. Choose 'mock' to test the full pipeline without an API key. The key (when needed) is asked hidden and saved in .env.",
         "options": [
             {"value": "mock", "label": "Mock provider", "detail": "canned responses, no API key needed", "recommended": True,
              "env": {"AI_PROVIDER": "mock"}},
             {"value": "gemini", "label": "Google Gemini", "detail": "gemini-3.6-flash (default real provider)",
              "env": {"AI_PROVIDER": "gemini"}, "env_required": ["GEMINI_API_KEY"]},
             {"value": "openai", "label": "OpenAI", "detail": "gpt-4o-mini",
              "env": {"AI_PROVIDER": "openai"}, "env_required": ["OPENAI_API_KEY"]},
             {"value": "anthropic", "label": "Anthropic", "detail": "claude-3-5-haiku",
              "env": {"AI_PROVIDER": "anthropic"}, "env_required": ["ANTHROPIC_API_KEY"]},
         ]},
    ],

    # ------------------------------------------------------------------ frontend (Node: npm / pnpm / yarn / bun)
    "frontend": {
        "enabled": True,
        "dir": "frontend",
        "package_manager": "auto",
        "node_min": 18,
        "build_script": "build",
        "dist": "dist",
        "dist_marker": "index.html",
        "install_in": ["dev", "prod"],
        "build_in": ["prod"],
        # F15 field lesson (2026-11-15): unset, a failed npm install / vite build only WARNED
        # and the launch continued — the prod API then started with no SPA and every UI test
        # failed with confusing timeouts. The frontend is essential for this project: fail
        # the launch loudly instead (the error + the log tail print before the exit).
        "required": True,
        "watch": ["package.json", "index.html", "vite.config.ts", "tsconfig.json", "src", "public"],
    },

    # ------------------------------------------------------------------ hooks (commands around the launch)
    "hooks": {
        "before_launch": [
            {"name": "Database init", "cwd": "database", "venv": "database",
             "cmd": ["{py.database}", "init_db.py"], "when_exists": "database/init_db.py"},
        ],
        "after_stop": [],
    },

    # ------------------------------------------------------------------ services (step 4)
    "services": [
        {"name": "api", "cwd": "backend", "venv": "backend", "when_exists": "backend/main.py",
         "cmd": ["{py.backend}", "-m", "uvicorn", "main:app", "--host", "{host}", "--port", "{port}"],
         "env": {"PYTHONPATH": "{root}"},
         "extra_args": {"dev": ["--reload"], "prod": ["--workers", "{sel.workers}"]},
         "health": "http://{host}:{port}/api/health", "restart": "on-failure"},
        {"name": "web", "cwd": "frontend", "when_exists": "frontend/package.json", "profiles": ["dev"],
         "cmd": ["{pm}", "run", "dev", "--", "--host", "{host}", "--port", "{port.web}"],
         "env": {"API_PROXY_TARGET": "http://{host}:{port}"},
         "health": "http://{host}:{port.web}/", "restart": "on-failure"},
    ],

    # ------------------------------------------------------------------ links shown when everything is up
    "urls": [
        {"label": "App", "url": "http://{host}:{port.web}/", "profiles": ["dev"], "open": True},
        {"label": "App", "url": "http://{host}:{port}/", "profiles": ["prod"], "open": True},
        {"label": "API docs", "url": "http://{host}:{port}/docs", "when_exists": "backend/main.py"},
    ],

    # ------------------------------------------------------------------ doctor
    # Docker was removed from the project (client decision, 2026-11-16) — git only now.
    "doctor": {"tools": ["git"], "min_disk_gb": 1.0},
}


# =====================================================================================================
# Section 1: loading the config + general helpers
# =====================================================================================================
BASE_DIR = Path(__file__).resolve().parent
_REAL_ENV = set(os.environ)          # variables that existed in the system before we read any file


def _deep_merge(dst: dict, src: dict) -> dict:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_merge(dst[k], v)
        else:
            dst[k] = v
    return dst


def _load_config() -> dict:
    cfg = copy.deepcopy(CONFIG)
    override = BASE_DIR / "launcher.json"
    if override.is_file():
        try:
            _deep_merge(cfg, json.loads(override.read_text(encoding="utf-8")))
        except (OSError, ValueError) as e:
            sys.exit(f"launcher.json is not valid JSON: {e}")
    cfg["python_min"] = tuple(cfg["python_min"])
    cfg.setdefault("ports", {}).setdefault("main", 8000)
    for key in ("environments", "env_vars", "questions", "services", "urls", "data_subdirs"):
        cfg[key] = list(cfg.get(key) or [])
    cfg["hooks"] = dict(cfg.get("hooks") or {})
    cfg["frontend"] = dict(cfg.get("frontend") or {})
    cfg["doctor"] = dict(cfg.get("doctor") or {})
    for e in cfg["environments"]:
        e.setdefault("component", e["name"].capitalize())
        e.setdefault("venv", True)
        e.setdefault("required", False)
        e.setdefault("pip_args", [])
        reqs = e.get("requirements")
        e["requirements"] = [reqs] if isinstance(reqs, str) else list(reqs or [])
    return cfg


CFG = _load_config()
if sys.version_info < CFG["python_min"]:
    sys.exit("Python %d.%d or newer is required." % CFG["python_min"][:2])

PREFIX = re.sub(r"[^A-Za-z0-9]+", "_", CFG.get("env_prefix") or CFG["slug"]).strip("_").upper()
PROFILES = list(CFG.get("profiles") or ["dev", "prod"])
ENV_SCHEMA = {s["name"]: s for s in CFG["env_vars"]}
NAME = CFG["name"]


def E(name: str) -> str:
    """Environment variable name with the project prefix: E('PORT') -> MYPROJECT_PORT."""
    return f"{PREFIX}_{name}"


def rel(p: Path | str) -> str:
    try:
        return str(Path(p).resolve().relative_to(BASE_DIR))
    except ValueError:
        return str(p)


def _exists_all(spec: dict) -> bool:
    w = spec.get("when_exists")
    if not w:
        return True
    return all((BASE_DIR / p).exists() for p in ([w] if isinstance(w, str) else w))


def active(spec: dict, profile: str) -> bool:
    """Is this service / hook / URL enabled for the current profile, and do its requirements (when_exists) exist?"""
    profs = spec.get("profiles")
    if profs and profile not in profs:
        return False
    return _exists_all(spec)


# =====================================================================================================
# Section 2: envfile
# Reads .env and puts every KEY=VALUE into os.environ. The rule: real system variables always win (setdefault),
# and the order is: .env.<profile> then .env.local then .env (whichever loads first wins).
# =====================================================================================================
_FILE_VALUES: dict[str, str] = {}     # values that came from files (for the report: source)
_GENERATED: set[str] = set()
_DEFAULTED: set[str] = set()


def _parse(line: str):
    line = line.strip()
    if line.startswith("export "):
        line = line[7:].lstrip()
    if not line or line.startswith("#") or "=" not in line:
        return None
    k, v = line.split("=", 1)
    return k.strip(), v.strip().strip("\"'")


def envfile_read(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            kv = _parse(line)
            if kv:
                out[kv[0]] = kv[1]
    return out


def envfile_load(path: Path) -> None:
    for k, v in envfile_read(path).items():
        if k not in os.environ:
            _FILE_VALUES[k] = v
        os.environ.setdefault(k, v)


def envfile_save_key(name: str, value: str) -> None:
    """Writes KEY=VALUE to .env (600 permissions) and to os.environ. If the key exists it is updated in place."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) or "\n" in value or "\r" in value:
        raise ValueError("invalid variable name or value")
    f = paths.ENV_FILE
    lines = f.read_text(encoding="utf-8").splitlines() if f.is_file() else []
    new_line, done = f"{name}={value}", False
    for i, line in enumerate(lines):
        kv = _parse(line)
        if kv and kv[0] == name:
            lines[i], done = new_line, True
    if not done:
        lines.append(new_line)
    f.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        os.chmod(f, 0o600)
    except OSError:
        pass
    os.environ[name] = value
    _FILE_VALUES[name] = value


_GENERATORS = {
    "hex32": lambda: secrets.token_hex(32),
    "hex16": lambda: secrets.token_hex(16),
    "urlsafe": lambda: secrets.token_urlsafe(32),
    "uuid": lambda: str(uuid.uuid4()),
    "password": lambda: secrets.token_urlsafe(18),
}


def env_source(spec: dict) -> str:
    n = spec["name"]
    if not os.environ.get(n):
        return "missing"
    if n in _GENERATED:
        return "generated"
    if n in _REAL_ENV:
        return "environment"
    if n in _FILE_VALUES:
        return paths.ENV_FILE.name
    if n in _DEFAULTED:
        return "default"
    return "selection"


# =====================================================================================================
# Section 3: paths  -  all paths in one place (computed after .env is read so <PREFIX>_DATA_DIR works)
#   <data>/runtime/venv/<name>   virtual environments      logs/*.log   logs
#   deps.json  requirements fingerprint + central library          selection.json  the last selection
#   launcher.state.json  the running instance             node/  the project-private Node.js copy
# =====================================================================================================
paths = SimpleNamespace()
_NO_VENV = False


def init_paths() -> None:
    data = Path(os.environ.get(E("DATA_DIR")) or CFG["data_dir"]).expanduser()
    data = (data if data.is_absolute() else BASE_DIR / data).resolve()
    runtime = data / "runtime"
    paths.__dict__.update(
        ROOT=BASE_DIR, DATA_DIR=data, RUNTIME=runtime, VENVS=runtime / "venv", LOGS=runtime / "logs",
        SELECTION_FILE=runtime / "selection.json", DEPS_FILE=runtime / "deps.json",
        STATE_FILE=runtime / "launcher.state.json", NODE_DIR=runtime / "node",
        ENV_FILE=BASE_DIR / ".env", INSTALL_LOG=runtime / "logs" / "install.log",
        HOOKS_LOG=runtime / "logs" / "hooks.log", FRONTEND_LOG=runtime / "logs" / "frontend.log",
    )


def ensure_dirs() -> None:
    for p in (paths.RUNTIME, paths.VENVS, paths.LOGS, *(paths.DATA_DIR / s for s in CFG["data_subdirs"])):
        p.mkdir(parents=True, exist_ok=True)


def env_spec(name: str) -> dict | None:
    return next((e for e in CFG["environments"] if e["name"] == name), None)


def uses_venv(spec: dict) -> bool:
    return not _NO_VENV and spec.get("venv", True) is not False


def venv_dir(name: str) -> Path:
    return paths.VENVS / name


def env_python(spec: dict) -> Path:
    if not uses_venv(spec):
        return Path(sys.executable)
    return venv_dir(spec["name"]) / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def bootstrap(profile: str) -> None:
    """Loads the .env files in order, computes the paths, and applies the env_vars defaults."""
    for fname in (f".env.{profile}", ".env.local", ".env"):
        envfile_load(BASE_DIR / fname)
    init_paths()
    os.environ[E("PROFILE")] = profile
    base = {"data": str(paths.DATA_DIR), "root": str(BASE_DIR), "runtime": str(paths.RUNTIME)}
    for spec in CFG["env_vars"]:
        if "default" in spec and not os.environ.get(spec["name"]):
            os.environ[spec["name"]] = expand(str(spec["default"]), base)
            _DEFAULTED.add(spec["name"])


_TPL = re.compile(r"\{([A-Za-z_][A-Za-z0-9_.]*)\}")


class Vars(dict):
    """The placeholders dictionary. {env.NAME} is read live from os.environ."""

    def __contains__(self, k):  # type: ignore[override]
        return dict.__contains__(self, k) or (isinstance(k, str) and k.startswith("env.") and k[4:] in os.environ)

    def __getitem__(self, k):
        if dict.__contains__(self, k):
            return dict.__getitem__(self, k)
        return os.environ[k[4:]]


def expand(s: str, vars_: dict) -> str:
    return _TPL.sub(lambda m: str(vars_[m.group(1)]) if m.group(1) in vars_ else m.group(0), s)


def unresolved(s: str) -> list[str]:
    return _TPL.findall(s)


# =====================================================================================================
# Section 4: ui  -  drawing everything in the terminal
#
#  1) Colors: _paint wraps the text in ANSI codes (truecolor if supported, otherwise 16 colors). If the output is a pipe or NO_COLOR: plain text.
#  2) Measuring: _w computes the real width of the text (strips color codes, wide characters = 2, combining ones = 0)
#     so tables stay aligned even when cells are colored.
#  3) table() / box() / menu(): tables, boxes, and selection menus. The recommended row (★) is the default on Enter.
#  4) InstallProgress: two lines that are redrawn in place. run_quiet writes the command output to a log file and the screen stays clean.
# =====================================================================================================
if os.name == "nt":
    os.system("")                     # enable ANSI escape codes in the Windows console
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_COLOR = bool(sys.stdout.isatty()) and not os.environ.get("NO_COLOR")
INTERACTIVE = sys.stdin.isatty() and sys.stdout.isatty()
_TRUE = _COLOR and (os.environ.get("COLORTERM", "").lower() in ("truecolor", "24bit")
                    or bool(os.environ.get("WT_SESSION")))
_ANSI = re.compile(r"\033\[[0-9;?]*[A-Za-z]")

# name: ((r, g, b), 16-color fallback)
_PAL = {
    "accent": ((129, 140, 248), "36"),
    "ok":     ((74, 222, 128), "32"),
    "warn":   ((250, 204, 21), "33"),
    "err":    ((248, 113, 113), "31"),
    "muted":  ((148, 163, 184), "90"),
    "sky":    ((56, 189, 248), "96"),
    "pink":   ((244, 114, 182), "35"),
    "amber":  ((251, 146, 60), "93"),
    "teal":   ((45, 212, 191), "92"),
}


def _paint(name: str, text: str, bold: bool = False) -> str:
    if not _COLOR:
        return text
    rgb, fb = _PAL[name]
    code = f"38;2;{rgb[0]};{rgb[1]};{rgb[2]}" if _TRUE else fb
    return f"\033[{'1;' if bold else ''}{code}m{text}\033[0m"


def accent(t, b=False): return _paint("accent", t, b)
def green(t):  return _paint("ok", t)
def yellow(t): return _paint("warn", t)
def red(t):    return _paint("err", t)
def gray(t):   return _paint("muted", t)
def bold(t):   return f"\033[1m{t}\033[0m" if _COLOR else t
def dim(t):    return f"\033[2m{t}\033[0m" if _COLOR else t


def strip(s: str) -> str:
    return _ANSI.sub("", s)


# ---------------------------------------------------------------- measuring

def _w(s: str) -> int:
    n = 0
    for ch in strip(s):
        if unicodedata.combining(ch):
            continue
        n += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return n


def _pad(s: str, w: int) -> str:
    return s + " " * max(w - _w(s), 0)


def _trunc(s: str, w: int) -> str:
    if _w(s) <= w:
        return s
    while s and _w(s) > w - 1:
        s = s[:-1]
    return s + "\u2026"


def width() -> int:
    return max(78, min(shutil.get_terminal_size((80, 24)).columns - 1, 100))


# ------------------------------------------------------------ one-line msgs

def info(msg: str) -> None: print(f"  {accent('•')} {msg}", flush=True)
def ok(msg: str) -> None:   print(f"  {green('✓')} {msg}", flush=True)
def warn(msg: str) -> None: print(f"  {yellow('!')} {yellow(msg)}", flush=True)
def fail(msg: str) -> None: print(f"  {red('✗')} {red(msg)}", flush=True)


def show_tail(lines: list[str], log_path=None, n: int = 12) -> None:
    """The last output lines of a failed command, in a dim color, + the location of the full log."""
    for ln in lines[-n:]:
        print("    " + gray(_trunc(ln, width() - 6)))
    if log_path:
        print("    " + gray(f"full log: {log_path}"))


# ------------------------------------------------------------------ banner

def banner(subtitle: str | None = None) -> None:
    W = width()
    ver = CFG.get("version")
    print()
    print("  " + accent("◆", True) + "  " + bold(NAME.upper())
          + ((accent(" · ", True) + accent(f"v{ver}", True)) if ver else ""))
    print("  " + gray(subtitle if subtitle is not None else CFG.get("tagline", "")))
    print(gray("  " + "─" * (W - 4)))


# ------------------------------------------------------- steps and sections

STEPS = ("Libraries", "Selection", "Prepare", "Launch")


def step(n: int, title: str) -> None:
    W = width()
    crumbs = []
    for i, name in enumerate(STEPS, 1):
        if i < n:
            crumbs.append(green("✓ ") + gray(name))
        elif i == n:
            crumbs.append(accent("● " + name, True))
        else:
            crumbs.append(gray("○ " + name))
    print()
    print(accent("━" * W))
    print("  " + accent(f"STEP {n}/{len(STEPS)}", True) + gray("  ·  ") + bold(title.upper()))
    print("  " + gray("  ──  ").join(crumbs))
    print(accent("━" * W))


def section(title: str, note: str = "") -> None:
    W = width()
    left = f"── {title} "
    right = f" {note} ──" if note else ""
    fill = max(W - _w(left) - _w(right), 2)
    line = accent("── ") + bold(title) + " " + gray("─" * fill)
    if note:
        line += gray(" " + note + " ──")
    print()
    print(line)


# ------------------------------------------------------------------- boxes

def box(title: str, lines: list[str], width_: int | None = None, tone: str = "accent") -> None:
    W = width_ or width()
    inner = W - 4
    edge = (lambda s: accent(s)) if tone == "accent" else gray
    flat: list[str] = []
    for ln in lines:
        if strip(ln) == ln and _w(ln) > inner:
            flat.extend(textwrap.wrap(ln, inner) or [""])
        else:
            flat.append(ln)
    t = f" {title} "
    print(edge("╭" + "─" * 1) + bold(accent(t) if tone == "accent" else gray(t))
          + edge("─" * max(W - 3 - _w(t), 0) + "╮"))
    for ln in flat:
        print(edge("│") + " " + ln + " " * max(inner - _w(ln), 0) + " " + edge("│"))
    print(edge("╰" + "─" * (W - 2) + "╯"))


def kv_lines(rows: list[tuple[str, str]]) -> list[str]:
    """[('Provider', 'OpenAI'), ...] -> aligned lines 'Provider : OpenAI' ready for box()."""
    kw = max((_w(k) for k, _ in rows), default=0)
    return [f"{_pad(k, kw)} : {v}" for k, v in rows]


def explain(options: list[tuple[str, str]], title: str = "What each option does") -> None:
    inner = width() - 4
    prefixes = [f"{k}." if k[:1].isdigit() else k for k, _ in options]
    pw = max((_w(p) for p in prefixes), default=0)
    indent = pw + 1
    lines: list[str] = []
    for prefix, (_, text) in zip(prefixes, options):
        wrapped = textwrap.wrap(text, max(inner - indent, 20)) or [""]
        lines.append(accent(_pad(prefix, pw), True) + " " + wrapped[0])
        lines.extend(" " * indent + w for w in wrapped[1:])
    box(title, lines, tone="muted")


def table(headers: list[str], rows: list[list[str]], title: str = "") -> None:
    w = [max([_w(h)] + [_w(str(r[i])) for r in rows]) for i, h in enumerate(headers)]

    def rule(l, m, r):
        return gray(l + m.join("─" * (x + 2) for x in w) + r)

    if title:
        print(bold(f" {title}"))
    print(rule("╭", "┬", "╮"))
    print(gray("│") + gray("│").join(f" {accent(_pad(h, w[i]), True)} "
                                     for i, h in enumerate(headers)) + gray("│"))
    print(rule("├", "┼", "┤"))
    for r in rows:
        print(gray("│") + gray("│").join(f" {_pad(str(c), w[i])} "
                                         for i, c in enumerate(r)) + gray("│"))
    print(rule("╰", "┴", "╯"))


# -------------------------------------------------------------------- menus

def _auto() -> bool:
    return not sys.stdin.isatty() or os.environ.get(E("AUTO")) == "1"


def ask(n: int, default: int = 1) -> int:
    if _auto():
        print(dim(f"  (non-interactive → using default {default})"), flush=True)
        return default
    rng = "1" if n == 1 else f"1-{n}"
    while True:
        try:
            raw = input(f"  {accent('›', True)} Select {gray(f'[{rng}]')} "
                        f"{gray(f'Enter = {default}')}: ").strip()
        except EOFError:
            return default
        if raw == "":
            return default
        if raw.isdigit() and 1 <= int(raw) <= n:
            return int(raw)
        print(red(f"    Enter a number from {rng}."), flush=True)


def ask_text(prompt: str, default: str = "") -> str:
    """One line of text. Enter alone returns `default`. Quotes around a pasted path are removed."""
    hint = f" {gray(f'Enter = {default}')}" if default else ""
    try:
        raw = input(f"  {prompt}{hint}\n  {accent('›', True)} ").strip().strip('"').strip("'")
    except EOFError:
        return default
    return raw or default


def ask_secret(prompt: str) -> str:
    """Hidden input (API keys). Empty string when skipped or when there is no terminal."""
    if not sys.stdin.isatty():
        return ""
    import getpass
    try:
        return getpass.getpass(f"  {prompt}\n  {accent('›', True)} ").strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def ask_yes_no(question: str, default: bool = True) -> bool:
    if _auto():
        return default
    hint = "[Y/n]" if default else "[y/N]"
    try:
        raw = input(f"  {accent('?', True)} {question} {gray(hint)} ").strip().lower()
    except EOFError:
        return default
    return default if not raw else raw.startswith("y")


def _options_box(headers: list[str], rows: list[dict], numbers: dict[int, int]) -> None:
    W = width()
    inner = W - 4
    gap = 2
    n_data = len(headers)
    has_status = any(r.get("state") in ("rec", "blocked") or r.get("tag") for r in rows)

    head = [""] + list(headers) + ([""] if has_status else [])
    body: list[tuple[list[str], str]] = []
    for i, r in enumerate(rows):
        state = r.get("state", "ok")
        num = f"[{numbers[i]}]" if i in numbers else " ✕ "
        data = [str(x) for x in r["cols"]]
        data += [""] * (n_data - len(data))
        status = ("★ recommended" if state == "rec"
                  else "not available" if state == "blocked" else r.get("tag", ""))
        body.append(([num] + data + ([status] if has_status else []), state))

    nc = len(head)
    widths = [max([_w(head[c])] + [_w(cells[c]) for cells, _ in body]) for c in range(nc)]
    over = sum(widths) + gap * (nc - 1) - inner
    if over > 0 and nc > 1:
        widths[1] = max(widths[1] - over, 8)
    used = sum(widths) + gap * (nc - 1)

    def line(cells: list[str], state: str, header: bool = False) -> str:
        parts = []
        for c, (txt, w) in enumerate(zip(cells, widths)):
            txt = _pad(_trunc(txt, w), w)
            is_status = has_status and c == nc - 1
            if header:
                txt = gray(txt)
            elif state == "blocked":
                txt = gray(txt)
            elif c == 0:
                txt = accent(txt, True) if state != "rec" else green(txt)
            elif state == "rec" and c == 1:
                txt = bold(txt)
            elif is_status and txt.strip():
                txt = green(txt) if state == "rec" else yellow(txt)
            parts.append(txt)
        return (gray("│") + " " + (" " * gap).join(parts)
                + " " * max(inner - used, 0) + " " + gray("│"))

    print(gray("╭" + "─" * (W - 2) + "╮"))
    print(line(head, "ok", header=True))
    print(gray("├" + "─" * (W - 2) + "┤"))
    for cells, state in body:
        print(line(cells, state))
    print(gray("╰" + "─" * (W - 2) + "╯"))


def menu(title: str | None, headers: list[str], items: list[dict], *,
         extras: list[dict] | tuple = (), explain_lines: list[tuple[str, str]] | None = None,
         note: str = "") -> int:
    """Section title, explanation box, numbered options, prompt.

    items / extras are dicts: cols (list[str]), state ("ok" | "rec" | "blocked"),
    desc (explanation), tag (small status for "ok" rows). "blocked" rows are gray,
    unnumbered and cannot be chosen. Returns the 0-based index into items + extras."""
    rows = list(items) + list(extras)
    n_items = len(items)
    numbers: dict[int, int] = {}
    for i, r in enumerate(rows):
        if r.get("state", "ok") != "blocked":
            numbers[i] = len(numbers) + 1
    if not numbers:
        raise RuntimeError("no selectable options")
    rec = [numbers[i] for i, r in enumerate(rows) if r.get("state") == "rec" and i in numbers]
    default = rec[0] if rec else 1

    exp: list[tuple[str, str]] = []
    if explain_lines is None:
        exp = [(str(numbers[i]), r["desc"]) for i, r in enumerate(rows)
               if i in numbers and r.get("desc")]
    else:
        nums = [numbers[i] for i in range(n_items) if i in numbers]
        if nums:
            rng = str(nums[0]) if len(nums) == 1 else f"{nums[0]}-{nums[-1]}"
            exp.extend((k.format(range=rng), t) for k, t in explain_lines)
        exp += [(str(numbers[i]), rows[i]["desc"]) for i in range(n_items, len(rows))
                if i in numbers and rows[i].get("desc")]
    if any(r.get("state") == "blocked" for r in rows):
        exp.append(("✕", "Gray rows are not available on this machine."))

    if title:
        section(title, note)
    if exp:
        explain(exp)
        print()
    _options_box(headers, rows, numbers)
    chosen = ask(len(numbers), default)
    return next(i for i, num in numbers.items() if num == chosen)


# ------------------------------------------------------- long-running work

@contextlib.contextmanager
def spinner(msg: str):
    """Animated one-line status for work with no measurable progress."""
    if not _COLOR:
        print(f"  … {msg}", flush=True)
        yield
        return
    stop = threading.Event()
    frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def spin():
        i = 0
        while not stop.is_set():
            sys.stdout.write(f"\r\033[2K  {accent(frames[i % len(frames)])} {msg}")
            sys.stdout.flush()
            i += 1
            time.sleep(0.08)

    t = threading.Thread(target=spin, daemon=True)
    t.start()
    try:
        yield
    finally:
        stop.set()
        t.join()
        sys.stdout.write("\r\033[2K")
        sys.stdout.flush()


def run_quiet(cmd: list[str], log_path, on_line=None, env=None, cwd=None) -> int:
    """Runs a command, writes all its output to the log file, and sends each line to on_line. 127 if the command is not found."""
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as lf:
        lf.write("\n$ " + " ".join(str(c) for c in cmd) + (f"   (cwd: {cwd})" if cwd else "") + "\n")
        try:
            p = subprocess.Popen([str(c) for c in cmd], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace",
                                 env=env, cwd=cwd)
        except OSError as e:
            lf.write(f"could not start: {e}\n")
            if on_line:
                on_line(f"could not start: {e}")
            return 127
        assert p.stdout is not None
        for line in p.stdout:
            lf.write(line)
            if on_line:
                on_line(line)
        return p.wait()


def run_step(cmd: list[str], log_path, env=None, cwd=None) -> tuple[int, list[str]]:
    """run_quiet + the last 12 lines of output (to show them if the command fails)."""
    tail: deque[str] = deque(maxlen=12)
    rc = run_quiet(cmd, log_path, on_line=lambda ln: tail.append(ln.rstrip()), env=env, cwd=cwd)
    return rc, list(tail)


class InstallProgress:
    W = 30

    def __init__(self, total: int):
        self.total = total
        self.i = 0
        self.name = ""
        self._drawn = False
        self._last: tuple[int, float] | None = None

    def start(self, name: str) -> None:
        self.i += 1
        self.name = name
        self.update(0.0)

    def update(self, frac: float) -> None:
        frac = max(0.0, min(1.0, frac))
        if not _COLOR:  # plain log lines: print the start and the end of each library once
            if frac in (0.0, 1.0) and self._last != (self.i, frac):
                self._last = (self.i, frac)
                print(f"({self.i}/{self.total}) {self.name} {int(frac * 100):3d}%", flush=True)
            return
        f = int(self.W * frac)
        l1 = f"  {gray(f'{self.i}/{self.total}')}  {bold(self.name)}"
        l2 = f"  {accent('━' * f)}{gray('─' * (self.W - f))}  {int(frac * 100):3d}%"
        if self._drawn:
            sys.stdout.write("\033[2F")
        sys.stdout.write("\033[2K" + l1 + "\n\033[2K" + l2 + "\n")
        sys.stdout.flush()
        self._drawn = True

    def interrupt(self) -> None:
        """Something else is about to print (a warning, a menu): stop redrawing the two-line bar in place."""
        if self._drawn:
            print(flush=True)
        self._drawn = False

    def done(self) -> None:
        self.update(1.0)

    def close(self) -> None:
        self._drawn = False
        ok(f"{self.total}/{self.total} libraries installed")


def pip_progress_hook(prog: InstallProgress):
    state = {"f": 0.0}
    steps = (("Collecting", 0.15), ("Downloading", 0.45), ("Building", 0.60),
             ("Installing collected", 0.85), ("Successfully installed", 1.0))

    def hook(line: str) -> None:
        for key, val in steps:
            if line.startswith(key) and val > state["f"]:
                state["f"] = val
                prog.update(val)
    return hook


# =====================================================================================================
# Section 5: env vars  -  asking for missing variables (a hidden secret or plain text) and saving them to .env
# =====================================================================================================
def _valid_env_value(spec: dict, val: str) -> bool:
    pat = spec.get("pattern")
    return bool(val) and (not pat or re.fullmatch(pat, val) is not None)


def _prompt_env_value(spec: dict) -> str:
    n = spec["name"]
    desc = spec.get("desc") or n
    for _ in range(3):
        if spec.get("secret", True):
            val = ask_secret(f"{desc}: paste {n} (input is hidden):")
        else:
            val = ask_text(f"{desc}: {n}", default=str(spec.get("default", "")))
        if not val:
            return ""
        if _valid_env_value(spec, val):
            return val
        fail(f"That does not look like a valid {n}.")
    return ""


def ensure_env_vars(names: list[str], auto: bool, required: bool = False, label: str = "") -> list[str]:
    """Interactive only: offer to type the missing variables now (saved to .env). Returns the ones still missing."""
    miss = [n for n in names if not os.environ.get(n)]
    if not miss or auto or not INTERACTIVE:
        return miss
    if not required:
        c = menu(f"{label + ': ' if label else ''}{', '.join(miss)} not set", ["Option"], [
            {"cols": ["Enter it now"], "state": "rec",
             "desc": f"Typed here and saved in {paths.ENV_FILE.name} (keep it git-ignored) so it is not asked again."},
            {"cols": ["Continue without it"],
             "desc": f"You can add it to {paths.ENV_FILE.name} later. Features that need it may not work."},
        ])
        if c == 1:
            return miss
    for n in miss:
        spec = ENV_SCHEMA.get(n, {"name": n, "secret": True})
        val = _prompt_env_value(spec)
        if not val:
            warn(f"No value entered for {n}.")
            continue
        try:
            envfile_save_key(n, val)
            ok(f"{n} saved to {paths.ENV_FILE.name}")
        except (ValueError, OSError) as e:
            fail(f"Could not save {n}: {e}")
    return [n for n in names if not os.environ.get(n)]


# =====================================================================================================
# Section 6: hardware + capacity  (determines the recommended number of workers from the CPU and memory)
# =====================================================================================================
@dataclass
class Hardware:
    os_name: str
    python: str
    cores: int
    ram_total: float
    ram_avail: float
    safe_ram: float
    known: bool


def _ram_gb() -> tuple[float, float]:
    """(total, available) in GB. psutil if present, otherwise the system method. (0, 0) if unknown."""
    try:
        import psutil  # optional
        vm = psutil.virtual_memory()
        return vm.total / 2**30, vm.available / 2**30
    except Exception:
        pass
    try:
        if os.name == "nt":
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [("l", ctypes.c_ulong), ("load", ctypes.c_ulong), ("tp", ctypes.c_ulonglong),
                            ("ap", ctypes.c_ulonglong), ("tpf", ctypes.c_ulonglong), ("apf", ctypes.c_ulonglong),
                            ("tv", ctypes.c_ulonglong), ("av", ctypes.c_ulonglong), ("ae", ctypes.c_ulonglong)]
            ms = MS()
            ms.l = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))  # type: ignore[attr-defined]
            return ms.tp / 2**30, ms.ap / 2**30
        if platform.system() == "Darwin":
            total = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True,
                                       timeout=5).stdout.strip()) / 2**30
            return total, total * 0.5
        info_ = dict(ln.split(":", 1) for ln in Path("/proc/meminfo").read_text().splitlines() if ":" in ln)
        return int(info_["MemTotal"].split()[0]) / 2**20, int(info_["MemAvailable"].split()[0]) / 2**20
    except Exception:
        return 0.0, 0.0


def detect_hardware() -> Hardware:
    total, avail = _ram_gb()
    known = total > 0
    return Hardware(f"{platform.system()} {platform.release()}", platform.python_version(), os.cpu_count() or 1,
                    total, avail, round(avail * 0.7, 1) if known else 0.0, known)


MAX_WORKERS = 64  # hard ceiling for a hand-edited selection file


def capacity_limits(cores: int, safe_ram: float, per_worker_gb: float = 0.3, hard_max: int | None = None) -> dict:
    by_ram = int(safe_ram / per_worker_gb) if safe_ram else MAX_WORKERS
    hi = max(1, min(cores * 2, by_ram, hard_max or MAX_WORKERS))
    return {"recommended_workers": max(1, min(hi, max(cores // 2, 1), 4)), "max_workers": hi}


# =====================================================================================================
# Section 7: selection  -  selection screens (step 2) from the questions in CONFIG["questions"]
#
#  - If there is a saved selection with the same questions: it asks whether to continue with it or choose again (--auto continues with it without asking).
#  - Each question by its type: choice (menu) / workers (suggested from the machine) / number / bool / text.
#  - The selection is saved in selection.json and exported as <PREFIX>_<ID> and as {sel.ID}, and the choice options
#    can specify env (variables to add) and env_required (variables that must exist, asked hidden if missing).
# =====================================================================================================
SELECTION_VERSION = 2


def _questions() -> list[dict]:
    return CFG["questions"]


def _schema_hash() -> str:
    sig = [(q["id"], q.get("type", "choice"), [o["value"] for o in q.get("options", [])]) for q in _questions()]
    return hashlib.sha1(json.dumps(sig, sort_keys=True).encode()).hexdigest()[:12]


def _opt_status(opt: dict) -> str:
    names = opt.get("env_required") or []
    if not names:
        return ""
    miss = [n for n in names if not os.environ.get(n)]
    return f"found ({', '.join(names)})" if not miss else f"not set ({', '.join(miss)})"


def _rec_index(q: dict) -> int:
    opts = q["options"]
    if q.get("prefer_configured"):
        for i, o in enumerate(opts):
            if o.get("env_required") and all(os.environ.get(n) for n in o["env_required"]):
                return i
    for i, o in enumerate(opts):
        if o.get("recommended") or ("default" in q and o["value"] == q["default"]):
            return i
    return 0


def _static_default(q: dict):
    t = q.get("type", "choice")
    if t == "choice":
        return q["options"][_rec_index({**q, "prefer_configured": False})]["value"]
    if t == "workers":
        return int(q.get("default", 2))
    if t == "number":
        return q.get("default", q.get("min", 1))
    if t == "bool":
        return bool(q.get("default", True))
    return q.get("default", "")


def _valid(q: dict, v) -> bool:
    t = q.get("type", "choice")
    if t == "choice":
        return any(o["value"] == v for o in q["options"])
    if t in ("number", "workers"):
        lo, hi = q.get("min", 1), q.get("max", MAX_WORKERS if t == "workers" else 10**9)
        return isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi
    if t == "bool":
        return isinstance(v, bool)
    return isinstance(v, str) and (not q.get("pattern") or re.fullmatch(q["pattern"], v) is not None)


def _clean(data: object) -> dict:
    """Keep only valid values, so a damaged or hand-edited selection.json can never crash the launcher."""
    vals = data.get("values") if isinstance(data, dict) else None
    vals = vals if isinstance(vals, dict) else {}
    return {q["id"]: (vals[q["id"]] if _valid(q, vals.get(q["id"])) else _static_default(q)) for q in _questions()}


def save_selection(sel: dict) -> None:
    paths.SELECTION_FILE.parent.mkdir(parents=True, exist_ok=True)
    paths.SELECTION_FILE.write_text(json.dumps(
        {"version": SELECTION_VERSION, "schema": _schema_hash(), "values": _clean({"values": sel})}, indent=2),
        encoding="utf-8")


def _read_selection_file() -> dict:
    try:
        data = json.loads(paths.SELECTION_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def load_selection() -> dict:
    return _clean(_read_selection_file())


def has_saved_selection() -> bool:
    """True only for a readable file of the current version made for these exact questions."""
    d = _read_selection_file()
    return (d.get("version") == SELECTION_VERSION and d.get("schema") == _schema_hash()
            and isinstance(d.get("values"), dict)
            and all(_valid(q, d["values"].get(q["id"])) for q in _questions()))


def _label(q: dict, v) -> str:
    if q.get("type", "choice") == "choice":
        return next((o["label"] for o in q["options"] if o["value"] == v), str(v))
    if isinstance(v, bool):
        return "yes" if v else "no"
    return str(v)


def _when_ok(q: dict, answers: dict) -> bool:
    return all(answers.get(k) in (vs if isinstance(vs, list) else [vs]) for k, vs in (q.get("when") or {}).items())


def _show_hardware(hw: Hardware) -> None:
    section("Hardware")
    wq = next((q for q in _questions() if q.get("type") == "workers"), None)
    ram = (f"{hw.ram_total:.1f} GB total · {hw.ram_avail:.1f} free" if hw.known else "unknown")
    rows = [("System", f"{hw.os_name} · Python {hw.python}"), ("CPU cores", str(hw.cores)), ("RAM", ram),
            ("Safe RAM", f"{hw.safe_ram:.1f} GB" if hw.known else "(not limited)")]
    if wq:
        cap = capacity_limits(hw.cores, hw.safe_ram, wq.get("per_worker_gb", 0.3), wq.get("max"))
        rows.append(("Workers", f"recommended {cap['recommended_workers']} · up to {cap['max_workers']}"))
    box("YOUR MACHINE", kv_lines(rows))


def _show_last(sel: dict) -> None:
    rows = [(q.get("title") or q["id"], _label(q, sel[q["id"]])) for q in _questions()]
    for q in _questions():
        if q.get("type", "choice") == "choice":
            o = next((o for o in q["options"] if o["value"] == sel[q["id"]]), None)
            if o and o.get("env_required"):
                rows.append(("  " + (q.get("title") or q["id"]) + " key", _opt_status(o)))
    box("LAST SELECTION", kv_lines(rows))


def _ask_choice(q: dict, auto: bool) -> str:
    opts, rec, title = q["options"], _rec_index(q), q.get("title") or q["id"]
    if auto:
        section(title)
        ok(f"{title}: {opts[rec]['label']}")
        return opts[rec]["value"]
    show_status = any(o.get("env_required") for o in opts)
    show_detail = any(o.get("detail") for o in opts)
    headers = [q.get("column", "Option")] + (["API key / variables"] if show_status else []) \
        + (["Details"] if show_detail else [])
    items = []
    for i, o in enumerate(opts):
        cols = [o["label"]] + ([_opt_status(o)] if show_status else []) + ([o.get("detail", "")] if show_detail else [])
        items.append({"cols": cols, "state": "rec" if i == rec else "ok", "desc": o.get("desc", "")})
    c = menu(title, headers, items,
             explain_lines=[("{range}", q["explain"])] if q.get("explain") else None)
    ok(f"{title}: {opts[c]['label']}")
    if opts[c].get("env_required"):
        ensure_env_vars(opts[c]["env_required"], auto, label=opts[c]["label"])
    return opts[c]["value"]


def _ask_workers(q: dict, hw: Hardware, auto: bool) -> int:
    cap = capacity_limits(hw.cores, hw.safe_ram, q.get("per_worker_gb", 0.3), q.get("max"))
    rec, hi = cap["recommended_workers"], cap["max_workers"]
    title, unit = q.get("title") or "Workers", q.get("unit", "workers")
    if auto:
        section(title)
        ok(f"{title}: {rec}")
        return rec
    items = [{"cols": [f"{rec} {unit}", "Recommended for this machine"], "state": "rec"}]
    if rec != 1:
        items.append({"cols": [f"1 {unit.rstrip('s')}", "Smallest footprint"]})
    items.append({"cols": ["Custom", f"Choose 1 to {hi}"]})
    c = menu(title, ["Count", "Details"], items,
             explain_lines=[("{range}", q["explain"])] if q.get("explain") else None)
    if items[c]["cols"][0] == "Custom":
        while True:
            raw = ask_text(f"Number of {unit} [1-{hi}]:", default=str(rec))
            if raw.isdigit() and 1 <= int(raw) <= hi:
                n = int(raw)
                break
            fail(f"Enter a whole number from 1 to {hi}.")
    else:
        n = rec if c == 0 else 1
    ok(f"{title}: {n}")
    return n


def _ask_number(q: dict, auto: bool) -> int:
    title, lo, hi, d = q.get("title") or q["id"], q.get("min", 1), q.get("max", 10**9), _static_default(q)
    section(title)
    if q.get("explain"):
        info(q["explain"])
    if auto:
        ok(f"{title}: {d}")
        return d
    while True:
        raw = ask_text(f"{title} [{lo}-{hi}]:", default=str(d))
        if raw.lstrip("-").isdigit() and lo <= int(raw) <= hi:
            ok(f"{title}: {int(raw)}")
            return int(raw)
        fail(f"Enter a whole number from {lo} to {hi}.")


def _ask_bool(q: dict, auto: bool) -> bool:
    title, d = q.get("title") or q["id"], _static_default(q)
    section(title)
    if q.get("explain"):
        info(q["explain"])
    v = d if auto else ask_yes_no(title + "?", d)
    ok(f"{title}: {'yes' if v else 'no'}")
    return v


def _ask_text_q(q: dict, auto: bool) -> str:
    title, d = q.get("title") or q["id"], _static_default(q)
    section(title)
    if q.get("explain"):
        info(q["explain"])
    while not auto:
        v = ask_text(f"{title}:", default=str(d))
        if _valid(q, v):
            ok(f"{title}: {v}")
            return v
        fail("That value is not valid" + (f" (pattern {q['pattern']})" if q.get("pattern") else "") + ".")
    ok(f"{title}: {d}")
    return d


def run_selection(auto: bool = False, reselect: bool = False) -> dict:
    """Run every selection screen and return (and save) the selection."""
    qs = _questions()
    if not qs:
        return {}
    if has_saved_selection() and not reselect:
        prev = load_selection()
        if auto:
            section("Selection")
            ok("Using the saved selection")
            _show_last(prev)
            return prev
        section("Previous selection")
        _show_last(prev)
        print()
        c = menu(None, ["Option"], [
            {"cols": ["Keep this selection and continue"], "state": "rec",
             "desc": "Skip the questions and use the previous choices."},
            {"cols": ["Choose again"], "desc": "Show the questions again and choose from scratch."},
        ])
        if c == 0:
            for q in qs:
                if q.get("type", "choice") == "choice":
                    o = next(o for o in q["options"] if o["value"] == prev[q["id"]])
                    if o.get("env_required"):
                        ensure_env_vars(o["env_required"], auto, label=o["label"])
            return prev

    hw = detect_hardware()
    if CFG.get("show_hardware", True):
        _show_hardware(hw)
    answers: dict = {}
    for q in qs:
        if not _when_ok(q, answers):
            answers[q["id"]] = _static_default(q)
            continue
        t = q.get("type", "choice")
        answers[q["id"]] = (_ask_choice(q, auto) if t == "choice" else _ask_workers(q, hw, auto) if t == "workers"
                            else _ask_number(q, auto) if t == "number" else _ask_bool(q, auto) if t == "bool"
                            else _ask_text_q(q, auto))
    save_selection(answers)
    print()
    ok("Selection saved")
    return answers


def apply_selection(sel: dict, vars_: dict) -> None:
    """Exports the selection: <PREFIX>_<ID> + the env variables of the chosen option.
    Keys that already exist in the real environment (system env or explicit -e overrides)
    are NOT overwritten: an explicit environment value always wins over the saved selection."""
    for q in _questions():
        v = sel.get(q["id"])
        key = E(re.sub(r"\W+", "_", q["id"]).upper())
        val = ("true" if v else "false") if isinstance(v, bool) else str(v)
        if key in _REAL_ENV:
            info(f"{key} kept from the environment (explicit -e / system env wins over the saved selection)")
        else:
            os.environ[key] = val
        if q.get("type", "choice") == "choice":
            opt = next((o for o in q["options"] if o["value"] == v), {})
            for k, val in (opt.get("env") or {}).items():
                if k in _REAL_ENV:
                    info(f"{k} kept from the environment (explicit -e / system env wins over the saved selection)")
                else:
                    os.environ[k] = expand(str(val), vars_)


# =====================================================================================================
# Section 8: deps  -  virtual environments + detecting missing libraries + installing (internet or central library)
#
#   ensure_venv        creates the venv if it doesn't exist or is broken. Updates pip with a short timeout for offline use.
#   read_specs         reads the requirements files (comments, -r include, ignores other lines starting with -)
#   missing_specs      runs the venv's own python: the name + the required version + the environment markers
#                      (uses the packaging module inside pip). It does not import the library.
#   fingerprint        a hash of the requirements: if unchanged and everything was checked before, the check is skipped (--recheck forces it)
#   install_all        central: sees what is missing as .whl and asks you (download into the folder / from the internet / cancel),
#                      then installs one by one with a progress bar, and any failure is recorded in install.log
# =====================================================================================================
def base_name(spec: str) -> str:
    """'uvicorn[standard]>=0.30' -> 'uvicorn'. Names are normalised the way pip does it."""
    return re.sub(r"[-_.]+", "-", re.split(r"[\[<>=!~ ;@]", spec.strip(), maxsplit=1)[0]).lower()


def read_specs(req_file: Path, _seen: set | None = None) -> list[str]:
    seen = _seen if _seen is not None else set()
    if req_file.resolve() in seen or not req_file.is_file():
        return []
    seen.add(req_file.resolve())
    specs: list[str] = []
    for line in req_file.read_text(encoding="utf-8").splitlines():
        line = re.sub(r"(^|\s)#.*$", "", line).strip()
        if not line:
            continue
        inc = re.match(r"(?:-r|--requirement)\s*=?\s*(\S+)", line)
        if inc:
            specs += read_specs(req_file.parent / inc.group(1), seen)
        elif not line.startswith("-"):
            specs.append(line)
    return specs


def env_specs(spec: dict) -> list[str]:
    return [s for f in spec["requirements"] for s in read_specs(BASE_DIR / f)]


# ------------------------------------------------------------------ virtual environments

def _pip_works(py: Path) -> bool:
    try:
        return subprocess.run([str(py), "-m", "pip", "--version"], capture_output=True,
                              timeout=60).returncode == 0
    except Exception:
        return False


def _is_running_in(target: Path) -> bool:
    try:
        return target.resolve() in Path(sys.executable).resolve().parents
    except OSError:
        return False


def ensure_venv(spec: dict) -> bool:
    """Create the venv when it is missing (or broken). Returns True when it was created now.

    Raises RuntimeError with the fix when Python cannot make one (typically Debian/Ubuntu without python3-venv)."""
    if not uses_venv(spec):
        return False
    name = spec["name"]
    py, target = env_python(spec), venv_dir(name)
    if py.exists() and _pip_works(py):
        return False
    if target.exists():
        if _is_running_in(target):
            raise RuntimeError(f"The '{name}' environment is damaged (pip does not run) and it is the one running "
                               f"now. Delete the folder {target} and run again.")
        shutil.rmtree(target, ignore_errors=True)  # half-made or broken: start clean
    paths.VENVS.mkdir(parents=True, exist_ok=True)
    res = subprocess.run([sys.executable, "-m", "venv", str(target)], capture_output=True, text=True)
    if res.returncode != 0 or not py.exists():
        tail = "\n".join((res.stderr or res.stdout or "").strip().splitlines()[-4:])
        hint = ("\nOn Debian/Ubuntu install it with:  sudo apt install python3-venv"
                if "ensurepip" in tail or "python3-venv" in tail else "")
        raise RuntimeError(f"Could not create the '{name}' environment.\n{tail}{hint}")
    # best effort: a current pip installs modern wheels reliably. Short timeouts so an offline machine is not stalled.
    try:
        subprocess.run([str(py), "-m", "pip", "install", "-q", "--upgrade", "pip", "--retries", "1",
                        "--timeout", "8", "--disable-pip-version-check"], capture_output=True, timeout=180)
    except subprocess.TimeoutExpired:
        pass
    return True


_CHECK_SCRIPT = r'''
import importlib.metadata as m, json, re, sys
try:
    from pip._vendor.packaging.requirements import Requirement
except Exception:
    Requirement = None
out = []
for spec in json.loads(sys.argv[1]):
    name = re.sub(r"[-_.]+", "-", re.split(r"[\[<>=!~ ;@]", spec.strip(), maxsplit=1)[0]).lower()
    req = None
    if Requirement is not None:
        try:
            req = Requirement(spec)
        except Exception:
            req = None
    if req is not None and req.marker is not None:
        try:
            if not req.marker.evaluate():
                continue
        except Exception:
            pass
    try:
        ver = m.version(name)
    except m.PackageNotFoundError:
        out.append([spec, "missing"])
        continue
    if req is not None and req.specifier and not req.url:
        try:
            if not req.specifier.contains(ver, prereleases=True):
                out.append([spec, "outdated"])
        except Exception:
            pass
print(json.dumps(out))
'''


def missing_specs(py: Path, specs: list[str]) -> list[tuple[str, str]]:
    """[(spec, 'missing'|'outdated')] for what is not satisfied in that interpreter."""
    if not specs:
        return []
    if not py.exists():
        return [(s, "missing") for s in specs]
    res = subprocess.run([str(py), "-c", _CHECK_SCRIPT, json.dumps(specs)], capture_output=True, text=True)
    try:
        return [(s, why) for s, why in json.loads(res.stdout.strip().splitlines()[-1])]
    except Exception:
        return [(s, "missing") for s in specs]


def fingerprint(spec: dict) -> str:
    h = hashlib.sha256()
    h.update(f"{sys.version_info[:2]}|{env_python(spec)}|{spec['pip_args']}".encode())
    for s in env_specs(spec):
        h.update(s.encode() + b"\n")
    return h.hexdigest()


def check_environment(spec: dict) -> dict:
    """{'name', 'total', 'missing': [item, ...]} for one environment. Each item is what install_all() needs."""
    py = env_python(spec)
    specs = env_specs(spec)
    items = [{"spec": s, "extra": list(spec["pip_args"]), "py": py, "lib": base_name(s), "status": why,
              "component": spec["component"], "venv": spec["name"]} for s, why in missing_specs(py, specs)]
    return {"name": spec["name"], "total": len(specs), "missing": items, "cached": False}


def show_environments(reports: list[dict]) -> None:
    rows = []
    for r in reports:
        n_missing = len(r["missing"])
        status = (green("complete" + (" (cached)" if r.get("cached") else "")) if not n_missing
                  else red(f"{n_missing} missing"))
        rows.append([r["name"], str(r["total"]), str(r["total"] - n_missing), status])
    table(["Environment", "Required", "Present", "Status"], rows)


def show_missing(items: list[dict], title: str = "Missing libraries") -> None:
    section(title, note=f"{len(items)} libraries")
    rows = [[str(i), it["lib"], it["component"], it["venv"], red(it.get("status", "missing"))]
            for i, it in enumerate(items, 1)]
    table(["#", "Library", "Component", "Environment", "Status"], rows)


# ------------------------------------------------------------------ deps.json (central library + fingerprints)

def _read_state_file() -> dict:
    try:
        data = json.loads(paths.DEPS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_state_file(state: dict) -> None:
    paths.DEPS_FILE.parent.mkdir(parents=True, exist_ok=True)
    paths.DEPS_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def saved_central() -> str | None:
    p = _read_state_file().get("central") or CFG.get("central_hint")
    return p if p and os.path.isdir(p) else None


def remember_central(path: str) -> None:
    state = _read_state_file()
    state["central"] = path
    _write_state_file(state)


def find_wheel(central: str, spec: str) -> str | None:
    """A .whl in the folder for this package (any version), or None."""
    want = base_name(spec)
    try:
        for f in os.listdir(central):
            if f.lower().endswith(".whl") and re.sub(r"[-_.]+", "-", f.split("-")[0]).lower() == want:
                return f
    except OSError:
        pass
    return None


def _usable_folder(raw: str) -> str | None:
    """Expand and check the folder. A folder that does not exist yet can be created (to be filled by downloads)."""
    path = os.path.abspath(os.path.expanduser(raw))
    if os.path.isdir(path):
        return path
    if ask_yes_no(f"'{path}' does not exist. Create it (empty, to be filled by downloads)?", True):
        try:
            os.makedirs(path, exist_ok=True)
            return path
        except OSError as e:
            fail(f"Could not create the folder: {e}")
    return None


def choose_source(forced_central: str | None = None) -> tuple[str, str | None]:
    """Returns ('online', None) or ('central', folder). `forced_central` (--central / <PREFIX>_CENTRAL) skips the menu."""
    if forced_central:
        folder = _usable_folder(forced_central)
        if not folder:
            fail(f"Central library folder not usable: {forced_central}")
            raise SystemExit(1)
        ok(f"Central library: {folder}")
        remember_central(folder)
        return "central", folder

    saved = saved_central()
    c = menu("How to get the missing libraries", ["Source"], [
        {"cols": ["Download from the internet (PyPI)"], "state": "rec",
         "desc": "Fastest to start. Requires an internet connection."},
        {"cols": ["Install from a central library (folder of .whl files)"],
         "desc": "Works offline. Point to a folder of .whl files; a wheel that is not there can be downloaded into "
                 "it (so the next run is offline), or fetched from the internet, or you can cancel."
                 + (f" Last used: {saved}" if saved else "")},
        {"cols": ["Cancel"], "desc": "Exit. Nothing is installed."},
    ])
    if c == 2:
        raise SystemExit(0)
    if c == 0:
        return "online", None
    while True:
        raw = ask_text("Path of the central library folder:", default=saved or "")
        folder = _usable_folder(raw) if raw else None
        if folder:
            remember_central(folder)
            return "central", folder
        if not sys.stdin.isatty():
            fail("No usable central library folder (and no terminal to ask again).")
            raise SystemExit(1)
        fail("Folder not found.")


# ------------------------------------------------------------------ install

def _ask_missing_policy() -> str:
    """What to do with wheels the central library cannot supply. Returns 'download' or 'online'."""
    c = menu("Some wheels are not in the central library", ["Action"], [
        {"cols": ["Download them into the central library, then install"], "state": "rec",
         "desc": "The wheels (and their dependencies) are saved for next time. Slower the first run."},
        {"cols": ["Install them directly from the internet"],
         "desc": "Faster now, but the central library is not updated."},
        {"cols": ["Cancel"], "desc": "Exit. Nothing more is installed."},
    ])
    if c == 2:
        raise SystemExit(0)
    return "download" if c == 0 else "online"


def _pip_download(item: dict, central: str, log_path) -> bool:
    """pip wheel also fetches every dependency, so the folder ends up complete for this package."""
    return run_quiet([sys.executable, "-m", "pip", "wheel", "-w", central, "--disable-pip-version-check",
                      *item["extra"], item["spec"]], log_path) == 0


def _install_one(item: dict, mode: str, central: str | None, log_path, hook=None) -> int:
    py = str(item["py"])
    if mode == "central" and not item.get("online"):
        cmd = [py, "-m", "pip", "install", "--disable-pip-version-check", "--no-index",
               f"--find-links={central}", item["spec"]]
    else:
        cmd = [py, "-m", "pip", "install", "--disable-pip-version-check", *item["extra"], item["spec"]]
    return run_quiet(cmd, log_path, hook)


def install_all(items: list[dict], mode: str, central: str | None, log_path) -> None:
    policy: str | None = None  # 'download' | 'online', once the person decided how to treat missing wheels
    if mode == "central":
        assert central
        gone = [it for it in items if not find_wheel(central, it["spec"])]
        if gone:
            show_missing([{**g, "status": "not in central"} for g in gone], title="Not in the central library")
            policy = _ask_missing_policy()
            for g in gone:
                if policy == "online":
                    g["online"] = True
                else:
                    with spinner(f"Downloading {g['lib']} into the central library"):
                        good = _pip_download(g, central, log_path)
                    if not good:
                        fail(f"Could not download {g['lib']}. Is the internet reachable? See {log_path}")
                        raise SystemExit(1)

    section("Installing libraries", note=f"{len(items)} to install")
    prog = InstallProgress(len(items))
    for it in items:
        prog.start(it["lib"])
        rc = _install_one(it, mode, central, log_path, pip_progress_hook(prog))
        if rc != 0 and mode == "central" and not it.get("online"):
            # the wheel is in the folder, but one of ITS dependencies is not (or it does not fit this Python / OS)
            prog.interrupt()
            warn(f"{it['lib']} could not be installed from the central library "
                 "(a dependency or a matching wheel is missing).")
            if policy is None:
                policy = _ask_missing_policy()
            if policy == "download":
                with spinner(f"Downloading {it['lib']} and its dependencies into the central library"):
                    good = _pip_download(it, central, log_path)
                rc = _install_one(it, mode, central, log_path) if good else 1
            else:
                it["online"] = True
                rc = _install_one(it, mode, central, log_path)
            prog.update(0.5)  # redraw this library's bar after the question
        if rc != 0:
            prog.interrupt()
            fail(f"Failed to install {it['lib']}. See {log_path}")
            raise SystemExit(1)
        prog.done()
    prog.close()


def still_missing(items: list[dict]) -> list[dict]:
    """After installing: the items that are STILL not satisfied in their venv (should be none)."""
    out = []
    for venv in {it["venv"] for it in items}:
        group = [it for it in items if it["venv"] == venv]
        gone = {s for s, _ in missing_specs(group[0]["py"], [it["spec"] for it in group])}
        out += [it for it in group if it["spec"] in gone]
    return out


# =====================================================================================================
# Section 9: node  -  Node.js used for the frontend (build / dev server). The order: existing (local or system) ->
# official download from nodejs.org with a sha256 check into <data>/runtime/node (no sudo) -> the system package manager if you agree.
# =====================================================================================================
def _node_min() -> int:
    return int(CFG["frontend"].get("node_min", 18))


def _node_dist() -> str:
    return (os.environ.get(E("NODE_MIRROR")) or CFG.get("node_mirror") or "https://nodejs.org/dist").rstrip("/")


def _layout(root: Path):
    if os.name == "nt":
        return root, root / "node.exe", root / "npm.cmd"
    return root / "bin", root / "bin" / "node", root / "bin" / "npm"


def _major(node_exe, env=None) -> int:
    try:
        out = subprocess.run([str(node_exe), "-v"], capture_output=True, text=True,
                             timeout=20, env=env).stdout
        return int(out.strip().lstrip("v").split(".")[0])
    except Exception:
        return 0


def node_find() -> dict | None:
    """A usable Node (>= node_min) as {"npm", "node", "env", "source", "version"}, or None."""
    cands = []
    bindir, node_exe, npm = _layout(paths.NODE_DIR)
    if node_exe.exists() and npm.exists():
        cands.append(("local", node_exe, npm, bindir))
    n, p = shutil.which("node"), shutil.which("npm")
    if n and p:
        cands.append(("system", Path(n), Path(p), Path(n).parent))
    if os.name == "nt":                          # winget installs here, PATH is not refreshed yet
        for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
            if base:
                b, ne, npm_ = _layout(Path(base) / "nodejs")
                if ne.exists() and npm_.exists():
                    cands.append(("system", ne, npm_, b))
    for source, node_exe, npm, bindir in cands:
        env = {**os.environ, "PATH": str(bindir) + os.pathsep + os.environ.get("PATH", "")}
        major = _major(node_exe, env)
        if major >= _node_min():
            return {"npm": str(npm), "node": str(node_exe), "env": env, "source": source, "version": major}
    return None


def _spec() -> dict | None:
    sysname = platform.system().lower()
    arch = {"x86_64": "x64", "amd64": "x64", "aarch64": "arm64", "arm64": "arm64"}.get(
        platform.machine().lower())
    if not arch:
        return None
    if sysname == "linux":
        return {"index": f"linux-{arch}", "archive": f"linux-{arch}.tar.gz"}
    if sysname == "darwin":
        return {"index": f"osx-{arch}-tar", "archive": f"darwin-{arch}.tar.gz"}
    if sysname == "windows":
        return {"index": f"win-{arch}-zip", "archive": f"win-{arch}.zip"}
    return None


def pick_release(index: list[dict], key: str, min_major: int | None = None) -> str | None:
    """Newest LTS release that has a build for `key`. index.json is sorted newest first."""
    min_major = min_major or _node_min()
    for e in index:
        try:
            major = int(e["version"].lstrip("v").split(".")[0])
        except (KeyError, ValueError):
            continue
        if e.get("lts") and key in e.get("files", []) and major >= min_major:
            return e["version"]
    return None


def _get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": f"{CFG['slug']}-launcher"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _node_download(url: str, dest: Path, label: str) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": f"{CFG['slug']}-launcher"})
    tty = sys.stdout.isatty()
    if not tty:
        info(f"{label} ...")
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
        total, done, last = int(r.headers.get("Content-Length") or 0), 0, -1
        while True:
            chunk = r.read(256 * 1024)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if tty and total and done * 100 // total != last:
                last = done * 100 // total
                sys.stdout.write(f"\r\033[2K  • {label} ... {last}%")
                sys.stdout.flush()
    if tty:
        sys.stdout.write("\r\033[2K")
        sys.stdout.flush()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _extract(archive: Path, dest: Path) -> None:
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as z:
            z.extractall(dest)
        return
    with tarfile.open(archive) as t:
        if hasattr(tarfile, "data_filter"):
            t.extractall(dest, filter="data")
        else:
            root = dest.resolve()
            for m in t.getmembers():
                target = (dest / m.name).resolve()
                if target != root and root not in target.parents:
                    raise RuntimeError(f"unsafe path in archive: {m.name}")
            t.extractall(dest)


def install_portable() -> str:
    """Download the newest LTS into <data>/runtime/node. Returns its version. Raises on any problem."""
    spec = _spec()
    if not spec:
        raise RuntimeError(f"nodejs.org has no build for {platform.system()} {platform.machine()}")
    dist = _node_dist()
    index = json.loads(_get(f"{dist}/index.json"))
    version = pick_release(index, spec["index"])
    if not version:
        raise RuntimeError("no suitable Node.js release found")
    name = f"node-{version}-{spec['archive']}"
    sums = _get(f"{dist}/{version}/SHASUMS256.txt").decode("utf-8", "replace")
    expected = next((ln.split()[0] for ln in sums.splitlines()
                     if len(ln.split()) == 2 and ln.split()[1] == name), None)
    if not expected:
        raise RuntimeError(f"no checksum published for {name}")
    paths.RUNTIME.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="node-", dir=paths.RUNTIME))
    try:
        archive = tmp / name
        _node_download(f"{dist}/{version}/{name}", archive, f"Downloading Node.js {version}")
        if _sha256(archive) != expected:
            raise RuntimeError("the download is corrupt (checksum mismatch)")
        with spinner("Unpacking Node.js"):
            out = tmp / "unpacked"
            _extract(archive, out)
            tops = [p for p in out.iterdir() if p.is_dir()]
            if len(tops) != 1:
                raise RuntimeError("unexpected archive layout")
            if paths.NODE_DIR.exists():
                shutil.rmtree(paths.NODE_DIR)
            shutil.move(str(tops[0]), str(paths.NODE_DIR))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return version


def _system_steps() -> list[list[str]]:
    sysname = platform.system()
    if sysname == "Darwin" and shutil.which("brew"):
        return [["brew", "install", "node"]]
    if sysname == "Windows" and shutil.which("winget"):
        return [["winget", "install", "-e", "--id", "OpenJS.NodeJS.LTS",
                 "--accept-source-agreements", "--accept-package-agreements"]]
    if sysname != "Linux":
        return []
    root = hasattr(os, "geteuid") and os.geteuid() == 0
    if root:
        sudo = []
    elif shutil.which("sudo"):
        sudo = ["sudo"]
    else:
        return []
    if shutil.which("apt-get"):
        return [sudo + ["apt-get", "install", "-y", "ca-certificates", "curl"],
                sudo + ["bash", "-c", "curl -fsSL https://deb.nodesource.com/setup_lts.x | bash -"],
                sudo + ["apt-get", "install", "-y", "nodejs"]]
    if shutil.which("dnf"):
        return [sudo + ["bash", "-c", "curl -fsSL https://rpm.nodesource.com/setup_lts.x | bash -"],
                sudo + ["dnf", "install", "-y", "nodejs"]]
    if shutil.which("pacman"):
        return [sudo + ["pacman", "-S", "--noconfirm", "nodejs", "npm"]]
    return []


def install_system() -> bool:
    """Run the package manager attached to the terminal, so a sudo password prompt works."""
    steps = _system_steps()
    if not steps:
        return False
    for cmd in steps:
        info("$ " + " ".join(cmd))
        if subprocess.run(cmd).returncode != 0:
            return False
    return True


def node_ensure(auto: bool = False) -> dict | None:
    """Return a usable Node (see node_find()), installing one if needed. None if everything failed."""
    found = node_find()
    if found:
        return found
    info(f"Node.js {_node_min()}+ is needed (frontend). "
         f"Installing a private copy in {rel(paths.NODE_DIR)} (no sudo, nothing else on this machine changes) ...")
    try:
        version = install_portable()
        found = node_find()
        if found:
            ok(f"Node.js {version} installed")
            return found
        warn("Node.js was unpacked but does not run on this machine.")
    except Exception as e:
        warn(f"Could not download Node.js: {e}")

    if not _system_steps():
        return None
    if auto or not sys.stdin.isatty():
        info(f"Skipping the system package manager (non-interactive). Install Node {_node_min()}+ yourself and run again.")
        return None
    if not ask_yes_no("Install Node.js with the system package manager instead? It may ask for your sudo password.",
                      True):
        return None
    if install_system():
        found = node_find()
        if found:
            ok(f"Node.js {found['version']} installed")
            return found
    warn("The system install did not give a working Node.js.")
    return None


# ------------------------------------------------------------------ frontend (npm / pnpm / yarn / bun)
_PM_INSTALL = {"npm": ["install", "--no-audit", "--no-fund"], "pnpm": ["install"], "yarn": ["install"],
               "bun": ["install"]}
_LOCKS = ("package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb", "bun.lock")


def detect_pm(folder: Path, preferred: str = "auto") -> str:
    if preferred and preferred != "auto":
        return preferred
    try:
        name = str(json.loads((folder / "package.json").read_text(encoding="utf-8")).get("packageManager", ""))
        name = name.split("@")[0]
        if name in _PM_INSTALL:
            return name
    except (OSError, ValueError, AttributeError):
        pass
    for lock, name in (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("bun.lockb", "bun"),
                       ("bun.lock", "bun"), ("package-lock.json", "npm")):
        if (folder / lock).exists():
            return name
    return "npm"


def resolve_pm(name: str, tool: dict) -> tuple[str, str]:
    if name == "npm" or name not in _PM_INSTALL:
        return tool["npm"], "npm"
    exe = shutil.which(name, path=tool["env"]["PATH"])
    if exe:
        return exe, name
    warn(f"{name} is not installed (try: corepack enable). Falling back to npm.")
    return tool["npm"], "npm"


def _watch_files(folder: Path, names: list[str]):
    for n in names:
        p = folder / n
        if p.is_file():
            yield p
        elif p.is_dir():
            yield from (f for f in p.rglob("*") if f.is_file() and "node_modules" not in f.parts)


def _build_stale(folder: Path, fe: dict) -> bool:
    marker = folder / fe.get("dist", "dist") / fe.get("dist_marker", "index.html")
    if not marker.exists():
        return True
    built = marker.stat().st_mtime
    return any(f.stat().st_mtime > built for f in _watch_files(folder, fe.get("watch", [])))


def _has_deps(folder: Path) -> bool:
    try:
        pj = json.loads((folder / "package.json").read_text(encoding="utf-8"))
        return any(pj.get(k) for k in ("dependencies", "devDependencies", "optionalDependencies"))
    except (OSError, ValueError, AttributeError):
        return True


def _install_stale(folder: Path) -> bool:
    nm = folder / "node_modules"
    if not nm.exists():
        return _has_deps(folder)          # package.json without dependencies: nothing to install
    stamp = nm / ".launcher-stamp"
    if not stamp.exists():
        return False                      # installed by hand: leave it alone
    t = stamp.stat().st_mtime
    return any((folder / n).exists() and (folder / n).stat().st_mtime > t for n in ("package.json", *_LOCKS))


def _services_need_node(profile: str) -> bool:
    blob = json.dumps([[s.get("cmd"), s.get("env"), s.get("extra_args")] for s in CFG["services"] if active(s, profile)]
                      + [h for hs in CFG["hooks"].values() for h in hs if active(h, profile)], default=str)
    return any(k in ("pm", "npm", "node") for k in _TPL.findall(blob)) or bool(
        re.search(r"\b(npm|npx|node|pnpm|yarn|bun)\b", blob))


def ensure_frontend(profile: str, skip: bool, auto: bool) -> dict | None:
    """Prepares the frontend: Node + install + build. Returns the tool (Node) if it was required, otherwise None."""
    fe = CFG["frontend"]
    section("Frontend")
    if skip:
        info("--no-frontend: the frontend is not touched")
        return None
    if not fe.get("enabled", True):
        info('Frontend is disabled in CONFIG ("frontend.enabled").')
        return None
    folder = BASE_DIR / fe.get("dir", "frontend")
    if not (folder / "package.json").exists():
        info(f"{rel(folder)}/package.json not found: no frontend to prepare.")
        return None
    os.environ[E("FRONTEND_DIST")] = str(folder / fe.get("dist", "dist"))
    want_install = profile in fe.get("install_in", ["dev", "prod"]) and _install_stale(folder)
    want_build = profile in fe.get("build_in", ["prod"]) and _build_stale(folder, fe)
    needs_node = _services_need_node(profile)
    if not (want_install or want_build or needs_node):
        ok("Frontend is up to date")
        return None
    tool = node_ensure(auto)
    if not tool:
        (fail if fe.get("required") else warn)(
            f"Node.js (npm) is not available, so the frontend cannot be prepared. Install Node {_node_min()}+ "
            "from nodejs.org and run again.")
        if fe.get("required"):
            sys.exit(1)
        return None
    pm_exe, pm_name = resolve_pm(detect_pm(folder, fe.get("package_manager", "auto")), tool)
    tool["pm"], tool["pm_name"] = pm_exe, pm_name
    log = paths.FRONTEND_LOG
    if want_install:
        with spinner(f"Installing frontend packages ({pm_name}) ..."):
            rc, tail = run_step([pm_exe, *_PM_INSTALL[pm_name]], log, env=tool["env"], cwd=folder)
        if rc != 0:
            (fail if fe.get("required") else warn)(f"{pm_name} install failed.")
            show_tail(tail, log)
            if fe.get("required"):
                sys.exit(1)
            return tool
        with contextlib.suppress(OSError):
            (folder / "node_modules" / ".launcher-stamp").touch()
        ok("Frontend packages installed")
    if want_build:
        with spinner("Building the frontend ..."):
            rc, tail = run_step([pm_exe, "run", fe.get("build_script", "build")], log, env=tool["env"], cwd=folder)
        if rc != 0:
            (fail if fe.get("required") else warn)("Frontend build failed.")
            show_tail(tail, log)
            if fe.get("required"):
                sys.exit(1)
            return tool
        ok(f"Frontend built ({fe.get('dist', 'dist')}/)")
    ok(f"Node.js {tool['version']} ({tool['source']}) · {pm_name}")
    return tool


# =====================================================================================================
# Section 10: runtime  -  ports, placeholders, hooks, processes, supervisor
# =====================================================================================================
def host() -> str:
    return os.environ.get(E("HOST")) or CFG["host"]


def _port_env(name: str) -> str:
    return E("PORT") if name == "main" else E("PORT_" + re.sub(r"\W+", "_", name).upper())


def base_ports() -> dict[str, int]:
    out = {}
    for n, p in CFG["ports"].items():
        raw = os.environ.get(_port_env(n))
        try:
            out[n] = int(raw) if raw else int(p)
        except ValueError:
            fail(f"{_port_env(n)} must be a number.")
            sys.exit(1)
    return out


def port_busy(h: str, p: int) -> bool:
    target = "127.0.0.1" if h in ("0.0.0.0", "", "::", "localhost") else h
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((target, p)) == 0


def free_port(start: int, avoid: set[int]) -> int:
    for p in range(start, start + 200):
        if p not in avoid and not port_busy(host(), p):
            return p
    raise RuntimeError(f"no free port found near {start}")


def _service_ports(spec: dict) -> set[str]:
    blob = json.dumps([spec.get("cmd"), spec.get("env"), spec.get("health"), spec.get("extra_args")], default=str)
    names = set()
    for k in _TPL.findall(blob):
        if k == "port":
            names.add("main")
        elif k.startswith("port."):
            names.add(k[5:])
    return names & set(CFG["ports"])


def resolve_ports(profile: str, auto: bool) -> dict[str, int]:
    """Checks only the ports used by the active services. If a port is busy: picks the nearest free port (or asks you)."""
    ports = base_ports()
    used: set[str] = set()
    for s in CFG["services"]:
        if active(s, profile):
            used |= _service_ports(s)
    for n in sorted(used, key=lambda x: (x != "main", x)):
        p = ports[n]
        if not port_busy(host(), p):
            continue
        nxt = free_port(p + 1, set(ports.values()))
        if auto or not INTERACTIVE:
            warn(f"Port {p} ({n}) is already in use: using {nxt} instead.")
        else:
            c = menu(f"Port {p} ({n}) is already in use", ["Action"], [
                {"cols": [f"Use port {nxt} instead"], "state": "rec",
                 "desc": f"Another program uses {p}. The launcher continues on {nxt}."},
                {"cols": ["Cancel"], "desc": f"Exit. Close the other program or set {_port_env(n)} to another port."},
            ])
            if c == 1:
                raise SystemExit(1)
        ports[n] = nxt
    for n, p in ports.items():
        os.environ[_port_env(n)] = str(p)
    return ports


def make_vars(profile: str, ports: dict[str, int], sel: dict, tool: dict | None) -> Vars:
    v = Vars(host=host(), port=ports["main"], profile=profile, root=str(BASE_DIR), data=str(paths.DATA_DIR),
             runtime=str(paths.RUNTIME), logs=str(paths.LOGS))
    for n, p in ports.items():
        v[f"port.{n}"] = p
    for k, x in sel.items():
        v[f"sel.{k}"] = ("true" if x else "false") if isinstance(x, bool) else x
    for i, e in enumerate(CFG["environments"]):
        v[f"py.{e['name']}"] = str(env_python(e))
        if i == 0:
            v["py"] = str(env_python(e))
    v.setdefault("py", sys.executable)
    pm = (tool or {}).get("pm") or shutil.which("npm") or "npm"
    v["pm"] = v["npm"] = pm
    v["node"] = (tool or {}).get("node") or shutil.which("node") or "node"
    return v


def expand_cmd(cmd, vars_: dict, where: str) -> list[str]:
    toks = shlex.split(cmd) if isinstance(cmd, str) else list(cmd or [])
    out = []
    for t in toks:
        e = expand(str(t), vars_)
        bad = unresolved(e)
        if bad:
            fail(f"{where}: unknown placeholder {{{bad[0]}}}.")
            info("Available: host, port, port.NAME, profile, root, data, runtime, logs, py, py.ENV, pm, node, "
                 "sel.ID, env.NAME (must be set), i")
            sys.exit(1)
        if e != "":
            out.append(e)
    return out


def expand_checked(s: str, vars_: dict, where: str) -> str:
    e = expand(s, vars_)
    bad = unresolved(e)
    if bad:
        fail(f"{where}: unknown placeholder {{{bad[0]}}}.")
        sys.exit(1)
    return e


def base_env(tool: dict | None) -> dict:
    env = dict(os.environ)
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    if tool:
        env["PATH"] = tool["env"]["PATH"]
    return env


def with_venv(env: dict, name: str | None) -> None:
    """Puts the venv's bin first in PATH (so any command like alembic / celery is found) and sets VIRTUAL_ENV."""
    spec = env_spec(name) if name else None
    if spec and uses_venv(spec):
        bindir = env_python(spec).parent
        env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
        env["VIRTUAL_ENV"] = str(bindir.parent)


def resolve_argv(argv: list[str], env: dict, cwd: Path, where: str) -> list[str]:
    if not argv:
        fail(f"{where}: empty command.")
        sys.exit(1)
    exe = argv[0]
    found = shutil.which(exe, path=env.get("PATH"))
    if not found and (os.sep in exe or "/" in exe):
        cand = Path(exe) if Path(exe).is_absolute() else cwd / exe
        if cand.exists():
            found = str(cand)
    if not found:
        fail(f"{where}: command not found: {exe}")
        info("Is the library installed in its environment, or is the tool missing from PATH?")
        sys.exit(1)
    return [found, *argv[1:]]


# ------------------------------------------------------------------ hooks
def run_hooks(stage: str, profile: str, vars_: dict, env0: dict) -> None:
    hooks = [h for h in CFG["hooks"].get(stage, []) if active(h, profile)]
    if not hooks:
        return
    section("Hooks", note=stage)
    for h in hooks:
        where = f"hook '{h.get('name', stage)}'"
        cwd = BASE_DIR / h.get("cwd", ".")
        env = dict(env0)
        with_venv(env, h.get("venv"))
        for k, x in (h.get("env") or {}).items():
            env[k] = expand_checked(str(x), vars_, where)
        argv = resolve_argv(expand_cmd(h["cmd"], vars_, where), env, cwd, where)
        label = h.get("name") or " ".join(argv[:2])
        with spinner(label):
            rc, tail = run_step(argv, paths.HOOKS_LOG, env=env, cwd=cwd)
        if rc == 0:
            ok(label)
        elif h.get("optional"):
            warn(f"{label} failed (optional, continuing).")
            show_tail(tail, paths.HOOKS_LOG, 4)
        else:
            fail(f"{label} failed (exit {rc}).")
            show_tail(tail, paths.HOOKS_LOG)
            sys.exit(1)


# ------------------------------------------------------------------ instance state
def read_state() -> dict:
    try:
        d = json.loads(paths.STATE_FILE.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def write_state(d: dict) -> None:
    try:
        paths.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        paths.STATE_FILE.write_text(json.dumps(d, indent=2), encoding="utf-8")
    except OSError:
        pass


def clear_state() -> None:
    with contextlib.suppress(OSError):
        paths.STATE_FILE.unlink()


def pid_alive(pid: int) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name == "nt":
        try:
            out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True,
                                 timeout=10).stdout
            return str(pid) in out
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


def instance_running() -> dict | None:
    st = read_state()
    pid = st.get("pid")
    if pid and pid != os.getpid() and pid_alive(pid):
        return st
    return None


def _owned(pid: int, argv: list[str]) -> bool:
    """Makes sure the pid is still the same service we started (not a reused pid). POSIX only."""
    if os.name == "nt" or not argv:
        return False
    try:
        cl = Path(f"/proc/{pid}/cmdline")
        line = (cl.read_bytes().replace(b"\0", b" ").decode("utf-8", "replace") if cl.exists() else
                subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True,
                               timeout=5).stdout)
    except Exception:
        return False
    return bool(line.strip()) and all(tok in line for tok in argv[:3])


def leftover_services(state: dict) -> list[dict]:
    """Services from an old run whose launcher died (kill -9 / terminal closed) but are still running."""
    return [s for s in state.get("services", []) if s.get("pid") and pid_alive(s["pid"])
            and _owned(s["pid"], s.get("argv") or [])]


def reap_stale_state() -> int:
    """Cleans up orphaned services (if any) and deletes the old state file. Returns the number that were stopped."""
    st = read_state()
    if not st or instance_running():
        return 0
    left = leftover_services(st)
    for s in left:
        with contextlib.suppress(OSError, ProcessLookupError):
            os.killpg(s["pid"], signal.SIGTERM)
    end = time.time() + 6
    while left and time.time() < end and any(pid_alive(s["pid"]) for s in left):
        time.sleep(0.2)
    for s in left:
        if pid_alive(s["pid"]):
            with contextlib.suppress(OSError, ProcessLookupError):
                os.killpg(s["pid"], signal.SIGKILL)
    clear_state()
    return len(left)


def fmt_dur(sec: float) -> str:
    sec = int(max(sec, 0))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m {s:02d}s" if m else f"{s}s"


# ------------------------------------------------------------------ processes
_SVC_COLORS = ("sky", "pink", "amber", "teal", "accent")
_OUT_LOCK = threading.Lock()


def rotate_log(path: Path) -> None:
    try:
        if path.exists() and path.stat().st_size > float(CFG.get("log_max_mb", 5)) * 1024 * 1024:
            os.replace(path, path.with_suffix(".log.1"))
    except OSError:
        pass


def log_prefix(name: str, color_i: int, w: int) -> str:
    return _paint(_SVC_COLORS[color_i % len(_SVC_COLORS)], _pad(name, w), True) + " " + gray("│") + " "


class Proc:
    """A running service: Popen + a thread that reads the output (log + prefixed printing) + a restart policy with backoff."""

    def __init__(self, name, argv, cwd, env, log_path, *, restart="never", max_restarts=5, essential=True,
                 health=None, health_timeout=60, color_i=0, name_w=8):
        self.name, self.argv, self.cwd, self.env, self.log_path = name, argv, cwd, env, Path(log_path)
        self.restart, self.max_restarts, self.essential = restart, int(max_restarts), essential
        self.health, self.health_timeout = health, int(health_timeout)
        self.color_i, self.name_w = color_i, name_w
        self.p: subprocess.Popen | None = None
        self.state, self.rc, self.restarts, self.resume_at, self.delay = "new", None, 0, 0.0, 0
        self.started = 0.0
        self.stream = False
        self.tail: deque[str] = deque(maxlen=40)

    @property
    def pid(self) -> int:
        return self.p.pid if self.p else 0

    def start(self) -> None:
        rotate_log(self.log_path)
        flags: dict = {}
        if os.name == "nt":
            flags["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        else:
            flags["start_new_session"] = True          # Ctrl+C in the terminal does not reach the services; we are the ones who stop them
        self.p = subprocess.Popen(self.argv, cwd=self.cwd, env=self.env, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
                                  errors="replace", bufsize=1, **flags)
        self.started, self.state = time.time(), "up"
        threading.Thread(target=self._pump, args=(self.p,), daemon=True).start()

    def _pump(self, p: subprocess.Popen) -> None:
        prefix = log_prefix(self.name, self.color_i, self.name_w)
        try:
            with open(self.log_path, "a", encoding="utf-8", buffering=1) as lf:
                lf.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} started: {' '.join(self.argv)}\n")
                assert p.stdout is not None
                for line in p.stdout:
                    lf.write(line)
                    line = line.rstrip("\r\n")
                    self.tail.append(line)
                    if self.stream:
                        with _OUT_LOCK:
                            sys.stdout.write(prefix + line + "\n")
                            sys.stdout.flush()
        except (OSError, ValueError):
            pass

    def poll(self):
        return self.p.poll() if self.p else None

    def tick(self) -> str | None:
        """Called roughly every half second. Returns an event: crashed / restarted / exited (or None)."""
        now = time.time()
        if self.state == "up":
            rc = self.poll()
            if rc is None:
                if self.restarts and now - self.started > 60:
                    self.restarts = 0                      # ran a full minute: reset the counter
                return None
            self.rc = rc
            if (self.restart == "always" or (self.restart == "on-failure" and rc != 0)) \
                    and self.restarts < self.max_restarts:
                self.restarts += 1
                self.delay = min(2 ** (self.restarts - 1), 15)
                self.resume_at, self.state = now + self.delay, "backoff"
                return "crashed"
            self.state = "dead"
            return "exited"
        if self.state == "backoff" and now >= self.resume_at:
            self.start()
            return "restarted"
        return None

    def stop(self, timeout: float = 8.0) -> None:
        p = self.p
        self.state = "dead"
        if not p or p.poll() is not None:
            return
        try:
            if os.name == "nt":
                p.send_signal(signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
            else:
                os.killpg(p.pid, signal.SIGTERM)
        except (OSError, ValueError):
            pass
        try:
            p.wait(timeout)
        except subprocess.TimeoutExpired:
            try:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
                else:
                    os.killpg(p.pid, signal.SIGKILL)
                p.wait(5)
            except (OSError, subprocess.TimeoutExpired):
                pass


def probe(url: str) -> bool:
    """tcp://host:port or http(s)://... any HTTP reply below 500 means the server is awake."""
    if url.startswith("tcp://"):
        h, _, p = url[6:].partition(":")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            return s.connect_ex((h or "127.0.0.1", int(p or 80))) == 0
    try:
        with urllib.request.urlopen(url, timeout=2):
            return True
    except urllib.error.HTTPError as e:
        return e.code < 500
    except (OSError, ValueError, http.client.HTTPException):
        return False


def wait_healthy(proc: Proc) -> bool:
    deadline = time.time() + proc.health_timeout
    with spinner(f"Starting {proc.name} · waiting for {proc.health}"):
        while time.time() < deadline:
            if proc.poll() is not None:
                return False
            if probe(proc.health):
                return True
            time.sleep(0.4)
    return False


def _build_proc(spec: dict, idx: int, count: int, profile: str, vars_: dict, env0: dict, color_i: int,
                name_w: int) -> Proc:
    v = Vars(vars_)
    v["i"] = idx
    name = spec["name"] if count == 1 else f"{spec['name']}-{idx}"
    where = f"service '{name}'"
    cmd = expand_cmd(spec["cmd"], v, where) + expand_cmd((spec.get("extra_args") or {}).get(profile, []), v, where)
    cwd = BASE_DIR / spec.get("cwd", ".")
    if not cwd.is_dir():
        fail(f"{where}: folder not found: {rel(cwd)}")
        sys.exit(1)
    env = dict(env0)
    with_venv(env, spec.get("venv"))
    for k, x in (spec.get("env") or {}).items():
        env[k] = expand_checked(str(x), v, where)
    argv = resolve_argv(cmd, env, cwd, where)
    health = expand_checked(spec["health"], v, where) if spec.get("health") else None
    return Proc(name, argv, cwd, env, paths.LOGS / f"service-{name}.log", restart=spec.get("restart", "never"),
                max_restarts=spec.get("max_restarts", 5), essential=spec.get("essential", True), health=health,
                health_timeout=spec.get("health_timeout", 60), color_i=color_i, name_w=name_w)


def _save_state(profile: str, procs: list[Proc], started: float) -> None:
    write_state({"pid": os.getpid(), "profile": profile, "started": started, "root": str(BASE_DIR),
                 "services": [{"name": p.name, "pid": p.pid, "health": p.health, "argv": p.argv} for p in procs]})


def stop_all(procs: list[Proc]) -> None:
    alive = [p for p in procs if p.p and p.poll() is None]
    if alive:
        with spinner(f"Stopping {len(alive)} service(s)"):
            for p in reversed(procs):
                p.stop()
    ok("Stopped")


def supervise(procs: list[Proc]) -> int:
    try:
        while True:
            time.sleep(0.4)
            for p in procs:
                ev = p.tick()
                if ev == "crashed":
                    warn(f"{p.name} exited with code {p.rc}. Restarting in {p.delay}s "
                         f"({p.restarts}/{p.max_restarts}) ...")
                elif ev == "restarted":
                    ok(f"{p.name} restarted · pid {p.pid}")
                elif ev == "exited":
                    if p.essential:
                        fail(f"{p.name} stopped (exit code {p.rc}"
                             + (f", gave up after {p.max_restarts} restarts" if p.restarts else "") + "). "
                             "Stopping everything.")
                        show_tail(list(p.tail), p.log_path)
                        return p.rc or 1
                    warn(f"{p.name} stopped (exit code {p.rc}). The other services keep running.")
            if all(p.state == "dead" for p in procs):
                info("All services have stopped.")
                return 0
    except KeyboardInterrupt:
        print()
        info("Ctrl+C received.")
        return 0


def _install_term_handlers() -> None:
    def _raise(signum, frame):  # noqa: ARG001
        raise KeyboardInterrupt
    for name in ("SIGINT", "SIGTERM", "SIGHUP", "SIGBREAK"):
        sig = getattr(signal, name, None)
        if sig is not None:
            with contextlib.suppress(ValueError, OSError):
                signal.signal(sig, _raise)


def step_launch(args: argparse.Namespace, sel: dict, profile: str, vars_: dict, tool: dict | None) -> int:
    step(4, "Launch")
    specs = [s for s in CFG["services"] if active(s, profile)]
    if not specs:
        box("NOTHING TO LAUNCH", [f"No service is enabled for profile '{profile}'.",
                                  'Add services in CONFIG["services"] (check "profiles" and "when_exists").'])
        return 0
    env0 = base_env(tool)
    run_hooks("before_launch", profile, vars_, env0)

    section("Services", note=profile)
    plan: list[tuple[dict, int, int]] = []
    for s in specs:
        raw = expand_checked(str(s.get("count", 1)), vars_, f"service '{s['name']}' count")
        try:
            n = max(1, int(raw))
        except ValueError:
            fail(f"service '{s['name']}': count '{raw}' is not a number.")
            sys.exit(1)
        plan += [(s, i, n) for i in range(1, n + 1)]
    name_w = max(len(s["name"] if n == 1 else f"{s['name']}-{n}") for s, _, n in plan)
    procs: list[Proc] = []
    started = time.time()
    _install_term_handlers()
    code = 0
    try:
        for ci, (s, i, n) in enumerate(plan):
            p = _build_proc(s, i, n, profile, vars_, env0, ci, name_w)
            procs.append(p)
            p.start()
            _save_state(profile, procs, started)
            if p.health:
                good = wait_healthy(p)
            else:
                time.sleep(1.0)                              # a short window to detect that it crashed immediately
                good = p.poll() is None
            if not good:
                died = p.poll() is not None
                fail(f"{p.name} " + (f"exited with code {p.poll()}." if died
                                     else f"did not answer on {p.health} within {p.health_timeout}s."))
                show_tail(list(p.tail), p.log_path)
                code = 1
                return code
            ok(f"{p.name} is up · pid {p.pid}" + (f" · {p.health}" if p.health else ""))

        run_hooks("after_launch", profile, vars_, env0)
        links = [(u.get("label", "URL"), expand_checked(u["url"], vars_, "urls")) for u in CFG["urls"]
                 if active(u, profile)]
        rows = [(lbl, url) for lbl, url in links] + [("Profile", profile)]
        for q in _questions():
            key = E(re.sub(r"\W+", "_", q["id"]).upper())
            value = sel.get(q["id"])
            if key in _REAL_ENV:  # an explicit -e / system env override wins (same rule as apply_selection)
                value = os.environ.get(key, value)
            rows.append((q.get("title") or q["id"], _label(q, value)))
        rows.append(("Logs", str(paths.LOGS)))
        print()
        box(f"{NAME.upper()} IS RUNNING", kv_lines(rows))
        if CFG.get("open_browser") and not args.no_browser and INTERACTIVE:
            first = next((expand_checked(u["url"], vars_, "urls") for u in CFG["urls"]
                          if u.get("open") and active(u, profile)), None)
            if first:
                with contextlib.suppress(Exception):
                    webbrowser.open(first)
        streaming = CFG.get("stream_logs", True) and not args.quiet
        if streaming:
            print()
            print(gray("  " + "─" * (width() - 4)))
            print("  " + gray("Live logs · Ctrl+C to stop everything"))
        else:
            info("Running. Press Ctrl+C to stop everything.")
        for p in procs:
            p.stream = streaming
        code = supervise(procs)
    except KeyboardInterrupt:
        print()
        info("Ctrl+C received.")
    finally:
        for p in procs:
            p.stream = False
        stop_all(procs)
        clear_state()
        with contextlib.suppress(SystemExit):
            run_hooks("after_stop", profile, vars_, env0)
    return code


# =====================================================================================================
# Section 11: run  -  the four steps in order (Libraries -> Selection -> Prepare -> Launch)
# =====================================================================================================
def _reexec_in_env() -> None:
    """If CONFIG["run_inside_env"] is set: makes sure the venv exists and then re-runs the same script inside it."""
    spec = env_spec(CFG.get("run_inside_env") or "")
    if not spec or not uses_venv(spec):
        return
    py = env_python(spec)
    if Path(sys.executable).absolute() == py.absolute() or os.environ.get(E("IN_VENV")) == "1":
        return
    if not py.exists():
        info(f"Creating the {spec['name']} environment (first run only) ...")
    try:
        ensure_venv(spec)
    except RuntimeError as e:
        fail(str(e))
        sys.exit(1)
    argv = [str(py), str(Path(__file__).resolve())] + sys.argv[1:]
    os.environ[E("IN_VENV")] = "1"
    if os.name == "nt":  # os.execv does not replace the process on Windows
        sys.exit(subprocess.call(argv))
    os.execv(str(py), argv)


def step_libraries(args: argparse.Namespace) -> None:
    step(1, "Libraries")
    section("Checking environments")
    envs = CFG["environments"]
    if not envs:
        info('No Python environments configured (CONFIG["environments"]).')
        return
    fps = dict(_read_state_file().get("fingerprints") or {})
    reports: list[dict] = []
    good_fp: dict[str, str] = {}
    active_envs: list[dict] = []
    for spec in envs:
        name = spec["name"]
        absent = [f for f in spec["requirements"] if not (BASE_DIR / f).is_file()]
        if not spec["requirements"] or absent:
            what = ", ".join(absent) or "no requirements file"
            if spec["required"]:
                fail(f"{name}: {what} not found.")
                sys.exit(1)
            warn(f"{name}: {what} not found. Environment skipped.")
            continue
        try:
            created = ensure_venv(spec)
            if created:
                ok(f"{name} environment created")
        except RuntimeError as e:
            fail(str(e))
            sys.exit(1)
        active_envs.append(spec)
        fp = fingerprint(spec)
        if not args.recheck and not created and fps.get(name) == fp and env_python(spec).exists():
            reports.append({"name": name, "total": len(env_specs(spec)), "missing": [], "cached": True})
            good_fp[name] = fp
            continue
        rep = check_environment(spec)
        reports.append(rep)
        if not rep["missing"]:
            good_fp[name] = fp
    if not reports:
        return
    show_environments(reports)

    def remember() -> None:
        state = _read_state_file()
        state["fingerprints"] = good_fp
        _write_state_file(state)

    pending = [it for r in reports for it in r["missing"]]
    if not pending:
        ok("All required libraries are present")
        remember()
        return
    show_missing(pending)
    mode, central = choose_source(args.central or os.environ.get(E("CENTRAL")))
    install_all(pending, mode, central, paths.INSTALL_LOG)
    importlib.invalidate_caches()
    left = still_missing(pending)
    if left:
        fail("Still missing after the install: " + ", ".join(it["lib"] for it in left)
             + f". See {paths.INSTALL_LOG}")
        sys.exit(1)
    for spec in active_envs:
        good_fp[spec["name"]] = fingerprint(spec)
    remember()


def step_prepare(args: argparse.Namespace, profile: str, auto: bool) -> dict | None:
    step(3, "Prepare")
    ensure_dirs()
    if CFG["env_vars"]:
        section("Environment variables", note=paths.ENV_FILE.name)
        rows, blocking = [], []
        for spec in CFG["env_vars"]:
            n = spec["name"]
            gen = _GENERATORS.get(spec.get("generate", ""))
            if not os.environ.get(n) and gen:
                try:
                    envfile_save_key(n, gen())
                    _GENERATED.add(n)
                except (OSError, ValueError) as e:
                    warn(f"Could not save the generated {n}: {e}")
            if not os.environ.get(n) and spec.get("required"):
                ensure_env_vars([n], auto, required=True)
            have = bool(os.environ.get(n))
            if have:
                status = green("✓ set")
            elif spec.get("required"):
                status, _ = red("✗ missing"), blocking.append(n)
            else:
                status = yellow("· optional")
            rows.append([n, status, env_source(spec) if have else "-", spec.get("desc", "")])
        table(["Variable", "Status", "Source", "Description"], rows)
        if blocking:
            fail("Required variables are missing: " + ", ".join(blocking))
            info(f"Put them in {paths.ENV_FILE.name} (run `python {Path(__file__).name} init` for a template) "
                 "and run again.")
            sys.exit(1)
    section("Data")
    ok(f"Data folder: {paths.DATA_DIR}")
    for s in CFG["data_subdirs"]:
        info(f"{s}/ → {paths.DATA_DIR / s}")
    return ensure_frontend(profile, args.no_frontend, auto)


def cmd_run(args: argparse.Namespace, profile: str, launch: bool = True) -> int:
    auto = _auto()
    ensure_dirs()
    if launch and not args.force:
        st = instance_running()
        if st:
            banner()
            fail(f"Already running (pid {st['pid']}, profile {st.get('profile')}). "
                 f"Run `python {Path(__file__).name} stop` first, or use --force.")
            return 1
    _reexec_in_env()
    banner(f"{CFG.get('tagline', '')} · profile: {profile}".strip(" ·"))
    if launch:
        n = reap_stale_state()
        if n:
            warn(f"Stopped {n} service(s) left over from a previous run that did not exit cleanly.")
    ports = resolve_ports(profile, auto) if launch else base_ports()

    step_libraries(args)
    base_vars = make_vars(profile, ports, {}, None)
    run_hooks("after_libraries", profile, base_vars, base_env(None))

    step(2, "Selection")
    if not _questions():
        info('No questions configured (CONFIG["questions"]).')
    sel = run_selection(auto, args.reselect)
    apply_selection(sel, base_vars)

    # S5 (2026-11-16): the "port" selection question feeds <PREFIX>_PORT — the same env var
    # _port_env("main") reads — and apply_selection exported it above. An explicit --port wins
    # (it is added to _REAL_ENV, so apply_selection left it alone). Sync the ports dict with the
    # chosen value, busy-check it exactly like resolve_ports does, and record the final port in
    # .env as API_PORT so integrations (the demo store) can find the backend.
    if args.port is None:
        raw = (os.environ.get(_port_env("main")) or "").strip()
        if raw.isdigit() and int(raw) != ports["main"]:
            info(f"Main port: {int(raw)} (from your selection)")
            ports["main"] = int(raw)
            if port_busy(host(), ports["main"]):
                nxt = free_port(ports["main"] + 1, set(ports.values()))
                warn(f"Port {ports['main']} (main) is already in use: using {nxt} instead.")
                ports["main"] = nxt
            os.environ[_port_env("main")] = str(ports["main"])
    envfile_save_key("API_PORT", str(ports["main"]))

    tool = step_prepare(args, profile, auto)
    vars_ = make_vars(profile, ports, sel, tool)
    if not launch:
        print()
        box("SETUP COMPLETE", kv_lines([("Profile", profile), ("Data", str(paths.DATA_DIR)),
                                        ("Logs", str(paths.LOGS)),
                                        ("Next", f"python {Path(__file__).name} {profile}")]))
        return 0
    return step_launch(args, sel, profile, vars_, tool)


# =====================================================================================================
# Section 12: the remaining commands  (doctor / status / stop / logs / clean / init / config)
# =====================================================================================================
def cmd_doctor(args: argparse.Namespace, profile: str) -> int:
    banner(f"Diagnostics · profile: {profile}")
    rows: list[list[str]] = []
    counts = {"ok": 0, "warn": 0, "fail": 0}
    badge = {"ok": green("✓ ok"), "warn": yellow("! warn"), "fail": red("✗ fail")}

    def add(level: str, check: str, detail: str = "") -> None:
        counts[level] += 1
        rows.append([badge[level], check, detail])

    pmin = ".".join(map(str, CFG["python_min"]))
    add("ok" if sys.version_info >= CFG["python_min"] else "fail", "Python",
        f"{platform.python_version()} (needs {pmin}+) · {sys.executable}")
    add("ok", "System", f"{platform.system()} {platform.release()} · {platform.machine()} · {os.cpu_count()} cores")
    add("ok" if INTERACTIVE else "warn", "Terminal",
        f"{'interactive' if INTERACTIVE else 'non-interactive (questions use defaults)'} · "
        f"{'colors' if _COLOR else 'no colors'}{' · truecolor' if _TRUE else ''}")

    for spec in CFG["environments"]:
        n = spec["name"]
        absent = [f for f in spec["requirements"] if not (BASE_DIR / f).is_file()]
        if not spec["requirements"] or absent:
            add("fail" if spec["required"] else "warn", f"Env '{n}'", f"requirements not found: {', '.join(absent)}")
            continue
        py = env_python(spec)
        if not py.exists():
            add("warn", f"Env '{n}'", "virtual environment not created yet (setup will create it)")
            continue
        miss = missing_specs(py, env_specs(spec))
        add("ok" if not miss else "warn", f"Env '{n}'",
            "all libraries satisfied" if not miss else f"{len(miss)} missing/outdated: "
            + ", ".join(base_name(s) for s, _ in miss[:5]) + ("…" if len(miss) > 5 else ""))

    fe = CFG["frontend"]
    fdir = BASE_DIR / fe.get("dir", "frontend")
    if fe.get("enabled", True) and (fdir / "package.json").exists():
        tool = node_find()
        add("ok" if tool else "warn", "Node.js", f"v{tool['version']} ({tool['source']})" if tool
            else f"not found (needs {_node_min()}+; the launcher downloads a private copy when needed)")
        add("ok", "Package manager", detect_pm(fdir, fe.get("package_manager", "auto")))
    else:
        add("ok", "Frontend", "none configured / no package.json")
    for t in CFG["doctor"].get("tools", []):
        p = shutil.which(t)
        add("ok" if p else "warn", f"Tool '{t}'", p or "not found (only needed if your hooks use it)")

    add("ok" if paths.ENV_FILE.is_file() else "warn", ".env", str(paths.ENV_FILE) if paths.ENV_FILE.is_file()
        else "not found (run `init` for a template)")
    for spec in CFG["env_vars"]:
        have = bool(os.environ.get(spec["name"]))
        if spec.get("required"):
            add("ok" if (have or spec.get("generate")) else "fail", f"Var {spec['name']}",
                "set" if have else "will be generated" if spec.get("generate") else "missing (required)")

    ports = base_ports()
    used = set()
    for s in CFG["services"]:
        if active(s, profile):
            used |= _service_ports(s)
    for n in sorted(used):
        busy = port_busy(host(), ports[n])
        add("warn" if busy else "ok", f"Port {ports[n]} ({n})", "in use (the launcher will pick another)" if busy
            else "free")

    probe_vars = make_vars(profile, ports, load_selection(), None)
    for s in CFG["services"]:
        if not active(s, profile):
            continue
        bad = unresolved(expand(json.dumps([s.get("cmd"), s.get("env"), s.get("health"), s.get("extra_args")],
                                           default=str), probe_vars))
        cwd = BASE_DIR / s.get("cwd", ".")
        if bad:
            add("fail", f"Service '{s['name']}'", f"unknown placeholder {{{bad[0]}}}")
        elif not cwd.is_dir():
            add("fail", f"Service '{s['name']}'", f"folder not found: {rel(cwd)}")
        else:
            add("ok", f"Service '{s['name']}'", f"config OK · cwd {rel(cwd)}")

    where = paths.DATA_DIR if paths.DATA_DIR.exists() else BASE_DIR
    free = shutil.disk_usage(where).free / 2**30
    add("ok" if free >= CFG["doctor"].get("min_disk_gb", 1.0) else "warn", "Disk space", f"{free:.1f} GB free")
    try:
        paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
        t = paths.DATA_DIR / ".write-test"
        t.write_text("x")
        t.unlink()
        add("ok", "Data folder", f"writable · {paths.DATA_DIR}")
    except OSError as e:
        add("fail", "Data folder", f"not writable: {e}")
    try:
        with urllib.request.urlopen("https://pypi.org/simple/pip/", timeout=4):
            add("ok", "Internet", "PyPI reachable")
    except Exception:
        add("warn", "Internet", "PyPI not reachable (use --central for offline installs)")

    table(["", "Check", "Detail"], [[r[0], r[1], _trunc(r[2], width() - 24)] for r in rows])
    print()
    (fail if counts["fail"] else warn if counts["warn"] else ok)(
        f"{counts['ok']} ok · {counts['warn']} warnings · {counts['fail']} failures")
    return 1 if counts["fail"] else 0


def cmd_status() -> int:
    banner("Status")
    st = instance_running()
    if not st:
        left = leftover_services(read_state())
        if left:
            warn("The launcher is gone but these services are still running: "
                 + ", ".join(f"{s['name']} (pid {s['pid']})" for s in left)
                 + f". Run `python {Path(__file__).name} stop` to clean up.")
        else:
            info("Not running.")
        return 0
    up = fmt_dur(time.time() - st.get("started", time.time()))
    box(f"{NAME.upper()} IS RUNNING", kv_lines([("Launcher PID", str(st["pid"])), ("Profile", str(st.get("profile"))),
                                               ("Uptime", up)]))
    rows = [[s["name"], str(s["pid"]), green("running") if pid_alive(s["pid"]) else red("stopped"),
             s.get("health") or "-"] for s in st.get("services", [])]
    if rows:
        print()
        table(["Service", "PID", "State", "Health URL"], rows)
    return 0


def cmd_stop() -> int:
    banner("Stop")
    st = instance_running()
    if not st:
        n = reap_stale_state()
        (ok if n else info)(f"Stopped {n} leftover service(s)." if n else "Nothing is running.")
        return 0
    pid = st["pid"]
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        else:
            os.kill(pid, signal.SIGTERM)
    except OSError as e:
        fail(f"Could not signal pid {pid}: {e}")
        return 1
    with spinner("Waiting for the services to stop"):
        end = time.time() + 20
        while time.time() < end and pid_alive(pid):
            time.sleep(0.3)
    if pid_alive(pid):                                   # still standing: force-kill the services
        warn("The launcher did not exit in time. Killing the services.")
        for s in st.get("services", []):
            with contextlib.suppress(OSError, ProcessLookupError):
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(s["pid"]), "/T", "/F"], capture_output=True)
                else:
                    os.killpg(s["pid"], signal.SIGKILL)
        with contextlib.suppress(OSError):
            os.kill(pid, signal.SIGKILL if os.name != "nt" else signal.SIGTERM)
    clear_state()
    ok("Stopped")
    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    files = sorted(paths.LOGS.glob("*.log")) if paths.LOGS.is_dir() else []
    tgt = args.targets[0] if args.targets else None
    if not tgt:
        banner("Logs")
        if not files:
            info("No log files yet.")
            return 0
        table(["Name", "Size", "Modified"], [[f.stem.removeprefix("service-"), f"{f.stat().st_size / 1024:.1f} KB",
                                              time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(f.stat().st_mtime))]
                                             for f in files])
        info(f"Show one:  python {Path(__file__).name} logs NAME [-n 50] [-f]")
        return 0
    match = next((f for f in files if f.stem in (tgt, f"service-{tgt}")), None)
    if not match:
        fail(f"No log named '{tgt}'. Available: " + ", ".join(f.stem.removeprefix("service-") for f in files))
        return 1
    with open(match, "r", encoding="utf-8", errors="replace") as fh:
        for ln in deque(fh, maxlen=max(args.lines, 1)):
            print(ln, end="")
        if args.follow:
            fh.seek(0, os.SEEK_END)
            try:
                while True:
                    ln = fh.readline()
                    if ln:
                        print(ln, end="", flush=True)
                    else:
                        time.sleep(0.3)
            except KeyboardInterrupt:
                print()
    return 0


def _safe_rm(p: Path) -> bool:
    rp = p.resolve()
    if not (BASE_DIR in rp.parents or paths.DATA_DIR in rp.parents or rp == paths.DATA_DIR / "runtime"):
        return False
    if rp.is_dir():
        shutil.rmtree(rp, ignore_errors=True)
    elif rp.exists():
        rp.unlink()
    return True


def cmd_clean(args: argparse.Namespace) -> int:
    banner("Clean")
    if instance_running():
        fail("It is running. Stop it first.")
        return 1
    fe = CFG["frontend"]
    fdir = BASE_DIR / fe.get("dir", "frontend")
    items = {
        "venvs": ("Python virtual environments", [paths.VENVS]),
        "logs": ("Logs", [paths.LOGS]),
        "node": ("Private Node.js copy", [paths.NODE_DIR]),
        "build": ("Frontend build output", [fdir / fe.get("dist", "dist")]),
        "modules": ("Frontend node_modules", [fdir / "node_modules"]),
        "selection": ("Saved selection and library cache", [paths.SELECTION_FILE, paths.DEPS_FILE]),
    }
    want = list(items) if "all" in args.targets else [t for t in args.targets if t in items]
    unknown = [t for t in args.targets if t not in items and t != "all"]
    if unknown:
        fail("Unknown target(s): " + ", ".join(unknown) + ". Use: all, " + ", ".join(items))
        return 1
    if not want:
        if _auto():
            info("Nothing selected. Pass targets: all, " + ", ".join(items))
            return 0
        want = [k for k, (lbl, ps) in items.items() if any(p.exists() for p in ps)
                and ask_yes_no(f"Remove {lbl.lower()}?", False)]
    if _is_running_in(paths.VENVS) and "venvs" in want:
        fail("The launcher itself is running inside the virtual environment; it cannot remove it.")
        want.remove("venvs")
    for k in want:
        lbl, ps = items[k]
        done = [_safe_rm(p) for p in ps if p.exists()]
        (ok if done and all(done) else info)(f"{'Removed' if done else 'Nothing to remove'}: {lbl}")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    banner("Init")
    target = BASE_DIR / ".env.example"
    names: dict[str, dict] = {s["name"]: s for s in CFG["env_vars"]}
    for q in _questions():
        for o in q.get("options", []):
            for n in o.get("env_required", []):
                names.setdefault(n, {"name": n, "secret": True, "desc": f"needed by '{o['label']}'"})
    lines = [f"# {NAME} - copy this file to .env and fill it in. Never commit the real .env.", ""]
    for n, s in names.items():
        lines.append(f"# {s.get('desc', n)}" + (" (required)" if s.get("required") else "")
                     + (" - generated automatically if empty" if s.get("generate") else ""))
        val = "" if s.get("secret") or s.get("generate") else str(s.get("default", ""))
        lines.append(f"{n}={val}")
    lines += ["", "# --- launcher settings (all optional)", f"# {E('HOST')}={CFG['host']}",
              f"# {E('PORT')}={CFG['ports']['main']}", f"# {E('DATA_DIR')}={CFG['data_dir']}",
              f"# {E('AUTO')}=1", f"# {E('CENTRAL')}=/path/to/wheels"]
    if target.exists() and not args.force:
        info(f"{target.name} already exists (use --force to overwrite).")
    else:
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        ok(f"Created {target.name}")
    gi = BASE_DIR / ".gitignore"
    wanted = [".env", ".env.local", ".env.*.local", f"{rel(paths.DATA_DIR)}/runtime/", "__pycache__/", "node_modules/",
              f"{rel(BASE_DIR / CFG['frontend'].get('dir', 'frontend') / CFG['frontend'].get('dist', 'dist'))}/"]
    have = gi.read_text(encoding="utf-8").splitlines() if gi.exists() else []
    add_ = [w for w in wanted if w not in have]
    if add_:
        with open(gi, "a", encoding="utf-8") as f:
            f.write(("\n" if have and have[-1] != "" else "") + "# added by Launcher.py\n" + "\n".join(add_) + "\n")
        ok(f".gitignore: added {', '.join(add_)}")
    else:
        info(".gitignore already has the usual entries")
    return 0


def cmd_config(profile: str) -> int:
    print(json.dumps({"profile": profile, "env_prefix": PREFIX,
                      "paths": {k: str(v) for k, v in vars(paths).items()}, "config": CFG},
                     indent=2, ensure_ascii=False, default=str))
    return 0


# =====================================================================================================
# Section 13: --demo  -  every screen component with sample data (changes nothing)
# =====================================================================================================
def demo() -> None:
    banner()
    for n, title in enumerate(STEPS, 1):
        step(n, title)

    section("One-line messages")
    info("info: a neutral message")
    ok("ok: something worked")
    warn("warn: something needs attention")
    fail("fail: something went wrong")

    section("Checking environments")
    fake_missing = [
        {"lib": "fastapi", "component": "Backend", "venv": "backend", "status": "missing"},
        {"lib": "uvicorn", "component": "Backend", "venv": "backend", "status": "outdated"},
        {"lib": "celery", "component": "Worker", "venv": "worker", "status": "missing"},
    ]
    show_environments([{"name": "backend", "total": 6, "missing": fake_missing[:2]},
                       {"name": "worker", "total": 9, "missing": fake_missing[2:]}])
    show_missing(fake_missing)
    show_missing([{**m, "status": "not in central"} for m in fake_missing[:2]], title="Not in the central library")

    section("Box")
    box("YOUR MACHINE", kv_lines([("System", "Linux 6.8 · Python 3.12"), ("CPU cores", "8"),
                                  ("RAM", "16.0 GB total · 9.2 free"), ("Workers", "recommended 3 · up to 8")]))
    explain([("1-3", "Explanation box: the number on the left, the text wrapped on the right."),
             ("✕", "Gray rows cannot be chosen.")])

    section("Menu (non-interactive: the recommended row is taken)")
    menu("LLM provider", ["Provider", "API key / variables", "Details"], [
        {"cols": ["OpenAI", "not set (OPENAI_API_KEY)", "gpt-4o-mini"]},
        {"cols": ["Anthropic", "found (ANTHROPIC_API_KEY)", "claude"], "state": "rec"},
        {"cols": ["Custom endpoint", "not set (CUSTOM_API_KEY)", "OpenAI-format URL"], "state": "blocked"},
    ], explain_lines=[("{range}", "Which service writes the answers.")])

    section("Installing libraries", note="3 to install")
    prog = InstallProgress(len(fake_missing))
    for m in fake_missing:
        prog.start(m["lib"])
        hook = pip_progress_hook(prog)
        for line in (f"Collecting {m['lib']}", f"Downloading {m['lib']}.whl", "Installing collected packages",
                     "Successfully installed"):
            hook(line)
            time.sleep(0.25)
        prog.done()
    prog.close()

    with spinner("Spinner for work with no measurable progress"):
        time.sleep(1.2)

    section("Doctor-style table")
    table(["", "Check", "Detail"], [[green("✓ ok"), "Python", "3.12.3"], [yellow("! warn"), "Port 8000 (main)", "in use"],
                                    [red("✗ fail"), "Var SECRET_KEY", "missing (required)"]])

    section("Live service logs")
    for i, (svc, text) in enumerate([("api", "INFO:     Uvicorn running on http://127.0.0.1:8000"),
                                     ("web", "VITE v5.4  ready in 312 ms"),
                                     ("worker-1", "[celery] ready.")]):
        print(log_prefix(svc, i, 8) + text)

    print()
    box(f"{NAME.upper()} IS RUNNING", kv_lines([("App", "http://127.0.0.1:5173/"), ("API docs", "http://127.0.0.1:8000/docs"),
                                                ("Profile", "dev"), ("Logs", "data/runtime/logs")]))


# =====================================================================================================
# Section 14: main
# =====================================================================================================
COMMANDS = ("run", "dev", "prod", "setup", "doctor", "status", "stop", "logs", "clean", "init", "config", "demo",
            "prompt")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog=Path(__file__).name, add_help=False)
    p.add_argument("command", nargs="?", default="run", choices=COMMANDS)
    p.add_argument("targets", nargs="*")
    p.add_argument("-h", "--help", action="store_true")
    p.add_argument("--profile")
    p.add_argument("--auto", action="store_true")
    p.add_argument("--reselect", action="store_true")
    p.add_argument("--recheck", action="store_true")
    p.add_argument("--central", metavar="PATH")
    p.add_argument("--no-frontend", action="store_true")
    p.add_argument("--no-venv", action="store_true")
    p.add_argument("--no-browser", action="store_true")
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--host")
    p.add_argument("--port", type=int)
    p.add_argument("-e", "--env", action="append", metavar="KEY=VALUE")
    p.add_argument("--force", action="store_true")
    p.add_argument("-n", "--lines", type=int, default=40)
    p.add_argument("-f", "--follow", action="store_true")
    return p.parse_args()


def main() -> int:
    global _NO_VENV
    args = parse_args()
    if args.help:
        print(__doc__)
        return 0
    _NO_VENV = args.no_venv
    cmd = args.command
    if cmd == "prompt":
        print(AI_PROMPT)
        return 0
    profile = cmd if cmd in ("dev", "prod") else (args.profile or CFG["default_profile"])
    if profile not in PROFILES:
        sys.exit(f"Unknown profile '{profile}'. Available: {', '.join(PROFILES)}")

    # Anything the user explicitly typed on the command line must be treated as a real system variable (wins over .env)
    explicit: dict[str, str] = {}
    for kv in args.env or []:
        k, sep, v = kv.partition("=")
        if not k or not sep:
            sys.exit("-e expects KEY=VALUE")
        explicit[k] = v
    if args.auto:
        explicit[E("AUTO")] = "1"
    if args.host:
        explicit[E("HOST")] = args.host
    if args.port:
        explicit[E("PORT")] = str(args.port)
    os.environ.update(explicit)
    _REAL_ENV.update(explicit)

    bootstrap(profile)
    if cmd == "demo":
        demo()
        return 0
    if cmd == "config":
        return cmd_config(profile)
    if cmd == "doctor":
        return cmd_doctor(args, profile)
    if cmd == "status":
        return cmd_status()
    if cmd == "stop":
        return cmd_stop()
    if cmd == "logs":
        return cmd_logs(args)
    if cmd == "clean":
        return cmd_clean(args)
    if cmd == "init":
        return cmd_init(args)
    return cmd_run(args, profile, launch=(cmd != "setup"))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n  Cancelled.")
        sys.exit(130)
