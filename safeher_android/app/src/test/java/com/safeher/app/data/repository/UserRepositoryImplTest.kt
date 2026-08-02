package com.safeher.app.data.repository

import com.safeher.app.core.datastore.UserPreferences
import com.safeher.app.core.network.NetworkMonitor
import com.safeher.app.core.network.SafeHerApi
import com.safeher.app.data.remote.dto.UserProfileDto
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import io.mockk.coEvery
import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class UserRepositoryImplTest {

    private val api: SafeHerApi = mockk()
    private val userPreferences: UserPreferences = mockk(relaxed = true)
    private val networkMonitor: NetworkMonitor = mockk()
    private val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()
    private lateinit var repository: UserRepositoryImpl

    @Before
    fun setup() {
        every { networkMonitor.isOnline } returns flowOf(true)
        repository = UserRepositoryImpl(api, userPreferences, networkMonitor, moshi)
    }

    @Test
    fun getProfile_success_mapsDtoAndVerification() = runTest {
        coEvery { api.getProfile() } returns UserProfileDto(
            id = "uuid-1",
            phone_number = "9876543210",
            name = "Jane Doe",
            city = "Mumbai",
        )
        coEvery { userPreferences.isPhoneVerified } returns flowOf(true)

        val result = repository.getProfile()

        assertTrue(result.isSuccess)
        val profile = result.getOrNull()!!
        assertEquals("Jane Doe", profile.name)
        assertEquals("9876543210", profile.phoneNumber)
        assertEquals("Mumbai", profile.city)
        assertTrue(profile.isVerified)
    }

    @Test
    fun getProfile_offline_returnsFailure() = runTest {
        every { networkMonitor.isOnline } returns flowOf(false)

        val result = repository.getProfile()

        assertTrue(result.isFailure)
        assertTrue(result.exceptionOrNull()?.message?.contains("offline", ignoreCase = true) == true)
    }

    @Test
    fun getProfile_emptyName_returnsFailure() = runTest {
        coEvery { api.getProfile() } returns UserProfileDto(
            id = "uuid-1",
            phone_number = "9876543210",
            name = "  ",
            city = null,
        )

        val result = repository.getProfile()

        assertTrue(result.isFailure)
        assertTrue(result.exceptionOrNull()?.message?.contains("incomplete", ignoreCase = true) == true)
    }
}
