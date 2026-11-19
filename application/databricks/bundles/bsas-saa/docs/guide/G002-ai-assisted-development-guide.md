# AI-Assisted Development for DataForge

## Summary

Adopt **GitHub Copilot and Genie Code as complementary AI development tools** for DataForge. Use Copilot for process-oriented development and Genie Code for data-centric development. Use [project instructions](../../AGENTS.md) and [reusable skills](../../.agents/skills) as shared sources of project guidance, minimizing tool-specific configuration and duplicated knowledge.

## 1. Coding Modes

### 1.1 VS Code + GitHub Copilot

Primary environment for general project development, including:

- Project initialization
- Databricks Apps development
- Python module development
- Databricks Asset Bundles and workflow configuration
- Ingestion configuration
- File manipulation
- Standardization process

### 1.2 Databricks Web UI + Genie Code

Preferred for Databricks-native and data-focused development, including:

- Data validation and transformation
- Curation logic
- Data exploration

**Recommendation:** Use Copilot for process-oriented development and Genie Code for data-centric development. Both tools complement each other.

## 2. Common AI Configuration

DataForge should maintain a shared AI configuration that works across both agents.

### 2.1 AGENTS.md - Development Instructions

- Maintain a root `AGENTS.md` for project-wide conventions.
- Use folder-level `AGENTS.md` for component-specific instructions.
- Include architecture, coding standards, security requirements, and development conventions.
- Keep instructions concise and avoid duplicating detailed workflows.

Instruction discovery and folder scope depend on the agent and its version.
Verify that the active tool loads the applicable `AGENTS.md` files; otherwise,
provide them explicitly as context. Registering skills does not establish that
project instructions have also been loaded.

### 2.2 Agent Skills - Reusable Workflows

- Store reusable skills in `.agents/skills`.
- Share the same skills across Copilot and Genie Code.

[GitHub documents](https://docs.github.com/en/copilot/concepts/customizations/agent-skills)
`.agents/skills` as a project skill location. Support varies by Copilot surface
and IDE version, so verify discovery in the installed environment. Sharing a
skill does not guarantee that both tools provide every command or integration
required by its workflow; read the skill prerequisites before using it.

### 2.3 Minimize Tool-Specific Instructions

- Prefer `AGENTS.md` over Copilot-specific instruction files.
- Limit `.github/instructions/*.instructions.md` to cases requiring Copilot-specific path matching.

## 3. Enable DataForge Skills in Genie Code

Genie Code supports registering additional skill directories, allowing DataForge to reuse the skills maintained for GitHub Copilot.

**Configuration steps:**

1. Open **Genie Code** in the Databricks workspace and select **Settings**.
2. In the skills settings, browse to the project's `.agents/skills` folder or
   enter its absolute workspace path starting with `/`.
3. Select **Add folder**.
4. Verify that the registered skills appear and enable the ones you need.

Register the parent `.agents/skills` folder containing individual skill
subfolders, each with a `SKILL.md`; do not register a single skill subfolder.
The project folder must be available in the workspace, for example through a
Databricks Git folder. A local Windows filesystem path is not a workspace path.

These steps follow the [Databricks skill registration documentation](https://docs.databricks.com/gcp/en/genie-code/skills).
Additional folders supplement the default `.assistant/skills` folders.

**Recommendation:** Maintain `.agents/skills` as the single source of truth.
Register it instead of duplicating DataForge skills under `.assistant/skills`.
