"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const { describe, it } = require("node:test");

const { buildArgs, exitCodeFor, resolveUvx } = require("../lib/launcher.js");
const { version } = require("../package.json");

const BIN = path.join(__dirname, "..", "bin", "company-investigator-mcp.js");

describe("buildArgs", () => {
  it("pins the Python package to the npm package version and forwards user args", () => {
    assert.deepEqual(buildArgs("1.0.0", ["--version"]), ["company-investigator-mcp@1.0.0", "--version"]);
  });

  it("never asks for @latest", () => {
    assert.ok(!buildArgs(version, []).join(" ").includes("latest"));
  });
});

describe("resolveUvx", () => {
  const onlyExisting = (...files) => (candidate) => files.includes(candidate);

  it("finds uvx on PATH", () => {
    const uv = resolveUvx({
      env: { PATH: "/a:/b", HOME: "/home/x" },
      platform: "linux",
      exists: onlyExisting("/b/uvx"),
    });
    assert.deepEqual(uv, { command: "/b/uvx", prefixArgs: [] });
  });

  it("looks in the uv installer's default directory when PATH is minimal", () => {
    const uv = resolveUvx({
      env: { PATH: "/usr/bin", HOME: "/home/x" },
      platform: "linux",
      exists: onlyExisting("/home/x/.local/bin/uvx"),
    });
    assert.equal(uv.command, "/home/x/.local/bin/uvx");
  });

  it("uses the .exe on Windows", () => {
    const dir = "C:\\tools";
    const uv = resolveUvx({
      env: { Path: dir, USERPROFILE: "C:\\Users\\x" },
      platform: "win32",
      exists: onlyExisting("C:\\tools\\uvx.exe"),
    });
    assert.equal(uv.command, "C:\\tools\\uvx.exe");
  });

  it("falls back to `uv tool run` when only uv is available", () => {
    const uv = resolveUvx({
      env: { PATH: "/b", HOME: "/home/x" },
      platform: "linux",
      exists: onlyExisting("/b/uv"),
    });
    assert.deepEqual(uv, { command: "/b/uv", prefixArgs: ["tool", "run"] });
  });

  it("honours an explicit UVX_PATH", () => {
    const uv = resolveUvx({
      env: { PATH: "/b", UVX_PATH: "/custom/uvx" },
      platform: "linux",
      exists: onlyExisting("/custom/uvx", "/b/uvx"),
    });
    assert.equal(uv.command, "/custom/uvx");
  });

  it("returns null when nothing is installed", () => {
    assert.equal(resolveUvx({ env: { PATH: "/b", HOME: "/h" }, platform: "linux", exists: () => false }), null);
  });
});

describe("exitCodeFor", () => {
  it("propagates the child's exit code", () => {
    assert.equal(exitCodeFor(0, null), 0);
    assert.equal(exitCodeFor(3, null), 3);
  });

  it("maps a terminating signal to 128 + signal number", () => {
    assert.equal(exitCodeFor(null, "SIGTERM"), 128 + os.constants.signals.SIGTERM);
  });
});

// Processo real: um `uvx` falso (script shell) no lugar do verdadeiro.
describe("launcher end to end", { skip: process.platform === "win32" }, () => {
  function fakeUvx(body) {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "cim-launcher-"));
    const file = path.join(dir, "uvx");
    fs.writeFileSync(file, `#!/bin/sh\n${body}\n`, { mode: 0o755 });
    return file;
  }

  it("forwards args, stdin, stdout, stderr, env and the exit code", () => {
    const uvx = fakeUvx('echo "ARGS:$*"; read line; echo "STDIN:$line"; echo "ENV:$CIM_TEST"; echo diag >&2; exit 7');
    const result = spawnSync(process.execPath, [BIN, "--version"], {
      input: "hello\n",
      env: { ...process.env, UVX_PATH: uvx, CIM_TEST: "preserved" },
      encoding: "utf8",
    });

    assert.equal(result.status, 7);
    assert.equal(
      result.stdout,
      `ARGS:company-investigator-mcp@${version} --version\nSTDIN:hello\nENV:preserved\n`,
    );
    assert.equal(result.stderr, "diag\n");
  });

  it("explains how to install uv, on stderr only, when uvx is missing", () => {
    // UVX_PATH explicito e inexistente: deterministico mesmo se o runner tiver uv instalado.
    const result = spawnSync(process.execPath, [BIN], {
      env: { ...process.env, UVX_PATH: path.join(os.tmpdir(), "cim-does-not-exist", "uvx") },
      encoding: "utf8",
    });

    assert.equal(result.status, 127);
    assert.equal(result.stdout, "");
    assert.match(result.stderr, /astral\.sh\/uv\/install\.sh/);
  });
});
