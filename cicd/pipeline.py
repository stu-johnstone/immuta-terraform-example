#!/usr/bin/env python3
"""Simulated CI/CD stages for the Immuta Terraform example (see the Makefile).

  check   Checks that every tag, group and attribute a policy names exists in
          locals.tf, and that policy keys are unique. No credentials needed.
  review  Asks a model whether the change does what the tickets ask, and
          nothing more. Every ticket in the tickets directory is sent. The
          prompt is cicd/prompt.md. The model is a local Ollama model (the
          default, no credentials) or a Dust agent (--backend dust).

Standard library only. The configuration and policies are read through
`terraform console`, so this script does not parse HCL or YAML itself.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPT = Path(__file__).resolve().parent / "prompt.md"
OUTPUT_DIR = ROOT / ".ci"

# What the review sends to Terraform console: the configuration a policy can
# refer to, and every policy document.
CONTEXT_EXPRESSION = (
    "jsonencode({"
    "tags = values(local.tags), "
    "groups = {for k, g in local.groups : k => {name = g.name, members = g.members, attributes = g.attributes}}, "
    "users = {for k, u in local.users : k => {name = u.name, attributes = u.attributes}}, "
    'policies = {for f in fileset(path.module, "policies/*.yaml") : f => yamldecode(file("${path.module}/${f}"))}'
    "})"
)

# Immuta functions in row-level predicates that name a tag or an attribute.
TAG_FUNCTION = re.compile(r"@columnTagged\(\s*'([^']+)'")
ATTRIBUTE_FUNCTION = re.compile(r"@(?:attributeValuesContains|hasAttribute)\(\s*'([^']+)'")

# Review verdicts, and the exit code each gives the stage.
VERDICT_EXIT_CODES = {"pass": 0, "fail": 1, "needs_human": 1}


def fail(message, code=2):
    print(f"error: {message}", file=sys.stderr)
    sys.exit(code)


def load_context():
    """Evaluates CONTEXT_EXPRESSION with terraform console."""
    result = subprocess.run(
        ["terraform", "console"],
        input=CONTEXT_EXPRESSION + "\n",
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    if result.returncode != 0:
        fail("terraform console failed (run `make init` first?):\n" + result.stderr.strip())

    # Console prints the JSON as an HCL string literal, which is also a JSON
    # string literal.
    return json.loads(json.loads(result.stdout.strip()))


def walk(value, key=None):
    """Yields every (key, value) pair in a decoded policy document."""
    if isinstance(value, dict):
        for child_key, child in value.items():
            yield child_key, child
            yield from walk(child, child_key)
    elif isinstance(value, list):
        for child in value:
            yield key, child
            yield from walk(child, key)


def policy_references(document):
    """Returns the tags, groups and attribute names a policy refers to."""
    tags, groups, attributes = set(), set(), set()

    for key, value in walk(document):
        if key in ("tag", "columnTag") and isinstance(value, str):
            tags.add(value)
        elif key == "groups" and isinstance(value, str):
            groups.add(value)
        elif key == "groups" and isinstance(value, dict) and "name" in value:
            groups.add(value["name"])
        elif key == "attributes" and isinstance(value, dict) and "name" in value:
            attributes.add(value["name"])
        elif isinstance(value, str):
            tags.update(TAG_FUNCTION.findall(value))
            attributes.update(ATTRIBUTE_FUNCTION.findall(value))

    return tags, groups, attributes


def known_tag(tag, tags):
    # Immuta creates parent tags, so "PII" exists when "PII.Name" does.
    return any(known == tag or known.startswith(tag + ".") for known in tags)


def check(_args):
    context = load_context()
    tags = context["tags"]
    groups = {group["name"] for group in context["groups"].values()}
    attributes = {name for user in context["users"].values() for name in user["attributes"]}
    attributes |= {name for group in context["groups"].values() for name in group["attributes"]}

    errors, warnings, keys = [], [], {}
    for path, document in sorted(context["policies"].items()):
        keys.setdefault(document.get("policyKey"), []).append(path)
        policy_tags, policy_groups, policy_attributes = policy_references(document)

        for tag in sorted(policy_tags):
            if not known_tag(tag, tags):
                errors.append(f"{path}: tag {tag!r} is not in local.tags")
        for group in sorted(policy_groups - groups):
            errors.append(f"{path}: group {group!r} is not in local.groups")
        for attribute in sorted(policy_attributes - attributes):
            # Attributes can also come from the identity provider, or be
            # granted later (PII Access), so this is only a warning.
            warnings.append(f"{path}: no user or group in locals.tf has attribute {attribute!r}")

    for key, paths in sorted(keys.items(), key=lambda item: str(item[0])):
        if len(paths) > 1:
            errors.append(f"policyKey {key!r} is used by more than one file: {', '.join(paths)}")

    for warning in warnings:
        print(f"warning: {warning}")
    for error in errors:
        print(f"error: {error}")

    count = len(context["policies"])
    if errors:
        print(f"Policy check failed: {len(errors)} error(s) in {count} policies.")
        sys.exit(1)
    print(f"Policy check passed: {count} policies, {len(warnings)} warning(s).")


def git(*args):
    result = subprocess.run(["git", *args], capture_output=True, text=True, cwd=ROOT)
    if result.returncode != 0:
        fail(f"git {' '.join(args)} failed:\n{result.stderr.strip()}")
    return result.stdout


def change_diff(base):
    """The change under review: Terraform files and policies against base,
    including uncommitted and new (untracked) files."""
    paths = ["policies", "*.tf"]
    diff = git("diff", "--no-color", base, "--", *paths)

    for path in git("ls-files", "--others", "--exclude-standard", "--", *paths).split():
        content = (ROOT / path).read_text()
        diff += f"\nNew file {path}:\n{content}"

    return diff.strip()


def section(title, body, language=""):
    return f"## {title}\n\nBEGIN {title.upper()}\n```{language}\n{body.strip()}\n```\nEND {title.upper()}\n"


def load_tickets(directory):
    """Every ticket in the directory, as one markdown document."""
    paths = sorted(Path(directory).glob("*.md"))
    if not paths:
        fail(f"no tickets (*.md) in {directory}")
    return "\n\n---\n\n".join(path.read_text().strip() for path in paths), len(paths)


def build_message(tickets, diff, context, plan):
    policies = "\n\n".join(
        f"# {path}\n{(ROOT / path).read_text().strip()}" for path in sorted(context["policies"])
    )
    configuration = {key: context[key] for key in ("users", "groups", "tags")}

    parts = [
        PROMPT.read_text(),
        "# Material\n",
        section("Tickets", tickets, "markdown"),
        section("Diff", diff, "diff"),
        section("Configuration", json.dumps(configuration, indent=2), "json"),
        section("Policies", policies, "yaml"),
    ]
    if plan is not None:
        parts.append(section("Plan", plan))

    return "\n".join(parts)


class Dust:
    """The few Dust API calls the review needs."""

    def __init__(self):
        self.api_key = os.environ.get("DUST_API_KEY")
        self.workspace = os.environ.get("DUST_WORKSPACE_ID")
        self.agent = os.environ.get("DUST_AGENT_ID")
        self.url = os.environ.get("DUST_API_URL", "https://dust.tt").rstrip("/")

        missing = [name for name, value in [
            ("DUST_API_KEY", self.api_key),
            ("DUST_WORKSPACE_ID", self.workspace),
            ("DUST_AGENT_ID", self.agent),
        ] if not value]
        if missing:
            fail(f"set {', '.join(missing)} (see README.md, Simulated CI/CD)")

    def request(self, method, path, body=None):
        request = urllib.request.Request(
            f"{self.url}/api/v1/w/{self.workspace}{path}",
            method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            # The response body explains the error and does not hold the key.
            fail(f"Dust API {method} {path} returned {error.code}: {error.read().decode(errors='replace')}")
        except urllib.error.URLError as error:
            fail(f"cannot reach the Dust API at {self.url}: {error.reason}")

    def ask(self, title, content, timeout=600):
        """Starts a conversation with the agent and waits for its reply."""
        response = self.request("POST", "/assistant/conversations", {
            "title": title,
            "visibility": "unlisted",
            "message": {
                "content": content,
                "mentions": [{"configurationId": self.agent}],
                "context": {"username": "immuta-ci", "timezone": "UTC"},
            },
        })
        conversation_id = response["conversation"]["sId"]
        print(f"Dust conversation: {self.url}/w/{self.workspace}/assistant/{conversation_id}")

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            conversation = self.request("GET", f"/assistant/conversations/{conversation_id}")["conversation"]
            reply = latest_agent_message(conversation)
            if reply and reply.get("status") == "succeeded":
                return reply.get("content") or ""
            if reply and reply.get("status") in ("failed", "cancelled"):
                fail(f"the agent's reply {reply['status']}: {reply.get('error')}")
            time.sleep(3)

        fail(f"no reply from the agent after {timeout} seconds")


class Ollama:
    """A model served by a local Ollama, so the review needs no credentials."""

    def __init__(self, model, context_tokens):
        self.url = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        if "://" not in self.url:
            self.url = f"http://{self.url}"
        self.model = model
        self.context_tokens = context_tokens

    def ask(self, title, content, timeout=900):
        """Sends the message to the model and returns its reply. title is unused."""
        print(f"Ollama model: {self.model} at {self.url}")
        request = urllib.request.Request(
            f"{self.url}/api/chat",
            method="POST",
            data=json.dumps({
                "model": self.model,
                "messages": [{"role": "user", "content": content}],
                "stream": False,
                # The default context is too small for the material: Ollama
                # would silently drop the start of the prompt.
                "options": {"num_ctx": self.context_tokens, "temperature": 0},
            }).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                reply = json.load(response)
        except urllib.error.HTTPError as error:
            fail(f"Ollama returned {error.code}: {error.read().decode(errors='replace')} "
                 f"(is the model pulled? ollama pull {self.model})")
        except urllib.error.URLError as error:
            fail(f"cannot reach Ollama at {self.url}: {error.reason} (is it running? ollama serve)")
        except TimeoutError:
            fail(f"no reply from Ollama after {timeout} seconds")
        return reply.get("message", {}).get("content") or ""


def reviewer(args):
    if args.backend == "dust":
        return Dust()
    return Ollama(args.model, args.context_tokens)


def latest_agent_message(conversation):
    # content is a list of messages, each a list of its versions.
    for versions in reversed(conversation.get("content", [])):
        if versions and versions[-1].get("type") == "agent_message":
            return versions[-1]
    return None


def parse_review(reply):
    """Reads the JSON object from the agent's reply."""
    match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", reply, re.DOTALL)
    text = match.group(1) if match else reply
    try:
        review = json.loads(text)
    except json.JSONDecodeError:
        return None
    return review if review.get("verdict") in VERDICT_EXIT_CODES else None


def print_review(review):
    marks = {"met": "PASS", "not_met": "FAIL", "unclear": "????"}

    print("\nAI review\n")
    for ticket in review.get("tickets", []):
        state = "addressed" if ticket.get("addressed") else "not addressed"
        print(f"  {ticket.get('ticket')}: {ticket.get('title', '')} ({state})")
        for criterion in ticket.get("criteria", []):
            print(f"    [{marks.get(criterion.get('status'), '????')}] {criterion.get('criterion')}")
            print(f"           {criterion.get('evidence')}")
    for regression in review.get("regressions", []):
        print(f"  [REGRESSION] {regression.get('ticket')}: {regression.get('criterion')}: {regression.get('explanation')}")
    for change in review.get("unrequested_changes", []):
        flag = "WIDENS ACCESS" if change.get("widens_access") else "unrequested"
        print(f"  [{flag}] {change.get('change')}: {change.get('explanation')}")
    for concern in review.get("concerns", []):
        print(f"  [concern] {concern}")
    print(f"\n  Risk: {review.get('risk')}   Verdict: {review['verdict'].upper()}")
    print(f"  {review.get('summary', '')}\n")


def review(args):
    model = reviewer(args)
    tickets, ticket_count = load_tickets(args.tickets)

    # Clear the last review, so a failed run never leaves an old verdict.
    for name in ("review.md", "review.json"):
        (OUTPUT_DIR / name).unlink(missing_ok=True)

    diff = change_diff(args.base)
    if not diff:
        print(f"No change to policies or Terraform files against {args.base}: nothing to review.")
        return

    plan = None
    if args.plan:
        plan_path = Path(args.plan)
        if not plan_path.is_file():
            fail(f"plan {args.plan} not found; run make ci-plan")
        plan = plan_path.read_text()
        if len(plan) > args.max_plan_chars:
            plan = plan[:args.max_plan_chars] + "\n... (plan truncated)"

    message = build_message(tickets, diff, load_context(), plan)
    print(f"Reviewing the change against {ticket_count} tickets in {args.tickets}.")
    reply = model.ask("Immuta policy review", message)

    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "review.md").write_text(reply)

    result = parse_review(reply)
    if result is None:
        print(reply)
        fail("the agent's reply has no valid review JSON (saved in .ci/review.md)", 1)

    (OUTPUT_DIR / "review.json").write_text(json.dumps(result, indent=2) + "\n")
    print_review(result)
    sys.exit(VERDICT_EXIT_CODES[result["verdict"]])


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("check", help="check policy references").set_defaults(run=check)

    review_parser = commands.add_parser("review", help="AI review of the change against the tickets")
    review_parser.add_argument("--tickets", default=str(ROOT / "tickets"), help="directory of ticket markdown files")
    review_parser.add_argument("--base", default="HEAD", help="git revision the change is compared with")
    review_parser.add_argument("--plan", help="terraform show output to include")
    review_parser.add_argument("--max-plan-chars", type=int, default=40000)
    review_parser.add_argument("--backend", choices=["ollama", "dust"], default="ollama",
                               help="local Ollama model (no credentials) or a Dust agent")
    review_parser.add_argument("--model", default="qwen3-coder:30b", help="Ollama model")
    review_parser.add_argument("--context-tokens", type=int, default=32768, help="Ollama context window")
    review_parser.set_defaults(run=review)

    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
