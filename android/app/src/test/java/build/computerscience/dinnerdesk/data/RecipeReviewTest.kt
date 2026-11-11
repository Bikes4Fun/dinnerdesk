package build.computerscience.dinnerdesk.data

import kotlinx.serialization.json.Json
import org.junit.Assert.*
import org.junit.Test

class RecipeReviewTest {
    @Test fun oldCachedRecipesDefaultToUnreviewed() {
        val row = Json.decodeFromString<RecipeSummary>("""{"id":1,"name":"Soup"}""")
        val detail = Json.decodeFromString<RecipeDetail>("""{"id":1,"name":"Soup"}""")
        assertFalse(row.reviewed)
        assertFalse(detail.reviewed)
        assertTrue(Json.decodeFromString<RecipeSummary>("""{"id":1,"name":"Soup","reviewed":true}""").reviewed)
    }

    @Test fun reviewedFilterComposesWithFavoritesAndIgnoresTags() {
        val rows = listOf(
            RecipeSummary(1, "Reviewed", favorited = true, reviewed = true),
            RecipeSummary(2, "Tag only", tags = listOf("reviewed")),
            RecipeSummary(3, "Reviewed sauce", tags = listOf("sauce"), reviewed = true),
        )
        val lists = RecipeCollections(rows)
        assertEquals(listOf(1, 3), lists.filter(rows, setOf(RecipeSearchFilter.Reviewed), emptySet()).map { it.id })
        assertEquals(listOf(1), lists.filter(rows, setOf(RecipeSearchFilter.Reviewed, RecipeSearchFilter.Fav), emptySet()).map { it.id })
        assertEquals(rows, lists.filter(rows, emptySet(), emptySet()))
    }
}
