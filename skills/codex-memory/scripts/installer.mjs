#!/usr/bin/env node
import { homedir } from "node:os";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const VERSION = "13.12.4";
const mode = process.argv[2] || "help";
const execute = process.argv.includes("--execute");
const codexConfig = join(homedir(), ".codex", "config.toml");

function backupConfig() {
  if (!existsSync(codexConfig)) return null;
  const destination = `${codexConfig}.skillshelf-backup-${new Date().toISOString().replace(/[:.]/g, "-")}`;
  writeFileSync(destination, readFileSync(codexConfig));
  return destination;
}

function run(args) {
  const command = process.platform === "win32" ? "npx.cmd" : "npx";
  const result = spawnSync(command, args, { stdio: "inherit", windowsHide: true, shell: false });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}

if (!["install", "uninstall"].includes(mode)) {
  console.log("Usage: node installer.mjs <install|uninstall> --execute");
  process.exit(0);
}

const npxArgs = ["--yes", `claude-mem@${VERSION}`, mode, "--ide", "codex-cli"];
if (!execute) {
  console.log(JSON.stringify({ dryRun: true, command: "npx", args: npxArgs, codexConfig }, null, 2));
  process.exit(0);
}

mkdirSync(join(homedir(), ".codex"), { recursive: true });
const backup = backupConfig();
console.log(`Codex configuration backup: ${backup || "not needed"}`);
run(npxArgs);
