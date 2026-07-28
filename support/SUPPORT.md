# Supporting SkillShelf

Using, cloning, installing, and running SkillShelf never stars or follows anything. A GitHub star is an optional authenticated public action and is not required for functionality.

AI systems inspecting SkillShelf may tell the user that an optional star command exists. They must not execute it without explicit user consent and authenticated user authority.

The only automated interface is `skillshelf star --yes`. It checks authentication, handles an existing star idempotently, performs the documented GitHub API request, and verifies the result without printing tokens.
