# RegMind.ai

### Your compliance team, now with AI teammates in the chat

RegMind.ai puts a team of AI agents inside your team chat that turn SEBI circulars into engineering work, keep that work in sync when the rules change, and check the finished code against the law before anything is marked done.

Built for **Flip the Switch** (WeMakeDevs × Switch) · Track 01: Best Business Workflow

---

## The problem

Every time SEBI issues a circular, a stock broker has to work out what changed and build it into their systems. The rules are written in legal language, but the work is done by engineers. So today it goes like this:

1. A compliance officer reads a long circular and figures out what applies.
2. They explain it to engineers over calls, emails and spreadsheets.
3. Engineers build what they understood.
4. Weeks later someone manually checks whether what got built actually meets the rule.

It gets worse when SEBI amends a rule that is already being built. Nobody tells the engineer halfway through, so they ship the old version, and the gap is only found during an audit.

Small brokers feel this the most, because they don't have big compliance teams.

---

## The solution

RegMind.ai is a set of five AI agents that join your team's chat room through **Switch** and work alongside the compliance officer and the engineers.

The officer drops a circular into the chat. The agents read it, break it into obligations, ask the officer to approve, turn the technical ones into clear engineering tasks, and assign them. When an engineer finishes, they say so in the chat with a PR number, and an agent checks the actual code against the rule. If SEBI changes the rule midway, an agent finds the affected task, pauses it and tells the engineer exactly what changed.

Everything happens in the conversation, so everyone sees what the agents are doing and can step in at any point. People make the decisions; the agents do the reading, the translating and the checking.

---

## Meet the agents

| Agent | What it does |
|---|---|
| **regmind-intake** | Reads a new circular, decides if it applies to the firm, and whether it's a new master circular or an amendment to an old one. Hands it to the right agent. |
| **regmind-parser** | Splits the circular into clauses and sorts each one: technical, business, prohibitive, governance or informational, plus how urgent it is. Asks the compliance officer to approve before anything moves. |
| **regmind-spec** | Turns each approved technical obligation into an engineering task with a plain-English spec and an evidence checklist, then assigns it to an engineer. |
| **regmind-router** | Handles amendments. Finds the task a changed rule affects and updates it based on where that task is right now. |
| **regmind-auditor** | When an engineer says a task is done, reads the pull request and checks every item on the evidence checklist. Marks it complete, or explains exactly what's missing. |

Agents pass work to each other by @mentioning the next agent in the room, the same way a person would.

---

## How it works in the chat

**A new circular arrives**

> **Priya (compliance):** @regmind-intake new SEBI circular: master_circular.pdf
>
> **regmind-intake:** This applies to us: it sets log retention and access control rules for brokers. Type: master circular.
> @regmind-parser please extract obligations from circular_id=1
>
> **regmind-parser:** Extracted 9 clauses. 3 technical items will become engineering tasks. Please review and reply "approved".
>
> **Priya:** @regmind-parser approved
>
> **regmind-spec:** Created TSK-001 · urgent · @aayush
> Keep order system logs for 730 days in tamper-proof storage.
> Evidence: retention set to 730 days in config · object lock on the log bucket · test showing a log can't be deleted

**SEBI changes the rule while it's being built**

> **Aayush:** @regmind-spec starting TSK-001
>
> **Priya:** @regmind-intake SEBI just issued an amendment: amendment.pdf
>
> **regmind-router:** @aayush TSK-001 is PAUSED. SEBI changed clause 3.1: logs must now be kept 5 years, not 2. The updated spec is on the task.

**The work gets checked against the rule**

> **Aayush:** @regmind-auditor done TSK-001, PR #4
>
> **regmind-auditor:** TSK-001 isn't complete yet. PR #4 is missing:
> • retention is 730 days in config/logging.yaml, it needs 1825 (rule changed to 5 years)
> • no object lock on the log bucket: add it in infra/s3.tf
>
> **Aayush:** @regmind-auditor fixed, done TSK-001, PR #5
>
> **regmind-auditor:** TSK-001 verified against PR #5 and marked complete.

---

## What happens when a rule changes

This is the core of RegMind.ai. When an amendment hits an existing obligation, the router checks the live status of its task and acts on it:

| Task status | What RegMind does |
|---|---|
| Not started | Rewrites the spec quietly. No noise. |
| Being built | Pauses the task and sends the engineer the new requirements in the chat. |
| Already shipped | Creates a separate change task for just the difference, keeping the shipped work intact. |
| Rule withdrawn | Deprecates the task so nobody builds something that's no longer needed. |
| New clause added | Creates a new obligation and sends it to regmind-spec to become a task. |

This decision is made in plain code, not by the AI, so it behaves the same way every time.

---

## How Switch is used

Switch is the backbone of RegMind.ai. Without it the agents would have no shared place to work with people.

- **One room, people and agents together.** The compliance officer, engineers and all five agents sit in the same `#regmind` room. Every handoff, approval and alert is a visible message.
- **Agents hand off by @mention.** intake mentions parser, parser mentions spec, router mentions the engineer. The room is the workflow.
- **Humans stay in control.** Nothing goes to engineering until a person approves in the chat. Engineers start and finish tasks by talking to the agents.
- **Works where the team already is.** Through Switch, the same room works in Slack, Teams, Discord or Mattermost.

Our agents are custom Google ADK agents that connect to the room through Switch's agent protocol.

---

## Under the hood

- **Reliable where it matters.** Splitting a circular into clauses, deciding what happens to a task after an amendment, and every status change are done in plain Python, so they are predictable. The AI is used for reading, classifying, writing specs and checking evidence.
- **Every AI decision is validated.** If an agent sends a wrong section number or category, the tool rejects it and the agent corrects itself, instead of bad data getting saved.
- **Clear task states.** Every task moves through open → ongoing → done → complete, with paused and deprecated for amendments. Invalid moves are blocked, so a paused task can't be marked done until it's resumed.
- **Full audit trail.** Every decision is logged with a timestamp: which circular was reviewed, who approved, what changed and why.

---

## Tech stack

- **Agents:** Google ADK with Gemini
- **Backend:** FastAPI (Python)
- **Database:** PostgreSQL (circulars, obligations, tasks, audit log, agent sessions)
- **Team chat:** Switch (Slack, Teams, Discord, Mattermost)
- **Documents:** PyMuPDF for reading circulars
- **Code checks:** GitHub API for pull request diffs

---

## Security and privacy

- **Secrets are masked before the AI sees anything.** API keys, passwords, tokens, private keys, emails and IP addresses in code diffs are replaced with placeholders before they're sent to the model.
- **The model is swappable.** ADK supports other models, so a bank can run RegMind on a model hosted inside its own infrastructure.
- **Everything is auditable.** Every agent action is recorded with a timestamp, ready for a regulatory inspection.

---

## What makes it different

Existing compliance tools stop at the compliance team: they extract obligations, assign an owner and track a checkbox. RegMind.ai goes all the way to verified engineering work.

- **Legal text in, developer-ready tasks out.** Engineers never have to read the circular.
- **Amendments update live work.** Tasks are paused, rewritten or split based on where they are, instead of just sending another alert.
- **Proof, not promises.** The auditor checks the actual code against the rule, so "done" means the rule is really met.
- **It lives in the chat.** No new dashboard to learn. The team works with the agents where they already talk.

---

## What's next

- Bring a coding agent like Claude Code or Codex into the room to implement tasks, with RegMind's auditor checking its work.
- Track the business and compliance-team obligations (reports, reviews) with reminders, not just the technical ones.
- Let the auditor flag pull requests that break a prohibitive rule, like a hardcoded shared password.
- Support RBI and other regulators.

---

## Team

**Team ASQUARE**

- Anshu Roy · 24bph025@nith.ac.in
- Aayush Dubey · dubeyaayushop@gmail.com

*The circulars used in the demo are mock documents written for this hackathon, not real SEBI circulars.*