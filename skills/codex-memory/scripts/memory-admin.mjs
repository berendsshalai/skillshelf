#!/usr/bin/env node
import { createHash } from "node:crypto";
import {
  copyFileSync,
  cpSync,
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  renameSync,
  statSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { homedir } from "node:os";
import { basename, dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { spawnSync } from "node:child_process";

export const FORMAT = "skillshelf-codex-memory-export-v1";
export const UPSTREAM_COMMIT = "132b46343e60ecf4057c427736c57b08f7615dfe";
const PORTABLE_FILES = [
  "claude-mem.db",
  "claude-mem.db-wal",
  "claude-mem.db-shm",
  "settings.json",
  "transcript-watch.json",
  "transcript-watch-state.json",
  "telemetry.json",
];
const SECRET_PATTERNS = [
  [/\b(?:sk|sk-proj|sk-ant|ghp|github_pat|phc)_[A-Za-z0-9_-]{12,}\b/gi, "[REDACTED_TOKEN]"],
  [/\bAKIA[0-9A-Z]{16}\b/g, "[REDACTED_AWS_KEY]"],
  [/\bBearer\s+[A-Za-z0-9._~+/-]{12,}=*/gi, "Bearer [REDACTED]"],
  [/\b((?:password|passwd|pwd|api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret))\s*[:=]\s*[^\s,;]+/gi, "$1=[REDACTED]"],
  [/-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/g, "[REDACTED_PRIVATE_KEY]"],
  [/\b(?:eyJ[A-Za-z0-9_-]{10,})\.(?:[A-Za-z0-9_-]{10,})\.(?:[A-Za-z0-9_-]{10,})\b/g, "[REDACTED_JWT]"],
  [/\b((?:session|auth|cookie)[_-]?(?:id|token)?)\s*[:=]\s*[^\s,;]+/gi, "$1=[REDACTED]"],
];

function parseArgs(argv) {
  const [command = "help", ...rest] = argv;
  const options = { _: [] };
  for (let i = 0; i < rest.length; i += 1) {
    const value = rest[i];
    if (!value.startsWith("--")) {
      options._.push(value);
      continue;
    }
    const key = value.slice(2);
    if (key.includes("=")) {
      const split = key.indexOf("=");
      options[key.slice(0, split)] = key.slice(split + 1);
    } else if (rest[i + 1] && !rest[i + 1].startsWith("--")) {
      options[key] = rest[++i];
    } else {
      options[key] = true;
    }
  }
  return { command, options };
}

function expandHome(value) {
  if (!value) return value;
  if (value === "~") return homedir();
  if (value.startsWith("~/") || value.startsWith("~\\")) return join(homedir(), value.slice(2));
  return value;
}

export function resolveDataDir(options = {}) {
  return resolve(expandHome(String(options["data-dir"] || process.env.CLAUDE_MEM_DATA_DIR || join(homedir(), ".claude-mem"))));
}

function assertContained(root, target) {
  const base = resolve(root);
  const candidate = resolve(target);
  if (candidate !== base && !candidate.startsWith(base + sep)) {
    throw new Error(`Refusing path outside ${base}: ${candidate}`);
  }
}

function sha256(buffer) {
  return createHash("sha256").update(buffer).digest("hex");
}

function atomicWrite(path, content) {
  mkdirSync(dirname(path), { recursive: true });
  const temporary = `${path}.tmp-${process.pid}-${Date.now()}`;
  writeFileSync(temporary, content, { mode: 0o600 });
  renameSync(temporary, path);
}

export function redactSecrets(text) {
  let output = String(text);
  for (const [pattern, replacement] of SECRET_PATTERNS) output = output.replace(pattern, replacement);
  return output;
}

function sqliteHeader(path) {
  if (!existsSync(path)) return { state: "missing" };
  const size = statSync(path).size;
  if (size === 0) return { state: "empty", size };
  const header = readFileSync(path).subarray(0, 16).toString("binary");
  return { state: header === "SQLite format 3\u0000" ? "valid" : "invalid", size };
}

function findExecutable(command) {
  const check = spawnSync(process.platform === "win32" ? "where.exe" : "sh", process.platform === "win32" ? [command] : ["-c", `command -v "${command}"`], {
    encoding: "utf8",
    windowsHide: true,
  });
  return check.status === 0 ? check.stdout.trim().split(/\r?\n/)[0] : null;
}

function inspectJson(path) {
  if (!existsSync(path)) return { state: "missing" };
  try {
    JSON.parse(readFileSync(path, "utf8"));
    return { state: "valid" };
  } catch (error) {
    return { state: "invalid", detail: error.message };
  }
}

export function doctor(options = {}) {
  const dataDir = resolveDataDir(options);
  const codexConfig = resolve(expandHome(String(options["codex-config"] || join(homedir(), ".codex", "config.toml"))));
  const configText = existsSync(codexConfig) ? readFileSync(codexConfig, "utf8") : "";
  const result = {
    dataDir,
    codex: {
      executable: findExecutable("codex"),
      config: codexConfig,
      pluginEnabled: /\[plugins\."claude-mem@[^"]+"\][\s\S]*?\benabled\s*=\s*true\b/.test(configText),
      hooksEnabled: /\[features\][\s\S]*?\bhooks\s*=\s*true\b/.test(configText),
    },
    storage: {
      directory: existsSync(dataDir) ? "present" : "missing",
      database: sqliteHeader(join(dataDir, "claude-mem.db")),
      settings: inspectJson(join(dataDir, "settings.json")),
      transcriptWatch: inspectJson(join(dataDir, "transcript-watch.json")),
    },
    privacy: {
      credentialFilePresent: existsSync(join(dataDir, ".env")),
      telemetry: inspectJson(join(dataDir, "telemetry.json")),
      note: "Credential contents are intentionally not read.",
    },
  };
  result.healthy = Boolean(result.codex.executable)
    && result.codex.pluginEnabled
    && result.codex.hooksEnabled
    && ["valid", "missing"].includes(result.storage.database.state)
    && !["invalid"].includes(result.storage.settings.state);
  return result;
}

function timestamp() {
  return new Date().toISOString().replace(/[:.]/g, "-");
}

function collectPortableFiles(dataDir) {
  return PORTABLE_FILES.filter((name) => existsSync(join(dataDir, name)));
}

export function backup(options = {}) {
  const dataDir = resolveDataDir(options);
  if (!existsSync(dataDir)) throw new Error(`Memory data directory does not exist: ${dataDir}`);
  const destinationRoot = resolve(expandHome(String(options.output || join(dataDir, "backups"))));
  const destination = join(destinationRoot, `backup-${timestamp()}`);
  assertContained(destinationRoot, destination);
  mkdirSync(destination, { recursive: true });
  const copied = [];
  for (const name of collectPortableFiles(dataDir)) {
    const source = join(dataDir, name);
    const target = join(destination, name);
    copyFileSync(source, target);
    copied.push({ path: name, bytes: statSync(target).size, sha256: sha256(readFileSync(target)) });
  }
  if (options["include-vector"]) {
    for (const name of ["chroma", "corpora"]) {
      const source = join(dataDir, name);
      if (existsSync(source)) cpSync(source, join(destination, name), { recursive: true, errorOnExist: true });
    }
  }
  const manifest = {
    format: "skillshelf-codex-memory-backup-v1",
    createdAt: new Date().toISOString(),
    sourceDataDir: dataDir,
    upstreamCommit: UPSTREAM_COMMIT,
    excluded: [".env", "worker.pid", "server API-key material"],
    files: copied,
  };
  atomicWrite(join(destination, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);
  return { destination, files: copied };
}

export function exportMemory(options = {}) {
  const dataDir = resolveDataDir(options);
  if (!existsSync(dataDir)) throw new Error(`Memory data directory does not exist: ${dataDir}`);
  const output = resolve(expandHome(String(options.output || join(process.cwd(), `codex-memory-export-${timestamp()}.json`))));
  const files = collectPortableFiles(dataDir).map((name) => {
    const buffer = readFileSync(join(dataDir, name));
    return { path: name, bytes: buffer.length, sha256: sha256(buffer), encoding: "base64", data: buffer.toString("base64") };
  });
  const payload = {
    format: FORMAT,
    createdAt: new Date().toISOString(),
    upstreamCommit: UPSTREAM_COMMIT,
    excluded: [".env", "credentials", "worker/server PID state"],
    files,
  };
  atomicWrite(output, `${JSON.stringify(payload, null, 2)}\n`);
  return { output, files: files.map(({ data, ...metadata }) => metadata) };
}

function readExport(input) {
  const payload = JSON.parse(readFileSync(input, "utf8"));
  if (payload.format !== FORMAT || !Array.isArray(payload.files)) throw new Error(`Unsupported export format: ${payload.format}`);
  for (const file of payload.files) {
    if (!PORTABLE_FILES.includes(file.path)) throw new Error(`Export contains disallowed path: ${file.path}`);
    const buffer = Buffer.from(file.data, file.encoding);
    if (buffer.length !== file.bytes || sha256(buffer) !== file.sha256) throw new Error(`Integrity check failed: ${file.path}`);
  }
  return payload;
}

export function importMemory(options = {}) {
  const input = resolve(expandHome(String(options.input || options._?.[0] || "")));
  if (!input || !existsSync(input)) throw new Error("Import requires --input <export.json>");
  const dataDir = resolveDataDir(options);
  const payload = readExport(input);
  mkdirSync(dataDir, { recursive: true });
  const existing = payload.files.filter((file) => existsSync(join(dataDir, file.path)));
  if (existing.length && !options.force) throw new Error(`Target contains ${existing.length} existing file(s); rerun with --force after taking a backup`);
  let safetyBackup = null;
  if (existing.length) safetyBackup = backup({ ...options, output: options["backup-dir"] || join(dataDir, "backups") });
  for (const file of payload.files) {
    const target = join(dataDir, file.path);
    assertContained(dataDir, target);
    atomicWrite(target, Buffer.from(file.data, file.encoding));
  }
  return { importedFrom: input, dataDir, files: payload.files.length, safetyBackup: safetyBackup?.destination || null };
}

export function migrate(options = {}) {
  const source = resolve(expandHome(String(options.from || "")));
  if (!source || !existsSync(source)) throw new Error("Migration requires --from <legacy-data-dir>");
  const target = resolveDataDir(options);
  if (source === target) throw new Error("Migration source and target are identical");
  const temporaryExport = join(dirname(target), `.codex-memory-migration-${process.pid}.json`);
  const exported = exportMemory({ "data-dir": source, output: temporaryExport });
  try {
    const imported = importMemory({ ...options, input: temporaryExport, "data-dir": target });
    return { source, target, exported: exported.files.length, imported: imported.files, safetyBackup: imported.safetyBackup };
  } finally {
    if (existsSync(temporaryExport)) unlinkSync(temporaryExport);
  }
}

export function recover(options = {}) {
  const dataDir = resolveDataDir(options);
  const current = sqliteHeader(join(dataDir, "claude-mem.db"));
  if (current.state === "valid" && !options.force) throw new Error("Database header is valid; recovery requires --force");
  const input = options.input
    ? resolve(expandHome(String(options.input)))
    : newestExport(resolve(expandHome(String(options["backup-dir"] || join(dataDir, "backups")))));
  if (!input) throw new Error("No recovery export found; provide --input <export.json>");
  return importMemory({ ...options, input, "data-dir": dataDir, force: true });
}

function newestExport(directory) {
  if (!existsSync(directory)) return null;
  const candidates = readdirSync(directory, { withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith(".json"))
    .map((entry) => join(directory, entry.name))
    .filter((path) => {
      try { return JSON.parse(readFileSync(path, "utf8")).format === FORMAT; } catch { return false; }
    })
    .sort((a, b) => statSync(b).mtimeMs - statSync(a).mtimeMs);
  return candidates[0] || null;
}

function printHelp() {
  console.log(`codex-memory administration
Usage: node memory-admin.mjs <command> [options]
Commands:
  doctor [--data-dir DIR] [--json]
  backup [--data-dir DIR] [--output DIR] [--include-vector]
  export [--data-dir DIR] [--output FILE]
  import --input FILE [--data-dir DIR] [--force]
  migrate --from DIR [--data-dir DIR] [--force]
  recover [--input FILE|--backup-dir DIR] [--data-dir DIR] [--force]
  redact [--input FILE] [--output FILE]
Credential files are never included in backup/export.`);
}

function main() {
  const { command, options } = parseArgs(process.argv.slice(2));
  let result;
  if (command === "doctor") result = doctor(options);
  else if (command === "backup") result = backup(options);
  else if (command === "export") result = exportMemory(options);
  else if (command === "import") result = importMemory(options);
  else if (command === "migrate") result = migrate(options);
  else if (command === "recover") result = recover(options);
  else if (command === "redact") {
    const text = options.input ? readFileSync(resolve(expandHome(String(options.input))), "utf8") : readFileSync(0, "utf8");
    const redacted = redactSecrets(text);
    if (options.output) atomicWrite(resolve(expandHome(String(options.output))), redacted);
    else process.stdout.write(redacted);
    return;
  } else {
    printHelp();
    return;
  }
  console.log(JSON.stringify(result, null, 2));
  if (command === "doctor" && !result.healthy) process.exitCode = 1;
}

const invoked = process.argv[1] && resolve(process.argv[1]) === resolve(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"));
if (invoked) main();
