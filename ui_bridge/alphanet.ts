/**
 * AlphaNet → UI connector.
 *
 * Copy this file into the frontend repo. It is the ONLY thing that should
 * know how AlphaNet stores a report; everything else in the UI works
 * against the types below.
 *
 * CONTRACT (do not work around these):
 *  1. The API is `report_versions.sections_json` — envelope contract
 *     v1.0.0 + `citation_map`. NEVER parse `final_report_md`. It is kept
 *     in the payload for debugging/export only; re-parsing markdown is
 *     the failure mode this whole contract exists to prevent.
 *  2. Run this SERVER-SIDE ONLY. It needs the Supabase service-role key,
 *     which bypasses RLS. RLS is fully closed and the key must never
 *     reach a browser. In Next.js: server components, route handlers, or
 *     `getServerSideProps` — never a client component.
 *  3. Blocks are pre-rendered analysis. The UI lays them out and styles
 *     them; it does not compute, re-derive, round, or convert units.
 *     Every number in AlphaNet carries lineage and a unit; changing one
 *     in the view layer breaks that chain.
 *
 * Generated against M&M report v5 / SONA v22, envelope contract 1.0.0.
 */

import type { SupabaseClient } from "@supabase/supabase-js";

/* ------------------------------------------------------------------ *
 * Blocks — the five envelope block types (s8_composer._BLOCK_REQUIRED)
 * ------------------------------------------------------------------ */

/** A citation string. One of:
 *   "AR.17" | "CC-May26.4" | "S-MARUTI" | "47"   → an evidence passage
 *   "calc:<formula_id>"                          → a computed value
 *   "sec:<LETTER>.<block_id>"                    → an upstream finding
 *   "edge:<id>" | "trail:<id>" | "event:<id>"    → graph / guidance / event
 *   a raw uuid                                   → legacy, still resolves
 */
export type Citation = string;

export interface NarrativeBlock {
  type: "narrative";
  id: string;
  title?: string;
  /** Markdown. May contain inline [LABEL] citation markers. */
  md: string;
  citations?: Citation[];
}

export interface MetricCardBlock {
  type: "metric_card";
  id: string;
  title?: string;
  metrics: Array<{
    name: string;
    value: number | string | null;
    /** "percent" | "x" | "inr_crore" | "inr" | "days" | "count" | … */
    unit?: string;
    /** "FY26" | "Q3FY26" | "TTM" — always present, always render it. */
    period?: string;
    /** "consolidated" | "standalone" — render it; the two are not mixable. */
    basis?: string;
    provenance?: Citation;
  }>;
  citations?: Citation[];
}

export interface TableBlock {
  type: "table";
  id: string;
  title?: string;
  columns: string[];
  /** Row cells align to `columns`. Mixed string | number | null. */
  rows: Array<Array<string | number | null>>;
  provenance?: Citation[];
  citations?: Citation[];
}

export interface RankedListBlock {
  type: "ranked_list";
  id: string;
  title?: string;
  items: Array<{
    rank: number;
    title: string;
    md: string;
    citations?: Citation[];
    /** What to watch for — render as a sub-line, it is a product feature. */
    monitorable?: string;
    severity?: string;
  }>;
  citations?: Citation[];
}

export interface FlagBlock {
  type: "flag";
  id: string;
  check: string;
  status: "OK" | "WATCH" | "FLAG";
  severity?: "low" | "medium" | "high";
  md: string;
  citations?: Citation[];
}

export type Block =
  | NarrativeBlock
  | MetricCardBlock
  | TableBlock
  | RankedListBlock
  | FlagBlock;

/* ------------------------------------------------------------------ *
 * Envelopes
 * ------------------------------------------------------------------ */

export interface Claim {
  text: string;
  /** Citation labels. Resolve via `resolveCitation`. */
  evidence_ids: Citation[];
  confidence?: number;
}

/** One management claim tested against a computed number (sections D1–D3
 *  produce these; D renders the scoreboard). The single most
 *  differentiated thing AlphaNet outputs — give it a real surface. */
export interface ClaimCheck {
  mgmt_claim: string;
  evidence_id: string | null;
  computed_ref: string | null;
  verdict: "corroborated" | "contradicted" | "unverifiable";
  note?: string;
  statement?: "D1" | "D2" | "D3";
  /** Present only when the model cited something unresolvable — audit
   *  trail, never render it. */
  evidence_id_raw?: string;
}

export interface Envelope {
  section: SectionLetter;
  blocks: Block[];
  claims?: Claim[];
  /** "Not found in sources" — a FIRST-CLASS output, not an error state.
   *  Gaps are reported, never papered over. Design a surface for these. */
  insufficiencies?: string[];
  claim_checks?: ClaimCheck[];
  followup_requests?: unknown[];
  credibility_notes_for_F?: string[];
  risk_candidates_for_H?: unknown[];
}

export type SectionLetter =
  | "B" | "C" | "D" | "D1" | "D2" | "D3"
  | "E" | "F" | "G" | "H" | "I" | "J";

export const SECTION_ORDER: SectionLetter[] = [
  "B", "C", "D", "D1", "D2", "D3", "E", "F", "G", "H", "I", "J",
];

export const SECTION_TITLES: Record<SectionLetter, string> = {
  B: "Business Overview",
  C: "Industry & Macro Context",
  D: "Financial Analysis",
  D1: "Profit & Loss (forensic)",
  D2: "Balance Sheet (forensic)",
  D3: "Cash Flow (forensic)",
  E: "Supply Chain",
  F: "Management, Governance & Guidance",
  G: "Peer Comparison",
  H: "Risks",
  I: "Valuation Context",
  J: "Key Takeaways",
};

/* ------------------------------------------------------------------ *
 * Citation map
 * ------------------------------------------------------------------ */

export interface CitationDocument {
  /** "AR.1–AR.54", "CC-May26.1–CC-May26.15", "S-MARUTI", "14–20" */
  label: string;
  doc_class: string;
  title: string;
  url: string;
  rows: number;
}

export interface CitationMap {
  /** citation label → evidence uuid */
  labels: Record<string, string>;
  documents: CitationDocument[];
}

/* ------------------------------------------------------------------ *
 * The bundle
 * ------------------------------------------------------------------ */

export interface ReportQuality {
  total: number;
  unresolved: number;
  verified_supported: number;
  verified_total: number;
}

export interface ReportBundle {
  ticker: string;
  companyName: string;
  entityId: string;
  version: number;
  generatedAt: string;
  envelopeContractVersion: string;
  runId: string | null;
  sections: Partial<Record<SectionLetter, Envelope>>;
  claimChecks: ClaimCheck[];
  citationMap: CitationMap;
  quality: ReportQuality;
  /** Pre-rendered snapshot markdown (section A). Deterministic, built in
   *  Python from computed values — the UI may render it as-is or read the
   *  same numbers off `section_*` metric_cards. */
  snapshotMd: string;
  /** Debug/export only. Do NOT parse. */
  finalReportMd: string;
}

/* ------------------------------------------------------------------ *
 * Fetchers  (server-side only — service-role key)
 * ------------------------------------------------------------------ */

export interface CompanyRef {
  entityId: string;
  name: string;
  ticker: string | null;
  latestVersion: number;
  generatedAt: string;
}

/** Every company that has at least one report. */
export async function listCompanies(
  db: SupabaseClient,
): Promise<CompanyRef[]> {
  const { data: entities, error: e1 } = await db
    .from("entities")
    .select("id, name, metadata")
    .eq("type", "company");
  if (e1) throw new Error(`listCompanies/entities: ${e1.message}`);

  const { data: reports, error: e2 } = await db
    .from("report_versions")
    .select("company_id, version, generated_at")
    .order("version", { ascending: false });
  if (e2) throw new Error(`listCompanies/reports: ${e2.message}`);

  const latest = new Map<string, { version: number; generated_at: string }>();
  for (const r of reports ?? []) {
    if (!latest.has(r.company_id)) {
      latest.set(r.company_id, {
        version: r.version,
        generated_at: r.generated_at,
      });
    }
  }
  return (entities ?? [])
    .filter((e) => latest.has(e.id))
    .map((e) => ({
      entityId: e.id,
      name: e.name,
      ticker: (e.metadata as { ticker?: string } | null)?.ticker ?? null,
      latestVersion: latest.get(e.id)!.version,
      generatedAt: latest.get(e.id)!.generated_at,
    }));
}

/**
 * Latest report for a ticker (as in `src/config.py` COMPANIES —
 * "SONACOMS", "M&M"). Pass `version` to pin a historical one: reports are
 * versioned precisely so "why did this say X last month" stays
 * answerable.
 */
export async function getReport(
  db: SupabaseClient,
  ticker: string,
  version?: number,
): Promise<ReportBundle | null> {
  const { data: entities, error: e1 } = await db
    .from("entities")
    .select("id, name, metadata")
    .eq("type", "company");
  if (e1) throw new Error(`getReport/entity: ${e1.message}`);

  const entity = (entities ?? []).find(
    (e) =>
      (e.metadata as { ticker?: string } | null)?.ticker?.toLowerCase() ===
      ticker.toLowerCase(),
  );
  if (!entity) return null;

  let q = db
    .from("report_versions")
    .select("version, generated_at, sections_json")
    .eq("company_id", entity.id);
  q = version != null
    ? q.eq("version", version)
    : q.order("version", { ascending: false });

  const { data, error } = await q.limit(1);
  if (error) throw new Error(`getReport/report: ${error.message}`);
  if (!data?.length) return null;

  const row = data[0];
  const sj = row.sections_json as Record<string, unknown>;

  const sections: Partial<Record<SectionLetter, Envelope>> = {};
  for (const letter of SECTION_ORDER) {
    const env = sj[`section_${letter}`] as Envelope | null | undefined;
    if (env) sections[letter] = env;
  }

  return {
    ticker,
    companyName: entity.name,
    entityId: entity.id,
    version: row.version,
    generatedAt: row.generated_at,
    envelopeContractVersion:
      (sj.envelope_contract_version as string) ?? "0.0.0",
    runId: (sj.run_id as string) ?? null,
    sections,
    claimChecks: (sj.claim_checks as ClaimCheck[]) ?? [],
    // Reports generated before the label change carry no citation_map;
    // their citations are raw uuids and resolve through `evidenceById`.
    citationMap: (sj.citation_map as CitationMap) ?? {
      labels: {},
      documents: [],
    },
    quality: (sj.quality as ReportQuality) ?? {
      total: 0,
      unresolved: 0,
      verified_supported: 0,
      verified_total: 0,
    },
    snapshotMd: (sj.snapshot_md as string) ?? "",
    finalReportMd: (sj.final_report_md as string) ?? "",
  };
}

/* ------------------------------------------------------------------ *
 * Citation resolution
 * ------------------------------------------------------------------ */

export type Resolution =
  | { kind: "evidence"; label: string; evidenceId: string;
      document: CitationDocument | null }
  | { kind: "computed"; formulaId: string }
  | { kind: "section"; section: SectionLetter | null; blockId: string;
      block: Block | null }
  | { kind: "edge"; id: string }
  | { kind: "trail"; id: string }
  | { kind: "event"; id: string }
  | { kind: "unresolved"; raw: string };

/**
 * Mirrors `s8_composer.resolve()` — including its precedence: the label
 * map is checked FIRST, because "AR.17" has the same <X>.<y> shape as a
 * bare upstream block id.
 *
 * `kind: "computed"` carries only the formula id: computed values are
 * derived at run time and are deliberately NOT persisted (derived ≠
 * observed), so there is no number to look up. Render these as a
 * provenance chip ("computed"), not as a link. See UI_HANDOFF.md §4.
 */
export function resolveCitation(
  cite: Citation,
  bundle: ReportBundle,
): Resolution {
  const c = String(cite).trim().replace(/^\[|\]$/g, "");

  const evidenceId = bundle.citationMap.labels[c];
  if (evidenceId) {
    return {
      kind: "evidence",
      label: c,
      evidenceId,
      document: documentForLabel(c, bundle.citationMap),
    };
  }

  if (c.startsWith("calc:")) {
    return { kind: "computed", formulaId: c.slice(5) };
  }
  if (c.startsWith("sec:")) {
    const body = c.slice(4);
    const dot = body.indexOf(".");
    const letter = (dot > 0 ? body.slice(0, dot) : null) as SectionLetter | null;
    const blockId = dot > 0 ? body.slice(dot + 1) : body;
    return {
      kind: "section",
      section: letter,
      blockId,
      block: findBlock(bundle, letter, blockId),
    };
  }
  if (c.startsWith("edge:")) return { kind: "edge", id: c.slice(5) };
  if (c.startsWith("trail:")) return { kind: "trail", id: c.slice(6) };
  if (c.startsWith("event:")) return { kind: "event", id: c.slice(6) };
  if (c.startsWith("evidence:")) {
    const body = c.slice(9);
    const id = bundle.citationMap.labels[body] ?? body;
    return {
      kind: "evidence",
      label: body,
      evidenceId: id,
      document: documentForLabel(body, bundle.citationMap),
    };
  }
  // legacy: a raw uuid, from a report generated before citation labels
  if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(c)) {
    return { kind: "evidence", label: c, evidenceId: c, document: null };
  }
  return { kind: "unresolved", raw: c };
}

/** The K-legend row a label belongs to. Document labels are ranges
 *  ("AR.1–AR.54", "14–20"); a passage label sits inside one. */
export function documentForLabel(
  label: string,
  map: CitationMap,
): CitationDocument | null {
  for (const d of map.documents) {
    if (d.label === label) return d;
    const [lo, hi] = d.label.split("–");
    if (!hi) continue;
    const stem = (s: string) => s.replace(/\.?\d+$/, "");
    if (stem(lo) === stem(label)) {
      const n = Number(label.replace(/^.*?(\d+)$/, "$1"));
      const a = Number(lo.replace(/^.*?(\d+)$/, "$1"));
      const b = Number(hi.replace(/^.*?(\d+)$/, "$1"));
      if (!Number.isNaN(n) && n >= a && n <= b) return d;
    }
  }
  return null;
}

/** Block ids appear both bare ("d2_bs_evolution") and section-prefixed
 *  ("B.b4b_concentration_metrics") — accept either, like the composer. */
export function findBlock(
  bundle: ReportBundle,
  letter: SectionLetter | null,
  blockId: string,
): Block | null {
  const search = letter && bundle.sections[letter]
    ? [bundle.sections[letter]!]
    : Object.values(bundle.sections);
  for (const env of search) {
    for (const b of env?.blocks ?? []) {
      if (b.id === blockId || b.id === `${env!.section}.${blockId}`) return b;
    }
  }
  return null;
}

/* ------------------------------------------------------------------ *
 * Drill-down: the passage behind a citation
 * ------------------------------------------------------------------ */

export interface EvidencePassage {
  id: string;
  text: string;
  pageOrTimestamp: string | null;
  documentTitle: string | null;
  documentUrl: string | null;
  docClass: string | null;
  publishedDate: string | null;
}

/**
 * The verbatim source text behind evidence uuids — this is what makes a
 * citation checkable rather than decorative. Wire it to click/hover on a
 * citation chip; it is the single highest-trust affordance in the product.
 */
export async function getEvidence(
  db: SupabaseClient,
  evidenceIds: string[],
): Promise<EvidencePassage[]> {
  if (!evidenceIds.length) return [];
  const { data: rows, error } = await db
    .from("evidence")
    .select("id, text, page_or_timestamp, source_document_id")
    .in("id", evidenceIds);
  if (error) throw new Error(`getEvidence: ${error.message}`);

  const docIds = [
    ...new Set((rows ?? []).map((r) => r.source_document_id).filter(Boolean)),
  ] as string[];
  const { data: docs } = docIds.length
    ? await db
        .from("source_documents")
        .select("id, title, url_or_path, published_date, metadata")
        .in("id", docIds)
    : { data: [] as Array<Record<string, unknown>> };

  const byId = new Map((docs ?? []).map((d) => [d.id as string, d]));
  return (rows ?? []).map((r) => {
    const d = r.source_document_id ? byId.get(r.source_document_id) : undefined;
    return {
      id: r.id,
      text: r.text,
      pageOrTimestamp: r.page_or_timestamp ?? null,
      documentTitle: (d?.title as string) ?? null,
      documentUrl: (d?.url_or_path as string) ?? null,
      docClass:
        ((d?.metadata as { doc_class?: string } | undefined)?.doc_class) ?? null,
      publishedDate: (d?.published_date as string) ?? null,
    };
  });
}

/**
 * Per-claim verification verdicts for a report's section envelope.
 * `verification_status` is 'verified' | 'failed' | 'pending' — a claim
 * the verifier could not fully support is 'failed'. Surfacing this is
 * the point of the verifier; do not hide failures.
 */
export async function getClaimVerification(
  db: SupabaseClient,
  knowledgeEntryId: string,
): Promise<Array<{ id: string; text: string; status: string;
                  evidenceIds: string[] }>> {
  const { data, error } = await db
    .from("claims")
    .select("id, text, verification_status, evidence_ids")
    .eq("knowledge_entry_id", knowledgeEntryId);
  if (error) throw new Error(`getClaimVerification: ${error.message}`);
  return (data ?? []).map((c) => ({
    id: c.id,
    text: c.text,
    status: c.verification_status,
    evidenceIds: c.evidence_ids ?? [],
  }));
}

/* ------------------------------------------------------------------ *
 * Display helpers — match the Python composer exactly so the UI and the
 * markdown export never disagree about a number.
 * ------------------------------------------------------------------ */

const UNIT_SUFFIX: Record<string, string> = {
  percent: "%",
  x: "×",
  inr_crore: " Cr",
  inr: "",
  days: " days",
};

/** Mirror of `s8_composer._fmt_value`. Formats only — never converts. */
export function formatValue(
  v: number | string | null | undefined,
  unit = "",
): string {
  if (v === null || v === undefined) return "—";
  let s: string;
  if (typeof v === "number") {
    s = v.toLocaleString("en-IN", { maximumFractionDigits: 1 });
  } else {
    s = String(v);
  }
  return `${s}${UNIT_SUFFIX[unit] ?? ""}`;
}

export const FLAG_TONE: Record<FlagBlock["status"],
  "ok" | "warn" | "alert"> = {
  OK: "ok",
  WATCH: "warn",
  FLAG: "alert",
};
