import json
import os
from datetime import datetime, timezone


def load_json(path: str) -> list | dict:
    if not os.path.exists(path):
        return []
    with open(path) as f:
        try:
            return json.load(f)
        except Exception:
            return []


def calc_pnl_stats(history: list) -> dict:
    if not history:
        return {
            "all_time": 0.0, "wins": 0, "losses": 0,
            "win_rate": 0.0, "avg_gain": 0.0, "avg_loss": 0.0,
            "best": 0.0, "worst": 0.0,
            "this_week": 0.0, "this_month": 0.0, "this_year": 0.0
        }

    from datetime import date, timedelta
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)

    all_time = 0.0
    this_week = 0.0
    this_month = 0.0
    this_year = 0.0
    wins = 0
    losses = 0
    gains = []
    loss_amounts = []
    best = None
    worst = None

    for t in history:
        pnl = t.get("realized_pnl", 0.0)
        close_date_str = t.get("close_date", "")
        all_time += pnl
        if best is None or pnl > best:
            best = pnl
        if worst is None or pnl < worst:
            worst = pnl
        if pnl > 0:
            wins += 1
            gains.append(pnl)
        elif pnl < 0:
            losses += 1
            loss_amounts.append(pnl)
        try:
            cd = date.fromisoformat(close_date_str)
            if cd >= week_start:
                this_week += pnl
            if cd >= month_start:
                this_month += pnl
            if cd >= year_start:
                this_year += pnl
        except Exception:
            pass

    total = wins + losses
    return {
        "all_time": round(all_time, 2),
        "this_week": round(this_week, 2),
        "this_month": round(this_month, 2),
        "this_year": round(this_year, 2),
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / total * 100, 1) if total > 0 else 0.0,
        "avg_gain": round(sum(gains) / len(gains), 2) if gains else 0.0,
        "avg_loss": round(sum(loss_amounts) / len(loss_amounts), 2) if loss_amounts else 0.0,
        "best": round(best, 2) if best is not None else 0.0,
        "worst": round(worst, 2) if worst is not None else 0.0,
    }


def pnl_color(val: float) -> str:
    if val > 0:
        return "#1a7f4b"
    elif val < 0:
        return "#c0392b"
    return "#888"


def fmt_pnl(val: float) -> str:
    sign = "+" if val >= 0 else ""
    return f"{sign}${val:,.2f}"


def generate_dashboard() -> None:
    positions = load_json("data/positions.json")
    history = load_json("data/history.json")
    signals = load_json("data/last_signals.json")

    open_positions = [p for p in positions
                      if p.get("status") in ("OPEN", "PARTIAL")]
    stats = calc_pnl_stats(history)
    scan_time = datetime.now(timezone.utc).strftime("%b %d %Y, %I:%M %p UTC")

    # Build positions HTML
    pos_html = ""
    if not open_positions:
        pos_html = '<p style="color:#888;font-size:14px;padding:12px 0">No open positions.</p>'
    for p in open_positions:
        status = p.get("status", "OPEN")
        status_color = "#1a7f4b" if status == "OPEN" else "#b07d0a"
        status_bg = "#eafaf1" if status == "OPEN" else "#fef9e7"
        ticker = p["ticker"]
        shares = p["shares_remaining"]
        avg_entry = p["avg_entry_price"]
        stop = p["stop"]
        target = p["target"]
        days = p.get("days_held", 0)
        realized = p.get("realized_pnl", 0.0)
        pos_html += f"""
        <div class="card" style="margin-bottom:10px">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
            <div style="font-size:17px;font-weight:500">{ticker}</div>
            <div style="display:flex;gap:8px;align-items:center">
              <span style="font-size:13px;font-weight:500;color:{pnl_color(realized)}">{fmt_pnl(realized)} realized</span>
              <span style="font-size:11px;font-weight:500;padding:2px 8px;border-radius:20px;
                background:{status_bg};color:{status_color}">{status}</span>
            </div>
          </div>
          <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:12px">
            <div class="pos-stat"><div class="pos-stat-label">Shares held</div><div class="pos-stat-val">{shares:.4f}</div></div>
            <div class="pos-stat"><div class="pos-stat-label">Avg entry</div><div class="pos-stat-val">${avg_entry:.2f}</div></div>
            <div class="pos-stat"><div class="pos-stat-label">Days held</div><div class="pos-stat-val">{days}</div></div>
            <div class="pos-stat"><div class="pos-stat-label">Stop loss</div><div class="pos-stat-val" style="color:#c0392b">${stop:.2f}</div></div>
            <div class="pos-stat"><div class="pos-stat-label">Target</div><div class="pos-stat-val" style="color:#1a7f4b">${target:.2f}</div></div>
            <div class="pos-stat"><div class="pos-stat-label">Trailing stop</div>
              <div class="pos-stat-val" style="color:#b07d0a">${p.get('trailing_stop', stop):.2f}</div></div>
          </div>
          <button class="btn-danger" onclick="openSellForm('{ticker}', {shares}, {avg_entry})">
            Log sell
          </button>
        </div>"""

    # Build signals HTML
    sig_html = ""
    if not signals:
        sig_html = '<p style="color:#888;font-size:14px;padding:12px 0">No signals from last scan.</p>'
    for s in signals[:10]:
        ticker = s["ticker"]
        score = s["score"]
        entry = s["entry"]
        stop = s["stop"]
        target = s["target"]
        shares = s["shares"]
        pv = s["position_value"]
        fired = [k for k, v in s.get("signals", {}).items() if v]
        fired_str = ", ".join(fired)
        sig_html += f"""
        <div class="card" style="margin-bottom:10px">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px">
            <div>
              <span style="font-size:16px;font-weight:500">{ticker}</span>
              <span style="font-size:12px;color:#888;margin-left:8px">Score {score}/10</span>
            </div>
            <button class="btn-success" onclick="openBuyForm('{ticker}', {entry}, {shares}, {stop}, {target})">
              Log buy
            </button>
          </div>
          <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:8px">
            <div class="pos-stat"><div class="pos-stat-label">Entry</div><div class="pos-stat-val">${entry:.2f}</div></div>
            <div class="pos-stat"><div class="pos-stat-label">Stop</div><div class="pos-stat-val" style="color:#c0392b">${stop:.2f}</div></div>
            <div class="pos-stat"><div class="pos-stat-label">Target</div><div class="pos-stat-val" style="color:#1a7f4b">${target:.2f}</div></div>
            <div class="pos-stat"><div class="pos-stat-label">Suggested shares</div><div class="pos-stat-val">{shares}</div></div>
            <div class="pos-stat"><div class="pos-stat-label">Position cost</div><div class="pos-stat-val">${pv:,.2f}</div></div>
            <div class="pos-stat"><div class="pos-stat-label">Max risk</div><div class="pos-stat-val">$25.00</div></div>
          </div>
          <div style="font-size:11px;color:#888">Signals: {fired_str}</div>
        </div>"""

    # Build history HTML
    hist_html = ""
    if not history:
        hist_html = '<p style="color:#888;font-size:14px;padding:12px 0">No closed trades yet.</p>'
    for t in reversed(history):
        ticker = t["ticker"]
        pnl = t.get("realized_pnl", 0.0)
        reason = t.get("exit_reason", "manual")
        entry_date = t.get("entry_date", "")
        close_date = t.get("close_date", "")
        days = t.get("days_held", 0)
        avg_entry = t.get("avg_entry_price", 0.0)
        hist_html += f"""
        <div style="display:flex;justify-content:space-between;align-items:center;
          padding:10px 0;border-bottom:0.5px solid #e5e5e5">
          <div>
            <div style="font-size:14px;font-weight:500">{ticker}</div>
            <div style="font-size:11px;color:#888">{entry_date} to {close_date}
              &middot; {days}d &middot; {reason} &middot; entry ${avg_entry:.2f}</div>
          </div>
          <div style="font-size:14px;font-weight:500;color:{pnl_color(pnl)}">{fmt_pnl(pnl)}</div>
        </div>"""

    # Build stats HTML
    def stat_block(label, value, color="#1a1a1a"):
        return f"""<div class="stat-card">
          <div class="stat-label">{label}</div>
          <div class="stat-val" style="color:{color}">{value}</div>
        </div>"""

    stats_html = f"""
    <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin-bottom:16px">
      {stat_block("This week", fmt_pnl(stats['this_week']), pnl_color(stats['this_week']))}
      {stat_block("This month", fmt_pnl(stats['this_month']), pnl_color(stats['this_month']))}
      {stat_block("This year", fmt_pnl(stats['this_year']), pnl_color(stats['this_year']))}
      {stat_block("All time", fmt_pnl(stats['all_time']), pnl_color(stats['all_time']))}
    </div>
    <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:8px">
      {stat_block("Win rate", f"{stats['win_rate']}%")}
      {stat_block("Total trades", str(stats['wins'] + stats['losses']))}
      {stat_block("Wins / Losses", f"{stats['wins']} / {stats['losses']}")}
      {stat_block("Avg gain", fmt_pnl(stats['avg_gain']), "#1a7f4b")}
      {stat_block("Avg loss", fmt_pnl(stats['avg_loss']), "#c0392b")}
      {stat_block("Best trade", fmt_pnl(stats['best']), "#1a7f4b")}
      {stat_block("Worst trade", fmt_pnl(stats['worst']), "#c0392b")}
    </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CSS Trader</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #f5f5f5; color: #1a1a1a; }}
  .header {{ background: #fff; border-bottom: 0.5px solid #e0e0e0;
    padding: 14px 16px; position: sticky; top: 0; z-index: 10; }}
  .header-row {{ display: flex; justify-content: space-between; align-items: center; }}
  .header-title {{ font-size: 18px; font-weight: 500; }}
  .header-scan {{ font-size: 11px; color: #888; margin-top: 2px; }}
  .regime-badge {{ font-size: 11px; font-weight: 500; padding: 3px 10px;
    border-radius: 20px; background: #eafaf1; color: #1a7f4b; }}
  .metrics {{ display: grid; grid-template-columns: repeat(3, 1fr);
    gap: 8px; padding: 12px 16px; }}
  .metric {{ background: #fff; border-radius: 10px; padding: 10px 12px;
    border: 0.5px solid #e0e0e0; text-align: center; }}
  .metric-val {{ font-size: 17px; font-weight: 500; }}
  .metric-lbl {{ font-size: 10px; color: #888; margin-top: 2px; }}
  .tabs {{ display: flex; gap: 0; padding: 0 16px;
    border-bottom: 0.5px solid #e0e0e0; background: #fff; }}
  .tab {{ font-size: 13px; padding: 10px 14px; cursor: pointer;
    border-bottom: 2px solid transparent; color: #888; white-space: nowrap; }}
  .tab.active {{ color: #1a1a1a; font-weight: 500;
    border-bottom-color: #1a1a1a; }}
  .tab-content {{ display: none; padding: 14px 16px; }}
  .tab-content.active {{ display: block; }}
  .card {{ background: #fff; border-radius: 12px; padding: 14px;
    border: 0.5px solid #e0e0e0; }}
  .pos-stat {{ background: #f8f8f8; border-radius: 8px; padding: 8px 10px; }}
  .pos-stat-label {{ font-size: 10px; color: #888; margin-bottom: 2px; }}
  .pos-stat-val {{ font-size: 13px; font-weight: 500; }}
  .stat-card {{ background: #fff; border-radius: 10px; padding: 12px 14px;
    border: 0.5px solid #e0e0e0; }}
  .stat-label {{ font-size: 11px; color: #888; margin-bottom: 4px; }}
  .stat-val {{ font-size: 18px; font-weight: 500; }}
  .btn-success {{ background: #eafaf1; color: #1a7f4b; border: 0.5px solid #a9dfbf;
    border-radius: 8px; padding: 7px 14px; font-size: 13px; cursor: pointer; }}
  .btn-danger {{ background: #fdf2f2; color: #c0392b; border: 0.5px solid #f1948a;
    border-radius: 8px; padding: 7px 14px; font-size: 13px; cursor: pointer;
    width: 100%; }}
  .overlay {{ display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.5);
    z-index: 100; align-items: center; justify-content: center; padding: 20px; }}
  .overlay.open {{ display: flex; }}
  .modal {{ background: #fff; border-radius: 16px; padding: 20px;
    width: 100%; max-width: 380px; }}
  .modal-title {{ font-size: 16px; font-weight: 500; margin-bottom: 16px; }}
  .form-group {{ margin-bottom: 14px; }}
  .form-label {{ font-size: 12px; color: #888; margin-bottom: 4px; display: block; }}
  .form-input {{ width: 100%; padding: 10px 12px; border: 0.5px solid #ddd;
    border-radius: 8px; font-size: 15px; outline: none; }}
  .form-input:focus {{ border-color: #1a1a1a; }}
  .form-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
  .form-hint {{ font-size: 11px; color: #aaa; margin-top: 3px; }}
  .btn-primary {{ background: #1a1a1a; color: #fff; border: none;
    border-radius: 8px; padding: 12px; font-size: 14px; cursor: pointer;
    width: 100%; margin-top: 4px; }}
  .btn-cancel {{ background: none; border: none; color: #888;
    font-size: 13px; cursor: pointer; width: 100%; padding: 10px;
    margin-top: 6px; }}
  select.form-input {{ appearance: none; }}
  .section-label {{ font-size: 11px; font-weight: 500; color: #888;
    letter-spacing: .06em; text-transform: uppercase; margin-bottom: 10px; }}
</style>
</head>
<body>

<div class="header">
  <div class="header-row">
    <div>
      <div class="header-title">CSS Trader</div>
      <div class="header-scan">Last scan: {scan_time}</div>
    </div>
    <div class="regime-badge">BULL</div>
  </div>
</div>

<div class="metrics">
  <div class="metric">
    <div class="metric-val" style="color:{pnl_color(stats['this_week'])}">{fmt_pnl(stats['this_week'])}</div>
    <div class="metric-lbl">This week</div>
  </div>
  <div class="metric">
    <div class="metric-val" style="color:{pnl_color(stats['all_time'])}">{fmt_pnl(stats['all_time'])}</div>
    <div class="metric-lbl">All time</div>
  </div>
  <div class="metric">
    <div class="metric-val">{stats['win_rate']}%</div>
    <div class="metric-lbl">Win rate</div>
  </div>
</div>

<div class="tabs">
  <div class="tab active" onclick="showTab('positions')">Positions ({len(open_positions)})</div>
  <div class="tab" onclick="showTab('signals')">Signals ({len(signals)})</div>
  <div class="tab" onclick="showTab('history')">History ({len(history)})</div>
  <div class="tab" onclick="showTab('stats')">Stats</div>
</div>

<div id="tab-positions" class="tab-content active">
  <div class="section-label" style="margin-bottom:12px">Open positions ({len(open_positions)}/5)</div>
  {pos_html}
</div>

<div id="tab-signals" class="tab-content">
  <div class="section-label" style="margin-bottom:12px">Latest buy signals &mdash; {scan_time}</div>
  {sig_html}
</div>

<div id="tab-history" class="tab-content">
  <div class="section-label" style="margin-bottom:12px">Closed trades</div>
  {hist_html}
</div>

<div id="tab-stats" class="tab-content">
  <div class="section-label" style="margin-bottom:12px">Performance</div>
  {stats_html}
</div>

<!-- Buy modal -->
<div class="overlay" id="buy-overlay">
  <div class="modal">
    <div class="modal-title" id="buy-title">Log buy</div>
    <div class="form-group">
      <label class="form-label">Shares purchased (fractional ok)</label>
      <input class="form-input" type="number" step="0.0001" id="buy-shares"
        placeholder="e.g. 1.5">
      <div class="form-hint" id="buy-shares-hint"></div>
    </div>
    <div class="form-group">
      <label class="form-label">Price per share you paid</label>
      <input class="form-input" type="number" step="0.0001" id="buy-price"
        placeholder="e.g. 234.81">
      <div class="form-hint" id="buy-price-hint"></div>
    </div>
    <div class="form-group">
      <label class="form-label">Stop loss price</label>
      <input class="form-input" type="number" step="0.0001" id="buy-stop">
    </div>
    <div class="form-group">
      <label class="form-label">Target price (50% exit)</label>
      <input class="form-input" type="number" step="0.0001" id="buy-target">
    </div>
    <button class="btn-primary" onclick="submitBuy()">Confirm buy</button>
    <button class="btn-cancel" onclick="closeModal()">Cancel</button>
  </div>
</div>

<!-- Sell modal -->
<div class="overlay" id="sell-overlay">
  <div class="modal">
    <div class="modal-title" id="sell-title">Log sell</div>
    <div class="form-group">
      <label class="form-label">Shares sold (fractional ok)</label>
      <input class="form-input" type="number" step="0.0001" id="sell-shares"
        placeholder="e.g. 0.75">
      <div class="form-hint" id="sell-shares-hint"></div>
    </div>
    <div class="form-group">
      <label class="form-label">Price per share you received</label>
      <input class="form-input" type="number" step="0.0001" id="sell-price"
        placeholder="e.g. 255.87">
    </div>
    <div class="form-group">
      <label class="form-label">Exit reason</label>
      <select class="form-input" id="sell-reason">
        <option value="target">Target hit</option>
        <option value="stop">Stop loss hit</option>
        <option value="trailing_stop">Trailing stop hit</option>
        <option value="time">Time stop (day 15)</option>
        <option value="signal_reversal">Signal reversal</option>
        <option value="manual">Manual exit</option>
      </select>
    </div>
    <div id="sell-pnl-preview"
      style="background:#f8f8f8;border-radius:8px;padding:10px 12px;
        margin-bottom:12px;font-size:13px;display:none">
    </div>
    <button class="btn-primary" onclick="submitSell()">Confirm sell</button>
    <button class="btn-cancel" onclick="closeModal()">Cancel</button>
  </div>
</div>

<script>
const DATA = {{
  positions: {json.dumps([p for p in positions if p.get('status') in ('OPEN','PARTIAL')])},
  signals: {json.dumps(signals[:10])}
}};

let activeTicker = null;
let activeShares = 0;
let activeEntry = 0;

function showTab(name) {{
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  event.target.classList.add('active');
}}

function openBuyForm(ticker, entry, shares, stop, target) {{
  activeTicker = ticker;
  document.getElementById('buy-title').textContent = 'Log buy — ' + ticker;
  document.getElementById('buy-shares').value = shares;
  document.getElementById('buy-price').value = entry;
  document.getElementById('buy-stop').value = stop;
  document.getElementById('buy-target').value = target;
  document.getElementById('buy-shares-hint').textContent =
    'Suggested: ' + shares + ' shares';
  document.getElementById('buy-price-hint').textContent =
    'Signal entry price: $' + entry;
  document.getElementById('buy-overlay').classList.add('open');
}}

function openSellForm(ticker, sharesRemaining, avgEntry) {{
  activeTicker = ticker;
  activeShares = sharesRemaining;
  activeEntry = avgEntry;
  document.getElementById('sell-title').textContent = 'Log sell — ' + ticker;
  document.getElementById('sell-shares').value = sharesRemaining;
  document.getElementById('sell-shares-hint').textContent =
    'Max: ' + sharesRemaining + ' shares remaining';
  document.getElementById('sell-pnl-preview').style.display = 'none';
  document.getElementById('sell-overlay').classList.add('open');

  document.getElementById('sell-price').oninput = function() {{
    const price = parseFloat(this.value);
    const shares = parseFloat(document.getElementById('sell-shares').value);
    if (!isNaN(price) && !isNaN(shares) && activeEntry) {{
      const pnl = (price - activeEntry) * shares;
      const preview = document.getElementById('sell-pnl-preview');
      preview.style.display = 'block';
      preview.style.color = pnl >= 0 ? '#1a7f4b' : '#c0392b';
      preview.textContent = 'Estimated P&L: ' +
        (pnl >= 0 ? '+' : '') + '$' + pnl.toFixed(2) +
        ' on ' + shares.toFixed(4) + ' shares';
    }}
  }};
}}

function closeModal() {{
  document.getElementById('buy-overlay').classList.remove('open');
  document.getElementById('sell-overlay').classList.remove('open');
  activeTicker = null;
}}

async function submitBuy() {{
  const shares = parseFloat(document.getElementById('buy-shares').value);
  const price = parseFloat(document.getElementById('buy-price').value);
  const stop = parseFloat(document.getElementById('buy-stop').value);
  const target = parseFloat(document.getElementById('buy-target').value);

  if (isNaN(shares) || shares <= 0) {{
    alert('Please enter a valid number of shares.'); return;
  }}
  if (isNaN(price) || price <= 0) {{
    alert('Please enter a valid price.'); return;
  }}

  const sig = DATA.signals.find(s => s.ticker === activeTicker) || {{}};
  const payload = {{
    action: 'buy',
    ticker: activeTicker,
    shares: shares,
    price: price,
    stop: stop,
    target: target,
    atr: sig.atr || 0,
    sector_etf: sig.sector_etf || 'N/A',
    score: sig.score || 0
  }};

  const result = await sendTrade(payload);
  if (result) {{
    alert('Buy logged for ' + activeTicker + '! Refresh the page in a moment to see it.');
    closeModal();
  }}
}}

async function submitSell() {{
  const shares = parseFloat(document.getElementById('sell-shares').value);
  const price = parseFloat(document.getElementById('sell-price').value);
  const reason = document.getElementById('sell-reason').value;

  if (isNaN(shares) || shares <= 0) {{
    alert('Please enter a valid number of shares.'); return;
  }}
  if (shares > activeShares + 0.0001) {{
    alert('Cannot sell more shares than you hold (' + activeShares + ').'); return;
  }}
  if (isNaN(price) || price <= 0) {{
    alert('Please enter a valid price.'); return;
  }}

  const payload = {{
    action: 'sell',
    ticker: activeTicker,
    shares: shares,
    price: price,
    reason: reason
  }};

  const result = await sendTrade(payload);
  if (result) {{
    const pnl = (price - activeEntry) * shares;
    alert('Sell logged for ' + activeTicker + '\\nP&L: ' +
      (pnl >= 0 ? '+' : '') + '$' + pnl.toFixed(2) +
      '\\nRefresh the page in a moment.');
    closeModal();
  }}
}}

async function sendTrade(payload) {{
  try {{
    const resp = await fetch('https://css-trader-api.onrender.com/trade', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify(payload)
    }});
    if (!resp.ok) {{
      const err = await resp.text();
      alert('Error: ' + err);
      return null;
    }}
    return await resp.json();
  }} catch(e) {{
    alert('Could not connect to the trade logger. Is it running?\\n' + e);
    return null;
  }}
}}

document.querySelectorAll('.overlay').forEach(o => {{
  o.addEventListener('click', function(e) {{
    if (e.target === this) closeModal();
  }});
}});
</script>
</body>
</html>"""

    os.makedirs("dashboard", exist_ok=True)
    with open("dashboard/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("[dashboard] Generated dashboard/index.html")


if __name__ == "__main__":
    generate_dashboard()
