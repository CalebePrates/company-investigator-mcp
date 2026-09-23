"use strict";

// Launcher fino: nao contem nenhuma logica do MCP. Localiza o `uvx` e executa o
// pacote Python `company-investigator-mcp` fixado na MESMA versao deste pacote npm,
// herdando stdin/stdout/stderr (o protocolo MCP trafega por stdio) e o ambiente.
// Diagnosticos do launcher vao sempre para o stderr - o stdout pertence ao protocolo.

const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawn } = require("node:child_process");

const PYTHON_PACKAGE = "company-investigator-mcp";

const UV_INSTALL_HELP = [
  "company-investigator-mcp: nao encontrei o `uvx` (parte do uv), necessario para",
  "executar o servidor Python. Instale o uv e tente de novo:",
  "",
  "  macOS/Linux:  curl -LsSf https://astral.sh/uv/install.sh | sh",
  "  Windows:      powershell -ExecutionPolicy ByPass -c \"irm https://astral.sh/uv/install.ps1 | iex\"",
  "  Alternativa:  pip install uv   (ou brew install uv)",
  "",
  "Documentacao: https://docs.astral.sh/uv/getting-started/installation/",
  "Se o uv ja estiver instalado fora do PATH, aponte UVX_PATH para o executavel `uvx`.",
].join("\n");

function executableNames(base, platform) {
  if (platform !== "win32") return [base];
  return [`${base}.exe`, `${base}.cmd`, `${base}.bat`, base];
}

// Clientes MCP graficos (ex.: apps desktop) costumam lancar processos com um PATH
// minimo, sem os diretorios onde o instalador do uv coloca os binarios - por isso,
// alem do PATH, olhamos os locais padrao de instalacao.
function pathFor(platform) {
  return platform === "win32" ? path.win32 : path.posix;
}

function candidateDirectories(env, platform) {
  const fromPath = (env.PATH || env.Path || "").split(pathFor(platform).delimiter).filter(Boolean);
  const home = env.HOME || env.USERPROFILE || os.homedir();
  const defaults = [
    env.UV_INSTALL_DIR,
    env.XDG_BIN_HOME,
    home && pathFor(platform).join(home, ".local", "bin"),
    home && pathFor(platform).join(home, ".cargo", "bin"),
  ];
  if (platform !== "win32") defaults.push("/opt/homebrew/bin", "/usr/local/bin");
  return [...fromPath, ...defaults.filter(Boolean)];
}

function isExecutableFile(filePath) {
  try {
    return fs.statSync(filePath).isFile();
  } catch {
    return false;
  }
}

function findExecutable(base, env, platform, exists) {
  for (const directory of candidateDirectories(env, platform)) {
    for (const name of executableNames(base, platform)) {
      const candidate = pathFor(platform).join(directory, name);
      if (exists(candidate)) return candidate;
    }
  }
  return null;
}

// Devolve { command, prefixArgs } para rodar uma ferramenta via uv, ou null.
// Preferencia: UVX_PATH explicito > `uvx` > `uv tool run` (equivalente ao uvx).
function resolveUvx({
  env = process.env,
  platform = process.platform,
  exists = isExecutableFile,
} = {}) {
  if (env.UVX_PATH) {
    return exists(env.UVX_PATH) ? { command: env.UVX_PATH, prefixArgs: [] } : null;
  }
  const uvx = findExecutable("uvx", env, platform, exists);
  if (uvx) return { command: uvx, prefixArgs: [] };
  const uv = findExecutable("uv", env, platform, exists);
  if (uv) return { command: uv, prefixArgs: ["tool", "run"] };
  return null;
}

// Versao fixada: o launcher npm X.Y.Z sempre executa o pacote PyPI X.Y.Z (nunca
// @latest). `uvx pacote@versao` roda o comando de mesmo nome do pacote.
function buildArgs(version, userArgs) {
  return [`${PYTHON_PACKAGE}@${version}`, ...userArgs];
}

function exitCodeFor(code, signal) {
  if (typeof code === "number") return code;
  const signalNumber = signal ? os.constants.signals[signal] : undefined;
  return signalNumber ? 128 + signalNumber : 1;
}

function run({
  version,
  argv = process.argv.slice(2),
  env = process.env,
  platform = process.platform,
  stderr = process.stderr,
  exit = process.exit,
} = {}) {
  const uv = resolveUvx({ env, platform });
  if (!uv) {
    stderr.write(`${UV_INSTALL_HELP}\n`);
    exit(127);
    return;
  }

  const child = spawn(uv.command, [...uv.prefixArgs, ...buildArgs(version, argv)], {
    stdio: "inherit",
    env,
    windowsHide: true,
    // .cmd/.bat so executam via shell no Windows; um .exe nunca precisa dele.
    shell: platform === "win32" && /\.(cmd|bat)$/i.test(uv.command),
  });

  const forward = (signal) => {
    if (child.exitCode === null && child.signalCode === null) child.kill(signal);
  };
  for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) {
    process.on(signal, () => forward(signal));
  }

  child.on("error", (error) => {
    stderr.write(`company-investigator-mcp: falha ao iniciar ${uv.command}: ${error.message}\n`);
    exit(127);
  });
  child.on("exit", (code, signal) => exit(exitCodeFor(code, signal)));
}

module.exports = {
  PYTHON_PACKAGE,
  UV_INSTALL_HELP,
  buildArgs,
  exitCodeFor,
  resolveUvx,
  run,
};
