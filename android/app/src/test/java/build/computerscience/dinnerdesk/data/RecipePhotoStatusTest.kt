package build.computerscience.dinnerdesk.data

import java.io.File
import kotlinx.serialization.json.Json
import org.junit.Assert.*
import org.junit.Test

class RecipePhotoStatusTest {
    private val json = Json { ignoreUnknownKeys = true }

    @Test fun sharedFixtureKeepsReviewPhotoFlagsAndCreditsIndependent() {
        val root = generateSequence(File(requireNotNull(System.getProperty("user.dir")))) { it.parentFile }
            .first { File(it, "tests/fixtures/recipe_photo_status.json").isFile }
        val recipe = json.decodeFromString<RecipeDetail>(File(root, "tests/fixtures/recipe_photo_status.json").readText())
        assertTrue(recipe.reviewed)
        assertEquals(2, recipe.galleryPhotos.size)
        val tested = recipe.galleryPhotos[0]
        assertTrue(tested.primary && tested.tested)
        assertFalse(tested.ai)
        assertEquals("Photo: Dinnerdesk", tested.credit)
        assertEquals("https://example.test/photos/tested", tested.sourceLink)
        assertTrue(recipe.galleryPhotos[1].ai)
        assertFalse(recipe.galleryPhotos[1].tested)
        assertNull(recipe.galleryPhotos[1].sourceLink)
    }

    @Test fun oldCachesHaveAPhotoFallbackButAnExplicitEmptyGalleryIsAuthoritative() {
        val old = json.decodeFromString<RecipeDetail>("""{"id":1,"name":"Soup","photo_path":"food/old.jpg","photo_ai":true}""")
        assertFalse(old.reviewed)
        assertEquals("food/old.jpg", old.galleryPhotos.single().path)
        assertTrue(old.galleryPhotos.single().ai)
        assertFalse(old.galleryPhotos.single().tested)
        assertTrue(old.copy(photos = emptyList()).galleryPhotos.isEmpty())
        assertNull(RecipeGalleryPhoto("x", sourceUrl = "javascript:alert(1)").sourceLink)
    }
}
