# Two-hour GIFT City presenter runbook

**Session:** From Agent Demo to Production — Building Two Multi-Agent Systems on AWS  
**Time:** 09:00–11:00 (120 minutes including five-minute break)  
**Room:** bright projector; slides intentionally white, dark text, no low-contrast code screenshots.  
**Presenter background to use:** Senior software engineer, cloud/DevOps experience, AWS Community Builder (DevOps) and AWS New Voices. Keep introduction accurate to your own bio; do not exaggerate company affiliation or claims.

## Preflight 20 minutes before doors open

```bash
cd <unzipped-project-folder>
python --version
python -m unittest discover -s tests -v
python -m agent_workshop.cli race
python -m agent_workshop.cli mr-risky
python -m agent_workshop.web
```

Open http://127.0.0.1:8765 in Chrome or Edge, zoom to 125–150%, and put the browser in presenter-friendly fullscreen. Turn on Do Not Disturb. Close production AWS consoles, personal browser tabs and any apps showing sensitive material. Keep a second terminal ready with `python -m agent_workshop.cli all`. If conference Wi-Fi is absent, your offline demos still run. Use the optional AWS Strands examples **only** if rehearsed against an allowed Bedrock model in the correct region with permissions and budgets.

## Minute-by-minute stage map

| Clock | Time | Topic | Required outcome |
|---|---:|---|---|
| 09:00–09:05 | 5 min | 3 market numbers, why listen, production question | Hook + credibility |
| 09:05–09:25 | 20 min | Agent loop, controls, patterns and research | Audience can choose single vs multiple agents |
| 09:25–09:45 | 20 min | **Demo 1** appointment concierge | Booking, idempotency, race, escalation |
| 09:45–10:00 | 15 min | Harness vs Runtime, Gateway vs Registry | Clear service boundaries |
| 10:00–10:05 | 5 min | Break | Reset demo |
| 10:05–10:23 | 18 min | **Demo 2** security-aware MR review | Evidence, independent specialists, policy |
| 10:23–10:43 | 20 min | Safety, evals, metrics, economics, rollout | Production readiness checklist |
| 10:43–10:52 | 9 min | Build vs buy, AWS DevOps Agent | Honest comparison |
| 10:52–11:00 | 8 min | Papers, practical exercises, Q&A | Attendees know what to do next |

### 09:00–09:05 — Five-minute script (say in your own voice)

**00:00–01:00.** “Good morning, GIFT City. Let me ask a simple question: who has waited on a call to book a doctor or service appointment? Imagine sending one message: ‘Friday after 5 PM, please.’ The system checks availability and replies with a confirmed slot. Now imagine twenty people asking for that one slot. Does your agent still work? Today we will see why the agent that speaks beautifully isn't necessarily the system that books correctly.”

**01:00–02:15.** “The stakes are huge. NVIDIA reported $115.8 billion in quarterly revenue in November 2026. Anthropic closed an IPO with about $93.5 billion of *gross offering proceeds* — not revenue. Gartner predicted in 2025 that more than 40% of agentic AI projects could be canceled by end of 2027. These three numbers are not directly comparable: company revenue, capital raised and a forecast. But they suggest the same important question: where does investment turn into useful software?”

**02:15–03:15.** “AI has a deep stack: semiconductor machinery, chip design, data centers, cloud platforms, models, orchestration and end-user applications. I am not going to teach chip physics today. I want to focus on the layer that engineers in this room can control: the tools agents use, the decisions they can make, and the processes that tell us when the result is trustworthy.”

**03:15–04:15.** “A quick introduction: I'm a senior software engineer working with cloud systems and DevOps and I'm active in AWS Community Builders and AWS New Voices. My experience is the operational side of software: what fails, how we debug it, what we deploy and how we recover. Many of you have more experience than me. Please challenge the design choices. Students, please ask the basic questions: those are often the best ones.”

**04:15–05:00.** “We will build two very different systems. One serves a customer. The second helps evaluate a GitLab merge request. Both will teach us the same key point: AI agents can propose actions; code and policy must decide what is safe to commit. Let's begin with the smallest useful agent loop.”

**Citations to display in your handout, not read aloud:** [NVIDIA earnings](https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Announces-Financial-Results-for-Third-Quarter-Fiscal-2027/); [Anthropic IPO closing](https://www.anthropic.com/news/ipo-close); [Gartner 2025 forecast](https://www.gartner.com/en/newsroom/press-releases/2025-06-25-gartner-predicts-over-40-percent-of-agentic-ai-projects-will-be-canceled-by-end-of-2027).

## Deep teaching: 09:05–09:25

Start with **chatbot / deterministic workflow / agent**. Chatbot generates response. Workflow code controls the steps. Agent uses a model to select a bounded next action from tools and interprets observations. The model is not your permissions engine. Teach this pseudocode:

```text
for step in 1..MAX_STEPS:
  proposed_tool = model(goal, context, tool_descriptions)
  validate_schema(proposed_tool.args)
  authorize(identity, proposed_tool.name, proposed_tool.args)
  result = invoke_tool_with_timeout_and_idempotency()
  append_observation_to_scoped_context(result)
  if goal_satisfied_and_verified(): stop
fail_closed_or_handoff()
```

**Explain harness engineering:** it includes prompt/model selection but also iteration and cost caps, tool contracts, context compaction, state/memory, retries, cancellation, trace propagation, failure policies, versioning and human handoff. A managed harness reduces repeated plumbing; it does not invent domain guarantees. The Google Research paper's 180 studied configurations found multi-agent benefits for parallelizable tasks and potential degradation for sequential ones. The MAST NeurIPS study reports 1,600+ annotated traces and 14 classes of multi-agent failure across design, coordination and verification. Neither paper is evidence that every use case needs more agents.

**Audience question:** “Why not one agent with four tools?” Answer: that may be superior. Separate agents are justifiable when independent role context, permissions, tool sets, evaluation or parallelization improves measured results.

**Illustrative math:** 3 independent critical steps at 95% success each imply `0.95^3 = 85.7375%` end-to-end completion. Real system failures may be correlated, and retries or partial recovery change this simple model.

## Demo 1 runbook: 09:25–09:45

**Learning goal:** separate language reasoning from booking authority. The browser demo is a deterministic simulation of multi-agent *roles*; it does not invoke Bedrock. The optional Strands example demonstrates actual model-driven agent-as-tool delegation.

**Step A — Intention (4 min).** Open appointment tab, use customer `customer-A`, send `Book Dr Rao on Friday after 5 PM`. Expected `OFFERED` with fictional date 2026-12-04 at 17:30. Explain that the availability specialist is read-only and the offered slot is not yet reserved. Ask “Have we booked anything yet?” Correct: no.

**Step B — Authoritative confirmation (3 min).** Click `YES`. Expected `CONFIRMED`, booking reference `BK-...`, and metrics booking count +1. State that only SQLite `UNIQUE(slot_id)` and the database commit own this invariant. Clarify that no real clinic was involved.

**Step C — Message replay (3 min).** Run `python -m agent_workshop.cli booking`. The scripted `YES` message is delivered twice with the same `message_id`. Expected identical reference and total bookings 1. Explain inbound SMS can duplicate, retry, and arrive out of order; real ingress must dedupe and handle replay.

**Step D — Concurrency (4 min).** Press **Run 20-customer race**. Expected 20 contenders, 1 confirmed, 19 conflicts, 1 booking. This is a local fixture test, NOT an AWS performance metric. Ask “Would another prompt solve this?” No; use database atomicity.

**Step E — Human handoff (3 min).** Send `Please ask a human supervisor to call me`. Expected `ESCALATED` with ticket. No actual human callback occurs; do not imply it does. Explain callback queues, SLA, identity, staff ownership and exception handling.

**If time overruns:** cut Step C but keep the race and human escalation.

**Expected failure questions:**

- *What if customer says Friday in another timezone?* Normalize customer and clinic timezone, confirm absolute timestamp and show locale-aware time.
- *What if the offer expires?* Add offer TTL, re-check at commit and return alternate slots.
- *Can the agent call any doctor?* Only if authorized integration supports it; no API means no confirmed reservation.
- *Is SMS available in India?* Two-way SMS availability and origination requirements are country/region specific. Re-check before claiming service eligibility.
- *What about sensitive health data?* Minimize; don't store symptoms in traces; no medical diagnoses; urgent cases escalate to appropriate care.

## Platform explanation: 09:45–10:00

**Managed Harness vs Runtime:** AWS AgentCore Runtime hosts developer-authored agent code and orchestration. Managed Harness supplies an opinionated configurable Strands-powered loop atop Runtime. You still choose model, tools, scopes, session semantics and domain API controls. [Official comparison](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness-vs-runtime.html).

**Registry vs Gateway:** AWS Agent Registry is a governed catalog for discovering agents, skills, tools and MCP servers. AgentCore Gateway provides an MCP-compatible tool endpoint and target integrations. Identity and tool-specific permissions remain essential. A registry listing is not an access grant. [Registry GA](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-agent-registry-generally-available/) · [Gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-building.html).

**How to decide:** if the custom loop adds little value, prefer managed Harness. If you need fine-grained control, your own framework, dependencies or workflow, use Runtime with explicit code. This is a decision, not a contest.

## Demo 2 runbook: 10:05–10:23

**Learning goal:** parallel evidence gathering + independent, deterministic release policy. This is a *synthetic* C# GitLab-style MR and a *fixture-based* local simulation. It does not scan a real repo or call GitLab.

**Step A — Show the source change (3 min).** Open `fixtures/risky_mr.json` or slide 32. Three source lines: `TimeSpan.FromMilliseconds(30)`, `LogInformation` with bearer token, and constant flag `always_on`; no tests changed.

**Step B — Dispatch four reviewers (4 min).** In MR tab select risky fixture and click review. Specialists simulate security, correctness, test impact and engineering standards. Four findings appear: one high, two medium, one low. Each cites a file and line. These are seeded fixtures, not an accuracy benchmark.

**Step C — Audience disagreement (3 min).** Ask: “If three reviewers say fine but Security says BLOCK, do we take a majority vote?” Answer no. Policy resolves verified risk thresholds; humans manage documented false-positive handling or exceptions.

**Step D — Show final gate (3 min).** Result `BLOCK`. It comes from deterministic code, *not* the model, and the system doesn't merge or comment in GitLab. Discuss permission boundaries and the cost of false positives.

**Step E — Clean fixture (2 min).** Switch to clean MR. It returns `STANDARD_REVIEW`. Explain absence of pattern findings is NOT proof of security, and real testing requires CI and validated analyzers.

**Step F — Make the AWS comparison (3 min).** AWS DevOps Agent's Code Change Risk Analysis already includes GitLab MR support, organization standards and optional verification testing. Its static analysis and verification testing have different latency/cost tradeoffs. Your solution should be built only when special requirements justify it. [AWS official](https://docs.aws.amazon.com/devopsagent/latest/userguide/working-with-devops-agent-code-change-risk-analysis-index.html).

**If time overruns:** skip the clean fixture, not the comparison or policy explanation.

## Production engineering: 10:23–10:43

### Security boundaries

SMS, MR descriptions, CI logs, retrieved docs and repository files are untrusted inputs. A prompt-injection payload in a code comment might say “ignore previous instructions”; that's part of the source material and never authority. Identity, IAM, tool allowlists, immutable audit and service-side policy carry the real security boundary. Avoid granting arbitrary shell/network/GitLab write access to all specialists. Use segregated read-only roles and explicit human review for high-impact changes.

### Observability and correctness

Correlate inbound `message_id` or Git commit SHA to supervisor invocation, model calls, tool calls, policy decisions, transaction IDs and final outcome. Measure tool latency, errors, retries, timeout and token use; separately measure outcome quality such as correct booking, false confirmation, MR finding precision and known-bug recall. Redact secrets and personal information before storing traces.

### Evaluations

Create a **golden test set** with correct expected outcomes. Booking scenarios: ambiguous date, unavailable slot, duplicate inbound SMS, two simultaneous confirmations, malformed message, escalation and consent. MR scenarios: seeded token exposure, unit mismatch, feature flag policy violation, missing tests, false positives, harmless changed file, unknown dependency. Record evidence per result and require independent human labels for complex cases. Never quote a fabricated 99% accuracy from running one seeded case.

### Reliability math

Use examples: 3 independent steps each at 95% -> 85.7% joint success. With 3 agent calls costing hypothetical $0.002 each, model subtotal is $0.006 per task. At 100,000 tasks that is $600 for **assumed model calls only**; actual AWS token prices, messaging charges, infra, evaluations, retries, engineering and failure handling are additional. Use current AWS pricing for actual budget decisions.

### Deployment

Version prompt and tool schemas, model ID, policy rules and evaluation dataset alongside code. Build GitLab CI with tests -> static analysis -> golden eval -> deploy to sandbox -> shadow mode -> canary -> explicit promotion. Preserve rollback and human/manual fallback. Don't tie irreversible writes to pure model confidence.

## Build-vs-buy: 10:43–10:52

The engineering lesson is not “our agent beats AWS DevOps Agent.” AWS already has code-change risk analysis and GitLab integration. Ask: What precise requirement cannot be met by managed features and extensions? Is the gap worth the security, maintenance, evaluation and upgrade burden? A thin coordinator over existing tools and AWS DevOps Agent may be preferable to a new full-stack reviewer.

**Strong closing line:** “The mature engineering decision is often not which agent to build, but which responsibility to keep out of the agent.”

## Questions that senior engineers may ask

1. *Is this really multi-agent?* The local mode **simulates agent roles deterministically** for repeatability. The optional Strands example uses real specialist agents and a supervisor; deployment is not provisioned.
2. *Why does the booking simulator not use NLU?* To isolate domain invariants. An agent intake can be added, but must never control transactional correctness.
3. *Why SQLite rather than DynamoDB?* Local test portability and unique slot semantics; production needs an appropriate transactional datastore and load tests.
4. *What makes a specialist an agent?* Independent model-driven loop/context and tool capabilities, not just a Python function name.
5. *How do you prevent action loops?* Max iterations, per-call timeout, tool budget, stop condition and escalation.
6. *How do you defend against prompt injection?* Separate trusted instructions from untrusted content, schema validation, least privileges, policy outside prompt and isolation.
7. *How do you prevent a malicious MR from stealing secrets?* No secrets in context, redaction, restricted repo access, outbound restrictions and read-only tools.
8. *Can all four reviews execute in parallel?* Yes if independent; preserve trace correlation and deadlines. Agent-as-tools may serialize depending on supervisor behavior. Explicit concurrent orchestration if latency matters.
9. *What is the source of truth?* Booking API database for reservations; GitLab + CI + policy approvals for merge decisions.
10. *What if the security reviewer has a false positive?* Document evidence, separate exception approval and maintain an audit trail.
11. *What if Bedrock is unavailable?* Retry within budget, fail closed for critical writes, return a manual path, protect customer experience.
12. *What if messages arrive out of order?* Sequence/TTL safeguards; SMS lacks ordering guarantees.
13. *Does Registry make tools secure?* No. It helps discovery and lifecycle governance; actual authorization happens at Gateway and backend.
14. *Does managed Harness eliminate code?* No. Domain contracts and transactions remain yours.
15. *Is the new code reviewer unique?* Not necessarily; AWS DevOps Agent already covers many cases. Customization must be justified.
16. *How do we measure MR review quality?* Precision, recall on known seeded defects, severity agreement and human review effort.
17. *How do we measure booking quality?* Correctly committed and customer-confirmed bookings, false confirmations, escalations, cost per completion.
18. *What about actual SMS costs?* Country-specific originator fees, per-message charges, opt-out flows, regional restrictions. Check live pricing.
19. *What about model vendor portability?* Strands allows different model providers, but prompts, evaluation quality, tool compatibility and policy must be retested.
20. *What can we do this afternoon?* Run local demos, add one fixture, design one trusted tool, define one business invariant, write an evaluation.

## Final 8 minutes: learning resources and challenge

- [ReAct](https://arxiv.org/abs/2210.03629): a foundational reasoning-and-action pattern.
- [Google Research scaling agent systems](https://research.google/blog/towards-a-science-of-scaling-agent-systems-when-and-why-agent-systems-work/): when multi-agent helps and hurts.
- [MAST NeurIPS 2025](https://proceedings.nips.cc/paper_files/paper/2025/hash/b1041e52d3be19f0a9bc491657488e4a-Abstract-Datasets_and_Benchmarks_Track.html): failure taxonomy.
- [Strands agents as tools](https://strandsagents.com/docs/learning/multi-agent-patterns-agents-as-tools/): supervisor pattern with examples.
- [AgentCore Harness vs Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness-vs-runtime.html): architecture decision.
- [Agent Registry](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-agent-registry-generally-available/): discovery and governance.
- [AWS DevOps Agent Code Change Risk Analysis](https://docs.aws.amazon.com/devopsagent/latest/userguide/working-with-devops-agent-code-change-risk-analysis-index.html): managed alternative.

**Hands-on homework:** run tests; add an expiration test for bookings; create a clean MR with no issues; then intentionally seed an MR with a harmless string that triggers a false-positive rule and discuss how to detect it. If using real Strands, keep data synthetic and tools read-only until evaluations are reliable.

**Final line:** “Agents propose. Tools execute. Policies authorize. Systems of record confirm.”

**Fact freshness:** AWS services and public financial information verified 25 November 2026. Recheck service regions, API shapes, and billing before event. No public data in this runbook is claimed to be measured during the workshop unless explicitly labeled as a fixture test.
