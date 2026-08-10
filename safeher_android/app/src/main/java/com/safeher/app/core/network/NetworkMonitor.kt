package com.safeher.app.core.network

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.distinctUntilChanged
import timber.log.Timber
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class NetworkMonitor @Inject constructor(
    @ApplicationContext private val context: Context,
) {

    val isOnline: Flow<Boolean> = callbackFlow {
        val connectivityManager =
            context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager

        val callback = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) {
                Timber.d(
                    "NetworkMonitor.onAvailable: emitting isOnline=true (capabilities=%s)",
                    connectivityManager.describeActiveNetwork(),
                )
                trySend(true)
            }

            override fun onLost(network: Network) {
                Timber.d("NetworkMonitor.onLost: emitting isOnline=false")
                trySend(false)
            }
        }

        val request = NetworkRequest.Builder()
            .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
            .build()

        connectivityManager.registerNetworkCallback(request, callback)
        val initialOnline = connectivityManager.hasInternetCapability()
        Timber.d(
            "NetworkMonitor.initial: emitting isOnline=%s capabilities=%s",
            initialOnline,
            connectivityManager.describeActiveNetwork(),
        )
        trySend(initialOnline)

        awaitClose { connectivityManager.unregisterNetworkCallback(callback) }
    }.distinctUntilChanged()

    private fun ConnectivityManager.hasInternetCapability(): Boolean {
        val network = activeNetwork ?: return false
        val capabilities = getNetworkCapabilities(network) ?: return false
        return capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
            capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
    }

    private fun ConnectivityManager.describeActiveNetwork(): String {
        val network = activeNetwork ?: return "activeNetwork=null"
        val capabilities = getNetworkCapabilities(network) ?: return "capabilities=null"
        return buildString {
            append("internet=")
            append(capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET))
            append(" validated=")
            append(capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED))
            append(" transports=")
            append(capabilities.describeTransports())
        }
    }

    private fun NetworkCapabilities.describeTransports(): String = buildList {
        if (hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) add("wifi")
        if (hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR)) add("cellular")
        if (hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)) add("ethernet")
        if (hasTransport(NetworkCapabilities.TRANSPORT_VPN)) add("vpn")
        if (isEmpty()) add("none")
    }.joinToString(",")
}
