package com.safeher.app.services.ai

/**
 * Stage 8 confirm-first policy (mirrors decision_contract.json confirmation block).
 *
 * With [AI_AUTO_SOS_ENABLED]=false, AI never sends SOS. User Yes opens manual SOS
 * countdown. CANCEL and NO_RESPONSE never create alerts.
 */
object AiConfirmFirstPolicy {

    enum class PromptKind { SUSPICIOUS, EMERGENCY }

    enum class Outcome {
        /** User tapped Cancel / I'm safe. */
        CANCELLED_NO_ALERT,
        /** Countdown elapsed with no tap; auto-SOS off → safe dismiss. */
        NO_RESPONSE_DISMISS_SAFE,
        /** Countdown elapsed; would only simulate SOS in DEMO/server — still no real alert when auto SOS off. */
        NO_RESPONSE_BLOCKED_NO_ALERT,
        /** User confirmed — proceed to manual SOS countdown UI (never silent WhatsApp). */
        USER_CONFIRMED_MANUAL_SOS,
        /** User confirmed fire path but AI auto SOS remains disabled — still manual only. */
        USER_CONFIRMED_AUTO_BLOCKED,
    }

    fun promptKind(action: String): PromptKind = when (action) {
        DecisionContract.ACTION_FIRE -> PromptKind.EMERGENCY
        else -> PromptKind.SUSPICIOUS
    }

    fun countdownSeconds(): Int = DecisionContract.CONFIRM_COUNTDOWN_SECONDS

    /**
     * Resolve user/timeout outcome. [autoSosEnabled] must remain false for Stage 8 beta.
     */
    fun resolve(
        userConfirmed: Boolean?,
        timedOut: Boolean,
        recommendedAction: String,
        autoSosEnabled: Boolean,
    ): Outcome {
        when {
            userConfirmed == false -> return Outcome.CANCELLED_NO_ALERT
            userConfirmed == true -> {
                // Confirm-first: always escalate to user-controlled manual SOS UI.
                // Never allow silent AI WhatsApp even if flag were true without explicit product change.
                return if (!autoSosEnabled) {
                    Outcome.USER_CONFIRMED_MANUAL_SOS
                } else {
                    // Flag true is out of Stage 8 scope; still prefer manual confirm path for fire.
                    if (recommendedAction == DecisionContract.ACTION_FIRE) {
                        Outcome.USER_CONFIRMED_AUTO_BLOCKED
                    } else {
                        Outcome.USER_CONFIRMED_MANUAL_SOS
                    }
                }
            }
            timedOut -> {
                // Contract demo NO_RESPONSE → TEST_SOS_TRIGGERED is simulation-only.
                // Production Android with AI_AUTO_SOS=false: dismiss safely, no alert.
                return if (!autoSosEnabled) {
                    Outcome.NO_RESPONSE_DISMISS_SAFE
                } else {
                    Outcome.NO_RESPONSE_BLOCKED_NO_ALERT
                }
            }
            else -> return Outcome.CANCELLED_NO_ALERT
        }
    }

    fun createsAlert(outcome: Outcome): Boolean = false // Stage 8: never

    fun opensManualSosCountdown(outcome: Outcome): Boolean =
        outcome == Outcome.USER_CONFIRMED_MANUAL_SOS ||
            outcome == Outcome.USER_CONFIRMED_AUTO_BLOCKED
}
