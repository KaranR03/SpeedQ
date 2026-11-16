"""Pydantic models: the Retell webhook payload (flat, field names match the voice agent)."""
from typing import List, Optional

from pydantic import BaseModel, model_validator

ISSUE_TYPES = ("SCAM_IN_PROGRESS", "FRAUD_UNAUTHORISED", "MONEY_MISSING", "HARDSHIP",
               "DISPUTE_CHARGE", "CARD_LOST_STOLEN", "CARD_DELIVERY", "GENERAL_ENQUIRY")
ACTIONS = ("ACTIVATE_SAFEBLOCK", "BLOCK_CARD", "RAISE_DISPUTE", "DRAFT_PAYMENT_RECALL",
           "DRAFT_SCAM_REPORT", "BOOK_CALLBACK", "SEND_CUSTOMER_UPDATE")


class ActionItem(BaseModel):
    action: str
    params: dict = {}


class Decision(BaseModel):
    decision: str                           # APPROVE | MODIFY | MANUAL
    actions: Optional[List[ActionItem]] = None   # MODIFY: the edited list to run
    officer: str = "officer"


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
    risk_signals: str = ""          # comma string
    customer_confirmed: bool = False
    priority_score: Optional[float] = None   # Retell's estimate: never used for ranking
    priority_band: Optional[str] = None
    priority_reasons: Optional[str] = None
    proposed_explanation: str = ""
    proposed_actions: str = ""      # comma string of action names
    status: str = "QUEUED"
    safeblock_activated: bool = False
    case_reference: str = ""
    customer_sentiment: str = ""
