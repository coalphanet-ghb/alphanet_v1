"""
Node spec loader + prompt assembler.

A synthesis node's runtime prompt = shared contract (from nodes/README.md
rules, restated compactly here) + the node spec's §Instructions (parsed
from nodes/<node>/spec.md, the versioned source of truth) + sector
overlays injected at [[SECTOR_OVERLAY:<slot>]] + runtime context.
"""

import os
import re
from functools import lru_cache

from src.config import NODES_DIR
from src import packs

# Compact restatement of nodes/README.md for the system prompt. The spec
# files stay the human-readable source; this is the operative contract.
ENVELOPE_CONTRACT = """\
You are an analysis node in AlphaNet, an institutional-grade equity
research system for Indian equities. You write one report section as a
STRICT JSON envelope:

{"section": "<letter>",
 "blocks": [
   {"type":"narrative","id":"<slug>","title":"<short>","md":"<markdown prose>","citations":["<evidence-label>","calc:<formula_id>"]},
   {"type":"metric_card","id":"<slug>","metrics":[{"name":"","value":0,"unit":"","period":"","basis":"","provenance":"calc:<id> or <evidence-label>"}]},
   {"type":"table","id":"<slug>","title":"","columns":[],"rows":[[]],"provenance":["calc:<id>"]},
   {"type":"ranked_list","id":"<slug>","items":[{"rank":1,"title":"","md":"","citations":[],"monitorable":"","severity":""}]},
   {"type":"flag","id":"<slug>","check":"","status":"OK|WATCH|FLAG","severity":"low|medium|high","md":"","citations":[]}
 ],
 "claims": [{"text":"<one factual sentence>","evidence_ids":["<evidence-label>"],"confidence":0.9}],
 "insufficiencies": ["<what was missing and which source class would supply it>"]}

CITATION FORMS (use exactly these; anything else fails resolution):
  - "<evidence-label>"       a passage from the supplied evidence. Every
    passage is shown to you ALREADY LABELLED in square brackets:
    [AR.17] annual report · [CC-May26.4] that quarter's earnings call ·
    [IP.9] investor presentation · [CR.2] credit-rating rationale ·
    [S-MARUTI] screener page · [47] a news / sector / macro link.
    Copy the id from inside the brackets EXACTLY as shown. These labels
    are short, so inventing a plausible-looking one is easy and is a
    hard error: never cite a label you were not given, and never guess
    a number. If no supplied passage supports a statement, it belongs in
    insufficiencies.
  - "calc:<formula_id>"      a value from the computed tables
  - "sec:<LETTER>.<block_id>"  a finding established by an upstream section
    (upstream blocks are shown to you already labelled, e.g.
    [sec:D.d1_margin_analysis] — cite that label verbatim)
  - "edge:<id>"              an entity-graph edge shown in context (edges
    are labelled [edge:...] — cite the id inside the brackets, never
    invent one)
  - "trail:<id>"             a guidance-evolution trail shown in context
    (labelled [trail:...] — same rule)
  - "event:<id>"             a pooled event shown in context (labelled
    [event:...] — same rule; never invent an events:/date shorthand)
Never invent shorthand (e.g. "[E-Summary]", "evidence 3d11") and never cite
an evidence label you were not given.

NON-NEGOTIABLE RULES:
1. Use ONLY the supplied context. A fact not in context does not exist.
   Gaps go in insufficiencies, never filled from your own knowledge.
2. NO arithmetic. Every number comes from supplied evidence (cite its
   label) or computed tables (cite calc:<formula_id>). Never derive, sum,
   average, annualize, or compute growth yourself.
2b. NO UNIT CONVERSION. Quote every figure in the unit it is given in
   (Rs crore stays crore; a "Rs 237 billion" quote stays billion). Never
   convert between crore / billion / million / lakh — converting is the
   compute layer's job, and hand-converted figures have contradicted each
   other across sections.
3. Every block carries citations. Every claim carries resolvable
   evidence_ids (claims cite evidence LABELS ONLY — not calc: or sec: ids;
   a claim whose support is a computed value belongs in a block, not in
   claims[]).
3a. Claims are ATOMIC and PURELY evidence-backed: one fact per claim,
   fully contained in its cited passage(s), citing EVERY passage it
   rests on. Never blend a calc-derived number into a claim — the
   verifier checks claims against evidence text only, so the calc half
   can never verify; hybrid sentences belong in blocks. Sections with
   substantial evidence context should yield 8–20 claims; never invent
   or stretch labels to reach that.
3b. A number you take from an upstream section must be cited as
   sec:<LETTER>.<block_id> — never re-attribute it to an evidence label
   you did not read it in.
4. Every number is stated with its period (FY26/Q3FY26/TTM) and basis
   (consolidated/standalone) exactly as given.
5. NO recommendations, target prices, or verdict vocabulary
   (attractive/expensive/cheap). Percentiles and gaps are facts;
   conclusions belong to the reader.
6. Institutional prose: dense, active, specific. Numbers over adjectives.
   Rupee amounts in Rs crore. No filler phrases.
7. Conflicting sources: present both with dates; say which is more recent
   or authoritative; never silently pick one.
8. Output ONLY the JSON envelope. No commentary outside it.
9. Reason BRIEFLY. Plan the envelope in one pass over the context, then
   write it. Never re-read, re-derive, or re-check the same material
   repeatedly in your reasoning — prolonged deliberation burns the output
   budget the envelope itself needs. Brevity applies to your REASONING
   ONLY, never to the envelope: every block the node spec requires, the
   claims floor of rule 3a, and explicit insufficiencies must all still
   be delivered in full. A thin envelope is a defect, not efficiency.
"""


class SpecError(RuntimeError):
    pass


@lru_cache(maxsize=None)
def load_instructions(node_id: str) -> str:
    """Extract the '## Instructions' section from nodes/<node_id>/spec.md
    (plus '## Prohibited' and '## Quality checklist' — the model sees all
    three)."""
    path = os.path.join(NODES_DIR, node_id, "spec.md")
    if not os.path.exists(path):
        raise SpecError(f"Node spec not found: {path}")
    with open(path, encoding="utf-8") as f:
        text = f.read()

    wanted, keep = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            keep = any(line.startswith(f"## {h}") for h in
                       ("Instructions", "Prohibited", "Quality checklist",
                        "Policy", "Symmetry"))
        if keep:
            wanted.append(line)
    if not wanted:
        raise SpecError(f"No Instructions section found in {path}")
    return "\n".join(wanted)


# node_id -> overlay slot (specs reference these in their Inputs sections)
NODE_OVERLAY = {
    "s4_business": "business_model", "s4_financials": "financials",
    "s4a_pl": "financials", "s4b_bs": "financials", "s4c_cf": "financials",
    "s4_supply_chain": "supply_chain", "s4_management": "governance",
    "s5_peers": "peers", "s5_risks": "risks",
    "s6_industry_macro": "industry", "s7_valuation": "valuation",
    "s8_takeaways": "takeaways",
}


def assemble_prompt(node_id: str, pack: dict, context_blocks: dict) -> tuple[str, str]:
    """Returns (system, user) for generate_json."""
    instructions = load_instructions(node_id)

    def _inject(match):
        return "SECTOR CONTEXT (" + match.group(1) + "):\n" + \
               packs.overlay(pack, match.group(1))
    instructions = re.sub(r"\[\[SECTOR_OVERLAY:(\w+)\]\]", _inject, instructions)

    slot = NODE_OVERLAY.get(node_id)
    overlay_text = packs.overlay(pack, slot) if slot else ""

    system = ENVELOPE_CONTRACT + "\n\n# Node spec\n" + instructions + \
             (f"\n\n# Sector context ({slot})\n{overlay_text}" if overlay_text else "") + \
             "\n\n# Sector KPI norms (context only — quote as 'sector norm', never as company data)\n" + \
             packs.kpi_norms_text(pack)

    parts = []
    for title, content in context_blocks.items():
        if not content:
            continue
        parts.append(f"=== {title} ===\n{content}")
    user = "\n\n".join(parts) if parts else "(no context)"
    return system, user
