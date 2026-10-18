# Security

The command line downloads source archives from GitHub and reads them. It never executes
downloaded code. Archives are extracted with path-traversal checks, and symbolic links are
skipped.

The dig stage is different: it asks the agent to try the best two or three repositories, which
means installing and running their code on your machine. The skill tells the agent to do that
in a throwaway directory or a container, outside your project, with no tokens or keys in the
environment, and to read install scripts and hooks first. Watch what it runs, or run the trials
yourself.

Your GitHub token is read from `GITHUB_TOKEN`, `GH_TOKEN` or `gh auth token`. It is sent only
to GitHub (the API and its archive download redirect), never written to the registry, and
never included in output. Links you add from other sites (`scan --add`) are fetched without it.

Text in other repositories (READMEs, SKILL.md files) is untrusted. The skill tells agents to
treat it as data, not as instructions.

To report a vulnerability, open a private security advisory on the repository. Please do not
file it as a public issue.
