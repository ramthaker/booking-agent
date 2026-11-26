# AWS production blueprint — what to build after the workshop

This file is a reference architecture, **not deployed infrastructure**. No AWS account resources are created by the local demo. Validate region, quotas, permissions, legal and SMS registration requirements before implementation.

## 1. Two independent workloads on one platform

```text
A. BOOKING
Two-way SMS origination number / Amazon Connect voice
  -> AWS End User Messaging SMS -> SNS event or Connect integration
  -> verified ingress + idempotency store + consent
  -> Strands Supervisor in AgentCore Runtime (or configured AgentCore Harness)
     -> Availability Tool (read only)
     -> Policy/Identity Tool (read only)
     -> Human Escalation Tool (create approved queue task)
  -> Human-confirmed customer intent
  -> Booking API with conditional transaction / uniqueness + expiry
  -> SMS response / contact-center update

B. MR REVIEW
GitLab MR webhook / GitLab CI
  -> verified webhook + commit SHA + changed file summary
  -> Supervisor Agent
     -> Security Reviewer (read diff; no repository write access)
     -> Correctness Reviewer (read diff)
     -> Test Impact Reviewer (read test results)
     -> Engineering Standards Reviewer (read approved policies)
  -> Findings normalization + external verifier
  -> Deterministic release policy + human approval / exception
  -> GitLab review comment (optional, separate scoped service account)
  -> Pipeline status / audit record (controlled write, not raw agent authority)

SHARED PLATFORM: Agent Registry (discovery) | Gateway (approved MCP tools)
Identity / IAM | AgentCore Memory (nontransactional, scoped)
Observability + evaluation | Secrets Manager | CloudWatch / audit
```

## 2. Service decisions that matter

| Concern | Candidate AWS capability | Reason / caveat |
|---|---|---|
| Agent loop | AgentCore Harness or Strands on AgentCore Runtime | Managed convenience vs custom code control |
| Tool interface | AgentCore Gateway | MCP entry point and target auth, not authorization of domain data by itself |
| Shared catalog | AWS Agent Registry | Metadata and governed discovery, not execution permission |
| Customer channel | AWS End User Messaging SMS | Two-way SMS availability is region/country/number-type dependent |
| Voice handoff | Amazon Connect | Contact-center staffing, routing, transcripts, consent |
| Authoritative bookings | DynamoDB conditional writes / relational transaction | Domain invariants, idempotency keys, slot expiry |
| Model | Amazon Bedrock model chosen per region | Check entitlement, quality, safety, latency, throughput and cost |
| MR source | GitLab read-only API + short-lived tokens | Avoid exposing private diffs to unintended principals |
| Code checks | Existing SAST, CI tests, AWS DevOps Agent where appropriate | Don't make models pretend to execute verification |
| Logs/traces | CloudWatch / OpenTelemetry | Redact PII, secrets, tokens and private code |

## 3. Authorization matrix example

| Actor / agent | Read availability | Commit booking | Read MR diff | Approve merge |
|---|:---:|:---:|:---:|:---:|
| Booking intake agent | Yes (scoped) | No | No | No |
| Booking domain service | Yes | Yes, after confirmation & auth | No | No |
| MR specialist agents | No | No | Yes (scoped) | No |
| Merge decision service | No | No | Findings only | Recommendation only |
| Human authorized approver | Based on role | Based on policy | Based on role | Yes, through GitLab |

Never use the foundation model's prompt as the control plane for the last two columns.

## 4. Production-ready invariants

**Booking:** One authoritative booking per slot; no duplicate booking on repeated inbound message ID; no confirmation without successful DB transaction; offer TTL; timezone normalization; verified user identity; conflict and manual fallback; safe urgent-case escalation; lawful data handling.

**MR:** Findings must cite a specific commit SHA/file/line; independent verification for blocking claims; no arbitrary shell/network calls from untrusted diff content; read-only access by default; suppression workflow logged; GitLab approval remains human-/policy-owned.

**Both:** Budget, timeout, retry ceiling, trace propagation, model and prompt version, evaluation fixture set, per-tool permissions, error recovery, cost per successful outcome, human escalation SLA and rollback playbook.

## 5. Suggested order of implementation

1. Run local tests and add extra fixtures for missing/late data.
2. Provision a sandbox Bedrock model with model-only IAM invocation permissions; try optional Strands example on *synthetic data*.
3. Introduce typed read-only tools and explicit schemas.
4. Add identity and entitlement checks in the service API and Gateway targets.
5. Integrate real scheduling APIs only after contractual authorization; use a transactional booking service.
6. Add GitLab API read-only integration; run existing static tools and tests first.
7. Use AgentCore Runtime or managed Harness in a nonproduction account; add trace spans, redaction and budget controls.
8. Add an evaluation pipeline and compare single-agent vs multi-agent baselines.
9. Run shadow mode: inspect outcomes without posting or committing.
10. Add controlled user consent or staff approval for any external action.

## 6. Build vs buy explicitly

AWS DevOps Agent Code Change Risk Analysis already provides managed repository review, GitLab integration, standards, cross-repo context and optional verification testing. Your own reviewer should therefore demonstrate **why an organization-specific orchestration or policy step is needed**, not claim that AWS lacks code review. Evaluate managed extension first; custom implementation adds operational and maintenance burden.

## 7. References (verified Nov 25, 2026)

- AWS AgentCore Harness vs Runtime: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness-vs-runtime.html
- AWS AgentCore Gateway: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-building.html
- AWS Agent Registry GA: https://aws.amazon.com/about-aws/whats-new/2026/08/aws-agent-registry-generally-available/
- AWS two-way SMS: https://docs.aws.amazon.com/sms-voice/latest/userguide/two-way-sms.html
- AWS DevOps Agent code risk analysis: https://docs.aws.amazon.com/devopsagent/latest/userguide/working-with-devops-agent-code-change-risk-analysis-index.html
- Strands agents-as-tools: https://strandsagents.com/docs/learning/multi-agent-patterns-agents-as-tools/
