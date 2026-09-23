"""Refuse mutation runs if the native approval environment is unprotected."""
import json
import os
from urllib.parse import quote
from urllib.request import Request, urlopen


def protected(environment):
    return any(rule.get("type") == "required_reviewers" and rule.get("reviewers") and rule.get("prevent_self_review") is True for rule in environment.get("protection_rules", []))


def main():
    operation = os.environ["DEMO_OPERATION"]
    if operation == "plan":
        return
    if operation not in ("deploy", "destroy"):
        raise SystemExit("Unsupported operation")
    name = "demo-cleanup" if operation == "destroy" else "demo-deploy"
    owner, repo = os.environ["GITHUB_REPOSITORY"].split("/", 1)
    url = f"https://api.github.com/repos/{quote(owner, safe='')}/{quote(repo, safe='')}/environments/{name}"
    request = Request(url, headers={"Authorization": "Bearer " + os.environ["GH_TOKEN"], "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with urlopen(request, timeout=15) as response:
            value = json.loads(response.read(131072))
    except (OSError, ValueError):
        raise SystemExit("Cannot verify the GitHub approval environment") from None
    if not protected(value):
        raise SystemExit("Configure required reviewers and prevent self-review on the deployment environment")


if __name__ == "__main__":
    main()
