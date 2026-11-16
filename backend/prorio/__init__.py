"""Prorio, Beacon Assist's back-office agent: Priority and Protocol.

Prorio is deterministic code, not a language model, and it calls no outside service: customer data stays inside the
backend. It reads only the structured fields of a Customer Service Card (never the customer's free-text summary),
gathers evidence from account data, scores the case, applies the gates, matches a protocol from the Protocol
Database and drafts a proposed solution for an officer to approve.

    agent.draft(card, ...)   full run at intake: priority + proposal + trace
    agent.rank(card, ...)    priority only, recomputed on every queue read so waiting time stays current
"""
