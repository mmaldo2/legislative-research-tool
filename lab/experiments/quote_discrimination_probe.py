"""HARDER discrimination probe for family10.quote_in_bill_text (Slice B GATE) -- NON-FROZEN experiment.

Status: the EASY probe (short inline text) leaned non-discriminating -- haiku caught 6/6 near-misses.
This is the harder re-probe the scope gate requires before any build: LONG bills, deterministic DEEP
single-word alterations buried mid-span, more candidates. It doubles as a prototype of the
deterministic adversarial-negative generator the build would need.

Run OUT-OF-SESSION with a dedicated key so the subscription rate limit does not block sonnet/opus:
    ANTHROPIC_API_KEY=sk-ant-api03-... PYTHONPATH=. uv run python -m lab.experiments.quote_discrimination_probe
(Falls back to the OAuth subscription client if ANTHROPIC_API_KEY is unset -- which WILL rate-limit
during an interactive session.)

GO bar: a clear capability gradient (haiku < sonnet < opus) on near-miss exclusion. If every model aces
it even here, deprioritize the flagship (it is vote_lookup-class). This is a measurement, not a build;
never tune the items to manufacture a gradient.
"""

import asyncio
import json
import os
import re

from lab.harness import get_connection

MODELS = [
    ("haiku", "claude-haiku-4-5"),
    ("sonnet", "claude-sonnet-4-6"),
    ("opus", "claude-opus-4-8"),
]

# Deterministic deep single-word swaps: semantically plausible, but not verbatim. Tried in order.
SWAPS = [
    ("shall not", "may not"),
    ("may not", "shall not"),
    (" shall ", " may "),
    ("Secretary", "Director"),
    ("annually", "quarterly"),
    ("biennially", "annually"),
    ("not less than", "not more than"),
    ("not more than", "not less than"),
    ("each", "every"),
]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def make_client():
    """Dedicated API key if set (no shared rate limit); else the OAuth subscription client."""
    import anthropic

    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return anthropic.AsyncAnthropic(api_key=key)
    from src.api.deps import get_oauth_anthropic_client

    return get_oauth_anthropic_client()


def deep_negative(span: str, full_norm: str) -> str | None:
    """Apply ONE deterministic deep edit to a span so it is no longer verbatim but stays plausible:
    first a numeric tweak (increment the first standalone integer past the first few words), else a
    swap-map substitution. Returns the altered span, or None if no edit yields a true non-substring."""
    words = span.split(" ")
    # numeric tweak (skip the first 5 words so the edit is buried, not at the head)
    for i in range(5, len(words)):
        if re.fullmatch(r"\d{1,4}", words[i]):
            alt = words.copy()
            alt[i] = str(int(words[i]) + 1)
            cand = " ".join(alt)
            if norm(cand) not in full_norm:
                return cand
    # swap-map substitution (first occurrence past the head)
    for old, new in SWAPS:
        idx = span.find(old, 25)
        if idx != -1:
            cand = span[:idx] + span[idx:].replace(old, new, 1)
            if norm(cand) not in full_norm:
                return cand
    return None


def build_candidates(full_norm: str, n_pos: int = 4, span_words: int = 34):
    """Deterministic long spans from deep in the body: n_pos positives + a deep-edited negative for
    each that admits an edit. Returns (candidates, gold_texts). Skips the first ~70 words (preamble)."""
    words = full_norm.split(" ")
    body_start = 70
    usable = len(words) - body_start - span_words
    if usable <= 0:
        return [], set()
    positives, negatives = [], []
    # evenly spaced, deterministic offsets across the body
    for k in range(n_pos):
        off = body_start + (usable * k) // max(1, n_pos)
        span = " ".join(words[off : off + span_words])
        if norm(span) not in full_norm:  # defensive (should always hold)
            continue
        positives.append(span)
        neg = deep_negative(span, full_norm)
        if neg:
            negatives.append(neg)
    cands = [(t, True) for t in positives] + [(t, False) for t in negatives]
    cands.sort(key=lambda it: it[0])  # content-ordered, so position != verbatim-ness
    return cands, {t for t, v in cands if v}


SYSTEM = (
    "You verify whether candidate quotes appear VERBATIM in a bill's text. Verbatim means the exact "
    "wording, word-for-word, ignoring only whitespace/line-break differences. A quote that is "
    "paraphrased, reworded, or has ANY single word changed (a different term or number) is NOT "
    "verbatim, even if it means the same thing. The alteration may be buried mid-sentence. Respond "
    'with ONLY a JSON object {"verbatim_ids": [ids that are verbatim]}. No other text.'
)


def parse_ids(txt: str) -> set:
    m = re.search(r"\{.*\}", txt, re.DOTALL)
    if not m:
        return set()
    try:
        return set(json.loads(m.group(0)).get("verbatim_ids", []))
    except Exception:
        return set()


async def create_with_retry(client, **kw):
    import anthropic

    for attempt in range(3):
        try:
            return await client.messages.create(**kw)
        except anthropic.RateLimitError:
            wait = 20 * (attempt + 1)
            print(f"        (429; waiting {wait}s -- use a dedicated ANTHROPIC_API_KEY to avoid this)")
            await asyncio.sleep(wait)
    raise RuntimeError("rate limited after retries")


async def ask(client, model_id, full_norm, candidates):
    lines = "\n".join(f"{qid}: {t}" for qid, t in candidates)
    user = (
        f"Bill text (whitespace-normalized):\n{full_norm}\n\n"
        f"Candidate quotes:\n{lines}\n\n"
        "Which candidate ids appear verbatim in the bill text?"
    )
    resp = await create_with_retry(
        client, model=model_id, max_tokens=400, system=SYSTEM,
        messages=[{"role": "user", "content": user}],
    )
    txt = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    await asyncio.sleep(2)
    return parse_ids(txt)


async def main():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT b.identifier, bt.content_text FROM bill_texts bt JOIN bills b ON b.id=bt.bill_id "
        "JOIN sessions s ON s.id=b.session_id WHERE s.identifier='119' "
        "AND bt.word_count BETWEEN 2500 AND 8000 ORDER BY bt.bill_id LIMIT 3"
    )
    bills = [(ident, norm(ct)) for ident, ct in cur.fetchall()]
    conn.close()

    by_bill, gold, meta = {}, {}, {}
    for ident, full_norm in bills:
        cands_raw, gold_texts = build_candidates(full_norm)
        cands, g = [], set()
        for i, (text, is_v) in enumerate(cands_raw, 1):
            qid = f"{ident}-q{i}"
            cands.append((qid, text))
            meta[qid] = "pos" if is_v else "neg"
            if is_v:
                g.add(qid)
        by_bill[ident] = (full_norm, cands)
        gold[ident] = g

    n = sum(len(c) for _f, c in by_bill.values())
    npos = sum(len(g) for g in gold.values())
    print(f"HARDER probe: {n} candidates ({npos} verbatim / {n - npos} deep near-miss) over "
          f"{len(bills)} long bills ({[b for b, _ in bills]})\n")

    client = make_client()
    for label, model_id in MODELS:
        exact = neg_caught = neg_total = pos_hit = pos_total = 0
        wrong = []
        try:
            for ident, (full_norm, cands) in by_bill.items():
                ans = await ask(client, model_id, full_norm, cands)
                g = gold[ident]
                exact += ans == g
                for qid, _t in cands:
                    is_v = qid in g
                    said = qid in ans
                    if is_v:
                        pos_total += 1
                        pos_hit += said
                        if not said:
                            wrong.append(f"{qid}(pos)MISSED")
                    else:
                        neg_total += 1
                        neg_caught += not said
                        if said:
                            wrong.append(f"{qid}(neg)FOOLED")
        except RuntimeError:
            print(f"{label:7s} {model_id:20s} | RATE-LIMITED (skipped) -- run with a dedicated key")
            continue
        print(f"{label:7s} {model_id:20s} | bills-exact {exact}/{len(bills)} | "
              f"near-miss caught {neg_caught}/{neg_total} | verbatim found {pos_hit}/{pos_total}")
        if wrong:
            print("        ", ", ".join(wrong))


if __name__ == "__main__":
    asyncio.run(main())
