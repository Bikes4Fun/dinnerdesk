package build.computerscience.dinnerdesk.data

import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.decodeFromJsonElement
import kotlinx.serialization.json.jsonObject
import org.junit.Assert.*
import org.junit.Test

class PrepPresentationTest {
    private val json = Json { ignoreUnknownKeys = true }
    private fun fixture(): Pair<PrepTask, List<PrepInstructionGroup>> {
        val root = generateSequence(File(requireNotNull(System.getProperty("user.dir")))) { it.parentFile }
            .first { File(it, "tests/fixtures/prep_presentation.json").isFile }
        val fixture = json.parseToJsonElement(File(root, "tests/fixtures/prep_presentation.json").readText()).jsonObject
        return json.decodeFromJsonElement<PrepTask>(fixture.getValue("task")) to
            json.decodeFromJsonElement<List<PrepInstructionGroup>>(fixture.getValue("expected"))
    }

    @Test fun cachedFallbackMatchesSharedContractAndPreservesSource() {
        val (task, expected) = fixture()
        assertEquals(expected, PrepTaskPresentation(task).instructionGroups)
        assertEquals("Whisk the other half to make the glaze.", task.meals.first().steps!!.first().text)
        assertEquals("source57", task.meals.first().steps!!.first().key)
        assertEquals("Refrigerate in a covered container.", task.storage)
    }

    @Test fun serverGroupsAreAuthoritativeIncludingEmptyResults() {
        val (task, expected) = fixture()
        assertEquals(expected, PrepTaskPresentation(task.copy(instructionGroups = expected)).instructionGroups)
        assertTrue(PrepTaskPresentation(task.copy(instructionGroups = emptyList())).instructionGroups.isEmpty())
    }
}
