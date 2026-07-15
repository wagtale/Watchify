package com.watchify.app

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

object WeatherManager {

    @SuppressLint("MissingPermission")
    fun getDeviceLocation(context: Context): Pair<Double, Double>? {
        val locationManager = context.getSystemService(Context.LOCATION_SERVICE) as android.location.LocationManager
        val hasFine = ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
        val hasCoarse = ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED
        
        if (!hasFine && !hasCoarse) {
            return null
        }
        
        try {
            val providers = locationManager.getProviders(true)
            var bestLocation: android.location.Location? = null
            for (provider in providers) {
                val l = locationManager.getLastKnownLocation(provider) ?: continue
                if (bestLocation == null || l.time > bestLocation.time) {
                    bestLocation = l
                }
            }
            if (bestLocation != null) {
                return Pair(bestLocation.latitude, bestLocation.longitude)
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
        return null
    }

    fun syncWeather(context: Context, bleManager: BleManager) {
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val prefs = context.getSharedPreferences("watch_prefs", Context.MODE_PRIVATE)
                val city = prefs.getString("weather_city", "") ?: ""
                var lat: Double = 0.0
                var lon: Double = 0.0
                var foundLocation = false

                if (city.isNotEmpty()) {
                    try {
                        val geoUrl = "https://nominatim.openstreetmap.org/search?q=${java.net.URLEncoder.encode(city, "UTF-8")}&format=json&limit=1"
                        val geoConn = URL(geoUrl).openConnection() as HttpURLConnection
                        geoConn.setRequestProperty("User-Agent", "WatchifyApp/1.0")
                        geoConn.connectTimeout = 5000
                        val geoText = geoConn.inputStream.bufferedReader().use { it.readText() }
                        val geoJson = org.json.JSONArray(geoText)
                        if (geoJson.length() > 0) {
                            val result = geoJson.getJSONObject(0)
                            lat = result.getString("lat").toDouble()
                            lon = result.getString("lon").toDouble()
                            foundLocation = true
                            prefs.edit().putFloat("last_lat", lat.toFloat()).putFloat("last_lon", lon.toFloat()).apply()
                        }
                    } catch(e:Exception) {}
                }

                if (!foundLocation) {
                    try {
                        // Auto-detect location using IP API for seamless UX
                        val ipUrl = "http://ip-api.com/json/"
                        val ipConn = URL(ipUrl).openConnection() as HttpURLConnection
                        ipConn.connectTimeout = 5000
                        val ipText = ipConn.inputStream.bufferedReader().use { it.readText() }
                        val ipJson = JSONObject(ipText)
                        if (ipJson.getString("status") == "success") {
                            lat = ipJson.getDouble("lat")
                            lon = ipJson.getDouble("lon")
                            val detectedCity = ipJson.getString("city")
                            prefs.edit()
                                .putFloat("last_lat", lat.toFloat())
                                .putFloat("last_lon", lon.toFloat())
                                .putString("weather_city", detectedCity)
                                .apply()
                            foundLocation = true
                            
                            // Broadcast city update to update MainActivity UI if open
                            val intent = android.content.Intent("com.watchify.app.CITY_UPDATED")
                            intent.setPackage(context.packageName)
                            intent.putExtra("city", detectedCity)
                            context.sendBroadcast(intent)
                        }
                    } catch(e:Exception) {}
                }

                if (!foundLocation) {
                    val loc = getDeviceLocation(context)
                    if (loc != null) {
                        lat = loc.first
                        lon = loc.second
                        prefs.edit().putFloat("last_lat", lat.toFloat()).putFloat("last_lon", lon.toFloat()).apply()
                        foundLocation = true
                        
                        try {
                            // Reverse geocode via OpenStreetMap to get city name
                            val revUrl = "https://nominatim.openstreetmap.org/reverse?lat=$lat&lon=$lon&format=json"
                            val revConn = URL(revUrl).openConnection() as HttpURLConnection
                            revConn.setRequestProperty("User-Agent", "WatchifyApp/1.0")
                            revConn.connectTimeout = 5000
                            val revText = revConn.inputStream.bufferedReader().use { it.readText() }
                            val revJson = JSONObject(revText)
                            if (revJson.has("address")) {
                                val addr = revJson.getJSONObject("address")
                                val detectedCity = addr.optString("city", addr.optString("town", addr.optString("village", "")))
                                if (detectedCity.isNotEmpty()) {
                                    prefs.edit().putString("weather_city", detectedCity).apply()
                                    val intent = android.content.Intent("com.watchify.app.CITY_UPDATED")
                                    intent.setPackage(context.packageName)
                                    intent.putExtra("city", detectedCity)
                                    context.sendBroadcast(intent)
                                }
                            }
                        } catch(e:Exception) {}
                    }
                }

                if (!foundLocation) {
                    lat = prefs.getFloat("last_lat", 40.7128f).toDouble()
                    lon = prefs.getFloat("last_lon", -74.0060f).toDouble()
                }

                var windyCurrentTemp: Int? = null
                val windyMax = mutableMapOf<Int, Int>()
                val windyMin = mutableMapOf<Int, Int>()
                val windyWeather = mutableMapOf<Int, MutableList<Int>>()
                
                try {
                    val urlStr = "https://api.windy.com/api/point-forecast/v2"
                    val jsonBody = JSONObject().apply {
                        put("lat", lat)
                        put("lon", lon)
                        put("model", "gfs")
                        put("parameters", org.json.JSONArray(listOf("temp", "ptype", "lclouds")))
                        put("levels", org.json.JSONArray(listOf("surface")))
                        put("key", BuildConfig.WINDY_API_KEY)
                    }
                    val urlConnection = URL(urlStr).openConnection() as HttpURLConnection
                    urlConnection.requestMethod = "POST"
                    urlConnection.setRequestProperty("Content-Type", "application/json")
                    urlConnection.doOutput = true
                    urlConnection.connectTimeout = 5000
                    urlConnection.readTimeout = 5000
                    urlConnection.outputStream.bufferedWriter().use { it.write(jsonBody.toString()) }
                    
                    val text = urlConnection.inputStream.bufferedReader().use { it.readText() }
                    val json = JSONObject(text)
                    
                    val tsArray = json.getJSONArray("ts")
                    val tempsArray = json.getJSONArray("temp-surface")
                    val ptypesArray = json.getJSONArray("ptype-surface")
                    val cloudsArray = json.getJSONArray("lclouds-surface")
                    val startTs = tsArray.getLong(0)
                    
                    for (i in 0 until tsArray.length()) {
                        val ts = tsArray.getLong(i)
                        val dayIdx = ((ts - startTs) / (1000 * 60 * 60 * 24)).toInt()
                        if (dayIdx in 0..2) {
                            val tempC = (tempsArray.getDouble(i) - 273.15).toInt()
                            windyMax[dayIdx] = maxOf(windyMax[dayIdx] ?: -100, tempC)
                            windyMin[dayIdx] = minOf(windyMin[dayIdx] ?: 100, tempC)
                            val ptype = ptypesArray.optInt(i, 0)
                            val cloud = cloudsArray.optDouble(i, 0.0)
                            val watchWType = when {
                                ptype > 0 -> 4 // Rain
                                cloud > 50 -> 2 // Cloudy
                                else -> 0 // Sunny
                            }
                            windyWeather.getOrPut(dayIdx) { mutableListOf() }.add(watchWType)
                        }
                    }
                    windyCurrentTemp = (tempsArray.getDouble(0) - 273.15).toInt()
                } catch (e: Exception) { e.printStackTrace() }

                var meteoCurrentTemp: Int? = null
                val meteoMax = mutableMapOf<Int, Int>()
                val meteoMin = mutableMapOf<Int, Int>()
                val meteoWeather = mutableMapOf<Int, Int>()
                
                try {
                    val urlStr = "https://api.open-meteo.com/v1/forecast?latitude=$lat&longitude=$lon&current_weather=true&daily=temperature_2m_max,temperature_2m_min,weathercode&timezone=auto"
                    val urlConnection = URL(urlStr).openConnection() as HttpURLConnection
                    urlConnection.connectTimeout = 5000
                    urlConnection.readTimeout = 5000
                    val text = urlConnection.inputStream.bufferedReader().use { it.readText() }
                    val json = JSONObject(text)
                    
                    val current = json.getJSONObject("current_weather")
                    meteoCurrentTemp = current.getDouble("temperature").toInt()
                    
                    val daily = json.getJSONObject("daily")
                    val maxTemps = daily.getJSONArray("temperature_2m_max")
                    val minTemps = daily.getJSONArray("temperature_2m_min")
                    val codes = daily.getJSONArray("weathercode")
                    
                    val count = maxTemps.length().coerceAtMost(3)
                    for (i in 0 until count) {
                        meteoMax[i] = maxTemps.getDouble(i).toInt()
                        meteoMin[i] = minTemps.getDouble(i).toInt()
                        val wcode = codes.getInt(i)
                        meteoWeather[i] = when (wcode) {
                            0 -> 0 // Sunny
                            1, 2, 3 -> 2 // Cloudy
                            45, 48 -> 7 // Fog
                            71, 73, 75 -> 6 // Snow
                            else -> 4 // Rain/Shower
                        }
                    }
                } catch (e: Exception) { e.printStackTrace() }

                val currentTempList = listOfNotNull(windyCurrentTemp, meteoCurrentTemp)
                val currentTemp = if (currentTempList.isNotEmpty()) currentTempList.average().toInt() else 0
                
                val forecasts = mutableListOf<WatchProtocol.WeatherForecast>()
                for (day in 0..2) {
                    val maxList = listOfNotNull(windyMax[day], meteoMax[day])
                    val minList = listOfNotNull(windyMin[day], meteoMin[day])
                    
                    val aggMax = if (maxList.isNotEmpty()) maxList.average().toInt() else currentTemp
                    val aggMin = if (minList.isNotEmpty()) minList.average().toInt() else currentTemp
                    
                    val wList = windyWeather[day] ?: listOf(0)
                    val windyCode = wList.groupingBy { it }.eachCount().maxByOrNull { it.value }?.key ?: 0
                    val meteoCode = meteoWeather[day] ?: 0
                    
                    val aggCode = maxOf(windyCode, meteoCode)
                    forecasts.add(WatchProtocol.WeatherForecast(aggCode, aggMin, aggMax))
                }
                
                val weatherPacket = WatchProtocol.buildWeatherPacket(currentTemp, forecasts)
                bleManager.sendChunks(weatherPacket)
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
    }
}
