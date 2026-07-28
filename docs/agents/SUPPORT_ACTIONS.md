# Support Actions

## Purpose

Support commands expose documentation and allow a user to star the repository through an explicit, verified action.

## Architecture

`skillshelf support` reads the repository support guide locally. `skillshelf star --yes` uses authenticated GitHub CLI calls to check, create, and verify a star. Neither command changes the six runtime definitions or invokes the eight opt-in maintenance definitions.

## Configuration

Local support output needs no credential. Starring requires installed and authenticated `gh`, network access, and explicit user consent.

## Commands

```powershell
skillshelf support
skillshelf star --yes
gh auth status
```

## Examples

Run `support` offline for guidance. Run `star --yes` only after the user asks; an existing star returns an idempotent confirmation.

## Failure Modes

Without `--yes`, starring fails closed. Missing `gh`, failed authentication, network/API errors, or failed verification return an error.

## Security Boundaries

A star changes the authenticated GitHub account and is never implied by normal agent use. Runtime specialists, maintenance definitions, evaluations, and support text cannot grant that consent. Runtime-recorded command results are evidence; any model description of external account state is interpretation.

## Tests

Offline tests can mock command behavior and confirmation checks. A real star is credentialled external proof and must not run during ordinary tests.

## Recovery

Authenticate `gh`, verify the intended account, and retry only with renewed consent. Remove an unwanted star through GitHub separately.

## Known Limitations

Support actions cover one repository and GitHub CLI. Offline proof cannot establish account access or external API state.
