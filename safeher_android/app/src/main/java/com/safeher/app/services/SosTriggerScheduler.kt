package com.safeher.app.services

import android.content.Context
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

fun interface SosTriggerScheduler {
    fun scheduleFlush()
}

@Singleton
class SosTriggerSchedulerImpl @Inject constructor(
    @ApplicationContext private val context: Context,
) : SosTriggerScheduler {
    override fun scheduleFlush() {
        SosTriggerWorker.enqueueFlush(context)
    }
}
