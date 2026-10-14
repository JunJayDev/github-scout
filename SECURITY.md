# Security

reuse-first downloads source archives from GitHub and reads them. It never executes
downloaded code. Archives are extracted with path-traversal checks, and symbolic links are
skipped.

Your GitHub token is read from `GITHUB_TOKEN`, `GH_TOKEN` or `gh auth token`. It is sent only
to GitHub (the API and its archive download redirect), never written to the registry, and
never included in output. Links you `ingest` from other sites are fetched without it.

Text in other repositories (READMEs, SKILL.md files) is untrusted. The skill tells agents to
treat it as data, not as instructions.

To report a vulnerability, open a private security advisory on the repository. Please do not
file it as a public issue.
