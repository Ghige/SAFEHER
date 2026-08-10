package com.safeher.app.services.ai

import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder

/** Encodes a mono 16 kHz PCM buffer as WAV for dataset upload. */
object AudioClipEncoder {

    private const val SAMPLE_RATE = 16_000

    fun encodeWavMono16(samples: ShortArray): ByteArray {
        val dataSize = samples.size * 2
        val buffer = ByteArrayOutputStream(44 + dataSize)
        buffer.write("RIFF".toByteArray())
        writeIntLe(buffer, 36 + dataSize)
        buffer.write("WAVE".toByteArray())
        buffer.write("fmt ".toByteArray())
        writeIntLe(buffer, 16)
        writeShortLe(buffer, 1)
        writeShortLe(buffer, 1)
        writeIntLe(buffer, SAMPLE_RATE)
        writeIntLe(buffer, SAMPLE_RATE * 2)
        writeShortLe(buffer, 2)
        writeShortLe(buffer, 16)
        buffer.write("data".toByteArray())
        writeIntLe(buffer, dataSize)
        val pcm = ByteBuffer.allocate(dataSize).order(ByteOrder.LITTLE_ENDIAN)
        for (sample in samples) {
            pcm.putShort(sample)
        }
        buffer.write(pcm.array())
        return buffer.toByteArray()
    }

    private fun writeIntLe(out: ByteArrayOutputStream, value: Int) {
        out.write(value and 0xFF)
        out.write(value shr 8 and 0xFF)
        out.write(value shr 16 and 0xFF)
        out.write(value shr 24 and 0xFF)
    }

    private fun writeShortLe(out: ByteArrayOutputStream, value: Int) {
        out.write(value and 0xFF)
        out.write(value shr 8 and 0xFF)
    }
}
