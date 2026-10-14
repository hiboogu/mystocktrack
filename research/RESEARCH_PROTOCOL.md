# mystocktrack event-driven research protocol (no external LLM API)

Inspired by the openly licensed InvestSkill research framework: https://github.com/yennanliu/InvestSkill . This document is a research checklist, **not** executable multi-agent code.

## Non-negotiable evidence gates
1. Record the research timestamp and market-session cutoff; label prices as close, intraday or delayed. Never combine periods without disclosure.
2. For each ticker, collect (a) a recent company filing/IR announcement, (b) the preceding 30-day event or explicitly say NOT VERIFIED, (c) macro/sector/counterparty implications, (d) a bear-case counterargument, (e) what would invalidate the thesis.
3. Distinguish FACT from INTERPRETATION from UNKNOWN; never claim causal attribution solely from simultaneous moves.
4. No invented price/RSI/MA/flow/return estimates. Stop quant scoring if the market snapshot is missing.
5. Treat stocks in portfolio.toml as positions; all others as watch-only. Holdings calculation uses one frozen, timestamped snapshot.
6. GPT in ChatGPT is a *separate manually performed analysis*, not an OpenAI API invocation and not execution of ClaudeLLM. Never label it as Python multi-agent output.
7. Never claim Skill was executed as code: a Markdown skill is an analyst procedure unless the host provides a skill runtime.
8. Produce: source ledger, 11-stock event matrix, positive thesis, strongest bear countercase, trigger/invalidation conditions, coverage gaps, and separate model output locations.

## Event propagation
Event -> directly affected firm -> customers/suppliers -> financial exposure -> valuation impact -> observed prices -> competing explanations -> falsification check.

## High priority for semiconductor NVDA/AMD
Compare Korea (Samsung/SK Hynix), US memory (Micron), China CXMT, GPU vendors (NVDA/AMD), SOX, and yields. HBM and commodity/server DRAM are distinct. Do not assume an HBM supply loss without direct evidence.

## Skill provenance
Referenced: https://github.com/yennanliu/InvestSkill/blob/main/prompts/catalyst-calendar.md and stock-eval / bear-case methods. No auto-installer run, no OpenAI key, no external AI API billed.
