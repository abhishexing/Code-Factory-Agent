import os
import re
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_REPO = (ROOT / "sample-springboot-app").resolve()
WORKSPACE_ROOT = (ROOT / "workspace").resolve()
EXCLUDED = {".git", ".idea", ".vscode", "target", ".mvn", "__pycache__"}
PROTECTED_NAMES = {".env", ".env.local", ".env.production", "id_rsa", "id_ed25519"}
MAX_FILE_BYTES = 300_000
COMMAND_TIMEOUT_SECONDS = 240
ISSUE_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]+-\d+$")


def _repo_for(issue_key: str) -> Path:
    if not ISSUE_KEY_RE.fullmatch(issue_key or ""):
        raise ValueError("Invalid Jira issue key.")
    repo = (WORKSPACE_ROOT / issue_key / "springboot-app").resolve()
    try:
        repo.relative_to(WORKSPACE_ROOT)
    except ValueError:
        raise ValueError("Workspace path is outside the permitted root.")
    return repo


def _safe_file(repo: Path, relative_path: str, for_write: bool = False) -> Path:
    if not relative_path or Path(relative_path).is_absolute():
        raise ValueError("Provide a relative project file path.")
    candidate = (repo / relative_path).resolve()
    try:
        candidate.relative_to(repo)
    except ValueError:
        raise ValueError("Path is outside the ticket workspace.")
    parts = candidate.relative_to(repo).parts
    if any(part in EXCLUDED or part in PROTECTED_NAMES for part in parts):
        raise ValueError("This path is protected and cannot be accessed.")
    if candidate.name.lower().startswith(".env"):
        raise ValueError("Environment files are protected.")
    if for_write and candidate.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}:
        raise ValueError("Key and certificate files cannot be written.")
    return candidate


def _git(repo: Path, *args: str, timeout: int = 45) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True,
        timeout=timeout, check=False
    )


def initialize_workspace(issue_key: str) -> dict:
    """Create an isolated working copy for a Jira issue, initialize Git, and create its feature branch."""
    try:
        repo = _repo_for(issue_key)
        if not SOURCE_REPO.is_dir():
            return {"error": "Bundled sample Spring Boot project was not found."}
        if not repo.exists():
            repo.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(
                SOURCE_REPO, repo,
                ignore=shutil.ignore_patterns(".git", "target", ".idea", ".vscode", "__pycache__")
            )
        if not (repo / ".git").exists():
            init = _git(repo, "init")
            if init.returncode:
                return {"error": "Git initialization failed: " + init.stderr[-3000:]}
            # Configure a predictable local identity; environment variables can override it.
            name = os.getenv("GIT_AUTHOR_NAME", "Jira Coding Agent")
            email = os.getenv("GIT_AUTHOR_EMAIL", "jira-coding-agent@users.noreply.github.com")
            for key, value in (("user.name", name), ("user.email", email)):
                configured = _git(repo, "config", key, value)
                if configured.returncode:
                    return {"error": "Could not configure local Git identity: " + configured.stderr[-1000:]}
            add = _git(repo, "add", "-A")
            if add.returncode:
                return {"error": "Could not stage baseline files: " + add.stderr[-2000:]}
            baseline = _git(repo, "commit", "-m", "chore: add sample Spring Boot baseline")
            if baseline.returncode:
                return {"error": "Could not create baseline commit: " + baseline.stderr[-3000:]}
        # A ticket-specific branch is created from the current default branch.
        branch = "agent/" + issue_key
        current = _git(repo, "branch", "--show-current")
        if current.returncode:
            return {"error": "Could not inspect Git branch: " + current.stderr[-1000:]}
        if current.stdout.strip() != branch:
            checkout = _git(repo, "checkout", "-B", branch)
            if checkout.returncode:
                return {"error": "Could not create feature branch: " + checkout.stderr[-2000:]}
        head = _git(repo, "rev-parse", "--short", "HEAD")
        return {
            "workspace": str(repo.relative_to(ROOT)),
            "issue_key": issue_key,
            "branch": branch,
            "baseline_commit": head.stdout.strip() if head.returncode == 0 else None,
            "message": "Isolated workspace is ready. Make all changes in this workspace, not the original sample project."
        }
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        return {"error": str(exc)}


def list_project_files(issue_key: str, directory: str = ".") -> dict:
    """List files and directories in the isolated Spring Boot workspace for this Jira issue."""
    try:
        repo = _repo_for(issue_key)
        path = _safe_file(repo, directory)
        if not path.is_dir():
            return {"error": f"Directory not found: {directory}"}
        entries = []
        for item in sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
            if item.name.startswith(".") or item.name in EXCLUDED or item.name.lower().startswith(".env"):
                continue
            entries.append({
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
                "path": item.relative_to(repo).as_posix()
            })
        return {"directory": directory, "entries": entries}
    except (ValueError, OSError) as exc:
        return {"error": str(exc)}


def read_project_file(issue_key: str, file_path: str) -> dict:
    """Read a UTF-8 source or configuration file from this issue's isolated workspace."""
    try:
        repo = _repo_for(issue_key)
        path = _safe_file(repo, file_path)
        if not path.is_file():
            return {"error": f"File not found: {file_path}"}
        if path.stat().st_size > MAX_FILE_BYTES:
            return {"error": "File exceeds the 300 KB inspection limit."}
        return {"path": file_path, "content": path.read_text(encoding="utf-8")}
    except (ValueError, OSError, UnicodeDecodeError) as exc:
        return {"error": str(exc)}


def write_project_file(issue_key: str, file_path: str, content: str) -> dict:
    """Create or replace a UTF-8 text file inside this Jira issue's isolated project workspace."""
    try:
        repo = _repo_for(issue_key)
        path = _safe_file(repo, file_path, for_write=True)
        if not repo.is_dir():
            return {"error": "Workspace is not initialized. Call initialize_workspace first."}
        if len(content.encode("utf-8")) > MAX_FILE_BYTES:
            return {"error": "Refusing to write a file larger than 300 KB."}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        return {"success": True, "path": file_path, "bytes_written": len(content.encode("utf-8"))}
    except (ValueError, OSError, UnicodeEncodeError) as exc:
        return {"error": str(exc)}


def run_project_tests(issue_key: str) -> dict:
    """Run the project's Maven test suite using the trusted local Maven executable or wrapper; this is diagnostic, not a commit gate."""
    try:
        repo = _repo_for(issue_key)
        if not repo.is_dir():
            return {"error": "Workspace is not initialized."}
        if os.name == "nt":
            wrapper = repo / "mvnw.cmd"
            mvn = shutil.which("mvn.cmd") or shutil.which("mvn")
            if wrapper.exists():
                command = ["cmd.exe", "/d", "/s", "/c", f'"{wrapper}" -B test']
            elif mvn:
                command = ["cmd.exe", "/d", "/s", "/c", f'"{mvn}" -B test']
            else:
                return {"error": "Maven was not found. Install Maven or add the Maven Wrapper; no tests were run."}
        else:
            wrapper = repo / "mvnw"
            mvn = shutil.which("mvn")
            if wrapper.exists():
                wrapper.chmod(wrapper.stat().st_mode | 0o111)
                command = [str(wrapper), "-B", "test"]
            elif mvn:
                command = [mvn, "-B", "test"]
            else:
                return {"error": "Maven was not found. Install Maven or add the Maven Wrapper; no tests were run."}
        result = subprocess.run(
            command, cwd=str(repo), capture_output=True, text=True,
            timeout=COMMAND_TIMEOUT_SECONDS, check=False
        )
        output = (result.stdout or "") + "\n" + (result.stderr or "")
        return {
            "tests_passed": result.returncode == 0,
            "exit_code": result.returncode,
            "output_tail": output[-12000:],
            "note": "Test result is informational. A failure does not block commit."
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Test command timed out after {COMMAND_TIMEOUT_SECONDS} seconds. A commit is still permitted."}
    except (ValueError, OSError) as exc:
        return {"error": str(exc)}


def get_git_status(issue_key: str) -> dict:
    """Show Git branch and working-tree status for this Jira issue's isolated workspace."""
    try:
        repo = _repo_for(issue_key)
        if not (repo / ".git").exists():
            return {"error": "Git repository is not initialized."}
        branch = _git(repo, "branch", "--show-current")
        status = _git(repo, "status", "--short")
        if branch.returncode or status.returncode:
            return {"error": (branch.stderr + status.stderr)[-3000:]}
        return {"branch": branch.stdout.strip(), "status": status.stdout.strip() or "clean"}
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        return {"error": str(exc)}


def get_git_diff(issue_key: str) -> dict:
    """Return the diff of tracked changes plus a list of untracked files in this issue workspace."""
    try:
        repo = _repo_for(issue_key)
        if not (repo / ".git").exists():
            return {"error": "Git repository is not initialized."}
        diff = _git(repo, "diff", "--")
        staged = _git(repo, "diff", "--cached", "--")
        status = _git(repo, "status", "--short")
        if diff.returncode or staged.returncode or status.returncode:
            return {"error": (diff.stderr + staged.stderr + status.stderr)[-3000:]}
        return {
            "unstaged_diff": diff.stdout[-20000:],
            "staged_diff": staged.stdout[-20000:],
            "status": status.stdout.strip() or "clean",
            "note": "Untracked files are listed in status but their content is not included in git diff until staged."
        }
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        return {"error": str(exc)}


def commit_changes(issue_key: str, commit_message: str) -> dict:
    """Stage project changes and create a local Git commit; test failures do not block this operation."""
    try:
        repo = _repo_for(issue_key)
        if not (repo / ".git").exists():
            return {"error": "Git repository is not initialized."}
        if not commit_message or len(commit_message) > 160 or "\n" in commit_message:
            return {"error": "Provide a single-line commit message of at most 160 characters."}
        # Only stage the project tree. The path protections and .gitignore keep secrets out.
        add = _git(repo, "add", "-A")
        if add.returncode:
            return {"error": "Git add failed: " + add.stderr[-3000:]}
        # Check for whitespace errors, but don't gate on tests.
        check = _git(repo, "diff", "--cached", "--check")
        if check.returncode:
            return {"error": "Git diff check found a problem; inspect and correct it before committing: " + check.stderr[-2000:]}
        staged = _git(repo, "diff", "--cached", "--quiet")
        if staged.returncode == 0:
            return {"error": "There are no changes to commit."}
        if staged.returncode not in (0, 1):
            return {"error": "Could not inspect staged changes."}
        result = _git(repo, "commit", "-m", commit_message, timeout=90)
        if result.returncode:
            return {"error": "Git commit failed: " + result.stderr[-4000:]}
        head = _git(repo, "rev-parse", "HEAD")
        branch = _git(repo, "branch", "--show-current")
        return {
            "success": True,
            "commit": head.stdout.strip() if head.returncode == 0 else None,
            "branch": branch.stdout.strip() if branch.returncode == 0 else None,
            "message": commit_message,
            "output": result.stdout[-2000:]
        }
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        return {"error": str(exc)}
