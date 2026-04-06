"""
Dock Chaos Dashboard — Real-time WebSocket visualization of chaos attacks.
Serves a simple HTML dashboard that connects via WebSocket to show live
fault injection events, recovery status, and timing.
"""

import asyncio
import json
import threading
from datetime import datetime, timezone

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse


dashboard_app = FastAPI(title="Dock Chaos Dashboard")

# Connected WebSocket clients
connected_clients: list[WebSocket] = []

# Event log
event_log: list[dict] = []


DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dock Chaos — Live Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Courier New', monospace;
            background: #0d1117;
            color: #c9d1d9;
            min-height: 100vh;
            padding: 20px;
        }
        .header {
            text-align: center;
            padding: 20px 0;
            border-bottom: 1px solid #30363d;
            margin-bottom: 20px;
        }
        .header h1 {
            color: #f85149;
            font-size: 28px;
        }
        .header p {
            color: #8b949e;
            margin-top: 5px;
        }
        .status-bar {
            display: flex;
            gap: 20px;
            justify-content: center;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .stat-box {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 15px 25px;
            text-align: center;
            min-width: 140px;
        }
        .stat-box .label {
            color: #8b949e;
            font-size: 12px;
            text-transform: uppercase;
        }
        .stat-box .value {
            font-size: 24px;
            font-weight: bold;
            margin-top: 5px;
        }
        .stat-box .value.green { color: #3fb950; }
        .stat-box .value.red { color: #f85149; }
        .stat-box .value.yellow { color: #d29922; }
        .stat-box .value.blue { color: #58a6ff; }

        .event-feed {
            max-width: 900px;
            margin: 0 auto;
        }
        .event-feed h2 {
            color: #58a6ff;
            margin-bottom: 10px;
            font-size: 16px;
        }
        .event {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 12px 16px;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            animation: slideIn 0.3s ease-out;
        }
        @keyframes slideIn {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .event .left { display: flex; align-items: center; gap: 12px; }
        .event .icon { font-size: 20px; }
        .event .fault-name { color: #d29922; font-weight: bold; }
        .event .target { color: #8b949e; }
        .event .right { text-align: right; }
        .event .recovery-time { font-size: 14px; }
        .event .recovery-time.fast { color: #3fb950; }
        .event .recovery-time.slow { color: #d29922; }
        .event .recovery-time.failed { color: #f85149; }
        .event .timestamp { color: #484f58; font-size: 11px; }

        .connection-status {
            position: fixed;
            bottom: 15px;
            right: 15px;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
        }
        .connection-status.connected {
            background: #0d2818;
            color: #3fb950;
            border: 1px solid #238636;
        }
        .connection-status.disconnected {
            background: #2d1215;
            color: #f85149;
            border: 1px solid #da3633;
        }
        .empty-state {
            text-align: center;
            color: #484f58;
            padding: 60px 20px;
            font-size: 14px;
        }
        .empty-state .big { font-size: 40px; margin-bottom: 10px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔥 Dock Chaos</h1>
        <p>Live Chaos Engineering Dashboard</p>
    </div>

    <div class="status-bar">
        <div class="stat-box">
            <div class="label">Faults Injected</div>
            <div class="value blue" id="total-faults">0</div>
        </div>
        <div class="stat-box">
            <div class="label">Recovered</div>
            <div class="value green" id="recovered">0</div>
        </div>
        <div class="stat-box">
            <div class="label">Failed</div>
            <div class="value red" id="failed">0</div>
        </div>
        <div class="stat-box">
            <div class="label">Avg Recovery</div>
            <div class="value yellow" id="avg-recovery">—</div>
        </div>
    </div>

    <div class="event-feed">
        <h2>Event Feed</h2>
        <div id="events">
            <div class="empty-state">
                <div class="big">⏳</div>
                <p>Waiting for chaos events...</p>
                <p>Run <code>dock-chaos attack --dashboard</code> to start</p>
            </div>
        </div>
    </div>

    <div class="connection-status disconnected" id="conn-status">Disconnected</div>

    <script>
        let totalFaults = 0;
        let recovered = 0;
        let failed = 0;
        let recoveryTimes = [];

        function connect() {
            const ws = new WebSocket(`ws://${window.location.host}/ws`);
            const statusEl = document.getElementById('conn-status');

            ws.onopen = () => {
                statusEl.textContent = 'Connected';
                statusEl.className = 'connection-status connected';
            };

            ws.onclose = () => {
                statusEl.textContent = 'Disconnected';
                statusEl.className = 'connection-status disconnected';
                setTimeout(connect, 2000);
            };

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                handleEvent(data);
            };
        }

        function handleEvent(data) {
            const eventsEl = document.getElementById('events');

            // Remove empty state on first event
            const emptyState = eventsEl.querySelector('.empty-state');
            if (emptyState) emptyState.remove();

            totalFaults++;

            let icon, recoveryClass, recoveryText;

            if (data.type === 'injection') {
                icon = '💥';
                recoveryClass = '';
                recoveryText = 'Injecting...';
            } else if (data.type === 'result') {
                if (data.recovered) {
                    recovered++;
                    icon = '✅';
                    recoveryClass = data.recovery_time_ms < 500 ? 'fast' : 'slow';
                    recoveryText = data.recovery_time_ms + 'ms';
                    recoveryTimes.push(data.recovery_time_ms);
                } else {
                    failed++;
                    icon = '❌';
                    recoveryClass = 'failed';
                    recoveryText = data.error || 'Failed';
                }
            }

            const eventEl = document.createElement('div');
            eventEl.className = 'event';
            eventEl.innerHTML = `
                <div class="left">
                    <span class="icon">${icon}</span>
                    <div>
                        <div class="fault-name">${data.fault || '—'}</div>
                        <div class="target">→ ${data.target || '—'}</div>
                    </div>
                </div>
                <div class="right">
                    <div class="recovery-time ${recoveryClass}">${recoveryText}</div>
                    <div class="timestamp">${new Date().toLocaleTimeString()}</div>
                </div>
            `;

            eventsEl.insertBefore(eventEl, eventsEl.firstChild);

            // Update stats
            document.getElementById('total-faults').textContent = totalFaults;
            document.getElementById('recovered').textContent = recovered;
            document.getElementById('failed').textContent = failed;

            if (recoveryTimes.length > 0) {
                const avg = Math.round(recoveryTimes.reduce((a, b) => a + b, 0) / recoveryTimes.length);
                document.getElementById('avg-recovery').textContent = avg + 'ms';
            }
        }

        connect();
    </script>
</body>
</html>
"""


@dashboard_app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    """Serve the chaos dashboard."""
    return DASHBOARD_HTML


@dashboard_app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for live chaos event streaming."""
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        # Send existing events on connect
        for event in event_log:
            await websocket.send_json(event)
        # Keep connection alive
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_clients.remove(websocket)


async def broadcast_event(event: dict):
    """Send an event to all connected dashboard clients."""
    event_log.append(event)
    disconnected = []
    for client in connected_clients:
        try:
            await client.send_json(event)
        except Exception:
            disconnected.append(client)
    for client in disconnected:
        connected_clients.remove(client)


def run_dashboard_server(host: str = "127.0.0.1", port: int = 8666):
    """Run the dashboard server in a background thread."""
    import uvicorn
    config = uvicorn.Config(dashboard_app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    return server
