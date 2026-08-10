package com.safeher.app.data.mapper

import com.safeher.app.data.remote.dto.AlertResponseDto
import com.safeher.app.domain.model.SafetyAlert

fun AlertResponseDto.toSafetyAlert(): SafetyAlert = SafetyAlert(
    id = id,
    triggerType = trigger_type,
    latitude = latitude,
    longitude = longitude,
    status = status,
    startedAt = started_at,
    endedAt = ended_at,
    evidenceUrl = evidence_url,
    whatsappSentCount = whatsapp_sent_count,
    whatsappFailedCount = whatsapp_failed_count,
    whatsappAllDelivered = whatsapp_all_delivered,
)
