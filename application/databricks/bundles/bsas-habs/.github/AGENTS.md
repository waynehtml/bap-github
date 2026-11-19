# GitHub Copilot Customization Instructions

Keep `../docs/guide/G002-github-copilot-guide.md` synchronized with the GitHub
Copilot customizations in this directory.

- When `copilot-instructions.md` or a file under `skills/`, `prompts/`, or
  `instructions/` is added, updated, renamed, or removed, make the corresponding
  change to the guide.
- Give every repository instruction, skill, prompt, and path-specific
  instruction its own guide section with `Function` and `Usage` subsections.
- Document automatic scope or matching rules for instructions.
- Document invocation, required inputs, and expected results for skills and
  prompts when applicable.
- Keep the guide concise and user-facing. Link to the source customization
  instead of duplicating its complete implementation instructions.
- Use `conf/oeds/config/<area>` as the canonical project-configuration layout
  and `oeds.config.<area>` as its import namespace in every customization.
- Do not finish a customization change while the guide is missing or
  inconsistent with the source.
