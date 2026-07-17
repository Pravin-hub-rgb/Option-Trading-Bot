const { execSync } = require('child_process');
const path = require('path');
const { concurrently } = require(path.join(__dirname, 'frontend', 'node_modules', 'concurrently'));

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

const { result } = concurrently(
  [
    {
      command: 'bun run dev',
      name: 'next',
      cwd: 'frontend',
      prefixColor: 'blue',
    },
    {
      command: '..\\.venv\\Scripts\\python server.py',
      name: 'py',
      cwd: 'backend',
      prefixColor: 'yellow',
    },
  ],
  { prefix: 'name', killOthersOnFail: true },
);

result.catch(() => process.exit(1));