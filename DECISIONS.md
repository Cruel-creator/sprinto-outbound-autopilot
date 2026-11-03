# 5 Pre-Build Decisions

These five decisions come before any code: Outcome, Baseline, Workflow change, Measurement plan, Kill criterion. Each one maps to something the tool records. The run writes those numbers to `out/summary.md` (run metrics) and `out/review.csv` (the Growth Lead's verdicts).

## 1. Outcome definition: what improvement, for whom, measured how?

- **For whom:** Sprinto's Growth Lead, who runs outbound.
- **Improvement:**
  - Hands-on time per prospect drops from 15–20 minutes of research and writing to about 2 minutes of reviewing `report.md`.
  - The 12th email in a list is as specific as the 1st.
- **Measured by:**
  - Pipeline seconds per company (logged on every run).
  - Review minutes per company.
  - Share of emails sent with no rewrite.
  - Reply rate compared with the manual baseline.

## 2. Baseline: what the current state looks like in numbers

| Metric | Today (manual) | Source |
|---|---|---|
| Time per company | 15–20 min | Case brief |
| List size per batch | 8–15 companies | Case brief |
| Hands-on time per batch | 2–5 hours | 8–15 × 15–20 min |
| Quality across a list | drops by the end of the list | Case brief |
| Reply rate on manual cold email | **not measured yet**: log the next 30 manual sends before switching | to collect |
| Qualification accuracy | not measured; the Growth Lead's own judgement is the reference | to collect |

## 3. Workflow change: what human process must change for this tool to work?

1. **Research and writing stop.** The Growth Lead reviews instead. They read `report.md` for each company and fill in one row of `out/review.csv`:
   - `lead_agrees`: is this the right company and person?
   - `edit_level`: none / light / rewrite
   - `replied`: added later
2. **Change the rules, not the emails.** The Growth Lead owns `config/icp.yaml` (the ICP rules) and `sprinto_facts.md` (the claims emails may use). Fix a recurring mistake in those files, not by hand-editing each email.
3. **Override a contact with a CSV row.** If the Growth Lead already knows the right person, they add a row to `contacts.csv`, which overrides Hunter.
4. **Sends go to the Growth Lead first.** Every email goes to their own inbox (`TO_EMAIL`). They forward it to the prospect, which is the approval step.

## 4. Measurement plan: how will you know in 90 days if it worked?

| Metric | Where it comes from | Target at day 90 |
|---|---|---|
| Hands-on minutes per company | review time logged against `out/summary.md` | ≤ 3 min (from 15–20) |
| Emails forwarded with no or light edits | `edit_level` in `review.csv` | ≥ 70% |
| Agreement on company and person | `lead_agrees` in `review.csv` | ≥ 80% |
| Reply rate | `replied` in `review.csv` against the manual baseline | ≥ baseline |
| Thin-signal companies resolved by the agent loop | "fixed → agent" column in `summary.md` | most `INSUFFICIENT_DATA` decided without a human |
| Cost per email | Gemini calls in the trace; Hunter searches (25 a month) | inside free tiers |

Review at days 30, 60 and 90. `summary.md` rebuilds these numbers from `review.csv` on every run.

## 5. Kill criterion: at what point do you shut it down?

- **Immediately, any one of these:**
  - A sent email contains a claim about the prospect or Sprinto that the evidence ledger can't back up.
  - An email reaches anyone other than `TO_EMAIL`.
- **At day 30:**
  - more than 50% of drafts marked `rewrite`, or
  - `lead_agrees` below 60%.

  Either one means review costs as much as writing, so the tool saves nothing.
- **At day 90:**
  - reply rate below the manual baseline after at least 100 sends, or
  - hands-on time per company still over 8 minutes.

## How the thin-signal problem is handled

A fixed pipeline scrapes, extracts and qualifies whatever it finds. When the homepage says little, the qualification is a guess and the hook is generic.

This pipeline handles that case in three ways:
- **Score bounds:** it scores with a low and a high bound. While the 60-point bar sits between them, the answer isn't known yet.
- **Agent loop:** it keeps fetching until the verdict is decided. It can fetch a page, run a grounded search or check job boards. The loop is capped at 4 tool calls, 2 searches and 120 s.
- **No guessing:** if the loop is still undecided, the company is marked `INSUFFICIENT_DATA` and no email is sent.

Each `report.md` shows the verdict a fixed pipeline would have given, the loop's final verdict, and the tool calls that changed it.
