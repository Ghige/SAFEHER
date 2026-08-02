package com.safeher.app.core.network

import com.safeher.app.data.remote.dto.ContactDto
import com.safeher.app.data.remote.dto.CreateContactRequestDto
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

interface ContactsApi {

    @GET("api/v1/users/contacts")
    suspend fun getContacts(): List<ContactDto>

    @POST("api/v1/users/contacts")
    suspend fun createContact(@Body body: CreateContactRequestDto): ContactDto

    @DELETE("api/v1/users/contacts/{contact_id}")
    suspend fun deleteContact(@Path("contact_id") contactId: String)
}
