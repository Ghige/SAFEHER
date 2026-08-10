package com.safeher.app.data.repository

/**
 * Thrown when SOS is queued locally because the device is offline.
 * The request will be sent automatically when connectivity returns.
 */
class OfflineSosQueuedException : Exception(MESSAGE) {
    companion object {
        const val MESSAGE =
            "SOS queued. Your alert will send automatically when you're back online."
    }
}
