# Merit

**An access pass earned by a verified public action, not a self-claim.** A fair-allowlist primitive for GenLayer.

Allowlists are the soft underbelly of every airdrop, mint and grant round. A team wants to reward the people who actually contributed, attended, or shipped, and what they have to work with is a form anybody can fill in, a snapshot anybody can farm, or a spreadsheet somebody has to police by hand. So the reward goes to whoever games the list best, and the people it was for get diluted.

Merit issues the pass from the action itself.

## How it works

1. **`open_program(name, requirement, source_url)`** — an organiser opens a program: a requirement in plain words and one public page that establishes who qualifies (a contributors file, an attendee list, a page that names the people who did the thing). The organiser is bound to `gl.message.sender_address`; the requirement and source are fixed and never edited.
2. **`claim(program_id)`** — an address claims **its own** pass (the address checked is the caller). The contract fetches the page itself and a GenLayer round decides: does this page show this address meeting the requirement? `QUALIFIED` → pass `ISSUED`; `NOT_QUALIFIED` → `DENIED`; `UNREADABLE` → nothing issued, try again later.
3. **`has_pass(program_id, address)`** — the boolean a downstream contract gates on: a fair airdrop, a mint open only to attendees, a vote weighted to people who did the work.

Reads: `get_program(id)`, `get_claim(program_id, address)`, `size()`, `page(start, count)`.

## Why it needs GenLayer

Whether a public page "shows this address qualifying" is a judgement over real-world text that no ordinary contract can make and no single admin should be trusted to make by hand. GenLayer validators each fetch the page and reach consensus on one categorical field, so the pass rests on a verified action against a public source, not on a self-report or a farmable snapshot.

## What it refuses

- **You can only claim for yourself.** The address checked is the caller, so nobody claims a pass on another address's behalf.
- **Never issues on silence.** A page that cannot be read is `UNREADABLE`; nothing issues, and the address can try again.
- **Never issues on the claimant's word.** The deciding evidence is the page the contract fetched, and the requirement is set by the organiser at open time and never changed.

## Live

- **Contract (GenLayer Asimov):** `0x137129dEB470FfC721548F48B537200eB605D55e`
- Explorer: https://explorer-asimov.genlayer.com/address/0x137129dEB470FfC721548F48B537200eB605D55e
- **App:** https://jspiiv.github.io/merit/ — reads programs from chain without a wallet; opening a program and claiming a pass are transactions on Asimov.

## Proven on Asimov

One program whose source (`docs/members/contributors.txt`) lists accepted contributors (`scripts/prove.mjs`, `results/proved.json`):
- an address **on the list** claims → **QUALIFIED** → pass **ISSUED**, `has_pass` true.
- an address **not on the list** claims → **NOT_QUALIFIED** → **DENIED**, `has_pass` false.

## Try it

Browse the live app, or from the CLI:

```
genlayer call 0x137129dEB470FfC721548F48B537200eB605D55e size
genlayer call 0x137129dEB470FfC721548F48B537200eB605D55e get_program --args '"0"'
```

Reproduce: `AT=0x137129dEB470FfC721548F48B537200eB605D55e PADV=<pw> PPUB=<pw> node scripts/prove.mjs` (after `npm i`).

## Where it stops, plainly

It judges whether a page shows an address qualifying, not whether the page is the right source. An organiser who names a page they can edit can wave people through; a requirement worded loosely can be read two ways. Name an authoritative public list and a requirement a stranger could check. It reads what is public: a page behind a login is `UNREADABLE`. And it grants a status, not money; a distribution contract reads `has_pass` and pays.

## Licence

AGPL-3.0-or-later.
