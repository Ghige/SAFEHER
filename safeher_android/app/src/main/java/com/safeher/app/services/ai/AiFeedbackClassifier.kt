package com.safeher.app.services.ai

/**
 * Maps confirm-dialog outcomes to privacy-safe feedback categories.
 * Predictions are candidates only — never gold training labels.
 */
object AiFeedbackClassifier {

    const val CONSENT_VERSION = "privacy-v2-metadata-only"

    fun predictionState(recommendedAction: String): String =
        if (recommendedAction == DecisionContract.ACTION_FIRE) "EMERGENCY" else "SUSPICIOUS"

    fun userFeedback(userConfirmed: Boolean?, timedOut: Boolean): String = when {
        userConfirmed == true -> "CONFIRMED_EMERGENCY"
        userConfirmed == false -> "CANCELLED"
        timedOut -> "TIMEOUT"
        else -> "NONE"
    }

    fun outcome(userConfirmed: Boolean?): String =
        if (userConfirmed == true) "MANUAL_SOS_OPENED" else "NO_ALERT"

    fun candidateCategory(userConfirmed: Boolean?, timedOut: Boolean): String = when {
        userConfirmed == true -> "USER_CONFIRMED_DISTRESS"
        userConfirmed == false -> "AI_FALSE_POSITIVE_CANDIDATE"
        timedOut -> "UNREVIEWED"
        else -> "UNREVIEWED"
    }
}
