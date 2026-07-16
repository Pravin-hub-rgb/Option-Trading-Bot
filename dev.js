const { spawn } = require("child_process");
const path = require("path");

const backend = spawn("python", ["main.py"], {
  cwd: __dirname,
  stdio: "inherit",
  shell: true,
});

const frontendDir = path.join(__dirname, "frontend");
const frontend = spawn("npm", ["run", "dev"], {
  cwd: frontendDir,
  stdio: "inherit",
  shell: true,
});

process.on("SIGINT", () => {
  backend.kill();
  frontend.kill();
  process.exit();
});
