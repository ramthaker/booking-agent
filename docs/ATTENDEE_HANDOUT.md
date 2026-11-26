# Workshop quick reference — From Agent Demo to Production

**One principle:** Agents propose. Tools execute. Policies authorize. Systems of record confirm.

## Run the demos (Python 3.10+; no AWS required)

```bash
python -m unittest discover -s tests -v
python -m agent_workshop.web
```

Open **http://127.0.0.1:8765**. Tab 1: `Dr Rao Friday after 5 PM` → `YES` → `Human`, then the **20-customer race**. Tab 2: review **risky MR** → inspect four findings → explain policy-driven BLOCK, then review **clean MR**. The local demos are **deterministic simulations**, not live model-driven agents or real provider integrations. Optional `strands_pattern.py` and `live_mr_multiagent.py` make actual billable Bedrock model calls when configured.

## Four architecture tests

1. Why does the task need model reasoning instead of a deterministic function?
2. Why does this task need more than one agent rather than one agent with tools?
3. Who can authorize the last state-changing operation?
4. What measured outcome, cost and failure rate make the design worth running?

## Try these exercises

- Booking: add offer expiry and test a late YES. Add different customer timezones and confirmation display. Introduce a mock availability outage.
- MR: add an intentionally harmless diff that matches a simplistic scanner rule and inspect the false-positive burden. Add a dedicated test change and watch the missing-tests finding disappear.
- Multi-agent: run `optional_aws/live_mr_multiagent.py` with enabled Bedrock, compare model suggestions against local deterministic findings and create a golden-evaluation report.

## Research papers and official material

- ReAct: https://arxiv.org/abs/2210.03629
- Google Research agent scaling: https://research.google/blog/towards-a-science-of-scaling-agent-systems-when-and-why-agent-systems-work/
- MAST/NeurIPS multi-agent failures: https://proceedings.nips.cc/paper_files/paper/2025/hash/b1041e52d3be19f0a9bc491657488e4a-Abstract-Datasets_and_Benchmarks_Track.html
- Strands agent-as-tools: https://strandsagents.com/docs/learning/multi-agent-patterns-agents-as-tools/
- AgentCore Harness vs Runtime: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness-vs-runtime.html
- AWS Agent Registry: https://aws.amazon.com/about-aws/whats-new/2026/08/aws-agent-registry-generally-available/
- AWS DevOps Agent: https://docs.aws.amazon.com/devopsagent/latest/userguide/working-with-devops-agent-code-change-risk-analysis-index.html
