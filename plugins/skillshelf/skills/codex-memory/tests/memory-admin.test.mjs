import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  backup,
  doctor,
  exportMemory,
  importMemory,
  migrate,
  recover,
  redactSecrets,
} from "../scripts/memory-admin.mjs";

function fixture() {
  const root = mkdtempSync(join(tmpdir(), "codex-memory-test-"));
  const data = join(root, "data");
  mkdirSync(data);
  writeFileSync(join(data, "claude-mem.db"), Buffer.concat([Buffer.from("SQLite format 3\0", "binary"), Buffer.alloc(100)]));
  writeFileSync(join(data, "settings.json"), '{"CLAUDE_MEM_TELEMETRY":"0"}\n');
  writeFileSync(join(data, "transcript-watch.json"), '{"watches":[]}\n');
  writeFileSync(join(data, ".env"), "ANTHROPIC_API_KEY=must-not-leave\n");
  return { root, data };
}

test("redacts common credentials without changing ordinary text", () => {
  const input = [
    "normal project decision",
    "password=hunter2",
    "Authorization: Bearer abcdefghijklmnopqrstuvwxyz",
    "api_key: " + ["sk", "proj_abcdefghijklmnopqrst"].join("-"),
    "cookie_token=secret-session-value",
    "eyJabcdefghijk.abcdefghijklmnop.abcdefghijklmnop",
  ].join("\n");
  const output = redactSecrets(input);
  assert.match(output, /normal project decision/);
  assert.doesNotMatch(output, /hunter2|abcdefghijklmnopqrstuvwxyz|sk-proj_|secret-session-value|eyJabcdefghijk/);
});

test("backup excludes credentials and records hashes", () => {
  const { root, data } = fixture();
  const result = backup({ "data-dir": data, output: join(root, "backups") });
  const manifest = JSON.parse(readFileSync(join(result.destination, "manifest.json"), "utf8"));
  assert.ok(manifest.files.some((file) => file.path === "claude-mem.db"));
  assert.ok(manifest.files.every((file) => /^[a-f0-9]{64}$/.test(file.sha256)));
  assert.ok(manifest.excluded.includes(".env"));
});

test("export/import verifies integrity and excludes .env", () => {
  const { root, data } = fixture();
  const output = join(root, "export.json");
  exportMemory({ "data-dir": data, output });
  const payload = JSON.parse(readFileSync(output, "utf8"));
  assert.ok(payload.files.every((file) => file.path !== ".env"));
  const restored = join(root, "restored");
  const result = importMemory({ input: output, "data-dir": restored });
  assert.equal(result.files, 3);
  assert.equal(doctor({ "data-dir": restored, "codex-config": join(root, "missing.toml") }).storage.database.state, "valid");
});

test("import rejects tampered payloads and refuses overwrite", () => {
  const { root, data } = fixture();
  const output = join(root, "export.json");
  exportMemory({ "data-dir": data, output });
  assert.throws(() => importMemory({ input: output, "data-dir": data }), /existing file/);
  const payload = JSON.parse(readFileSync(output, "utf8"));
  payload.files[0].data = Buffer.from("tampered").toString("base64");
  const tampered = join(root, "tampered.json");
  writeFileSync(tampered, JSON.stringify(payload));
  assert.throws(() => importMemory({ input: tampered, "data-dir": join(root, "tampered-target") }), /Integrity check failed/);
});

test("migration and forced recovery preserve a safety backup", () => {
  const { root, data } = fixture();
  const migrated = join(root, "migrated");
  const migration = migrate({ from: data, "data-dir": migrated });
  assert.equal(migration.imported, 3);
  const recoveryExport = join(root, "recovery.json");
  exportMemory({ "data-dir": data, output: recoveryExport });
  writeFileSync(join(migrated, "claude-mem.db"), "corrupt");
  const result = recover({ input: recoveryExport, "data-dir": migrated, force: true });
  assert.ok(result.safetyBackup);
  assert.equal(doctor({ "data-dir": migrated, "codex-config": join(root, "missing.toml") }).storage.database.state, "valid");
});
