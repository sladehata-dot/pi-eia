/**
 * pi-save-server.js — Pi Energy Quote Save Server
 * ─────────────────────────────────────────────────
 * Runs a tiny local HTTP server that writes quote files directly to
 * the filesystem — no browser directory picker needed.
 *
 * SETUP (one-time):
 *   1. Install Node.js from https://nodejs.org  (free, ~30MB)
 *   2. Double-click "Start Save Server.bat" (or run: node pi-save-server.js)
 *   3. The tool auto-detects the server and uses it instead of the picker
 *
 * The server listens on http://localhost:3737 — only accessible from
 * this machine (not exposed to the network).
 *
 * USAGE:
 *   node pi-save-server.js [customers-folder-path]
 *
 * If no path is provided it defaults to a "Customers" folder next to
 * this script.
 */

const http = require('http');
const fs   = require('fs');
const path = require('path');

const PORT           = 3737;
const DEFAULT_ROOT   = path.join(__dirname, 'Customers');
const customersRoot  = process.argv[2] ? path.resolve(process.argv[2]) : DEFAULT_ROOT;

// Ensure the Customers root exists
if (!fs.existsSync(customersRoot)) {
  fs.mkdirSync(customersRoot, { recursive: true });
  console.log(`Created Customers folder: ${customersRoot}`);
}

const server = http.createServer((req, res) => {
  // CORS — allow only the Pi Energy tool (file:// and localhost)
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }

  // ── GET /ping — health check (tool uses this to detect server) ──
  if (req.method === 'GET' && req.url === '/ping') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ ok: true, root: customersRoot }));
    return;
  }

  // ── POST /save — write files ──
  if (req.method === 'POST' && req.url === '/save') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      try {
        const { customerName, files } = JSON.parse(body);
        // files = [{ name: 'Pi Quote.html', content: '...' }, { name: 'Customer Copy.html', content: '...' }]

        if (!customerName || typeof customerName !== 'string') throw new Error('customerName required');

        // Sanitise folder name (strip characters unsafe in Windows paths)
        const safeName = customerName.replace(/[<>:"/\\|?*]/g, '_').trim() || 'Unknown';
        const dir      = path.join(customersRoot, safeName);

        if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });

        const saved = [];
        for (const f of (files || [])) {
          const safefile = path.basename(f.name);           // prevent path traversal
          const fullPath = path.join(dir, safefile);
          fs.writeFileSync(fullPath, f.content, 'utf8');
          saved.push(fullPath);
          console.log(`  Saved: ${fullPath}`);
        }

        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: true, saved }));
      } catch (e) {
        console.error('Save error:', e.message);
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: false, error: e.message }));
      }
    });
    return;
  }

  res.writeHead(404); res.end();
});

server.listen(PORT, '127.0.0.1', () => {
  console.log('');
  console.log('  ╔════════════════════════════════════════════╗');
  console.log('  ║   Pi Energy — Quote Save Server  ✅ Ready  ║');
  console.log('  ╚════════════════════════════════════════════╝');
  console.log('');
  console.log(`  Listening on  http://127.0.0.1:${PORT}`);
  console.log(`  Saving to     ${customersRoot}`);
  console.log('');
  console.log('  Open pi_energy_config_tool.html and save quotes —');
  console.log('  files will appear in the Customers folder instantly.');
  console.log('  Press Ctrl+C to stop.');
  console.log('');
});
