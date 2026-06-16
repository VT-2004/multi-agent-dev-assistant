import os
import re
import time
import json
from datetime import datetime

from langchain_groq import ChatGroq

from app.core.config import settings
from app.core.state import AgentState

MODEL_NAME = "llama-3.1-8b-instant"

# Safety cap on how much of a file we show the model, to stay within Groq free-tier TPM limits
MAX_FILE_CHARS = 12000

# Set DEBUG_CODE_AGENT=1 in the environment to print raw LLM responses and edit-matching details
DEBUG = os.getenv("DEBUG_CODE_AGENT", "0") == "1"

SYSTEM_PROMPT = """You are an expert software engineer working on the "{repo_name}" codebase.

You will be given a GitHub issue and the current content of relevant files.
Your job is to make the minimal code changes needed to resolve the issue.

Respond with ONLY a valid JSON object in this exact structure, with no other text before or after:

{{
  "reasoning": "2-4 sentences explaining your approach",
  "edits": [
    {{
      "file_path": "relative/file/path",
      "search": "exact existing code to find, copied verbatim",
      "replace": "new code that should replace it"
    }}
  ]
}}

Rules:
- The "search" text must match the original file EXACTLY, character for character including whitespace.
- The "search" text must be a complete logical unit — for array or object declarations, include the ENTIRE declaration from start to closing bracket and semicolon, not just the opening bracket.
- Keep "search" as short as possible while still being unique (typically 1-4 lines).
- Only include edits for lines that actually need to change.
- Output ONLY the JSON object. No markdown, no code fences, no explanation outside the JSON.
- You MUST use double quotes for all string values in the JSON.
- In the "replace" value, use the same quote style as the original file."""


def get_llm():
    return ChatGroq(
        model=MODEL_NAME,
        temperature=0.2,
        max_tokens=2000,
    )


def read_file_full(repo_name: str, file_path: str) -> str:
    """Read the full, untruncated current content of a file from the cloned repo."""
    full_path = os.path.join(settings.REPO_CLONE_PATH, repo_name, file_path)
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()
    except (IOError, UnicodeDecodeError):
        return ""


def truncate_for_prompt(content: str) -> str:
    """Truncate file content shown to the model, to control prompt size."""
    if len(content) > MAX_FILE_CHARS:
        return content[:MAX_FILE_CHARS] + "\n\n... [file truncated for length] ..."
    return content


def build_user_prompt(state: AgentState, file_paths: list) -> str:
    parts = [
        f"ISSUE TITLE: {state['issue_title']}",
        f"ISSUE BODY: {state['issue_body']}",
    ]

    if state.get("retry_count", 0) > 0:
        parts.append(f"\nPREVIOUS ATTEMPT FAILED REVIEW.")
        parts.append(f"REVIEW FEEDBACK: {state.get('review_notes', '')}")
        parts.append("Please fix the issues described above in your new response.\n")

    parts.append("\nRELEVANT FILES:")

    for fp in file_paths:
        full_content = read_file_full(state["repo_name"], fp)
        truncated = truncate_for_prompt(full_content)
        parts.append(f"\n--- {fp} ---\n{truncated}")

        # Extract and explicitly show complete lines that are likely edit targets,
        # so the model can copy them verbatim as "search" text
        relevant_lines = []
        for line in full_content.splitlines():
            stripped = line.strip()
            # Flag array/object declarations and other common edit targets
            if stripped.startswith("const ") and ("=[" in stripped.replace(" ", "") or "= [" in stripped):
                relevant_lines.append(line)

        if relevant_lines:
            parts.append(f"\nCOMPLETE LINES FOR EXACT MATCHING (copy these verbatim as your 'search' value):")
            for line in relevant_lines[:5]:  # limit to 5 most relevant
                parts.append(f"  {repr(line)}")

    return "\n".join(parts)


def parse_response(text: str):
    """Parse JSON response into (reasoning, [edits])."""
    # Strip markdown code fences if the model adds them despite instructions
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text)

    try:
        data = json.loads(text)
        reasoning = data.get("reasoning", "")
        edits = [
            {
                "file_path": e["file_path"],
                "search": e["search"],
                "replace": e["replace"],
            }
            for e in data.get("edits", [])
            if "file_path" in e and "search" in e and "replace" in e
        ]
        return reasoning, edits
    except (json.JSONDecodeError, KeyError) as exc:
        if DEBUG:
            print(f"JSON parse error: {exc}")
        return "", []
def expand_search_to_full_line(search: str, file_content: str) -> str:
    """
    If the search text matches only part of a line (e.g. just the opening of
    an array declaration), expand it to include the full line(s) up to and
    including the closing bracket/semicolon. This prevents partial replacements
    that leave leftover original content in the file.
    """
    idx = file_content.find(search)
    if idx == -1:
        return search  # not found, return as-is

    # Find the start of the line containing the match
    line_start = file_content.rfind("\n", 0, idx) + 1

    # Find the end of the complete statement (closing ]; or };)
    end_idx = idx + len(search)
    depth = search.count("[") + search.count("{") - search.count("]") - search.count("}")

    if depth <= 0:
        # Already balanced — just expand to end of line
        line_end = file_content.find("\n", idx)
        if line_end == -1:
            line_end = len(file_content)
        return file_content[line_start:line_end]

    # Walk forward until brackets are balanced
    while end_idx < len(file_content) and depth > 0:
        ch = file_content[end_idx]
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        end_idx += 1

    # Extend to end of that line
    line_end = file_content.find("\n", end_idx)
    if line_end == -1:
        line_end = len(file_content)

    return file_content[line_start:line_end]

def expand_search_to_full_line(search: str, file_content: str) -> str:
    """
    If the search text matches only part of a line (e.g. just the opening of
    an array declaration), expand it to include the full line(s) up to and
    including the closing bracket/semicolon. This prevents partial replacements
    that leave leftover original content in the file.
    """
    idx = file_content.find(search)
    if idx == -1:
        return search  # not found, return as-is

    # Find the start of the line containing the match
    line_start = file_content.rfind("\n", 0, idx) + 1

    # Find the end of the complete statement (closing ]; or };)
    end_idx = idx + len(search)
    depth = search.count("[") + search.count("{") - search.count("]") - search.count("}")

    if depth <= 0:
        # Already balanced — just expand to end of line
        line_end = file_content.find("\n", idx)
        if line_end == -1:
            line_end = len(file_content)
        return file_content[line_start:line_end]

    # Walk forward until brackets are balanced
    while end_idx < len(file_content) and depth > 0:
        ch = file_content[end_idx]
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        end_idx += 1

    # Extend to end of that line
    line_end = file_content.find("\n", end_idx)
    if line_end == -1:
        line_end = len(file_content)

    return file_content[line_start:line_end]


def code_agent_node(state: AgentState) -> dict:
    retry_count = state.get("retry_count", 0)

    file_paths = []
    for c in state.get("retrieved_context", []):
        fp = c["file_path"]
        if fp not in file_paths:
            file_paths.append(fp)
        if len(file_paths) == 1:
            break

    system_prompt = SYSTEM_PROMPT.format(repo_name=state["repo_name"])
    user_prompt = build_user_prompt(state, file_paths)

    time.sleep(8)
    llm = get_llm()
    response = llm.invoke([
        ("system", system_prompt),
        ("user", user_prompt),
    ])

    if DEBUG:
        print(f"\n=== RAW LLM RESPONSE (attempt {retry_count + 1}) ===")
        print(response.content)
        print("=== END RAW RESPONSE ===\n")

    reasoning, edits = parse_response(response.content)

    if DEBUG:
        print(f"Parsed {len(edits)} edit(s) from response.")

    file_contents = {}
    applied = 0
    skipped = 0

    for edit in edits:
        fp = edit["file_path"]
        if fp not in file_contents:
            file_contents[fp] = read_file_full(state["repo_name"], fp)

        # Expand partial search text to the full logical line/statement
        expanded_search = expand_search_to_full_line(edit["search"], file_contents[fp])
        if expanded_search != edit["search"]:
            if DEBUG:
                print(f"Expanded search from {edit['search']!r} to {expanded_search!r}")
            edit["search"] = expanded_search

        found = edit["search"] in file_contents[fp]

        if DEBUG:
            print(f"\n--- Edit for {fp} ---")
            print(f"SEARCH (repr): {edit['search']!r}")
            print(f"Found in file: {found}")

        if found:
            file_contents[fp] = file_contents[fp].replace(edit["search"], edit["replace"], 1)
            applied += 1
        else:
            skipped += 1

    changes = []
    for fp, new_content in file_contents.items():
        if new_content != read_file_full(state["repo_name"], fp):
            changes.append({"file_path": fp, "content": new_content})

    attempt_label = f"attempt {retry_count + 1}"
    log = {
        "agent": "code_agent",
        "message": (
            f"[{attempt_label}] Reasoning: {reasoning} | "
            f"Applied {applied} edit(s), skipped {skipped}, "
            f"{len(changes)} file(s) changed."
        ),
        "timestamp": datetime.utcnow().isoformat(),
    }

    return {
        "proposed_changes": changes,
        "logs": [log],
    }