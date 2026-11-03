"""The one outbound call: a Wikipedia search over HTTPS. No API key needed.

Only the user's question is sent, never course text. The exact query is logged
to logs/web_lookup.log so the traffic write-up can show what left the machine
(TLS hides the payload in a pcap).
"""
import requests

from rag.guard import file_logger

API = "https://en.wikipedia.org/w/api.php"
# Wikipedia asks API clients for a descriptive User-Agent with a contact URL.
USER_AGENT = "CS5342-Group6-Tutor/0.1 (https://github.com/tobiamarvi/CS5342_NetworkSecurityProject_Group6)"
log = file_logger("web_lookup")


def search(question, n=3):
    """Return up to n [{title, text, url}] from Wikipedia, or [] on any network error."""
    params = {
        "action": "query", "format": "json", "formatversion": 2,
        "generator": "search", "gsrsearch": question, "gsrlimit": n,
        "prop": "extracts|info", "exintro": 1, "explaintext": 1, "exlimit": n,
        "inprop": "url",
    }
    log.info("GET %s gsrsearch=%r", API, question)
    try:
        r = requests.get(API, params=params, headers={"User-Agent": USER_AGENT}, timeout=10)
        r.raise_for_status()
        pages = r.json().get("query", {}).get("pages", [])
    except (requests.RequestException, ValueError) as e:
        log.warning("lookup failed: %s", e)
        return []
    pages.sort(key=lambda p: p.get("index", 0))
    return [{"title": p["title"], "text": p.get("extract", "")[:1500], "url": p["fullurl"]}
            for p in pages if p.get("extract")]
