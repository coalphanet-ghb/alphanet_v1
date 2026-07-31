# PIPELINE BACKLOG — the next optimisation era

> Opened 2026-07-27 by the owner, mid-way through the UI work. These are
> **not yet plans** — they are the shape of the next pipeline rethink,
> captured while the reasoning was fresh so it is not lost. Each will be
> turned into a proper phased plan (with gates) before anything is
> built.
>
> Sequencing note: this era comes AFTER the current UI/snapshot work.
> Nothing here is in flight. Where a claim below was verified against
> the live system it says **[verified]**; where it is a proposal it says
> **[owner suggestion]**.

---

## 1. The report may be the wrong shape — atomic claims, not paragraphs

**The owner's observation.** For the UI, what is actually needed is
atomic sentences, not long explanatory prose. The useful unit is:

> an **atomic claim**, **mapped to its section**, carrying a
> **verification tail**.

If that is the deliverable, then the long paragraph-writing half of
synthesis deserves a hard look: how much of it is genuinely load-bearing
versus expensive prose nobody reads?

### What already exists [verified 2026-07-27]

Most of the substrate is built:

- **Claims are already atomic by contract.** `ENVELOPE_CONTRACT` rule 3a:
  *"Claims are ATOMIC and PURELY evidence-backed: one fact per claim,
  fully contained in its cited passage(s)."* Real stored example:
  `"Management claimed FY26 EBITDA growth was 13.5%."`
- **They are already section-scoped** — every claim hangs off a
  `knowledge_entries` row whose `section` is `section_B` … `section_J`.
- **They are already verified** — s9 checks each against its cited
  evidence text; latest run 130 verified / 23 failed / 0 pending.
- **Source passages are already section-mapped at ingestion**
  (Round 4.2: each passage carries `sections: [B..I]`), so "which
  sections can this document feed" is answered at read time.
- **Claims already carry citation labels** in the envelope
  (`evidence_ids: ["AR.47"]`) with `citation_map` resolving to uuids —
  so a UI footnote is already renderable.

So the owner's read is right: **this much is already happening.**

### The gaps that stop it being the product [verified]

1. **Per-claim verdicts do not reach `sections_json`** — a stored claim
   is `{text, claim_id, confidence, evidence_ids}`, no verdict field.
   **Owner ruling 2026-07-27: this is NOT a gap.** Under the refined
   direction below, the UI renders *blocks*, not claims; verification
   stays an internal quality mechanism, and the aggregate `quality`
   object already ships. What a reader needs beside a statement is
   simply **the source it came from**, not a four-way verdict taxonomy.
   **One condition attaches to that ruling:** if raw claim text ever
   *does* surface in the UI, its verdict must surface with it, or
   filtering must guarantee only verified claims render — the latest
   run had 130 verified and **23 failed**, and showing those 23
   unmarked would present unverified assertions as fact, which the
   honesty posture forbids. Decide that explicitly when the time comes;
   do not let it happen by default.
2. **Computed insights never enter the claims layer at all.** Claims
   citing `calc:` or `sec:` are stripped and not persisted, because the
   verifier can only check a sentence against evidence *text*. That is
   deliberate (rule 3a) but it means every number-derived insight —
   often the most valuable analysis — exists only as prose inside a
   block. Currently ~21–28% of emitted claims are dropped this way
   (HANDOFF4 §6). If claims become the product, this class needs a
   home: either a second verification mode for calc-backed claims
   (deterministic — check the number against the computed table), or an
   explicit "computed insight" object that is checked differently.
3. **Claims are an unordered audit list, not a reading order.** They are
   emitted as a flat array per section with no ranking, grouping or
   narrative sequence. A section rendered as bare claims today would
   read as disconnected bullets.
4. **There is no "synthesised insight" object.** Cross-evidence
   conclusions ("margin compression is acquisition-driven, not
   operational") live inside narrative prose. Nothing in the schema
   represents a one-line insight that is *derived* rather than quoted.

### The direction [owner, refined 2026-07-27]

An earlier framing — "assemble sections out of claims plus synthesised
one-liners" — was **set aside** as too large a change: it would have
made claims the product, forcing an answer to how derived insights get
verified and how a flat claim array becomes a reading order.

**The refined direction is smaller and better scoped:**

> **Synthesis stays the primary producer. Only its output STYLE
> changes: terse, properly-ordered bullet points per section, instead
> of explanatory paragraphs — because bullets are what the UI renders.**

Why this is the better version of the same instinct:
- **No schema revolution.** Blocks stay blocks; `narrative.md` simply
  carries terse ordered bullets rather than prose. Envelope contract
  v1.0.0 may survive untouched, so no frontend coordination cost.
- **The claims layer is untouched** — it stays exactly what it is
  today, the internal verification spine (which is why gap 1 above
  stops mattering).
- **The cost saving is on the expensive side.** Prose is output
  tokens, and output is ~4× the price of input; terser sections cut
  the dominant half of the bill.
- **It is testable on one section** before committing to all twelve.

Open questions before this becomes a plan:
- Does a bullet-form section still read as institutional research, or
  does it read as a dump? Test on one section (F or D1) and read it
  against the current version side by side.
- Terseness has bitten before: rule 9 (reason briefly) once produced a
  section with **zero claims and zero insufficiencies** because the
  model economised on the envelope itself. Any style instruction must
  again say explicitly that brevity applies to PROSE, never to
  required blocks, the claims floor, or insufficiencies.
- Does `final_report_md` (the markdown rendering) still make sense, or
  does it become a by-product? **Now measurable (2026-07-30):** it is
  **35.4% of every stored report** — 154.8 KB of the latest 438 KB row —
  and fully derivable from the section blocks by the composer. Dropping
  it is worth ~18 MB per coverage pass and ~35% of every refresh
  thereafter, against a Supabase free ceiling of 500 MB that first
  coverage plus ~2 refreshes already reaches. It also halves the ~430 KB
  the report-detail page pulls per view, which sets a ceiling of roughly
  11,600 views/month on 5 GB of free egress. Full projection:
  `INFRASTRUCTURE.md §4.1–4.2`. This is no longer only a "does the shape
  make sense" question — it is the cheapest storage lever on the board.
- Which blocks are genuinely load-bearing? The UI mapping exercise
  (HANDOFF4 §7.2) answers this — **do it first**, since it is the
  evidence for what to keep.

### Does the passage index (`AR.47`) matter to anyone? [owner question]

Citation labels are `<doc-mnemonic>.<passage-index>` — `AR.47`,
`CC-May26.4`, `S-MARUTI`. The index is **load-bearing machinery**: it is
what resolves a citation to one specific passage uuid via
`citation_map`, and "AR" alone cannot — SONA's annual report alone
contributes 136 passages.

But **it is almost certainly meaningless to a reader.** What a user
wants beside a statement is "Annual Report FY26" or "Q4 FY26 earnings
call" — ideally with the passage text one click away — not `AR.47`.

So the question for the UI mapping exercise is not whether to keep the
index (we must) but **what the UI should display in its place**:
- a human source name per citation (needs a doc-title lookup shipped
  alongside `citation_map` — we have the titles, they are just not in
  the payload), and
- optionally the passage text itself, for a hover or expand.

Worth settling at the same time as §1, since both are about what a
citation looks like to a human rather than to the resolver.

## 2. Is the verifier worth its tokens?

**The owner's question**, to be answered with data, not opinion.

Facts to start from [verified]:
- The verifier is now the **most expensive single node** in a run
  (~$0.06–0.09; on the latest run 9 calls, 27.7K in / 20.2K out).
- Latest quality: 140/170 supported ⇒ **17.6% not fully supported**,
  inside the historical 6–16% band's neighbourhood.
- Efficiency work already done: excerpt dedup (Round 2.2, roughly
  halved verifier input), budget raised to 12 batches so coverage is
  complete.
- It is a **product feature** by standing decision (FOUNDATIONS §3.4 —
  the cheapest, highest-leverage trust lever), so the question is
  *efficiency and design*, never *whether to keep coverage*.

Questions to answer:
- What do failed verdicts actually change? Do "partial" verdicts ever
  cause a reader to distrust a correct number — i.e. is the failure
  signal itself noisy?
- Should calc-backed claims get a **deterministic** verifier (compare
  the asserted number to the computed table) rather than being dropped?
  That would be cheaper *and* stronger than the LLM check.
- Can verification move to the claim's *own* generation step, instead
  of a separate pass over everything?
- Is `confidence` (emitted per claim, currently unused) worth anything?

## 3. The spec / skill nodes will need rewriting

If §1 changes the output shape, then every `nodes/*/spec.md` — which is
where "how to analyse this section, what to look for, what to avoid"
lives — is written for the wrong deliverable. Same for the
`ENVELOPE_CONTRACT` block types and the sector-pack overlays.

This is not a separate project; it is the implementation surface of §1.
Noted separately only because it is easy to underestimate: the specs
**are** the prompts (`src/specs.py` parses them at runtime), so
rewriting them *is* rewriting the product's behaviour, and every one
needs its own `diff_golden` cycle.

---

## Suggested order when this era opens

1. **UI mapping exercise first** (already the plan of record, HANDOFF4
   §7.2) — it tells us which blocks are actually rendered, which are
   dead weight, and what a citation should look like to a human.
   Everything below should be decided from that evidence, not before it.
2. **Prove the style change on ONE section** — terse ordered bullets for
   F or D1, read side by side against the current output, with the
   brevity-never-applies-to-required-blocks guard in place. Cheap, and
   it either validates the direction or kills it before twelve specs
   get rewritten.
3. **Then §2** (verifier design review) — its answer, especially
   deterministic checking of calc-backed claims, changes what §1 can
   assume about which insights are checkable.
4. **Then §1 as a real plan**, with §3 (spec rewrites) as its
   implementation surface.
