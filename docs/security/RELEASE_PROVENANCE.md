# Release Provenance

## Purpose

SkillShelf release metadata identifies shipped artifacts, dependency locks, source state and
checksums so a recipient can verify what was built.

## Architecture

`scripts/build-release.py` validates the repository, builds plugin/runtime/source/Python artifacts,
creates a complete SPDX 2.3 SBOM, emits an in-toto SLSA provenance statement, and writes SHA-256
checksums. `validate-release.py` verifies archive safety, versions, dependency relationships,
subjects and every digest.

## Configuration

Build from a reviewed commit with `sdk/python/requirements.lock`, its checksum,
`upstream-lock.json` and `vendor-manifest.json` present. Signing credentials are intentionally not
required for local builds.

## Commands

Run `python scripts/build-release.py`, then
`python scripts/validate-release.py dist/skillshelf-VERSION --version VERSION`.

## Example

The provenance records the 40-character Git commit, dirty-state flag, Python version and SHA-256
of each dependency lock; every artifact except `SHA256SUMS` is checksummed.

## Security boundaries

Archive paths are validated against traversal and unsupported member types. Symlinks, repository
state, work files, local credentials and upstream submodule contents are excluded from source
archives.

## Failure modes

Missing runtime members, inconsistent versions, incomplete SBOM relationships, invalid provenance
subjects and checksum drift fail validation.

## Tests

Release-artifact tests cover complete releases, missing artifacts, unsafe/incomplete archives,
checksum mismatch, version mismatch, SBOM completeness and provenance integrity.

## Recovery

Discard the failed output directory, correct the source/lock inconsistency, rebuild and revalidate.
Never edit checksums or provenance after artifact creation.

## Known limitations

Local provenance is unsigned. CI/release signing and transparency-log publication require an
explicitly configured protected release environment.
