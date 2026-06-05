package app.walkpedia

import android.annotation.SuppressLint
import android.content.Context
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Bundle

/**
 * GPS via the framework LocationManager (no Google Play Services dependency, so
 * the app stays fully open-source / dependency-light). Updates roughly every 3 s
 * or 10 m of movement.
 */
class LocationProvider(context: Context, private val onLocation: (Location) -> Unit) {
    private val lm = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager

    private val listener = object : LocationListener {
        override fun onLocationChanged(location: Location) = onLocation(location)
        override fun onStatusChanged(provider: String?, status: Int, extras: Bundle?) {}
        override fun onProviderEnabled(provider: String) {}
        override fun onProviderDisabled(provider: String) {}
    }

    @SuppressLint("MissingPermission") // caller must ensure ACCESS_FINE_LOCATION is granted
    fun start() {
        lm.requestLocationUpdates(LocationManager.GPS_PROVIDER, 3000L, 10f, listener)
    }

    fun stop() = lm.removeUpdates(listener)
}
