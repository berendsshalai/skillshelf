# OpenAPI Import

## Purpose

OpenAPI import creates an inactive, reviewable SkillShelf connector manifest from a local or
explicitly authorised specification.

## Architecture

The importer parses OpenAPI 3 JSON or YAML, resolves local references, selects operations, converts
parameters and security references, and writes a draft through the connector registry. Import
never activates credentials or performs an API operation.

## Configuration

Pass a local specification path and connector ID. Remote specifications require the network policy
to permit their HTTPS origin. Supply secrets later by environment-variable reference.

## Commands

Use `skillshelf connector import-openapi SPEC --id NAME --json`, then
`skillshelf connector inspect NAME`, review the draft, and run `connector test`.

## Example

Importing a stock API with `GET /inventory` produces a read operation with explicit query
parameters and a disabled sync checkpoint until review.

## Security boundaries

External `$ref` targets, executable code generation, inline secrets and non-loopback HTTP URLs are
rejected. Imported write operations remain inactive and approval-required.

## Failure modes

Unsupported OpenAPI versions, ambiguous servers, recursive references and operations without an
identifier fail with source locations.

## Tests

Importer tests cover JSON/YAML, parameters, local references, security schemes, unsafe remote
references, duplicate operation IDs and deterministic output.

## Recovery

Fix the source schema or specify the intended server and repeat import under a new ID. Existing
reviewed connectors are never overwritten.

## Known limitations

Complex callbacks and arbitrary schema-to-domain mapping require manual review. The importer
creates configuration, not a generated provider SDK.
