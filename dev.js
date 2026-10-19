const { execSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { concurrently } = require(path.join(__dirname, 'frontend', 'node_modules', 'concurrently'));

function ensureBunOnPath() {
  const bunExe = 'bun.exe';
  const pathDirs = (process.env.PATH || '').split(path.delimiter).filter(Boolean);
  const hasBun = pathDirs.some((dir) => fs.existsSync(path.join(dir, bunExe)));
  if (hasBun) return;

  const candidates = [
    path.join(os.homedir(), '.bun', 'bin'),
    path.join(process.env.LOCALAPPDATA || '', 'bun', 'bin'),
    path.join(__dirname, 'frontend', 'node_modules', '.bin'),
  ];
  const bunDir = candidates.find((dir) => dir && fs.existsSync(path.join(dir, bunExe)));
  if (!bunDir) {
    console.error('[dev] Could not locate bun.exe. Install Bun or add it to your PATH.');
    process.exit(1);
  }
  process.env.PATH = [bunDir, ...pathDirs].join(path.delimiter);
}

function killPort(port) {
  try {
    execSync(
      `powershell -Command "$(Get-NetTCPConnection -LocalPort ${port} -ErrorAction SilentlyContinue | Where-Object { $_.OwningProcess -gt 0 } | Select-Object -ExpandProperty OwningProcess -Unique) | ForEach-Object { Stop-Process -Id $_ -Force }"`,
      { stdio: 'ignore', timeout: 3000 },
    );
  } catch (_) {}
}

killPort(3001);
killPort(8002);
killPort(8765);

ensureBunOnPath();

const { result } = concurrently(
  [
    {
      command: 'bun run dev',
      name: 'next',
      cwd: path.join(__dirname, 'frontend'),
      prefixColor: 'blue',
    },
    {
      command: '..\\.venv\\Scripts\\python server.py',
      name: 'py',
      cwd: path.join(__dirname, 'backend'),
      prefixColor: 'yellow',
    },
  ],
  { prefix: 'name', killOthersOnFail: true },
);

result.catch(() => process.exit(1));