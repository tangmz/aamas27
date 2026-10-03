"""Executable illustrative semantics for persistent challenges; no LLM or gold.

This implements procedural safety only. It cannot establish answer correctness.
"""
from dataclasses import dataclass, field


@dataclass
class Challenge:
    author: str
    alternative: str
    evidence: str
    status: str = 'pending'
    disposition: str = ''


@dataclass
class Ledger:
    capacity: int = 5
    challenges: dict = field(default_factory=dict)
    closed: bool = False
    overflow: bool = False

    def register(self, challenge_id, author, alternative, evidence):
        if self.closed:
            raise ValueError('Decision is already closed')
        if not all(isinstance(x, str) and x.strip() for x in (challenge_id, author, alternative, evidence)):
            raise ValueError('Registration needs identifiers, alternative and evidence')
        if challenge_id in self.challenges:
            old = self.challenges[challenge_id]
            if (old.author, old.alternative, old.evidence) != (author, alternative, evidence):
                raise ValueError('Registered challenge is immutable')
            return
        if len(self.challenges) >= self.capacity:
            self.overflow = True
            return  # Capacity exhaustion forces an unresolved decision at closure.
        self.challenges[challenge_id] = Challenge(author, alternative, evidence)

    def change_endorsement(self, author, answer):
        if self.closed:
            raise ValueError('Decision is already closed')
        # Endorsement changes deliberately do not erase registered standing.

    def resolve(self, challenge_id, status, disposition):
        if self.closed or status not in {'upheld', 'rejected'} or not disposition.strip():
            raise ValueError('Resolution requires an open decision and a recorded disposition')
        challenge = self.challenges[challenge_id]
        if challenge.status != 'pending':
            raise ValueError('Challenge has already received a disposition')
        challenge.status, challenge.disposition = status, disposition

    def expire(self):
        if self.closed:
            raise ValueError('Decision is already closed')
        for challenge in self.challenges.values():
            if challenge.status == 'pending':
                challenge.status = 'deferred'
                challenge.disposition = 'Review budget or deadline exhausted'

    def close(self, proposed_answer):
        if self.closed or any(c.status == 'pending' for c in self.challenges.values()):
            raise ValueError('Cannot close with a pending challenge')
        self.closed = True
        if self.overflow or any(c.status == 'deferred' for c in self.challenges.values()):
            return 'UNRESOLVED'
        return proposed_answer


def verify_finite_examples():
    """Check small traces, not a statistical simulation of model behaviour."""
    checked = 0
    for initial in ('A', 'B'):
        for later in ('A', 'B'):
            for disposition in ('upheld', 'rejected', 'deferred'):
                ledger = Ledger(capacity=1)
                ledger.register('c1', 'agent1', initial, 'Specific disputed claim')
                ledger.change_endorsement('agent1', later)
                assert ledger.challenges['c1'].status == 'pending'
                try:
                    ledger.close(later)
                    raise AssertionError('Pending challenge was bypassed')
                except ValueError:
                    pass
                if disposition == 'deferred':
                    ledger.expire()
                else:
                    ledger.resolve('c1', disposition, 'Recorded reason')
                result = ledger.close(later)
                assert result == ('UNRESOLVED' if disposition == 'deferred' else later)
                checked += 1
    ledger = Ledger(capacity=1)
    ledger.register('c1', 'agent1', 'A', 'Claim 1')
    ledger.register('c2', 'agent2', 'B', 'Claim 2')
    ledger.resolve('c1', 'rejected', 'Recorded reason')
    assert ledger.close('A') == 'UNRESOLVED'
    return {'checked_traces': checked + 1, 'meaning': 'software checks of specified safety properties; not empirical evidence'}
