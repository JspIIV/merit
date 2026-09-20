# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""Merit: an access pass earned by a verified public action, not a self-claim.

Allowlists are the soft underbelly of every airdrop, mint and grant round. A team
wants to reward the people who actually contributed, attended, or shipped, and
what they have to work with is a form anybody can fill in, a snapshot anybody can
farm, or a spreadsheet somebody has to police by hand. So the reward goes to
whoever games the list best, and the people it was for get diluted.

Merit issues the pass from the action itself. An organiser opens a program with a
requirement in plain words and one public page that establishes who qualifies:
a contributors file, an attendee list, a page that names the people who did the
thing. An address then claims its own pass, and the contract fetches that page
and asks a round of validators one question, reading this page, does this address
meet the requirement? Only if they agree does the pass issue. Nobody grants
themselves a pass by saying so, and nobody hand-approves the list.

## What it answers

    has_pass(program_id, address) -> bool

for another contract to gate on: an airdrop that pays only verified contributors,
a mint open only to attendees, a vote weighted to people who actually did the
work. The gate is a verified action, checked against a public source, not a
self-report and not a snapshot that can be farmed.

## What it refuses

You can only claim for yourself: the address checked is the caller, so nobody
claims a pass on another address's behalf. It never issues on silence: a page
that cannot be read is UNREADABLE and issues nothing, and the same address can try
again later. It never issues on the claimant's word: the deciding evidence is the
page the contract fetched, and the requirement is set by the organiser at open
time and never edited.

## Where it stops, plainly

It judges whether a page shows an address qualifying, not whether the page is the
right source. An organiser who names a page they can edit can wave people through;
a requirement worded loosely can be read two ways. Name an authoritative public
list and a requirement a stranger could check. It reads what is public: a page
behind a login is UNREADABLE. And it grants a status, not money; a distribution
contract reads has_pass and pays.
"""

from genlayer import *
import json

QUALIFIED = "QUALIFIED"
NOT_QUALIFIED = "NOT_QUALIFIED"
UNREADABLE = "UNREADABLE"
DECISIONS = (QUALIFIED, NOT_QUALIFIED, UNREADABLE)

ISSUED = "ISSUED"
DENIED = "DENIED"
UNRESOLVED = "UNRESOLVED"

MAX_NAME = 120
MAX_REQUIREMENT = 400
MAX_URL = 300
MAX_PAGE = 6000
MAX_REASON = 300
MAX_QUOTE = 300

FETCH_FAILED = "__FETCH_FAILED__"


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _clip(text: str, limit: int) -> str:
    text = str(text).strip()
    return text if len(text) <= limit else text[:limit] + " [...]"


def _addr(value) -> str:
    text = str(value).strip().lower()
    if not text.startswith("0x") or len(text) != 42:
        return ""
    for character in text[2:]:
        if character not in "0123456789abcdef":
            return ""
    return text


def _url_ok(url: str) -> bool:
    text = str(url).strip()
    if len(text) < 8 or len(text) > MAX_URL or " " in text:
        return False
    return text.startswith("https://") or text.startswith("http://")


def _field(raw: str, name: str, allowed, fallback: str) -> str:
    try:
        text = str(raw).strip()
        obj = json.loads(text[text.index("{"):text.rindex("}") + 1])
        if isinstance(obj, dict):
            said = str(obj.get(name, "")).strip().upper()
            return said if said in allowed else fallback
    except Exception:
        pass
    return fallback


def _text_field(raw: str, name: str, limit: int) -> str:
    try:
        text = str(raw).strip()
        obj = json.loads(text[text.index("{"):text.rindex("}") + 1])
        if isinstance(obj, dict):
            return _clip(str(obj.get(name, "")), limit)
    except Exception:
        pass
    return ""


def _key(pid: str, addr: str) -> str:
    return pid + "|" + addr


def _task(requirement: str, address: str, page: str) -> str:
    return f"""An address is claiming a pass in a program. Decide, only from the page below,
whether this address qualifies under the requirement.

THE REQUIREMENT, set by the organiser:
{requirement}

THE ADDRESS CLAIMING THE PASS:
{address}

THE PUBLIC PAGE THAT ESTABLISHES WHO QUALIFIES:
{page}

Decide one of:
  {QUALIFIED} the page shows this exact address meeting the requirement
  {NOT_QUALIFIED} the page was read and this address does not meet the requirement
  {UNREADABLE} the page could not be read, or does not establish who qualifies either way

Match the address exactly, case-insensitively. Do not assume an address qualifies
because similar ones do, and do not treat an unreachable or unrelated page as a
pass or a denial: that is {UNREADABLE}. A pass issues only on {QUALIFIED}, so give
it only when the page genuinely shows this address meeting the requirement.

Reply with bare JSON and nothing else:
{{"decision": "{QUALIFIED}" or "{NOT_QUALIFIED}" or "{UNREADABLE}",
  "quote": "the line on the page that decided it, or empty",
  "reason": "one sentence naming what decided it"}}"""


class Merit(gl.Contract):
    """Programs, and the passes addresses earn in them by a verified public action."""

    # str(program_id) -> the program as JSON.
    programs: TreeMap[str, str]
    program_ids: DynArray[str]
    # "program_id|address" -> the claim as JSON.
    claims: TreeMap[str, str]

    def __init__(self) -> None:
        pass

    @gl.public.write
    def open_program(self, name: str, requirement: str, source_url: str) -> str:
        """Open a program: a requirement in plain words and one public page that establishes who qualifies.

        The organiser is bound to the caller. The requirement and source are fixed
        here and never edited, so nobody moves the goalposts after passes issue.
        """
        organiser = gl.message.sender_address.as_hex.lower()
        title = _clip(name, MAX_NAME)
        rule = _clip(requirement, MAX_REQUIREMENT)
        link = str(source_url).strip()
        if not title:
            return json.dumps({"ok": False, "error": "give the program a name"})
        if not rule:
            return json.dumps({"ok": False, "error": "state the requirement in plain words"})
        if not _url_ok(link):
            return json.dumps({"ok": False,
                               "error": "give an http(s) source URL that establishes who qualifies"})

        pid = str(len(self.program_ids))
        record = {
            "id": pid,
            "organiser": organiser,
            "opened_at": _now_iso(),
            "name": title,
            "requirement": rule,
            "source_url": link,
            "issued": 0,
            "denied": 0,
        }
        self.programs[pid] = json.dumps(record)
        self.program_ids.append(pid)
        return json.dumps({"ok": True, "id": pid})

    @gl.public.write
    def claim(self, program_id: str) -> str:
        """Claim your own pass. The contract checks the caller's address against the program's source.

        The address verified is the caller, so nobody claims for anybody else. The
        page is fetched by the contract inside the round; the claimant passes in
        nothing the round trusts.
        """
        pid = str(program_id).strip()
        stored = self.programs.get(pid, None)
        if stored is None:
            return json.dumps({"ok": False, "error": "no program with that id"})
        program = json.loads(stored)
        claimant = gl.message.sender_address.as_hex.lower()
        key = _key(pid, claimant)

        existing = self.claims.get(key, None)
        if existing is not None:
            prev = json.loads(existing)
            if prev["status"] == ISSUED:
                return json.dumps({"ok": False, "error": "this address already holds a pass",
                                   "status": ISSUED})

        # Copy into locals before the round. Nothing inside the block reads self
        # and nothing inside it raises.
        requirement = program["requirement"]
        url = program["source_url"]

        def look() -> str:
            page = ""
            try:
                got = gl.nondet.web.render(url)
                page = got if isinstance(got, str) else getattr(got, "body", "")
                if isinstance(page, (bytes, bytearray)):
                    page = page.decode("utf-8", "replace")
                page = _clip(str(page), MAX_PAGE)
            except Exception:
                page = FETCH_FAILED
            if not page or page == FETCH_FAILED:
                return json.dumps({"decision": UNREADABLE, "quote": "",
                                   "reason": "the source page could not be read"})
            try:
                return str(gl.nondet.exec_prompt(_task(requirement, claimant, page)))
            except Exception as error:
                return json.dumps({"decision": UNREADABLE, "quote": "",
                                   "reason": _clip("the prompt failed: " + str(error), MAX_REASON)})

        raw = gl.eq_principle.prompt_comparative(
            look,
            principle=(
                f"Both answers must carry the same value in the field named decision, one of "
                f"{QUALIFIED}, {NOT_QUALIFIED} or {UNREADABLE}. That single field decides whether "
                "this address is granted a pass, so two readers differing on it are not wording a "
                "judgement differently, they disagree about whether the address qualifies. The "
                "quote and the reason are not compared, and the two readers will not have fetched "
                "byte-identical copies of the page."
            ),
        )

        decision = _field(raw, "decision", DECISIONS, "")
        if not decision:
            return json.dumps({"ok": False,
                               "error": "the round produced no decision this contract recognises",
                               "round_said": _clip(str(raw), 400)})

        status = ISSUED if decision == QUALIFIED else DENIED if decision == NOT_QUALIFIED else UNRESOLVED
        claim = {
            "program_id": pid,
            "address": claimant,
            "decision": decision,
            "status": status,
            "reason": _text_field(raw, "reason", MAX_REASON),
            "quote": _text_field(raw, "quote", MAX_QUOTE),
            "at": _now_iso(),
        }
        # Count issued/denied once per address: only when this is the first time
        # the address reaches a resolved status.
        was_resolved = existing is not None and json.loads(existing)["status"] in (ISSUED, DENIED)
        self.claims[key] = json.dumps(claim)
        if not was_resolved:
            if status == ISSUED:
                program["issued"] = int(program.get("issued", 0)) + 1
                self.programs[pid] = json.dumps(program)
            elif status == DENIED:
                program["denied"] = int(program.get("denied", 0)) + 1
                self.programs[pid] = json.dumps(program)
        return json.dumps({"ok": True, "program_id": pid, "address": claimant,
                           "decision": decision, "status": status, "reason": claim["reason"]})

    # ------------------------------------------------------------------ reads

    @gl.public.view
    def has_pass(self, program_id: str, address: str) -> str:
        """The one field a downstream contract gates on: does this address hold a verified pass."""
        pid = str(program_id).strip()
        who = _addr(address)
        if not who:
            return json.dumps({"exists": False, "has_pass": False, "error": "not an address"})
        stored = self.claims.get(_key(pid, who), None)
        if stored is None:
            return json.dumps({"exists": False, "has_pass": False})
        claim = json.loads(stored)
        return json.dumps({"exists": True, "program_id": pid, "address": who,
                           "has_pass": claim["status"] == ISSUED, "status": claim["status"]})

    @gl.public.view
    def get_claim(self, program_id: str, address: str) -> str:
        """The full claim record for an address in a program, including the deciding reason."""
        pid = str(program_id).strip()
        who = _addr(address)
        if not who:
            return json.dumps({"exists": False})
        stored = self.claims.get(_key(pid, who), None)
        if stored is None:
            return json.dumps({"exists": False})
        return stored

    @gl.public.view
    def get_program(self, program_id: str) -> str:
        """A program's name, requirement, source and issued/denied counts."""
        pid = str(program_id).strip()
        stored = self.programs.get(pid, None)
        if stored is None:
            return json.dumps({"exists": False})
        return stored

    @gl.public.view
    def size(self) -> str:
        """How many programs exist, and passes issued and denied across all of them."""
        issued = 0
        denied = 0
        for position in range(len(self.program_ids)):
            record = json.loads(self.programs[self.program_ids[position]])
            issued += int(record.get("issued", 0))
            denied += int(record.get("denied", 0))
        return json.dumps({"programs": len(self.program_ids), "issued": issued, "denied": denied})

    @gl.public.view
    def page(self, start: str, count: str) -> str:
        """A slice of the programs, newest first, for a frontend to render."""
        total = len(self.program_ids)
        try:
            begin = int(str(start).strip())
        except Exception:
            begin = 0
        try:
            want = int(str(count).strip())
        except Exception:
            want = 20
        if begin < 0:
            begin = 0
        if want < 1:
            want = 1
        if want > 50:
            want = 50
        out = []
        seen = 0
        position = total - 1 - begin
        while position >= 0 and seen < want:
            out.append(json.loads(self.programs[self.program_ids[position]]))
            position -= 1
            seen += 1
        return json.dumps({"total": total, "start": begin, "count": len(out), "items": out})
