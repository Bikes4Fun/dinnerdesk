package build.computerscience.dinnerdesk.data

import android.content.Context
import android.util.Log
import build.computerscience.dinnerdesk.BuildConfig
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.serialization.KSerializer
import kotlinx.serialization.SerializationException
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.serializer
import okhttp3.Call
import okhttp3.Callback
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import java.io.IOException
import java.net.ConnectException
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import java.util.concurrent.TimeUnit
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/** Server calls. Mirrors ios/dinnerdesk/API.swift: same paths, caching and error words. */
object Api {
    val origin: HttpUrl = BuildConfig.APP_ORIGIN.toHttpUrl()

    /** Sent as X-Dinnerdesk-App on every request so the server log shows which build sent it (#2). */
    val appBuild = "android ${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})"

    val json = Json {
        ignoreUnknownKeys = true
        coerceInputValues = true
        explicitNulls = false
        encodeDefaults = true
    }

    lateinit var client: OkHttpClient
        private set
    lateinit var cookies: PersistentCookieJar
        private set

    fun init(context: Context) {
        if (::client.isInitialized) return
        ResponseCache.init(context)
        cookies = PersistentCookieJar(context)
        client = OkHttpClient.Builder()
            .cookieJar(cookies)
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .build()
    }

    fun url(path: String): String = origin.newBuilder().addPathSegments(path.trim('/')).build().toString()

    fun photoUrl(path: String?): String? {
        if (path.isNullOrEmpty()) return null
        if (path.startsWith("http")) return path
        return origin.resolve(path.removePrefix("/"))?.toString()
    }

    /** `cache = true` keeps the response on the device so `cached` can show it instantly next time. */
    suspend inline fun <reified T> get(
        path: String, query: Map<String, String> = emptyMap(), reportErrors: Boolean = true, cache: Boolean = false,
    ): T = get(serializer(), path, query, reportErrors, cache)

    suspend fun <T> get(
        serializer: KSerializer<T>, path: String, query: Map<String, String> = emptyMap(),
        reportErrors: Boolean = true, cache: Boolean = false,
    ): T {
        val epoch = ResponseCache.epoch
        try {
            val request = Request.Builder().url(apiUrl(path, query)).header("X-Dinnerdesk-App", appBuild).build()
            val (code, text) = execute(request, "GET", path)
            throwIfBad(code, text)
            val value = decode(serializer, text)
            if (cache) ResponseCache.store(text.toByteArray(), ResponseCache.key(path, query), epoch)
            return value
        } catch (error: Throwable) {
            if (reportErrors) reportFailure(error)
            throw error
        }
    }

    /** The raw bytes of a GET, for files the person saves (Download my data, #64). */
    suspend fun getData(path: String): ByteArray {
        val request = Request.Builder().url(apiUrl(path)).header("X-Dinnerdesk-App", appBuild).build()
        val response = await(client.newCall(request))
        response.use {
            val bytes = it.body?.bytes() ?: ByteArray(0)
            throwIfBad(it.code, String(bytes))
            return bytes
        }
    }

    /** The last saved response for a GET, decoded, or null when there is none or it no longer decodes. */
    inline fun <reified T> cached(path: String, query: Map<String, String> = emptyMap()): T? =
        cached(serializer(), path, query)

    fun <T> cached(serializer: KSerializer<T>, path: String, query: Map<String, String> = emptyMap()): T? {
        val data = ResponseCache.data(ResponseCache.key(path, query)) ?: return null
        return try { json.decodeFromString(serializer, String(data)) } catch (_: Exception) { null }
    }

    /** `cacheAs` saves the response under that GET path when a write returns the same shape. */
    suspend inline fun <reified T> send(
        path: String, method: String, body: Map<String, Any?>? = null, cacheAs: String? = null,
    ): T = send(serializer(), path, method, body, cacheAs)

    suspend fun <T> send(
        serializer: KSerializer<T>, path: String, method: String, body: Map<String, Any?>? = null, cacheAs: String? = null,
    ): T {
        val epoch = ResponseCache.epoch
        val payload = body?.let { toJson(it).toString() }
        try {
            val requestBody = (payload ?: if (method == "GET") null else "").let {
                it?.toRequestBody(JSON_TYPE)
            }
            val request = Request.Builder().url(apiUrl(path))
                .header("X-Dinnerdesk-App", appBuild)
                .method(method, if (method == "GET") null else requestBody)
                .build()
            val (code, text) = execute(request, method, path)
            throwIfBad(code, text)
            val value = decode(serializer, text)
            Freshness.noteWrite(path, method)
            if (cacheAs != null) ResponseCache.store(text.toByteArray(), ResponseCache.key(cacheAs), epoch)
            return value
        } catch (error: Throwable) {
            reportFailure(error)
            throw error
        }
    }

    /** Free-form JSON for household prefs (KitchenAPI.json on iOS). */
    suspend fun jsonObject(path: String, method: String = "GET", body: Map<String, Any?>? = null): JsonObject =
        if (method == "GET") get(JsonObject.serializer(), path) else send(JsonObject.serializer(), path, method, body)

    /** Leaving a screen cancels its requests. That is not a failure to show the user. */
    fun isCancellation(error: Throwable): Boolean = error is CancellationException

    fun reportFailure(error: Throwable) {
        if (isCancellation(error) || error is ApiError) return
        Log.w("Dinnerdesk", "Request failed: ${error.javaClass.simpleName}")
    }

    /** What the person reads when a call fails, like `localizedDescription` on iOS. */
    fun message(error: Throwable): String = when (error) {
        is ApiError -> error.message
        is UnknownHostException, is ConnectException -> "The Internet connection appears to be offline."
        is SocketTimeoutException -> "The request timed out."
        is SerializationException, is IllegalArgumentException -> "The data couldn’t be read because it isn’t in the correct format."
        is IOException -> "Couldn’t connect to the server. Please try again."
        else -> error.message ?: "Couldn't complete this action. Please try again."
    }

    private fun apiUrl(path: String, query: Map<String, String> = emptyMap()): HttpUrl {
        val builder = origin.newBuilder().addPathSegments("api/" + path.trim('/'))
        for ((key, value) in query) builder.addQueryParameter(key, value)
        return builder.build()
    }

    private suspend fun execute(request: Request, method: String, path: String): Pair<Int, String> {
        val response = await(client.newCall(request))
        response.use {
            // Keep method/path diagnostics out of the UI and omit bodies and query values.
            if (it.code == 405) {
                Log.w("Dinnerdesk", "Request rejected: $method /api/$path (405); allowed: ${it.header("Allow") ?: "unspecified"}")
            }
            return it.code to (it.body?.string() ?: "")
        }
    }

    private fun throwIfBad(code: Int, body: String) {
        if (code !in 200..299) throw ApiError(code, body)
    }

    private fun <T> decode(serializer: KSerializer<T>, text: String): T = json.decodeFromString(serializer, text)

    suspend fun await(call: Call): Response = suspendCancellableCoroutine { continuation ->
        continuation.invokeOnCancellation { call.cancel() }
        call.enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                if (continuation.isActive) continuation.resumeWithException(e)
            }

            override fun onResponse(call: Call, response: Response) {
                if (continuation.isActive) continuation.resume(response) else response.close()
            }
        })
    }

    private val JSON_TYPE = "application/json".toMediaType()

    /** Maps, lists, strings, numbers, booleans and null, like JSONSerialization. */
    fun toJson(value: Any?): JsonElement = when (value) {
        null -> JsonNull
        is JsonElement -> value
        is String -> JsonPrimitive(value)
        is Number -> JsonPrimitive(value)
        is Boolean -> JsonPrimitive(value)
        is Map<*, *> -> JsonObject(value.entries.associate { (k, v) -> k.toString() to toJson(v) })
        is Iterable<*> -> JsonArray(value.map { toJson(it) })
        is Array<*> -> JsonArray(value.map { toJson(it) })
        else -> JsonPrimitive(value.toString())
    }
}

class ApiError(val code: Int, val body: String) : Exception() {
    override val message: String
        get() {
            if (code == 404 || code == 405) return "This action is currently unavailable. Please try again later. If it keeps happening, contact Dinnerdesk support."
            if (code == 401) return "Please sign in again to continue."
            if (code == 403) return "You don't have access to this action."
            if (code >= 500) return "The server couldn't complete this action. Please try again shortly."
            try {
                val obj = Api.json.parseToJsonElement(body) as? JsonObject
                if (obj != null) {
                    val detail = obj["detail"]
                    if (detail is JsonPrimitive && detail.isString) return detail.content
                    if (detail is JsonObject) (detail["message"] as? JsonPrimitive)?.let { if (it.isString) return it.content }
                    (obj["message"] as? JsonPrimitive)?.let { if (it.isString) return it.content }
                }
            } catch (_: Exception) {
            }
            return "Couldn't complete this action. Please try again."
        }
}
