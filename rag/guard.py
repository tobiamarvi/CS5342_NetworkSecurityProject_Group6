"""Input/output checks shared by both agents. Adversarial-testing fixes go here."""
import logging
import re
import secrets
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parents[1] / "logs"


def file_logger(name):
    """Logger writing to logs/<name>.log (shared with agents/web_lookup.py)."""
    log = logging.getLogger(name)
    if not log.handlers:
        LOG_DIR.mkdir(exist_ok=True)
        h = logging.FileHandler(LOG_DIR / f"{name}.log", encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(h)
        log.setLevel(logging.INFO)
    return log


log = file_logger("security")

MAX_INPUT_CHARS = 2000
REFUSAL = "Sorry, I can't help with that. I can answer questions about the CS5342 course material."

# Random per process: if it ever shows up in a reply, the system prompt leaked.
CANARY = "CANARY-" + secrets.token_hex(4)

FLAGGED = [re.compile(p, re.I) for p in (
    r"\b(ignore|disregard|forget)\b.{0,30}\b(previous|prior|above|earlier|all)\b.{0,20}\b(instructions?|rules?|prompts?)",
    r"\bsystem\s+prompt\b",
    r"\b(reveal|print|show|repeat|output)\b.{0,30}\b(instructions?|rules|prompt)\b",
    r"\byou\s+are\s+now\b",
    r"\b(developer|dan|god)\s+mode\b",
    r"\bjailbreak",
    r"\b(api|secret)\s*keys?\b",
    r"\banswer\s+keys?\b",
    r"\bcanary\b",
)]


def check_input(text):
    """Return a reason string if the input should be refused, else None."""
    if len(text) > MAX_INPUT_CHARS:
        reason = f"input too long ({len(text)} chars)"
    else:
        hit = next((p.pattern for p in FLAGGED if p.search(text)), None)
        reason = f"matched {hit!r}" if hit else None
    if reason:
        log.warning("flagged input: %s | %r", reason, text[:300])
    return reason


def check_output(text, system_prompt):
    """Return True if the reply leaks the system prompt."""
    long_lines = [l.strip() for l in system_prompt.splitlines() if len(l.strip()) > 40]
    leaked = CANARY in text or any(l in text for l in long_lines)
    if leaked:
        log.warning("blocked output that leaked the system prompt: %r", text[:300])
    return leaked
