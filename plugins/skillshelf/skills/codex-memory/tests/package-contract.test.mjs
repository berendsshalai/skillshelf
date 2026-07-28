import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const skill = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const vendor = resolve(skill, "..", "..", "vendor", "memory");

function portableDigests(buffer) {
  const digests = new Set([createHash("sha256").update(buffer).digest("hex")]);
  if (!buffer.includes(0)) {
    const text = buffer.toString("utf8");
    if (!text.includes("\uFFFD")) {
      const crlf = Buffer.from(text.replace(/\r?\n/g, "\r\n"), "utf8");
      digests.add(createHash("sha256").update(crlf).digest("hex"));
    }
  }
  return digests;
}

test("skill frontmatter and required resources exist", () => {
  const source = readFileSync(join(skill, "SKILL.md"), "utf8");
  assert.match(source, /^---\r?\nname: codex-memory\r?\ndescription: .+\r?\n---/);
  for (const path of [
    "README.md",
    "PROVENANCE.yml",
    "SEMANTIC_CONTRACT.yml",
    "UPSTREAM_DIFF.md",
    "references/privacy.md",
    "references/retrieval.md",
    "references/operations.md",
    "references/architecture.md",
  ]) assert.ok(existsSync(join(skill, path)), path);
});

test("semantic contract preserves progressive retrieval and privacy", () => {
  const contract = readFileSync(join(skill, "SEMANTIC_CONTRACT.yml"), "utf8");
  assert.match(contract, /search_then_filter_then_timeline_then_batch_fetch/);
  assert.match(contract, /redact secrets before storage or import/);
  assert.match(contract, /exclude credentials from backup and export/);
  assert.match(contract, /SQLite keyword or FTS search/);
});

test("vendored snapshot hashes match manifest", () => {
  const lines = readFileSync(join(vendor, "MANIFEST.sha256"), "utf8").trim().split(/\r?\n/);
  assert.equal(lines.length, 27);
  for (const line of lines) {
    const match = /^([a-f0-9]{64})  (.+)$/.exec(line);
    assert.ok(match, line);
    const content = readFileSync(join(vendor, match[2]));
    assert.ok(portableDigests(content).has(match[1]), match[2]);
  }
});

test("upstream licence and notice are present", () => {
  assert.match(readFileSync(join(vendor, "LICENSE"), "utf8"), /Apache License\s+Version 2\.0/);
  assert.match(readFileSync(join(vendor, "NOTICE"), "utf8"), /Claude-Mem[\s\S]*Copyright 2026 Alex Newman/);
});
