package build.computerscience.dinnerdesk.data

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/** One read/merge/write at a time for the server's shallow-merged grocery preferences. */
internal class GroceryPreferenceUpdates(
    private val read: suspend () -> Map<String, Any?>,
    private val write: suspend (Map<String, Any?>) -> Unit,
) {
    private val mutex = Mutex()
    suspend fun update(patch: Map<String, Any?>) = mutex.withLock {
        val grocery = read().toMutableMap()
        grocery.putAll(patch)
        write(grocery)
    }
}

/** Compare with the last successful value only after earlier writes finish. */
internal class PreferenceWriter<T : Any>(private val write: suspend (T) -> Unit) {
    private val mutex = Mutex()
    private var saved: T? = null
    suspend fun load(read: suspend () -> T): T = mutex.withLock { read().also { saved = it } }
    suspend fun save(value: T) = mutex.withLock {
        if (saved != value) {
            // A failed response cannot prove the server didn't apply the write.
            saved = null
            write(value)
            saved = value
        }
    }
}

internal data class PantryPickResult(val remaining: List<String>, val failure: Throwable? = null)

/** Stop at the first failure and retain exactly the names that still need saving. */
internal suspend fun savePantrySelection(names: List<String>, save: suspend (String) -> Unit): PantryPickResult {
    for ((index, name) in names.withIndex()) {
        try { save(name) }
        catch (e: CancellationException) { throw e }
        catch (e: Exception) { return PantryPickResult(names.drop(index), e) }
    }
    return PantryPickResult(emptyList())
}
