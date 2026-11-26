"""Offline simulated specialist review. No external repository access or mutations."""
from __future__ import annotations
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parent.parent

@dataclass(frozen=True)
class Finding:
    agent: str
    severity: str
    rule: str
    file: str
    line: int
    evidence: str
    recommendation: str

    def to_dict(self):
        return asdict(self)


class SecurityReviewer:
    name = "Security Agent"
    def review(self, changed):
        out = []
        for row in changed:
            if re.search(r'Log(?:Information|Debug|Warning).*\b(?:Token|Bearer|Secret)\b', row['text'], re.I):
                out.append(Finding(self.name, 'HIGH', 'SEC-001', row['file'], row['line'],
                   row['text'].strip(), 'Remove authentication material from logs; use redaction.'))
        return out


class CorrectnessReviewer:
    name = "Correctness Agent"
    def review(self, changed):
        return [Finding(self.name, 'MEDIUM', 'COR-001', row['file'], row['line'], row['text'].strip(),
           'Check units: use FromSeconds(30) if the requirement is a 30-second timeout.')
           for row in changed if 'FromMilliseconds(30)' in row['text']]


class TestImpactReviewer:
    name = "Test Impact Agent"
    def review(self, changed):
        sources = [r for r in changed if r['file'].startswith('src/')]
        tests = [r for r in changed if r['file'].startswith('tests/')]
        if sources and not tests:
            first = sources[0]
            return [Finding(self.name, 'LOW', 'TEST-001', first['file'], first['line'],
                  'Source changed; fixture contains no corresponding test diff.',
                  'Add a regression test for timeout and logging behavior.')]
        return []


class StandardsReviewer:
    name = "Engineering Standards Agent"
    def review(self, changed):
        return [Finding(self.name, 'MEDIUM', 'ORG-001', row['file'], row['line'], row['text'].strip(),
               'Use a controlled feature flag and a reviewed rollout plan.')
               for row in changed if 'FeatureFlag = "always_on"' in row['text']]


class ReviewSupervisor:
    def __init__(self):
        self.specialists = (SecurityReviewer(), CorrectnessReviewer(), TestImpactReviewer(), StandardsReviewer())

    def review(self, scenario: str = 'risky'):
        source = ROOT / 'fixtures' / (scenario + '_mr.json')
        if not source.exists():
            raise ValueError(f"Unknown fixture: {scenario}")
        data = json.loads(source.read_text(encoding='utf-8'))
        rows = data['changes']
        # Independent read-only specialist checks may run concurrently.
        with ThreadPoolExecutor(max_workers=len(self.specialists)) as pool:
            reviewed = list(pool.map(lambda specialist: specialist.review(rows), self.specialists))
        findings = [finding for group in reviewed for finding in group]
        findings.sort(key=lambda f: (['CRITICAL','HIGH','MEDIUM','LOW'].index(f.severity), f.rule))
        # This decision is NOT a model majority vote. The release policy is independent.
        if any(f.severity in ('CRITICAL', 'HIGH') for f in findings):
            decision = 'BLOCK'
        elif any(f.severity == 'MEDIUM' for f in findings):
            decision = 'REVIEW_REQUIRED'
        elif findings:
            decision = 'ADVISORY'
        else:
            decision = 'STANDARD_REVIEW'
        return {'mr': data['title'], 'scenario': scenario, 'decision': decision,
                'specialists': [a.name for a in self.specialists],
                'findings': [f.to_dict() for f in findings],
                'summary': {'high': sum(f.severity=='HIGH' for f in findings),
                  'medium':sum(f.severity=='MEDIUM' for f in findings),
                  'low':sum(f.severity=='LOW' for f in findings)},
                'operations': 'read-only; no GitLab comment or merge action'}
