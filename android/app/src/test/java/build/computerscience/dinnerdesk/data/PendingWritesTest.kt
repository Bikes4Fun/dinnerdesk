package build.computerscience.dinnerdesk.data

import java.io.IOException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.async
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test

class PendingWritesTest {
    @Test fun changingPortionsBackWhileTheFirstSaveIsPendingStillSavesTheFinalValue() = runBlocking {
        val started = CompletableDeferred<Unit>()
        val release = CompletableDeferred<Unit>()
        val writes = mutableListOf<Int>()
        val writer = PreferenceWriter<Int> {
            if (it == 5) { started.complete(Unit); release.await() }
            writes.add(it)
        }
        writer.load { 4 }
        val first = async(start = CoroutineStart.UNDISPATCHED) { writer.save(5) }
        started.await()
        val second = async(start = CoroutineStart.UNDISPATCHED) { writer.save(4) }
        release.complete(Unit)
        first.await(); second.await()
        assertEquals(listOf(5, 4), writes)
        writer.save(4)
        assertEquals(listOf(5, 4), writes)
    }

    @Test fun aFailedWriteDoesNotPreventRetryingThePreviousSavedValue() = runBlocking {
        var shouldFail = true
        val writes = mutableListOf<Int>()
        val writer = PreferenceWriter<Int> {
            if (shouldFail) throw IOException("response lost")
            writes.add(it)
        }
        writer.load { 4 }
        try { writer.save(5); fail("expected failure") } catch (_: IOException) { }
        shouldFail = false
        writer.save(4)
        assertEquals(listOf(4), writes)
    }

    @Test fun aFailedInitialLoadDoesNotPreventSaving() = runBlocking {
        val writes = mutableListOf<Int>()
        val writer = PreferenceWriter<Int> { writes.add(it) }
        try { writer.load { throw IOException("offline") }; fail("expected failure") } catch (_: IOException) { }
        writer.save(6)
        assertEquals(listOf(6), writes)
    }

    @Test fun concurrentGroceryEditsMergeAgainstTheLatestSavedObject() = runBlocking {
        var server: Map<String, Any?> = mapOf("hideChecked" to true)
        var reads = 0
        val started = CompletableDeferred<Unit>()
        val release = CompletableDeferred<Unit>()
        val updater = GroceryPreferenceUpdates(
            read = {
                val value = server.toMap()
                if (++reads == 1) { started.complete(Unit); release.await() }
                value
            },
            write = { server = it.toMap() },
        )
        val aisles = async(start = CoroutineStart.UNDISPATCHED) { updater.update(mapOf("aisles" to listOf("produce"))) }
        started.await()
        val stores = async(start = CoroutineStart.UNDISPATCHED) { updater.update(mapOf("stores" to listOf("market"))) }
        release.complete(Unit)
        aisles.await(); stores.await()
        assertEquals(mapOf("hideChecked" to true, "aisles" to listOf("produce"), "stores" to listOf("market")), server)
    }

    @Test fun pantryFailureRetainsOnlyUnsavedSelectionsAndCanRetryThem() = runBlocking {
        val saved = mutableListOf<String>()
        val result = savePantrySelection(listOf("salt", "rice", "beans")) {
            if (it == "rice") throw IOException("offline")
            saved.add(it)
        }
        assertEquals(listOf("salt"), saved)
        assertEquals(listOf("rice", "beans"), result.remaining)
        assertNotNull(result.failure)
        val retry = savePantrySelection(result.remaining) { saved.add(it) }
        assertTrue(retry.remaining.isEmpty())
        assertEquals(listOf("salt", "rice", "beans"), saved)
    }
}
