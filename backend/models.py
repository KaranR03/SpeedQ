"""Pydantic models: the Clario (Retell) case card payload, flat, field names match the voice agent.

Valid issue types come from the Protocol Database (prorio.protocols.ISSUE_TYPES) and the executable actions from
prorio.propose.ACTIONS.
"""
from typing import List, Optional

from pydantic import BaseModel, model_validator


class ActionItem(BaseModel):
    action: str
    params: dict = {}


class Decision(BaseModel):
    decision: str                           # APPROVE | MODIFY | MANUAL
    actions: Optional[List[ActionItem]] = None   # MODIFY: the edited list to run
    officer: str = "officer"
    note: str = ""                          # optional: why (shown to the protocol owner)
    suggest_update: bool = True             # MODIFY: "Suggest as a protocol update?"


class OfficerNote(BaseModel):
    officer: str = "officer"
    note: str = ""


class OwnerDecision(BaseModel):
    owner: str = "protocol owner"
    reason: str = ""


class Rerank(BaseModel):
    band: Optional[str] = None     # exactly one of band / score
    score: Optional[int] = None
    reason: str = ""               # required, checked in store.rerank
    officer: str = "officer"


class RetellPayload(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def _tidy(cls, data):
        """The agent is a language model: it may send null for fields it did not use, or a JSON
        list where we expect comma text. Treat null as "not provided" and join lists."""
        if not isinstance(data, dict):
            return data
        out = {}
        for k, v in data.items():
            if v is None:
                continue
            out[k] = ",".join(str(x) for x in v) if isinstance(v, list) else v
        return out

    customer_id: str
    issue_type: str
    customer_name: str = ""
    language: str = "en"
    language_label: str = ""
    summary_en: str = ""
    summary_customer_lang: str = ""
    linked_transactions: str = ""   # comma string
    risk_signals: str = ""          # comma string: CUSTOMER_REPORTS_PRESSURE, VULNERABILITY_CUES, ESSENTIALS_AT_RISK
    customer_confirmed: bool = False
    priority_score: Optional[float] = None   # Retell's estimate: never used for ranking
    priority_band: Optional[str] = None
    priority_reasons: Optional[str] = None
    proposed_explanation: str = ""
    proposed_actions: str = ""      # comma string of action names
    status: str = "QUEUED"
    safeblock_activated: bool = False
    card_locked: bool = False       # the customer locked their card during the conversation
    case_reference: str = ""
    customer_sentiment: str = ""
