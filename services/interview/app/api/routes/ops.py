from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.config import settings
from app.schemas import PublicIntegrationInfo, ServiceInfo


router = APIRouter(tags=["ops"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/v1/integrations", response_model=PublicIntegrationInfo, tags=["integrations"])
def integrations() -> PublicIntegrationInfo:
    return PublicIntegrationInfo(
        voice_websocket_url=settings.voice_ws_public_url,
        voice_demo_ui_url=settings.voice_http_public_url,
    )


@router.get("/", response_model=ServiceInfo)
def root(request: Request) -> ServiceInfo:
    base = str(request.base_url).rstrip("/")
    return ServiceInfo(
        service="interview-platform",
        version=settings.app_version,
        student_voice_ui=settings.voice_http_public_url,
        voice_websocket=settings.voice_ws_public_url,
        crm_ui=f"{base}/crm",
        api_docs=f"{base}/docs",
    )


@router.get("/go/voice")
def go_voice() -> RedirectResponse:
    return RedirectResponse(settings.voice_http_public_url, status_code=302)


@router.get("/crm", response_class=HTMLResponse, tags=["crm-web"])
def crm_web() -> str:
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Spiders CRM</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    /* ── Reset & tokens ─────────────────────────────────── */
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg:        #f0f2f9;
      --sidebar:   #1a1f36;
      --sidebar-hover: #252d4a;
      --sidebar-active: #3b4880;
      --panel:     #ffffff;
      --text:      #111827;
      --muted:     #6b7280;
      --border:    #e5e9f4;
      --brand:     #4f56d6;
      --brand-light: #eef0ff;
      --green:     #16a34a;
      --red:       #dc2626;
      --amber:     #d97706;
    }
    body {
      font-family: 'Inter', system-ui, sans-serif;
      background: var(--bg);
      color: var(--text);
      height: 100vh;
      overflow: hidden;
      display: flex;
    }

    /* ── LOGIN SCREEN ────────────────────────────────────── */
    #loginScreen {
      position: fixed; inset: 0;
      background: linear-gradient(135deg, #1a1f36 0%, #2e3561 100%);
      display: flex; align-items: center; justify-content: center;
      z-index: 1000;
    }
    #loginScreen.hidden { display: none; }
    .login-card {
      background: #fff;
      border-radius: 20px;
      padding: 48px 44px;
      width: 400px;
      box-shadow: 0 24px 64px rgba(0,0,0,.35);
    }
    .login-logo {
      font-size: 28px; font-weight: 800;
      color: var(--brand); margin-bottom: 4px;
    }
    .login-sub {
      font-size: 13px; color: var(--muted); margin-bottom: 36px;
    }
    .login-field { margin-bottom: 16px; }
    .login-field label {
      display: block; font-size: 12px; font-weight: 600;
      color: #374151; margin-bottom: 6px; letter-spacing: .03em;
    }
    .login-field input {
      width: 100%; padding: 12px 14px;
      border: 1.5px solid #d1d5db; border-radius: 10px;
      font-size: 14px; color: var(--text);
      transition: border-color .2s;
    }
    .login-field input:focus { outline: none; border-color: var(--brand); }
    .login-btn {
      width: 100%; padding: 13px;
      background: var(--brand); color: #fff;
      border: 0; border-radius: 10px;
      font-size: 15px; font-weight: 700;
      cursor: pointer; margin-top: 8px;
      transition: background .2s;
    }
    .login-btn:hover { background: #3d44b8; }
    #loginErr {
      margin-top: 12px; font-size: 13px; color: var(--red);
      text-align: center; min-height: 20px;
    }

    /* ── APP SHELL ───────────────────────────────────────── */
    #appShell {
      display: flex; width: 100%; height: 100vh;
      opacity: 0; pointer-events: none; transition: opacity .3s;
    }
    #appShell.ready { opacity: 1; pointer-events: all; }

    /* ── SIDEBAR ─────────────────────────────────────────── */
    .sidebar {
      width: 240px; flex-shrink: 0;
      background: var(--sidebar);
      display: flex; flex-direction: column;
      padding: 0; overflow: hidden;
    }
    .sidebar-header {
      padding: 24px 20px 18px;
      border-bottom: 1px solid rgba(255,255,255,.08);
    }
    .brand { font-size: 20px; font-weight: 800; color: #fff; }
    .brand-units { font-size: 11px; color: rgba(255,255,255,.4); margin-top: 3px; }
    .sidebar-user {
      display: flex; align-items: center; gap: 10px;
      padding: 14px 20px;
      border-bottom: 1px solid rgba(255,255,255,.08);
    }
    .avatar-circle {
      width: 32px; height: 32px; border-radius: 50%;
      background: var(--brand); color: #fff;
      display: flex; align-items: center; justify-content: center;
      font-size: 13px; font-weight: 700; flex-shrink: 0;
    }
    .user-info { flex: 1; }
    .user-name { font-size: 13px; font-weight: 600; color: #fff; }
    .user-role { font-size: 11px; color: rgba(255,255,255,.4); }
    .nav-section { padding: 18px 12px 4px; }
    .nav-section-label {
      font-size: 10px; font-weight: 700; letter-spacing: .1em;
      text-transform: uppercase; color: rgba(255,255,255,.3);
      padding: 0 8px; margin-bottom: 6px;
    }
    .nav-item {
      display: flex; align-items: center; gap: 10px;
      padding: 10px 12px; border-radius: 8px;
      color: rgba(255,255,255,.65); font-size: 14px; font-weight: 500;
      cursor: pointer; border: 0; background: transparent;
      width: 100%; text-align: left;
      transition: background .15s, color .15s;
    }
    .nav-item:hover { background: var(--sidebar-hover); color: #fff; }
    .nav-item.active { background: var(--sidebar-active); color: #fff; font-weight: 600; }
    .nav-icon { width: 18px; text-align: center; opacity: .8; font-size: 15px; }
    .sidebar-footer {
      margin-top: auto;
      padding: 14px 20px;
      border-top: 1px solid rgba(255,255,255,.08);
    }
    .logout-btn {
      font-size: 12px; color: rgba(255,255,255,.4);
      background: none; border: 0; cursor: pointer; padding: 4px 0;
    }
    .logout-btn:hover { color: #fff; }

    /* ── MAIN AREA ───────────────────────────────────────── */
    .main-area {
      flex: 1; display: flex; flex-direction: column;
      overflow: hidden;
    }
    .topbar {
      background: var(--panel);
      border-bottom: 1px solid var(--border);
      padding: 0 28px;
      height: 58px;
      display: flex; align-items: center; justify-content: space-between;
      flex-shrink: 0;
    }
    .page-title { font-size: 18px; font-weight: 700; color: var(--text); }
    .topbar-right { display: flex; align-items: center; gap: 12px; }
    .unit-tabs {
      display: flex; gap: 4px;
    }
    .unit-tab {
      padding: 5px 12px; border-radius: 999px;
      font-size: 12px; font-weight: 600;
      border: 1.5px solid var(--border);
      background: transparent; color: var(--muted); cursor: pointer;
      transition: all .15s;
    }
    .unit-tab.active {
      background: var(--brand-light); color: var(--brand);
      border-color: #c7caff;
    }
    .page-content {
      flex: 1; overflow-y: auto; padding: 24px 28px;
    }

    /* ── PAGES ───────────────────────────────────────────── */
    .page { display: none; }
    .page.active { display: block; }

    /* ── CARDS / KPI ─────────────────────────────────────── */
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px; margin-bottom: 24px;
    }
    .kpi-card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 20px;
      position: relative; overflow: hidden;
    }
    .kpi-card::before {
      content: ''; position: absolute;
      top: 0; left: 0; right: 0; height: 3px;
      background: var(--brand);
    }
    .kpi-card.green::before { background: var(--green); }
    .kpi-card.red::before   { background: var(--red); }
    .kpi-card.amber::before { background: var(--amber); }
    .kpi-label { font-size: 12px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; }
    .kpi-value { font-size: 36px; font-weight: 800; line-height: 1.1; margin: 8px 0 4px; }
    .kpi-hint  { font-size: 12px; color: var(--muted); }

    /* ── SECTION HEADER ──────────────────────────────────── */
    .section-hdr {
      display: flex; align-items: center; justify-content: space-between;
      margin-bottom: 14px;
    }
    .section-title { font-size: 16px; font-weight: 700; }
    .live-dot {
      display: inline-block; width: 8px; height: 8px;
      border-radius: 50%; background: var(--green);
      margin-left: 8px; animation: pulse 2s infinite;
    }
    @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }

    /* ── TABLES ──────────────────────────────────────────── */
    .data-table {
      width: 100%; border-collapse: collapse;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      overflow: hidden;
      font-size: 13.5px;
    }
    .data-table th {
      padding: 11px 14px; text-align: left;
      background: #f8f9fe;
      font-size: 11px; font-weight: 700; color: var(--muted);
      text-transform: uppercase; letter-spacing: .05em;
      border-bottom: 1px solid var(--border);
    }
    .data-table td {
      padding: 12px 14px;
      border-bottom: 1px solid #f1f3fb;
      color: var(--text);
      vertical-align: middle;
    }
    .data-table tr:last-child td { border-bottom: 0; }
    .data-table tr:hover td { background: #fbfcff; }

    /* ── BADGES ──────────────────────────────────────────── */
    .badge {
      display: inline-block;
      padding: 3px 10px; border-radius: 999px;
      font-size: 11px; font-weight: 700;
    }
    .badge.hot  { background: #fff0f2; color: #be1b42; }
    .badge.warm { background: #fff7e0; color: #92530a; }
    .badge.cold { background: #e8f4ff; color: #1561a3; }
    .badge.stage {
      background: var(--brand-light); color: var(--brand);
    }

    /* ── BUTTONS ─────────────────────────────────────────── */
    .btn {
      padding: 7px 14px; border-radius: 8px;
      font-size: 13px; font-weight: 600; cursor: pointer;
      border: 1.5px solid var(--border);
      background: var(--panel); color: var(--text);
      transition: all .15s;
    }
    .btn:hover { border-color: var(--brand); color: var(--brand); }
    .btn.primary {
      background: var(--brand); color: #fff; border-color: var(--brand);
    }
    .btn.primary:hover { background: #3d44b8; border-color: #3d44b8; }
    .btn.danger  { background: #fff0f2; color: var(--red); border-color: #fecdd3; }
    .btn.sm { padding: 4px 10px; font-size: 12px; }

    /* ── LEAD DETAIL DRAWER ──────────────────────────────── */
    .content-split {
      display: grid;
      grid-template-columns: 1fr 420px;
      gap: 20px;
    }
    .drawer {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 20px;
      height: fit-content;
    }
    .drawer-title {
      font-size: 15px; font-weight: 700;
      margin-bottom: 16px;
      padding-bottom: 12px;
      border-bottom: 1px solid var(--border);
      display: flex; align-items: center; justify-content: space-between;
    }
    .detail-row {
      display: flex; justify-content: space-between;
      padding: 9px 0;
      border-bottom: 1px solid #f3f4fb;
      font-size: 13.5px;
    }
    .detail-row:last-child { border-bottom: 0; }
    .detail-key { color: var(--muted); font-weight: 500; }
    .detail-val { font-weight: 600; }
    .ai-summary {
      background: var(--brand-light);
      border: 1px solid #c7caff;
      border-radius: 10px;
      padding: 12px 14px;
      font-size: 13px; color: #2b3080; line-height: 1.5;
      margin: 12px 0;
    }
    .turn-card {
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 12px 14px;
      margin-bottom: 10px;
      background: var(--panel);
    }
    .turn-header {
      display: flex; justify-content: space-between;
      font-size: 12px; font-weight: 700; margin-bottom: 6px;
    }
    .turn-user { color: var(--brand); }
    .turn-ai { color: var(--green); }
    .turn-text { font-size: 13px; line-height: 1.55; color: #2d3a52; }
    .turn-meta { font-size: 11px; color: var(--muted); margin-top: 6px; }

    /* ── PIPELINE KANBAN ─────────────────────────────────── */
    .kanban {
      display: flex; gap: 14px;
      overflow-x: auto; padding-bottom: 8px;
      align-items: flex-start;
    }
    .kanban-lane {
      flex-shrink: 0; width: 220px;
      background: #f4f6fc;
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 12px;
    }
    .lane-header {
      display: flex; justify-content: space-between; align-items: center;
      margin-bottom: 10px;
    }
    .lane-title {
      font-size: 12px; font-weight: 700;
      text-transform: uppercase; letter-spacing: .06em;
      color: #374375;
    }
    .lane-count {
      background: #dde2f3; color: #374375;
      border-radius: 999px; font-size: 11px; font-weight: 700;
      padding: 2px 8px;
    }
    .k-card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 12px;
      margin-bottom: 8px;
      cursor: pointer; transition: box-shadow .15s;
    }
    .k-card:hover { box-shadow: 0 2px 12px rgba(79,86,214,.12); }
    .k-name { font-size: 13px; font-weight: 700; margin-bottom: 2px; }
    .k-meta { font-size: 11px; color: var(--muted); margin-bottom: 6px; }

    /* ── CALL INTEL ──────────────────────────────────────── */
    .intel-card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px 18px;
      margin-bottom: 12px;
    }
    .intel-header {
      display: flex; justify-content: space-between; align-items: flex-start;
      margin-bottom: 10px;
    }
    .intel-name { font-size: 15px; font-weight: 700; }
    .intel-unit { font-size: 12px; color: var(--muted); margin-top: 2px; }
    .chip-row { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
    .chip {
      display: inline-flex; align-items: center;
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 3px 10px;
      font-size: 11px; color: #4d5c7f; background: #f8f9fe;
    }
    .chip.highlight { border-color: #c7caff; background: var(--brand-light); color: var(--brand); }

    /* ── ALERTS ──────────────────────────────────────────── */
    .alert-row {
      display: flex; align-items: center; justify-content: space-between;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 14px 16px;
      margin-bottom: 8px;
    }
    .alert-row.danger { border-left: 3px solid var(--red); }
    .alert-row.warn   { border-left: 3px solid var(--amber); }
    .alert-label { font-size: 14px; font-weight: 600; }
    .alert-sub   { font-size: 12px; color: var(--muted); margin-top: 2px; }

    /* ── SLIDE-OVER PANEL ───────────────────────────────── */
    .overlay {
      position: fixed; inset: 0;
      background: rgba(15,20,40,.45);
      z-index: 200;
      opacity: 0; pointer-events: none;
      transition: opacity .25s;
    }
    .overlay.open { opacity: 1; pointer-events: all; }
    .slideover {
      position: fixed; top: 0; right: 0; bottom: 0;
      width: 520px; max-width: 95vw;
      background: #fff;
      box-shadow: -4px 0 40px rgba(0,0,0,.18);
      z-index: 201;
      display: flex; flex-direction: column;
      transform: translateX(100%);
      transition: transform .28s cubic-bezier(.4,0,.2,1);
    }
    .slideover.open { transform: translateX(0); }
    .so-header {
      padding: 18px 20px;
      border-bottom: 1px solid var(--border);
      display: flex; align-items: center; justify-content: space-between;
      flex-shrink: 0;
    }
    .so-title { font-size: 16px; font-weight: 700; }
    .so-close {
      background: none; border: 0; font-size: 20px;
      color: var(--muted); cursor: pointer; padding: 4px 8px;
      border-radius: 6px; line-height: 1;
    }
    .so-close:hover { background: #f3f4fb; }
    .so-body {
      flex: 1; overflow-y: auto;
      padding: 20px;
    }
    .so-section {
      margin-bottom: 20px;
    }
    .so-section-title {
      font-size: 11px; font-weight: 700; text-transform: uppercase;
      letter-spacing: .08em; color: var(--muted);
      margin-bottom: 10px; padding-bottom: 6px;
      border-bottom: 1px solid var(--border);
    }
    .so-actions {
      display: flex; gap: 8px; flex-wrap: wrap;
      padding: 14px 20px;
      border-top: 1px solid var(--border);
      flex-shrink: 0; background: #fafbff;
    }
    /* audio player */
    .audio-row {
      display: flex; align-items: center; gap: 10px;
      padding: 8px 12px;
      background: #f4f6ff;
      border: 1px solid #dde2f4;
      border-radius: 8px; margin-bottom: 6px;
    }
    .audio-row audio { flex: 1; height: 32px; }
    .audio-label { font-size: 11px; font-weight: 600; color: var(--brand); min-width: 60px; }
    .log-turn {
      border-left: 3px solid var(--border);
      padding: 8px 12px; margin-bottom: 8px;
      border-radius: 0 8px 8px 0;
      background: #fafbff;
    }
    .log-turn.caller { border-left-color: var(--brand); }
    .log-turn.aria   { border-left-color: var(--green); }
    .log-speaker { font-size: 11px; font-weight: 700; margin-bottom: 4px; }
    .log-speaker.caller { color: var(--brand); }
    .log-speaker.aria   { color: var(--green); }
    .log-text { font-size: 13px; line-height: 1.55; color: #2d3a52; }
    .log-meta { font-size: 11px; color: var(--muted); margin-top: 5px; }

    /* ── SLIDE-OVER TABS ────────────────────────────────── */
    .so-tab {
      flex: 1; padding: 10px 6px;
      font-size: 12px; font-weight: 600;
      background: none; border: 0;
      border-bottom: 2px solid transparent;
      color: var(--muted); cursor: pointer;
      transition: all .15s;
    }
    .so-tab:hover { color: var(--brand); }
    .so-tab.active { color: var(--brand); border-bottom-color: var(--brand); }
    /* ── ENQUIRY FORM ────────────────────────────────────── */
    .enq-section-label {
      font-size: 11px; font-weight: 700; text-transform: uppercase;
      letter-spacing: .07em; color: var(--brand);
      margin: 18px 0 10px; padding: 6px 0;
      border-bottom: 1px solid #e8eaff;
    }
    .enq-row {
      display: grid; grid-template-columns: 1fr 1fr; gap: 10px;
      margin-bottom: 10px;
    }
    .enq-row.full { grid-template-columns: 1fr; }
    .enq-field label {
      display: block; font-size: 11px; font-weight: 600;
      color: #4b5568; margin-bottom: 4px;
    }
    .enq-field input, .enq-field select, .enq-field textarea {
      width: 100%; padding: 8px 10px;
      border: 1.5px solid var(--border); border-radius: 8px;
      font-size: 13px; color: var(--text);
      background: #fff; transition: border-color .15s;
      font-family: inherit;
    }
    .enq-field input:focus, .enq-field select:focus, .enq-field textarea:focus {
      outline: none; border-color: var(--brand);
    }
    .enq-field textarea { resize: vertical; min-height: 64px; }
    .enq-check-row {
      display: flex; gap: 20px; margin-bottom: 10px;
    }
    .enq-check {
      display: flex; align-items: center; gap: 6px;
      font-size: 13px; cursor: pointer;
    }
    .enq-check input[type=checkbox] { width: 15px; height: 15px; cursor: pointer; }
    .save-form-btn {
      width: 100%; padding: 11px;
      background: var(--brand); color: #fff;
      border: 0; border-radius: 10px;
      font-size: 14px; font-weight: 700;
      cursor: pointer; margin-top: 16px;
      transition: background .2s;
    }
    .save-form-btn:hover { background: #3d44b8; }

    /* ── MISC ────────────────────────────────────────────── */
    .empty-state {
      text-align: center; padding: 60px 20px;
      color: var(--muted); font-size: 14px;
    }
    .empty-state .icon { font-size: 36px; margin-bottom: 12px; }
    .text-muted { color: var(--muted); }
    .text-green { color: var(--green); font-weight: 600; }
    .text-red   { color: var(--red);   font-weight: 600; }
    .text-amber { color: var(--amber); font-weight: 600; }
    .mono { font-family: 'Courier New', monospace; font-size: 12px; }
    .mt-16 { margin-top: 16px; }
    .mb-16 { margin-bottom: 16px; }
  </style>
</head>
<body>

<!-- ── LOGIN SCREEN ──────────────────────────────────────── -->
<div id="loginScreen">
  <div class="login-card">
    <div class="login-logo">Spiders CRM</div>
    <div class="login-sub">QSpiders · JSpiders · PySiders · ProSpiders</div>
    <div class="login-field">
      <label>Username</label>
      <input id="u" type="text" placeholder="Enter username" value="admin" />
    </div>
    <div class="login-field">
      <label>Password</label>
      <input id="p" type="password" placeholder="Enter password" value="admin123" onkeydown="if(event.key==='Enter')doLogin()" />
    </div>
    <button class="login-btn" onclick="doLogin()">Sign in</button>
    <div id="loginErr"></div>
  </div>
</div>

<!-- ── APP SHELL ─────────────────────────────────────────── -->
<div id="appShell">

  <!-- Sidebar -->
  <aside class="sidebar">
    <div class="sidebar-header">
      <div class="brand">Spiders CRM</div>
      <div class="brand-units">QSpiders · JSpiders · PySiders</div>
    </div>
    <div class="sidebar-user">
      <div class="avatar-circle" id="userInitial">A</div>
      <div class="user-info">
        <div class="user-name" id="userName">Admin</div>
        <div class="user-role">Administrator</div>
      </div>
    </div>

    <div class="nav-section">
      <div class="nav-section-label">Overview</div>
      <button class="nav-item active" data-page="dashboard" onclick="gotoPage('dashboard')">
        <span class="nav-icon">⊞</span> Dashboard
      </button>
    </div>
    <div class="nav-section">
      <div class="nav-section-label">Student Journey</div>
      <button class="nav-item" data-page="pipeline" onclick="gotoPage('pipeline')">
        <span class="nav-icon">⟶</span> Admission Pipeline
      </button>
      <button class="nav-item" data-page="records" onclick="gotoPage('records')">
        <span class="nav-icon">◉</span> Student Records
      </button>
      <button class="nav-item" data-page="postcall" onclick="gotoPage('postcall')">
        <span class="nav-icon">⏺</span> Post Call Flow
      </button>
    </div>
    <div class="nav-section">
      <div class="nav-section-label">Insights</div>
      <button class="nav-item" data-page="analytics" onclick="gotoPage('analytics')">
        <span class="nav-icon">↑</span> Analytics
      </button>
      <button class="nav-item" data-page="alerts" onclick="gotoPage('alerts')">
        <span class="nav-icon">⚠</span> Alerts
      </button>
    </div>

    <div class="sidebar-footer">
      <button class="logout-btn" onclick="doLogout()">← Sign out</button>
    </div>
  </aside>

  <!-- Main Area -->
  <div class="main-area">
    <!-- Top bar -->
    <div class="topbar">
      <div class="page-title" id="pageTitle">Dashboard</div>
      <div class="topbar-right">
        <div class="unit-tabs" id="unitTabs">
          <button class="unit-tab active" data-unit="" onclick="setUnit(this)">All</button>
          <button class="unit-tab" data-unit="qspiders" onclick="setUnit(this)">QSpiders</button>
          <button class="unit-tab" data-unit="jspiders" onclick="setUnit(this)">JSpiders</button>
          <button class="unit-tab" data-unit="pysiders" onclick="setUnit(this)">PySiders</button>
          <button class="unit-tab" data-unit="prospiders" onclick="setUnit(this)">ProSpiders</button>
        </div>
        <button class="btn sm" onclick="refreshAll()">↻ Refresh</button>
      </div>
    </div>

    <!-- Page content -->
    <div class="page-content">

      <!-- ── PAGE: DASHBOARD ── -->
      <div id="page-dashboard" class="page active">
        <div class="kpi-grid">
          <div class="kpi-card">
            <div class="kpi-label">Total Leads</div>
            <div class="kpi-value" id="kpiLeads">—</div>
            <div class="kpi-hint">Auto-filled from calls</div>
          </div>
          <div class="kpi-card green">
            <div class="kpi-label">Hot Leads</div>
            <div class="kpi-value" id="kpiHot">—</div>
            <div class="kpi-hint">Priority callbacks now</div>
          </div>
          <div class="kpi-card amber">
            <div class="kpi-label">Calls Today</div>
            <div class="kpi-value" id="kpiCalls">—</div>
            <div class="kpi-hint">Across all units</div>
          </div>
          <div class="kpi-card red">
            <div class="kpi-label">SLA Breached</div>
            <div class="kpi-value" id="kpiSla">—</div>
            <div class="kpi-hint" id="slaHint">Checking...</div>
          </div>
        </div>
        <div class="section-hdr">
          <div class="section-title">Recent Leads <span class="live-dot"></span></div>
        </div>
        <table class="data-table" id="dashLeadTable">
          <thead>
            <tr>
              <th>Name</th><th>Phone</th><th>Unit</th><th>Stage</th>
              <th>Band</th><th>Score</th><th>Counsellor</th><th>Actions</th>
            </tr>
          </thead>
          <tbody id="dashLeadBody">
            <tr><td colspan="8" class="empty-state">Login to load leads.</td></tr>
          </tbody>
        </table>
      </div>

      <!-- ── PAGE: PIPELINE ── -->
      <div id="page-pipeline" class="page">
        <div class="section-hdr mb-16">
          <div class="section-title">Admission Pipeline</div>
          <div class="text-muted" style="font-size:13px;">Drag leads across stages</div>
        </div>
        <div class="kanban" id="kanbanBoard"></div>
      </div>

      <!-- ── PAGE: STUDENT RECORDS ── -->
      <div id="page-records" class="page">
        <div class="content-split">
          <div>
            <div class="section-hdr mb-16">
              <div class="section-title">Student Records</div>
              <button class="btn sm" onclick="loadLeads()">↻ Reload</button>
            </div>
            <table class="data-table">
              <thead>
                <tr><th>Name</th><th>Phone</th><th>Unit</th><th>Stage</th><th>Band</th><th>SLA</th><th></th></tr>
              </thead>
              <tbody id="recordsBody">
                <tr><td colspan="7" class="empty-state">Loading...</td></tr>
              </tbody>
            </table>
          </div>
          <div id="recordDrawer" class="drawer">
            <div class="drawer-title">
              <span>Lead Detail</span>
              <span class="text-muted" style="font-size:12px;">Select a row</span>
            </div>
            <div id="drawerContent">
              <div class="empty-state"><div class="icon">👤</div>Select a lead to view details and conversation replay.</div>
            </div>
          </div>
        </div>
      </div>

      <!-- ── PAGE: POST CALL FLOW ── -->
      <div id="page-postcall" class="page">
        <div class="section-hdr mb-16">
          <div class="section-title">Post Call Flow — Call Intelligence</div>
        </div>
        <div id="callIntelList"></div>
      </div>

      <!-- ── PAGE: ANALYTICS ── -->
      <div id="page-analytics" class="page">
        <div class="kpi-grid" id="analyticsKpi" style="grid-template-columns:repeat(3,1fr);">
          <div class="kpi-card">
            <div class="kpi-label">Enquiry</div>
            <div class="kpi-value" id="pEnquiry">—</div>
          </div>
          <div class="kpi-card green">
            <div class="kpi-label">Enrolled</div>
            <div class="kpi-value" id="pEnrolled">—</div>
          </div>
          <div class="kpi-card amber">
            <div class="kpi-label">Fee Payment</div>
            <div class="kpi-value" id="pFee">—</div>
          </div>
        </div>
        <div class="section-hdr mb-16">
          <div class="section-title">Priority Queue</div>
        </div>
        <table class="data-table">
          <thead>
            <tr><th>#</th><th>Lead</th><th>Unit</th><th>Stage</th><th>Band</th><th>Priority Score</th><th>SLA</th><th>Actions</th></tr>
          </thead>
          <tbody id="priorityQueueBody">
            <tr><td colspan="8" class="empty-state">Loading...</td></tr>
          </tbody>
        </table>
      </div>

      <!-- ── PAGE: ALERTS ── -->
      <div id="page-alerts" class="page">
        <div class="section-hdr mb-16">
          <div class="section-title">SLA Breaches</div>
          <button class="btn sm" onclick="loadAlerts()">↻ Reload</button>
        </div>
        <div id="slaList"><div class="empty-state">Loading...</div></div>
        <div class="section-hdr mt-16 mb-16">
          <div class="section-title">Failed Automation Jobs</div>
        </div>
        <div id="jobsList"><div class="empty-state">Loading...</div></div>
        <div class="section-hdr mt-16 mb-16">
          <div class="section-title">Operations Metrics</div>
        </div>
        <div id="opsMetrics"><div class="empty-state">Loading...</div></div>
      </div>

    </div><!-- /page-content -->
  </div><!-- /main-area -->
</div><!-- /appShell -->

<!-- ── SLIDE-OVER: Lead Detail + Logs + Audio ─────────── -->
<div class="overlay" id="soOverlay" onclick="closeSlideOver()"></div>
<div class="slideover" id="slideover">
  <div class="so-header">
    <div>
      <div class="so-title" id="soTitle">Lead Detail</div>
      <div id="soSubtitle" style="font-size:12px;color:var(--muted);margin-top:2px;"></div>
    </div>
    <button class="so-close" onclick="closeSlideOver()">✕</button>
  </div>
  <!-- Tab bar -->
  <div style="display:flex;gap:0;border-bottom:1px solid var(--border);flex-shrink:0;">
    <button class="so-tab active" onclick="switchSoTab('profile')" id="soTabProfile">Profile</button>
    <button class="so-tab" onclick="switchSoTab('form')" id="soTabForm">📋 Enquiry Form</button>
    <button class="so-tab" onclick="switchSoTab('logs')" id="soTabLogs">Logs &amp; Audio</button>
  </div>
  <div class="so-body">
    <!-- TAB: Profile -->
    <div id="soTabContent-profile">
      <div class="so-section" id="soProfile"></div>
      <div class="so-section" id="soSummarySection"></div>
    </div>
    <!-- TAB: Enquiry Form -->
    <div id="soTabContent-form" style="display:none;">
      <div class="so-section">
        <div class="so-section-title" style="display:flex;justify-content:space-between;align-items:center;">
          Post-Call Enquiry Form
          <span id="soFormStatus" style="font-size:11px;color:var(--muted);"></span>
        </div>
        <div id="soFormContent">
          <div class="empty-state">Open a lead to load the form.</div>
        </div>
      </div>
    </div>
    <!-- TAB: Logs & Audio -->
    <div id="soTabContent-logs" style="display:none;">
      <div class="so-section" id="soLogs">
        <div class="so-section-title">Conversation Logs &amp; Recordings</div>
        <div id="soLogsContent"><div class="empty-state" style="padding:20px;">Loading...</div></div>
      </div>
    </div>
  </div>
  <div class="so-actions" id="soActions"></div>
</div>

<script>
// ── State ─────────────────────────────────────────────────
let token = "";
let currentUser = "Admin";
let selectedUnit = "";
let currentLeads = [];
let currentPage = "dashboard";

const PAGE_TITLES = {
  dashboard: "Dashboard",
  pipeline:  "Admission Pipeline",
  records:   "Student Records",
  postcall:  "Post Call Flow",
  analytics: "Analytics",
  alerts:    "Alerts",
};

// ── Auth ──────────────────────────────────────────────────
function authH() {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function doLogin() {
  const u = document.getElementById("u").value.trim();
  const p = document.getElementById("p").value.trim();
  const errEl = document.getElementById("loginErr");
  errEl.textContent = "Signing in…";
  const r = await fetch("/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: u, password: p }),
  });
  const data = await r.json();
  if (!r.ok) {
    errEl.textContent = data.detail || "Invalid credentials.";
    return;
  }
  token = data.access_token;
  currentUser = u;
  document.getElementById("userName").textContent = u.charAt(0).toUpperCase() + u.slice(1);
  document.getElementById("userInitial").textContent = u.charAt(0).toUpperCase();
  document.getElementById("loginScreen").classList.add("hidden");
  document.getElementById("appShell").classList.add("ready");
  await refreshAll();
}

function doLogout() {
  token = "";
  document.getElementById("loginScreen").classList.remove("hidden");
  document.getElementById("appShell").classList.remove("ready");
}

// ── Navigation ────────────────────────────────────────────
function gotoPage(page) {
  currentPage = page;
  document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
  document.getElementById("page-" + page).classList.add("active");
  document.querySelectorAll(".nav-item[data-page]").forEach(b =>
    b.classList.toggle("active", b.dataset.page === page));
  document.getElementById("pageTitle").textContent = PAGE_TITLES[page] || page;
  window.location.hash = page;
  if (token) {
    if (page === "pipeline") renderKanban(currentLeads);
    if (page === "analytics") { renderPriorityQueue(currentLeads); loadPipelineCounts(); }
    if (page === "postcall") renderCallIntel(currentLeads);
    if (page === "alerts") loadAlerts();
  }
}

// ── Unit filter ───────────────────────────────────────────
async function setUnit(btn) {
  document.querySelectorAll(".unit-tab").forEach(t => t.classList.remove("active"));
  btn.classList.add("active");
  selectedUnit = btn.dataset.unit || "";
  await loadLeads();
  if (currentPage === "pipeline") renderKanban(currentLeads);
  if (currentPage === "analytics") renderPriorityQueue(currentLeads);
  if (currentPage === "postcall") renderCallIntel(currentLeads);
}

// ── Data loading ──────────────────────────────────────────
async function refreshAll() {
  await loadLeads();
  await loadDashboardKpis();
  if (currentPage === "pipeline") renderKanban(currentLeads);
  if (currentPage === "analytics") { renderPriorityQueue(currentLeads); loadPipelineCounts(); }
  if (currentPage === "postcall") renderCallIntel(currentLeads);
  if (currentPage === "alerts") loadAlerts();
}

async function loadLeads() {
  if (!token) return;
  const q = new URLSearchParams({ limit: "50" });
  if (selectedUnit) q.set("unit", selectedUnit);
  const r = await fetch("/v1/leads?" + q, { headers: authH() });
  if (!r.ok) return;
  currentLeads = await r.json();
  renderDashLeads(currentLeads);
  renderRecordsTable(currentLeads);
}

async function loadDashboardKpis() {
  if (!token) return;
  const [pipeR, metricsR] = await Promise.all([
    fetch("/v1/analytics/admissions-pipeline", { headers: authH() }),
    fetch("/v1/ops/metrics", { headers: authH() }),
  ]);
  if (pipeR.ok) {
    const d = await pipeR.json();
    const total = Object.values(d).reduce((a,b) => a + Number(b||0), 0);
    document.getElementById("kpiCalls").textContent = total;
    document.getElementById("kpiLeads").textContent = total;
  }
  document.getElementById("kpiHot").textContent =
    currentLeads.filter(l => (l.lead_band||"").toLowerCase() === "hot").length;
  if (metricsR.ok) {
    const m = await metricsR.json();
    document.getElementById("kpiSla").textContent = m.sla_breached || 0;
    const breached = m.sla_breached || 0;
    const hint = document.getElementById("slaHint");
    hint.textContent = breached > 0 ? breached + " need attention" : "All healthy";
    hint.className = "kpi-hint " + (breached > 0 ? "text-red" : "text-green");
  }
}

async function loadPipelineCounts() {
  if (!token) return;
  const r = await fetch("/v1/analytics/admissions-pipeline", { headers: authH() });
  if (!r.ok) return;
  const d = await r.json();
  document.getElementById("pEnquiry").textContent  = d.enquiry    || 0;
  document.getElementById("pEnrolled").textContent = d.enrolled   || 0;
  document.getElementById("pFee").textContent      = d.fee_payment|| 0;
}

async function loadAlerts() {
  if (!token) return;
  loadSlaList();
  loadJobsList();
  loadOpsMetrics();
}

async function loadSlaList() {
  const r = await fetch("/v1/sla/breaches", { headers: authH() });
  const host = document.getElementById("slaList");
  if (!r.ok) { host.innerHTML = '<div class="empty-state text-red">Unable to load SLA data.</div>'; return; }
  const items = await r.json();
  if (!items.length) {
    host.innerHTML = '<div class="empty-state"><div class="icon">✅</div>No SLA breaches right now.</div>'; return;
  }
  host.innerHTML = items.map(x => `
    <div class="alert-row danger">
      <div>
        <div class="alert-label">${x.lead_id}</div>
        <div class="alert-sub">${x.stage} · Counsellor: ${x.assigned_counsellor || "Unassigned"}</div>
      </div>
      <span class="badge hot">SLA Breached</span>
    </div>
  `).join("");
}

async function loadJobsList() {
  const r = await fetch("/v1/automation/jobs?status=dead_lettered&limit=20", { headers: authH() });
  const host = document.getElementById("jobsList");
  if (!r.ok) { host.innerHTML = '<div class="empty-state text-red">Unable to load jobs.</div>'; return; }
  const items = await r.json();
  if (!items.length) {
    host.innerHTML = '<div class="empty-state"><div class="icon">✅</div>No failed jobs.</div>'; return;
  }
  host.innerHTML = items.map(x => `
    <div class="alert-row warn">
      <div>
        <div class="alert-label mono">#${x.id} — ${x.automation_type}</div>
        <div class="alert-sub">Channel: ${x.channel} · Attempts: ${x.attempts} · <span class="text-red">${x.status}</span></div>
      </div>
      <button class="btn danger sm" onclick="retryJob(${x.id})">↺ Retry</button>
    </div>
  `).join("");
}

async function loadOpsMetrics() {
  const r = await fetch("/v1/ops/metrics", { headers: authH() });
  const host = document.getElementById("opsMetrics");
  if (!r.ok) return;
  const m = await r.json();
  host.innerHTML = `
    <table class="data-table">
      <tbody>
        <tr><td>Total Leads</td><td><strong>${m.leads_total}</strong></td></tr>
        <tr><td>Total Calls</td><td><strong>${m.calls_total}</strong></td></tr>
        <tr><td>Total Jobs</td><td><strong>${m.jobs_total}</strong></td></tr>
        <tr><td>Jobs Failed</td><td><strong class="${m.jobs_failed > 0 ? 'text-amber' : 'text-green'}">${m.jobs_failed}</strong></td></tr>
        <tr><td>Dead-lettered</td><td><strong class="${m.jobs_dead_lettered > 0 ? 'text-red' : 'text-green'}">${m.jobs_dead_lettered}</strong></td></tr>
      </tbody>
    </table>
  `;
}

async function retryJob(id) {
  await fetch("/v1/automation/jobs/" + id + "/retry", { method: "POST", headers: authH() });
  loadJobsList();
}

// ── Renderers ─────────────────────────────────────────────
function fmt(v) { return (v == null || v === "") ? "—" : v; }
function bandClass(b) {
  const s = (b||"cold").toLowerCase();
  return s === "hot" ? "hot" : s === "warm" ? "warm" : "cold";
}

function priorityScore(l) {
  const base = Number(l.lead_score || 0);
  const boost = (l.lead_band||"").toLowerCase() === "hot" ? 18 :
                (l.lead_band||"").toLowerCase() === "warm" ? 8 : 0;
  return Math.min(100, base + boost + (l.sla_breached?20:0) + (l.emi_flag?4:0) + (l.referral_flag?3:0));
}

function renderDashLeads(leads) {
  const tbody = document.getElementById("dashLeadBody");
  if (!leads.length) {
    tbody.innerHTML = '<tr><td colspan="8"><div class="empty-state"><div class="icon">📋</div>No leads found.</div></td></tr>';
    return;
  }
  tbody.innerHTML = leads.slice(0,15).map(l => `
    <tr>
      <td><strong>${fmt(l.name)}</strong></td>
      <td class="mono">${fmt(l.phone)}</td>
      <td>${fmt(l.unit)}</td>
      <td><span class="badge stage">${fmt(l.stage)}</span></td>
      <td><span class="badge ${bandClass(l.lead_band)}">${fmt(l.lead_band)}</span></td>
      <td><strong>${fmt(l.lead_score)}</strong></td>
      <td>${fmt(l.assigned_counsellor)}</td>
      <td>
        <button class="btn sm" onclick="openDrawer('${l.lead_id}')">View</button>
        <button class="btn sm primary" onclick="moveStage('${l.lead_id}','counselling')">→ Counsel</button>
      </td>
    </tr>
  `).join("");
}

function renderRecordsTable(leads) {
  const tbody = document.getElementById("recordsBody");
  if (!leads.length) {
    tbody.innerHTML = '<tr><td colspan="7"><div class="empty-state">No records.</div></td></tr>';
    return;
  }
  tbody.innerHTML = leads.map(l => `
    <tr>
      <td><strong>${fmt(l.name)}</strong></td>
      <td class="mono">${fmt(l.phone)}</td>
      <td>${fmt(l.unit)}</td>
      <td><span class="badge stage">${fmt(l.stage)}</span></td>
      <td><span class="badge ${bandClass(l.lead_band)}">${fmt(l.lead_band)}</span></td>
      <td class="${l.sla_breached ? 'text-red' : 'text-green'}">${l.sla_breached ? 'Breached' : 'On track'}</td>
      <td><button class="btn sm" onclick="openDrawer('${l.lead_id}')">Open</button></td>
    </tr>
  `).join("");
}

function renderKanban(leads) {
  const host = document.getElementById("kanbanBoard");
  const lanes = [
    { key: "enquiry",     label: "Enquiry" },
    { key: "demo",        label: "Demo" },
    { key: "counselling", label: "Counselling" },
    { key: "fee_payment", label: "Fee" },
    { key: "enrolled",    label: "Enrolled" },
    { key: "placed",      label: "Placed" },
  ];
  host.innerHTML = lanes.map(({ key, label }) => {
    const cards = leads.filter(l => (l.stage||"").toLowerCase() === key);
    const cardHtml = cards.length
      ? cards.slice(0,8).map(c => `
          <div class="k-card" onclick="openDrawer('${c.lead_id}')">
            <div class="k-name">${fmt(c.name)}</div>
            <div class="k-meta">${fmt(c.phone)}</div>
            <div style="display:flex;gap:5px;flex-wrap:wrap;">
              <span class="badge ${bandClass(c.lead_band)}">${fmt(c.lead_band)}</span>
              <span class="chip">${fmt(c.unit)}</span>
            </div>
          </div>`).join("")
      : '<div class="empty-state" style="padding:24px 0;font-size:12px;">No leads</div>';
    return `
      <div class="kanban-lane">
        <div class="lane-header">
          <div class="lane-title">${label}</div>
          <span class="lane-count">${cards.length}</span>
        </div>
        ${cardHtml}
      </div>`;
  }).join("");
}

function renderPriorityQueue(leads) {
  const tbody = document.getElementById("priorityQueueBody");
  if (!leads.length) {
    tbody.innerHTML = '<tr><td colspan="8"><div class="empty-state">No leads.</div></td></tr>';
    return;
  }
  const sorted = [...leads].map(l => ({...l, ps: priorityScore(l)})).sort((a,b) => b.ps - a.ps);
  tbody.innerHTML = sorted.slice(0,20).map((l, i) => `
    <tr>
      <td class="text-muted">${i+1}</td>
      <td><strong>${fmt(l.name)}</strong><div class="mono text-muted">${fmt(l.phone)}</div></td>
      <td>${fmt(l.unit)}</td>
      <td><span class="badge stage">${fmt(l.stage)}</span></td>
      <td><span class="badge ${bandClass(l.lead_band)}">${fmt(l.lead_band)}</span></td>
      <td><strong>${l.ps}</strong></td>
      <td class="${l.sla_breached ? 'text-red' : 'text-green'}">${l.sla_breached ? 'Breached' : 'On track'}</td>
      <td>
        <button class="btn sm" onclick="openDrawer('${l.lead_id}')">Open</button>
        <button class="btn sm primary" onclick="moveStage('${l.lead_id}','counselling')">Prioritize</button>
      </td>
    </tr>
  `).join("");
}

function renderCallIntel(leads) {
  const host = document.getElementById("callIntelList");
  if (!leads.length) {
    host.innerHTML = '<div class="empty-state"><div class="icon">📞</div>No call data yet.</div>';
    return;
  }
  const top = [...leads].map(l => ({...l, ps: priorityScore(l)})).sort((a,b) => b.ps - a.ps).slice(0,8);
  host.innerHTML = top.map(l => `
    <div class="intel-card">
      <div class="intel-header">
        <div>
          <div class="intel-name">${fmt(l.name)}</div>
          <div class="intel-unit">${fmt(l.unit)} · ${fmt(l.phone)}</div>
        </div>
        <div style="display:flex;gap:8px;align-items:center;">
          <span class="badge ${bandClass(l.lead_band)}">${fmt(l.lead_band)}</span>
          <button class="btn sm primary" onclick="openDrawer('${l.lead_id}')">Replay →</button>
        </div>
      </div>
      <div class="ai-summary">${fmt(l.next_action)}</div>
      <div class="chip-row">
        <span class="chip ${l.emi_flag ? 'highlight' : ''}">${l.emi_flag ? '💰 EMI discussed' : 'No EMI signal'}</span>
        <span class="chip ${l.referral_flag ? 'highlight' : ''}">${l.referral_flag ? '🤝 Referral' : 'No referral'}</span>
        <span class="chip ${l.placement_interest ? 'highlight' : ''}">${l.placement_interest ? '🎯 Placement interest' : ''}</span>
        <span class="chip ${l.sla_breached ? 'highlight' : ''}">SLA: ${l.sla_breached ? '⚠ Breached' : '✓ Healthy'}</span>
      </div>
    </div>
  `).join("");
}

// ── Slide-over: open / close ──────────────────────────────
function openSlideOver() {
  document.getElementById("soOverlay").classList.add("open");
  document.getElementById("slideover").classList.add("open");
}
function closeSlideOver() {
  document.getElementById("soOverlay").classList.remove("open");
  document.getElementById("slideover").classList.remove("open");
}

// ── openDrawer: works from ANY page via slide-over ────────
async function openDrawer(leadId) {
  if (!token) return;

  // Reset to Profile tab
  switchSoTab("profile");

  // Show slide-over immediately with loading state
  document.getElementById("soTitle").textContent = "Loading…";
  document.getElementById("soSubtitle").textContent = leadId;
  document.getElementById("soProfile").innerHTML = "";
  document.getElementById("soSummarySection").innerHTML = "";
  document.getElementById("soLogsContent").innerHTML =
    '<div class="empty-state" style="padding:20px 0;">Loading conversation…</div>';
  document.getElementById("soActions").innerHTML = "";
  openSlideOver();

  const r = await fetch("/v1/leads/" + leadId, { headers: authH() });
  if (!r.ok) {
    document.getElementById("soTitle").textContent = "Error";
    document.getElementById("soProfile").innerHTML =
      '<div class="empty-state text-red">Could not load lead data.</div>';
    return;
  }
  const d = await r.json();
  const l = d.lead;

  // Header
  document.getElementById("soTitle").textContent = fmt(l.name);
  document.getElementById("soSubtitle").textContent =
    fmt(l.unit) + " · " + fmt(l.phone) + " · " + leadId;

  // Profile grid
  document.getElementById("soProfile").innerHTML = `
    <div class="so-section-title">Lead Profile</div>
    <table style="width:100%;font-size:13px;border-collapse:collapse;">
      <tr>
        <td style="padding:7px 0;color:var(--muted);font-weight:500;width:46%;">Stage</td>
        <td><span class="badge stage">${fmt(l.stage)}</span></td>
      </tr>
      <tr>
        <td style="padding:7px 0;color:var(--muted);font-weight:500;border-top:1px solid #f1f3fb;">Lead Band</td>
        <td style="border-top:1px solid #f1f3fb;"><span class="badge ${bandClass(l.lead_band)}">${fmt(l.lead_band)}</span></td>
      </tr>
      <tr>
        <td style="padding:7px 0;color:var(--muted);font-weight:500;border-top:1px solid #f1f3fb;">Score</td>
        <td style="border-top:1px solid #f1f3fb;"><strong>${fmt(l.lead_score)}</strong></td>
      </tr>
      <tr>
        <td style="padding:7px 0;color:var(--muted);font-weight:500;border-top:1px solid #f1f3fb;">Counsellor</td>
        <td style="border-top:1px solid #f1f3fb;">${fmt(l.assigned_counsellor)}</td>
      </tr>
      <tr>
        <td style="padding:7px 0;color:var(--muted);font-weight:500;border-top:1px solid #f1f3fb;">Course interest</td>
        <td style="border-top:1px solid #f1f3fb;">${fmt(l.course_interest)}</td>
      </tr>
      <tr>
        <td style="padding:7px 0;color:var(--muted);font-weight:500;border-top:1px solid #f1f3fb;">Branch</td>
        <td style="border-top:1px solid #f1f3fb;">${fmt(l.branch_interest)}</td>
      </tr>
      <tr>
        <td style="padding:7px 0;color:var(--muted);font-weight:500;border-top:1px solid #f1f3fb;">EMI needed</td>
        <td style="border-top:1px solid #f1f3fb;" class="${l.emi_flag ? 'text-amber' : ''}">${l.emi_flag ? "Yes" : "No"}</td>
      </tr>
      <tr>
        <td style="padding:7px 0;color:var(--muted);font-weight:500;border-top:1px solid #f1f3fb;">Referral</td>
        <td style="border-top:1px solid #f1f3fb;" class="${l.referral_flag ? 'text-green' : ''}">${l.referral_flag ? "Yes" : "No"}</td>
      </tr>
      <tr>
        <td style="padding:7px 0;color:var(--muted);font-weight:500;border-top:1px solid #f1f3fb;">SLA status</td>
        <td style="border-top:1px solid #f1f3fb;" class="${l.sla_breached ? 'text-red' : 'text-green'}">${l.sla_breached ? "⚠ Breached" : "✓ Healthy"}</td>
      </tr>
    </table>
  `;

  // AI summary
  document.getElementById("soSummarySection").innerHTML = `
    <div class="so-section-title">AI Call Summary</div>
    <div class="ai-summary">${fmt(l.ai_call_summary)}</div>
    <div class="ai-summary" style="margin-top:8px;background:#f0fff6;border-color:#b7f0d0;color:#155c2e;">
      <strong>Next action:</strong> ${fmt(l.next_action)}
    </div>
  `;

  // Actions footer
  document.getElementById("soActions").innerHTML = `
    <button class="btn primary" onclick="moveStage('${leadId}','counselling');closeSlideOver();">→ Counselling</button>
    <button class="btn" onclick="moveStage('${leadId}','fee_payment');closeSlideOver();">→ Fee</button>
    <button class="btn" onclick="moveStage('${leadId}','enrolled');closeSlideOver();">→ Enroll</button>
    <button class="btn" onclick="moveStage('${leadId}','placed');closeSlideOver();">→ Placed</button>
  `;

  // Load enquiry form (pre-populated from call data)
  loadEnquiryForm(leadId);
  // Load conversation logs + audio
  loadConversationInSlideOver(leadId);
}

async function loadConversationInSlideOver(leadId) {
  const host = document.getElementById("soLogsContent");
  const r = await fetch("/v1/leads/" + leadId + "/conversation", { headers: authH() });
  if (!r.ok) {
    host.innerHTML = '<div class="empty-state text-red">Could not load conversation logs.</div>';
    return;
  }
  const conv = await r.json();
  if (!conv.turns || !conv.turns.length) {
    host.innerHTML = '<div class="empty-state" style="padding:16px 0;">No conversation turns recorded yet.<br><span style="font-size:12px;color:var(--muted);">Turns are captured when INTERVIEW_WEBHOOK_URL is set.</span></div>';
    return;
  }

  // Group turns by call_id for per-call sections
  const callGroups = {};
  conv.turns.forEach(t => {
    if (!callGroups[t.call_id]) callGroups[t.call_id] = [];
    callGroups[t.call_id].push(t);
  });

  let html = "";
  Object.entries(callGroups).forEach(([callId, turns]) => {
    // Find any recording URL for this call
    const recTurn = turns.find(t => t.recording_url);
    const audioHtml = recTurn
      ? `<div class="audio-row">
           <span class="audio-label">▶ Recording</span>
           <audio controls preload="none">
             <source src="/v1/calls/${callId}/recording" type="audio/mpeg">
             Your browser does not support audio.
           </audio>
         </div>`
      : `<div style="font-size:11px;color:var(--muted);margin-bottom:8px;">No recording for this call.</div>`;

    const turnsHtml = turns
      .sort((a,b) => a.turn_index - b.turn_index || a.id - b.id)
      .map(t => {
        const isCaller = t.speaker === "user";
        return `
          <div class="log-turn ${isCaller ? 'caller' : 'aria'}">
            <div class="log-speaker ${isCaller ? 'caller' : 'aria'}">
              ${isCaller ? "👤 CALLER" : "🤖 ARIA (AI)"}
            </div>
            <div class="log-text">${fmt(t.text)}</div>
            <div class="log-meta">
              Turn ${t.turn_index}
              ${t.latency_ms ? " · " + t.latency_ms + " ms total" : ""}
              ${t.stt_ms ? " · STT " + t.stt_ms + "ms" : ""}
              ${t.llm_ms ? " · LLM " + t.llm_ms + "ms" : ""}
              ${t.tts_ms ? " · TTS " + t.tts_ms + "ms" : ""}
            </div>
          </div>`;
      }).join("");

    html += `
      <div style="margin-bottom:20px;">
        <div style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px;">
          Call — ${callId}
        </div>
        ${audioHtml}
        ${turnsHtml}
      </div>`;
  });

  host.innerHTML = html;
}

async function moveStage(leadId, stage) {
  if (!token) return;
  await fetch("/v1/leads/" + leadId + "/stage", {
    method: "POST",
    headers: { ...authH(), "Content-Type": "application/json" },
    body: JSON.stringify({ stage, note: "UI: moved to " + stage }),
  });
  await loadLeads();
  await openDrawer(leadId);
  if (currentPage === "pipeline") renderKanban(currentLeads);
}

// ── Slide-over tabs ───────────────────────────────────────
function switchSoTab(tab) {
  ["profile","form","logs"].forEach(t => {
    document.getElementById("soTabContent-" + t).style.display = t === tab ? "block" : "none";
    document.getElementById("soTab" + t.charAt(0).toUpperCase() + t.slice(1)).classList.toggle("active", t === tab);
  });
}

// ── Enquiry form load & render ────────────────────────────
let _currentFormLeadId = null;

async function loadEnquiryForm(leadId) {
  _currentFormLeadId = leadId;
  const host = document.getElementById("soFormContent");
  const status = document.getElementById("soFormStatus");
  host.innerHTML = '<div class="empty-state" style="padding:16px 0;">Loading form…</div>';
  status.textContent = "";

  const r = await fetch("/v1/leads/" + leadId + "/enquiry-form", { headers: authH() });
  let f = {};
  if (r.ok) {
    f = await r.json();
    if (f.form_filled_at) {
      status.textContent = "Last saved: " + new Date(f.form_filled_at).toLocaleString();
      status.style.color = "var(--green)";
    }
  }

  host.innerHTML = `
    <div class="enq-section-label">Personal Information</div>
    <div class="enq-check-row">
      <label class="enq-check">
        <input type="checkbox" id="ef_someone_else" ${f.enquiry_for_someone_else ? "checked" : ""}>
        Enquiry for someone else
      </label>
      <label class="enq-check">
        <input type="checkbox" id="ef_experienced" ${f.experienced_enquiry ? "checked" : ""}>
        Experienced Enquiry
      </label>
    </div>
    <div class="enq-row">
      <div class="enq-field"><label>Student Name</label>
        <input id="ef_name" value="${v(f.name)}" placeholder="Full name" /></div>
      <div class="enq-field"><label>Mobile Number</label>
        <input id="ef_phone" value="${v(f.phone)}" placeholder="+91..." /></div>
    </div>
    <div class="enq-row">
      <div class="enq-field"><label>Email</label>
        <input id="ef_email" type="email" value="${v(f.email)}" placeholder="email@example.com" /></div>
      <div class="enq-field"><label>Highest Degree</label>
        <input id="ef_degree" value="${v(f.highest_degree)}" placeholder="B.E / B.Sc / MCA..." /></div>
    </div>
    <div class="enq-row">
      <div class="enq-field"><label>Year of Passing (YOP)</label>
        <input id="ef_yop" value="${v(f.year_of_passing)}" placeholder="2023" /></div>
      <div class="enq-field"><label>Class Timing</label>
        <select id="ef_timing">
          ${["","Morning","Afternoon","Evening","Weekend"].map(o =>
            `<option value="${o}" ${f.class_timing === o ? "selected" : ""}>${o || "-- Select --"}</option>`).join("")}
        </select>
      </div>
    </div>
    <div class="enq-row full">
      <div class="enq-field"><label>Time Slot</label>
        <select id="ef_slot">
          ${["","7am–9am","9am–11am","11am–1pm","1pm–3pm","3pm–5pm","5pm–7pm","7pm–9pm","Sat–Sun"].map(o =>
            `<option value="${o}" ${f.time_slot === o ? "selected" : ""}>${o || "-- Select --"}</option>`).join("")}
        </select>
      </div>
    </div>

    <div class="enq-section-label">Regular Course Enquiries</div>
    <div class="enq-row">
      <div class="enq-field"><label>Course</label>
        <input id="ef_course" value="${v(f.course_interest)}" placeholder="Selenium / Java / Python..." /></div>
      <div class="enq-field"><label>Branch</label>
        <input id="ef_branch" value="${v(f.branch_interest)}" placeholder="BTM / Jayanagar / HSR..." /></div>
    </div>
    <div class="enq-row full">
      <div class="enq-field"><label>Mode of Class</label>
        <select id="ef_mode">
          ${["","Classroom","Online","Hybrid"].map(o =>
            `<option value="${o}" ${f.mode_of_class === o ? "selected" : ""}>${o || "-- Select --"}</option>`).join("")}
        </select>
      </div>
    </div>

    <div class="enq-section-label">Special Course Enquiries</div>
    <div class="enq-row">
      <div class="enq-field"><label>Special Course</label>
        <input id="ef_special" value="${v(f.special_course)}" placeholder="ISTQB / OCJP / DevOps..." /></div>
      <div class="enq-field"><label>Other Course</label>
        <input id="ef_other" value="${v(f.other_course)}" placeholder="Any other course" /></div>
    </div>
    <div class="enq-row full">
      <div class="enq-field"><label>Mode of Class (Special)</label>
        <select id="ef_smode">
          ${["","Classroom","Online","Hybrid"].map(o =>
            `<option value="${o}" ${f.special_mode_of_class === o ? "selected" : ""}>${o || "-- Select --"}</option>`).join("")}
        </select>
      </div>
    </div>

    <div class="enq-section-label">Referrals</div>
    <div class="enq-row">
      <div class="enq-field"><label>Referral Name</label>
        <input id="ef_rname" value="${v(f.referral_name)}" placeholder="Who referred?" /></div>
      <div class="enq-field"><label>Referral Mobile</label>
        <input id="ef_rmobile" value="${v(f.referral_mobile)}" placeholder="+91..." /></div>
    </div>
    <div class="enq-row full">
      <div class="enq-field"><label>Comments</label>
        <textarea id="ef_comments" placeholder="Any additional notes from the call...">${v(f.enquiry_comments)}</textarea>
      </div>
    </div>

    <button class="save-form-btn" onclick="saveEnquiryForm()">💾 Save Enquiry Form</button>
  `;
}

function v(val) { return (val == null || val === "—") ? "" : String(val); }

async function saveEnquiryForm() {
  if (!_currentFormLeadId || !token) return;
  const btn = document.querySelector(".save-form-btn");
  const status = document.getElementById("soFormStatus");
  btn.textContent = "Saving…"; btn.disabled = true;

  const payload = {
    enquiry_for_someone_else: document.getElementById("ef_someone_else").checked,
    experienced_enquiry:      document.getElementById("ef_experienced").checked,
    name:             document.getElementById("ef_name").value.trim() || null,
    phone:            document.getElementById("ef_phone").value.trim() || null,
    email:            document.getElementById("ef_email").value.trim() || null,
    class_timing:     document.getElementById("ef_timing").value || null,
    time_slot:        document.getElementById("ef_slot").value || null,
    highest_degree:   document.getElementById("ef_degree").value.trim() || null,
    year_of_passing:  document.getElementById("ef_yop").value.trim() || null,
    course_interest:  document.getElementById("ef_course").value.trim() || null,
    branch_interest:  document.getElementById("ef_branch").value.trim() || null,
    mode_of_class:    document.getElementById("ef_mode").value || null,
    special_course:   document.getElementById("ef_special").value.trim() || null,
    other_course:     document.getElementById("ef_other").value.trim() || null,
    special_mode_of_class: document.getElementById("ef_smode").value || null,
    referral_name:    document.getElementById("ef_rname").value.trim() || null,
    referral_mobile:  document.getElementById("ef_rmobile").value.trim() || null,
    enquiry_comments: document.getElementById("ef_comments").value.trim() || null,
  };

  const r = await fetch("/v1/leads/" + _currentFormLeadId + "/enquiry-form", {
    method: "POST",
    headers: { ...authH(), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  btn.disabled = false;
  if (r.ok) {
    const saved = await r.json();
    btn.textContent = "✓ Saved";
    btn.style.background = "var(--green)";
    status.textContent = "Saved at " + new Date(saved.form_filled_at).toLocaleString();
    status.style.color = "var(--green)";
    setTimeout(() => {
      btn.textContent = "💾 Save Enquiry Form";
      btn.style.background = "";
    }, 2500);
    await loadLeads();
  } else {
    btn.textContent = "✕ Save failed — retry";
    btn.style.background = "var(--red)";
    status.textContent = "Error saving form.";
    status.style.color = "var(--red)";
  }
}

// ── Boot ──────────────────────────────────────────────────
const hash = window.location.hash.replace("#","");
if (hash && PAGE_TITLES[hash]) {
  setTimeout(() => gotoPage(hash), 200);
}
</script>
</body>
</html>
"""
