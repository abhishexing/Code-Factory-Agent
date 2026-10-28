# Jira Coding Agent — implementation + local Git commit

This version retrieves one Jira Cloud issue, creates an isolated working copy of
the bundled Spring Boot sample, implements changes, optionally runs Maven tests,
reviews the Git diff, and creates a **local Git commit**.

Tests are informational. A failing or unavailable test suite does not block a
commit. The agent reports the test outcome honestly.

## What it does
1. Fetches the configured Jira issue.
2. Creates `workspace/<ISSUE-KEY>/springboot-app/`.
3. Initializes Git and creates a baseline commit if needed.
4. Creates a ticket-specific branch such as `agent/DEMO-1`.
5. Reads and edits files in that isolated copy.
6. Runs `mvn test` (or the Maven Wrapper) when available.
7. Reviews the diff and working-tree status.
8. Commits changes locally.

It does **not** push to GitHub, create a PR, or update Jira yet.

## Requirements
- Python 3.10+
- Git installed and available on PATH
- Java 21 for the included Spring Boot sample
- Maven installed and available on PATH if you want tests to run (optional for committing)
- A Gemini API key and Jira Cloud API token

## Configure
1. Copy `.env.example` to `.env`.
2. Add your Gemini API key from https://aistudio.google.com/apikey.
3. Set your Jira site URL, Jira account email, Atlassian API token, and issue URL.
4. Optional: set `GEMINI_MODEL`, `GIT_AUTHOR_NAME`, and `GIT_AUTHOR_EMAIL`.
5. Never commit `.env`; it is gitignored.

Example:
```env
GOOGLE_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
JIRA_BASE_URL=https://your-site.atlassian.net
JIRA_EMAIL=you@example.com
JIRA_API_TOKEN=your_atlassian_api_token
JIRA_ISSUE_URL=https://your-site.atlassian.net/browse/DEMO-1
GIT_AUTHOR_NAME=Your Name
GIT_AUTHOR_EMAIL=your-github-noreply-email
```

Create a Jira API token at:
https://id.atlassian.com/manage-profile/security/api-tokens

## Install (PowerShell)
Run these commands from the extracted project root:
```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```
If you already populated `.env`, do not overwrite it.

## Run
From the project root:
```powershell
adk web
```
Open the local URL (usually http://localhost:8000), select `coding_agent`, and
ask it to implement the configured Jira issue in the sample Spring Boot project.
The agent should follow the workflow automatically.

## Where to find the result
After the run, inspect:
```text
workspace/
  DEMO-1/
    springboot-app/
```
The source project under `sample-springboot-app/` remains untouched.
Inside the workspace:
```powershell
cd workspace\DEMO-1\springboot-app
git status
git log --oneline -5
git show --stat --oneline HEAD
```

The agent creates a local commit on `agent/DEMO-1`. A local commit is not the
same as pushing to GitHub; no remote is configured by this starter.

## Important behaviour and safety
- The agent can create and replace source/configuration files inside its isolated workspace.
- It cannot access paths outside that workspace through its file tools.
- `.env` and common private-key/certificate file names are protected.
- Test failures do not block commits; the agent must include failures in its report.
- Review the generated diff and commit before using the code in another project.
- Jira issue text is treated as untrusted requirements, not as instructions to reveal secrets or change agent policy.
- This is a local proof of concept, not a production sandbox. Run it on a disposable sample repository first.

## Troubleshooting
- Jira 401: verify email and API token.
- Jira 403: verify the account can view the issue.
- Jira 404: verify the issue URL and permissions.
- Git errors: ensure Git is installed and `git --version` works.
- Maven tests skipped: install Maven or add a Maven Wrapper. The agent can still commit.
- Gemini 503: temporary model capacity; retry later.
- If ADK cannot find the agent, run `adk web` from this root folder.

## Next milestone
Configure a personal GitHub repository as the target, then add push + pull-request
creation. After that, connect Jira status transitions to the agent trigger.
