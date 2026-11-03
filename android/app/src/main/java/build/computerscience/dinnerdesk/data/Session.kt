package build.computerscience.dinnerdesk.data

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import build.computerscience.dinnerdesk.BuildConfig
import kotlinx.serialization.json.JsonObject

/** Who is using the app: signed in, a guest, or not decided yet. Mirrors Session in AuthView.swift. */
class Session {
    private val prefs get() = ResponseCache.prefs

    var status by mutableStateOf<AuthStatus?>(null)
    var loadError by mutableStateOf<String?>(null)

    private val guestState = mutableStateOf(prefs.getBoolean(GUEST_KEY, false))
    /** The person chose "Continue as guest" on this device. */
    var guest: Boolean
        get() = guestState.value
        set(value) {
            guestState.value = value
            prefs.edit().putBoolean(GUEST_KEY, value).apply()
        }

    /** Show the sign-in screen before the app? */
    val needsSignIn: Boolean
        get() {
            val s = status ?: return false
            if (s.authenticated) return false
            return !guest
        }

    val canContinueAsGuest = true

    /** Show the quick start tour. Set it from anywhere (More, Settings) to replay the tour. */
    var showTour by mutableStateOf(false)
    private var tourCheckedFor: String? = null

    /** First run: the tour once if the household hasn't finished the current version, or this device is on a new build. */
    suspend fun checkTour() {
        val s = status ?: return
        if (needsSignIn) return
        val key = "${s.householdId ?: 0}"
        if (tourCheckedFor != key) {
            try {
                val prefs = KitchenApi.prefs()
                tourCheckedFor = key
                if (Tour.isDue(prefs) || Tour.isNewBuild) showTour = true else Tour.noteBuild()
            } catch (e: Throwable) {
                if (Api.isCancellation(e)) return
                loadError = Api.message(e)
            }
        }
    }

    suspend fun refresh() {
        try {
            val next = AuthApi.status()
            // Clear saved plans and recipes before showing a different account's data.
            ResponseCache.noteAccount(if (next.authenticated) "${next.email ?: ""}:${next.householdId ?: 0}" else null)
            status = next
            loadError = null
            if (next.authenticated) guest = false
        } catch (e: Throwable) {
            if (Api.isCancellation(e)) return
            loadError = Api.message(e)
        }
    }

    fun continueAsGuest() { guest = true }

    suspend fun signOut() {
        try {
            AuthApi.logout()
        } catch (e: Throwable) {
            loadError = Api.message(e)
            return
        }
        guest = false
        tourCheckedFor = null
        refresh()
    }

    /** After the server deleted the account its session is already gone, so skip logout. */
    suspend fun accountDeleted() {
        guest = false
        tourCheckedFor = null
        refresh()
    }

    private companion object {
        const val GUEST_KEY = "dinnerdesk.guest"
    }
}

/** Tour bookkeeping shared by Session and the tour screen (TourView.swift). */
object Tour {
    /** Raise this (and TOUR_VERSION in web/src/Tour.jsx) with a major update. */
    const val VERSION = 2
    private const val BUILD_KEY = "dinnerdesk.tourBuild"
    private val build = BuildConfig.VERSION_CODE.toString()

    /** The tour version this household last finished or skipped; 0 if never. */
    fun seen(prefs: JsonObject): Int = prefs.int("tour_version") ?: if (prefs["tour_done"] == null) 0 else 1

    fun isDue(prefs: JsonObject) = seen(prefs) < VERSION

    /** This device saw the tour (or was checked) on an earlier build. */
    val isNewBuild: Boolean
        get() {
            val last = ResponseCache.prefs.getString(BUILD_KEY, null) ?: return false
            return last != build
        }

    fun noteBuild() { ResponseCache.prefs.edit().putString(BUILD_KEY, build).apply() }
}
