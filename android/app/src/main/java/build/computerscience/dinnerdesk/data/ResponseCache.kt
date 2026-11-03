package build.computerscience.dinnerdesk.data

import android.content.Context
import android.content.SharedPreferences
import android.webkit.CookieManager
import coil.imageLoader
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.serialization.KSerializer
import kotlinx.serialization.serializer
import okhttp3.Cookie
import okhttp3.CookieJar
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import java.io.File
import java.security.MessageDigest

/**
 * Server responses kept on the device so screens paint instantly, work with a weak signal,
 * and don't refetch on every visit. Stores the raw JSON bytes of a GET (or of a write that
 * returns the same shape). Mirrors ios/dinnerdesk/ResponseCache.swift.
 */
object ResponseCache {
    private const val ACCOUNT_KEY = "dinnerdesk.cache.account"
    private lateinit var app: Context
    private lateinit var directory: File
    lateinit var prefs: SharedPreferences
        private set

    private val accountChangedFlow = MutableSharedFlow<Unit>(extraBufferCapacity = 1)

    /** A different account (or a guest) is now using the app; drop the previous one's data. */
    val accountChanged: SharedFlow<Unit> = accountChangedFlow

    fun init(context: Context) {
        app = context.applicationContext
        directory = File(app.cacheDir, "api")
        prefs = app.getSharedPreferences("dinnerdesk", Context.MODE_PRIVATE)
    }

    /** One key per path and query, independent of query order. */
    fun key(path: String, query: Map<String, String> = emptyMap()): String {
        val trimmed = path.trim('/')
        if (query.isEmpty()) return trimmed
        return trimmed + "?" + query.entries.sortedBy { it.key }.joinToString("&") { "${it.key}=${it.value}" }
    }

    fun data(key: String): ByteArray? = try { file(key).takeIf { it.exists() }?.readBytes() } catch (_: Exception) { null }

    /** Bumped by `clear()`. A response requested before the cache was cleared is never written into the new one. */
    @Volatile
    var epoch = 0
        private set

    fun store(data: ByteArray, key: String, requestedAt: Int? = null) {
        if (requestedAt != null && requestedAt != epoch) return
        try {
            directory.mkdirs()
            val target = file(key)
            val temp = File(directory, target.name + ".tmp")
            temp.writeBytes(data)
            temp.renameTo(target)
        } catch (_: Exception) {
            // A full disk or a cleared cache only costs a network request later.
        }
    }

    /** Save a value changed on this device in the same shape the server sends. */
    inline fun <reified T> save(value: T, key: String) = save(serializer(), value, key)

    fun <T> save(serializer: KSerializer<T>, value: T, key: String) {
        try { store(Api.json.encodeToString(serializer, value).toByteArray(), key) } catch (_: Exception) {}
    }

    /** Seconds since the saved copy was written, or null when there is none. */
    fun age(key: String): Double? {
        val f = file(key)
        if (!f.exists()) return null
        return (System.currentTimeMillis() - f.lastModified()) / 1000.0
    }

    fun remove(key: String) {
        file(key).delete()
    }

    /** Drop everything, e.g. when a different account signs in on this device. */
    @OptIn(coil.annotation.ExperimentalCoilApi::class)
    fun clear() {
        epoch += 1
        directory.deleteRecursively()
        val loader = app.imageLoader
        loader.memoryCache?.clear()
        loader.diskCache?.clear()
    }

    /** Clear the cache when the signed-in account changes, so one kitchen never sees another's plan. */
    fun noteAccount(account: String?) {
        val current = account ?: "guest"
        val previous = prefs.getString(ACCOUNT_KEY, null)
        if (previous != null && previous != current) {
            clear()
            Freshness.invalidateAll()
            accountChangedFlow.tryEmit(Unit)
        }
        prefs.edit().putString(ACCOUNT_KEY, current).apply()
    }

    private fun file(key: String): File {
        val digest = MessageDigest.getInstance("SHA-256").digest(key.toByteArray())
            .joinToString("") { "%02x".format(it) }
        return File(directory, "$digest.json")
    }
}

/**
 * When each kind of data last came from the server in this launch. Screens skip the network
 * while their data is fresh; a write that changes the data marks it stale.
 */
object Freshness {
    const val PLAN = "plan"
    const val RECIPES = "recipes"
    const val GROCERY = "grocery"
    const val PREP = "prep"
    const val HOUSEHOLD = "household"
    const val HIDDEN = "hidden"
    const val AUTH = "auth"

    /** Long enough that moving between tabs never refetches; short enough to see other devices' changes later. */
    const val WINDOW = 10 * 60.0

    /** A saved recipe is shown without asking the server for this long. */
    const val RECIPE_AGE = 24 * 60 * 60.0

    private val loaded = mutableMapOf<String, Long>()

    @Synchronized
    fun isFresh(key: String, within: Double = WINDOW): Boolean {
        val at = loaded[key] ?: return false
        return (System.currentTimeMillis() - at) / 1000.0 < within
    }

    @Synchronized
    fun mark(key: String) { loaded[key] = System.currentTimeMillis() }

    @Synchronized
    fun invalidate(vararg keys: String) { for (key in keys) loaded.remove(key) }

    @Synchronized
    fun invalidateAll() = loaded.clear()

    /** A successful write elsewhere in the app can change data the Store keeps. */
    fun noteWrite(rawPath: String, @Suppress("UNUSED_PARAMETER") method: String) {
        val path = rawPath.trim('/')
        val parts = path.split("/").filter { it.isNotEmpty() }
        if (path.startsWith("auth/") || path.startsWith("household/")) {
            invalidateAll()
        } else if (path == "household") {
            invalidate(HOUSEHOLD, GROCERY)
        } else if (path.startsWith("pantry") || path.startsWith("overrides") || path.startsWith("grocery/places")) {
            invalidate(GROCERY)
        } else if (parts.firstOrNull() == "recipes") {
            // Reading a web page into a draft saves nothing.
            if (parts.size == 2 && parts[1] == "import") return
            val flagOnly = parts.size == 3 && parts[2] in setOf("favorite", "try", "hidden", "rating", "dev-notes")
            if (!flagOnly) {
                invalidate(RECIPES, PLAN, GROCERY, PREP)
                if (parts.size >= 2) ResponseCache.remove(ResponseCache.key("recipes/${parts[1]}"))
            }
        }
    }
}

/** Keeps the sign-in (and guest kitchen) cookies across launches, like HTTPCookieStorage on iOS. */
class PersistentCookieJar(context: Context) : CookieJar {
    private val store = context.getSharedPreferences("dinnerdesk.cookies", Context.MODE_PRIVATE)
    private val cookies = mutableMapOf<String, Cookie>()

    init {
        for ((_, value) in store.all) {
            val raw = value as? String ?: continue
            val url = raw.substringBefore('\n')
            val header = raw.substringAfter('\n')
            val parsed = url.toHttpUrlOrNull()?.let { Cookie.parse(it, header) } ?: continue
            if (parsed.expiresAt > System.currentTimeMillis()) cookies[id(parsed)] = parsed
        }
    }

    @Synchronized
    override fun saveFromResponse(url: HttpUrl, cookies: List<Cookie>) {
        val edit = store.edit()
        for (cookie in cookies) {
            val key = id(cookie)
            if (cookie.expiresAt <= System.currentTimeMillis()) {
                this.cookies.remove(key)
                edit.remove(key)
            } else {
                this.cookies[key] = cookie
                edit.putString(key, "${url.scheme}://${cookie.domain}/\n$cookie")
            }
        }
        edit.apply()
    }

    @Synchronized
    override fun loadForRequest(url: HttpUrl): List<Cookie> {
        val now = System.currentTimeMillis()
        cookies.values.removeAll { it.expiresAt <= now }
        return cookies.values.filter { it.matches(url) }
    }

    /** Copies the session into the web view's cookie store (Taste Lab). */
    @Synchronized
    fun syncToWebView(url: HttpUrl) {
        val manager = CookieManager.getInstance()
        for (cookie in cookies.values.filter { it.matches(url) }) manager.setCookie(url.toString(), cookie.toString())
        manager.flush()
    }

    private fun id(cookie: Cookie) = "${cookie.domain}|${cookie.path}|${cookie.name}"
}
