package com.safeher.app.services.ai

import kotlin.math.min

/**
 * Configurable consecutive-hot / N-of-M decision over 1-second scores.
 *
 * Does not write DecisionContract constants. Threshold comes from [AiDetectionConfig].
 */
class SustainedDistressDecider(
    private val config: AiDetectionConfig,
) {
    private var episodeSeq = 0L
    private var currentEpisodeId: Long? = null
    private var lastHotTimestampMs: Long = 0L

    init {
        require(config.useConsecutiveHotLogic || config.allowNOfMLogic) {
            "Enable consecutive-hot and/or N-of-M logic"
        }
        require(config.consecutiveHotRequired >= 2) {
            "consecutiveHotRequired must be >= 2 so one high score is not confirmed distress"
        }
        if (config.allowNOfMLogic) {
            require(config.nOfMHotCount >= 2) {
                "nOfMHotCount must be >= 2 so one high score is not confirmed distress"
            }
            require(config.nOfMWindow >= config.nOfMHotCount) {
                "nOfMWindow must be >= nOfMHotCount"
            }
        }
    }

    fun reset() {
        currentEpisodeId = null
        lastHotTimestampMs = 0L
    }

    fun evaluate(history: List<ScoreSample>, nowMs: Long): TemporalDecision {
        val threshold = config.confidenceThreshold
        val horizonMs = (config.evidenceHorizonSeconds * 1000.0).toLong()
        val inHorizon = history
            .filter { sample -> nowMs - sample.timestampMs <= horizonMs }
            .sortedBy { it.timestampMs }

        fun isHot(sample: ScoreSample): Boolean = sample.score >= threshold

        var consecutive = 0
        for (sample in inHorizon.asReversed()) {
            if (isHot(sample)) consecutive++ else break
        }

        val m = min(config.nOfMWindow, inHorizon.size)
        val lastM = if (m == 0) emptyList() else inHorizon.takeLast(m)
        val hotCount = lastM.count(::isHot)
        val consecutiveOk = config.useConsecutiveHotLogic &&
            consecutive >= config.consecutiveHotRequired
        val nOfMOk = config.allowNOfMLogic &&
            lastM.size >= config.nOfMHotCount &&
            hotCount >= config.nOfMHotCount
        val sustained = consecutiveOk || nOfMOk
        val anyHot = inHorizon.any(::isHot)

        val state = when {
            sustained -> TemporalState.SUSTAINED
            anyHot -> TemporalState.WATCH
            else -> TemporalState.NONE
        }

        updateEpisode(nowMs, anyHot, inHorizon, ::isHot)

        val maxScore = inHorizon.maxOfOrNull { it.score } ?: 0.0
        val reason = "consecutive=$consecutive/${config.consecutiveHotRequired}" +
            ";nOfM=$hotCount/${config.nOfMHotCount}of${config.nOfMWindow}" +
            ";horizon=${config.evidenceHorizonSeconds}s" +
            ";threshold=$threshold" +
            ";episode=${currentEpisodeId ?: "-"}"

        return TemporalDecision(
            state = state,
            consecutiveHot = consecutive,
            hotInWindow = hotCount,
            windowSize = lastM.size,
            maxScoreInHorizon = maxScore,
            horizonSeconds = config.evidenceHorizonSeconds,
            threshold = threshold,
            episodeId = currentEpisodeId,
            consecutiveSatisfied = consecutiveOk,
            nOfMSatisfied = nOfMOk,
            reason = reason,
        )
    }

    private fun updateEpisode(
        nowMs: Long,
        anyHot: Boolean,
        inHorizon: List<ScoreSample>,
        isHot: (ScoreSample) -> Boolean,
    ) {
        if (anyHot) {
            lastHotTimestampMs = inHorizon.last { isHot(it) }.timestampMs
            if (currentEpisodeId == null) {
                episodeSeq += 1
                currentEpisodeId = episodeSeq
            }
            return
        }
        val quietMs = (config.episodeQuietGapSeconds * 1000.0).toLong()
        if (currentEpisodeId != null && nowMs - lastHotTimestampMs >= quietMs) {
            currentEpisodeId = null
        }
    }
}
