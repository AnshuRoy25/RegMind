"""
Fetch pull request diffs for regmind-auditor.

Order of lookup:
1. DEMO_DIFFS_DIR/pr_<number>.diff if that file exists (offline demos and tests)
2. GitHub API for settings.github_repo (or the repo passed in)

Every diff goes through guardrails.mask_secrets before it reaches the LLM.
"""

from pathlib import Path

import httpx

from app.agents.guardrails import mask_secrets
from app.core.config import settings

MAX_DIFF_CHARS = 30000


async def get_pr_diff(pr_number: int, repo: str = "") -> dict:
    """Get the code changes (unified diff) of a pull request, with secrets masked.

    Args:
        pr_number: Pull request number, e.g. 4.
        repo: Optional "owner/name". Leave empty to use the team's default repo.

    Returns:
        ok, diff, files_changed, masked_secrets, truncated.
    """
    diff_text = None

    demo_dir = getattr(settings, "demo_diffs_dir", "")
    if demo_dir:
        local = Path(demo_dir) / f"pr_{pr_number}.diff"
        if local.exists():
            diff_text = local.read_text(encoding="utf-8")

    if diff_text is None:
        repo = repo or settings.github_repo
        if not repo:
            return {"ok": False, "error": "No GitHub repo configured (GITHUB_REPO) and no demo diff found"}
        headers = {"Accept": "application/vnd.github.v3.diff", "User-Agent": "regmind-auditor"}
        if settings.github_token:
            headers["Authorization"] = f"Bearer {settings.github_token}"
        url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(url, headers=headers)
        except httpx.HTTPError as exc:
            return {"ok": False, "error": f"Could not reach GitHub: {exc}"}
        if response.status_code == 404:
            return {"ok": False, "error": f"PR #{pr_number} not found in {repo}"}
        if response.status_code != 200:
            return {"ok": False, "error": f"GitHub returned {response.status_code}"}
        diff_text = response.text

    files_changed = []
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            files_changed.append(line[6:])

    masked, count = mask_secrets(diff_text)
    truncated = len(masked) > MAX_DIFF_CHARS
    return {"ok": True, "pr_number": pr_number, "files_changed": files_changed,
            "diff": masked[:MAX_DIFF_CHARS], "masked_secrets": count, "truncated": truncated}

