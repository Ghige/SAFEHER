"""Simulated confirmation countdown + DEMO-only action gate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from .config import DecisionEngineConfig

UserChoice = Literal["CANCEL", "NO_RESPONSE"]


@dataclass
class ConfirmationResult:
    prompted: bool
    message: str
    countdown_seconds: int
    user_choice: Optional[str]
    countdown_result: str
    simulated_action: str
    real_sos_attempted: bool = False


class DemoActionGuard:
    """Refuses all real SOS / contact / messaging actions while DEMO_MODE is true."""

    def __init__(self, cfg: DecisionEngineConfig):
        self.cfg = cfg

    def execute_simulated_sos(self, reason: str) -> dict:
        if not self.cfg.demo_mode:
            raise RuntimeError("DEMO_MODE required — refusing non-demo SOS path.")
        if self.cfg.safety.get("refuse_real_actions_while_demo_mode", True):
            return {
                "action": "TEST_SOS_TRIGGERED",
                "real_sos": False,
                "phone_call": False,
                "sms": False,
                "whatsapp": False,
                "emergency_contacts": False,
                "logged_only": True,
                "reason": reason,
                "note": "SIMULATION ONLY — no real alert was sent.",
            }
        raise RuntimeError("Blocked: real actions are not implemented and must stay disabled.")


def run_confirmation(
    cfg: DecisionEngineConfig,
    *,
    user_choice: UserChoice,
    trigger_reason: str,
) -> ConfirmationResult:
    conf = cfg.confirmation
    if not conf.get("enabled", True):
        return ConfirmationResult(
            prompted=False,
            message="",
            countdown_seconds=0,
            user_choice=None,
            countdown_result="SKIPPED",
            simulated_action="NONE",
        )

    seconds = int(conf.get("countdown_seconds", 30))
    message = str(conf.get("message", "Possible emergency detected"))
    guard = DemoActionGuard(cfg)

    if user_choice == "CANCEL":
        return ConfirmationResult(
            prompted=True,
            message=message,
            countdown_seconds=seconds,
            user_choice="CANCEL",
            countdown_result=str(conf.get("cancel_action", "CANCELLED")),
            simulated_action="NONE",
        )

    # NO RESPONSE → simulated TEST_SOS only
    sim = guard.execute_simulated_sos(trigger_reason)
    return ConfirmationResult(
        prompted=True,
        message=message,
        countdown_seconds=seconds,
        user_choice="NO_RESPONSE",
        countdown_result=str(conf.get("no_response_action", "TEST_SOS_TRIGGERED")),
        simulated_action=sim["action"],
        real_sos_attempted=False,
    )
