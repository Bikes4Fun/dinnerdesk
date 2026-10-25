package build.computerscience.dinnerdesk.ui

import android.graphics.Bitmap
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.outlined.Book
import androidx.compose.material.icons.outlined.Delete
import androidx.compose.material.icons.outlined.EditNote
import androidx.compose.material.icons.outlined.Link
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import build.computerscience.dinnerdesk.data.Api
import build.computerscience.dinnerdesk.data.CreatedRecipe
import build.computerscience.dinnerdesk.data.Ok
import build.computerscience.dinnerdesk.data.RecipeDraft
import build.computerscience.dinnerdesk.data.RecipeList
import build.computerscience.dinnerdesk.data.RecipeSummary
import coil.compose.AsyncImage
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

private enum class RecipeFormMode { Write, ImportUrl }

/** The kitchen's own recipes: ones written here, imported from a website, or saved as copies. */
@Composable
fun MyRecipesView() {
    val nav = LocalNav.current
    val scope = rememberCoroutineScope()
    var recipes by remember { mutableStateOf<List<RecipeSummary>>(emptyList()) }
    var loaded by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var form by remember { mutableStateOf<RecipeFormMode?>(null) }
    var addMenu by remember { mutableStateOf(false) }

    suspend fun load() {
        try {
            val box: RecipeList = Api.get("recipes", mapOf("mine" to "true", "limit" to "500"))
            // A server without the `mine` filter sends every recipe; keep only the kitchen's own.
            recipes = box.recipes.filter { !it.catalog }
            error = null
        } catch (e: Throwable) {
            if (!Api.isCancellation(e)) error = Api.message(e)
        }
        loaded = true
    }
    LaunchedEffect(Unit) { load() }

    Column(Modifier.fillMaxSize().background(Theme.bg)) {
        NavBar("My recipes", actions = {
            Box {
                IconAction(Icons.Filled.Add, "Add recipe") { addMenu = true }
                DropdownMenu(addMenu, { addMenu = false }, containerColor = Theme.surface) {
                    DropdownMenuItem({ Text("Write your own", style = Theme.body) }, { addMenu = false; form = RecipeFormMode.Write }, leadingIcon = { Icon(Icons.Outlined.EditNote, null) })
                    DropdownMenuItem({ Text("Import from a website", style = Theme.body) }, { addMenu = false; form = RecipeFormMode.ImportUrl }, leadingIcon = { Icon(Icons.Outlined.Link, null) })
                }
            }
        })
        ThemeList({ load() }) {
            error?.let { Box(Modifier.padding(16.dp)) { ErrorBanner(it) } }
            if (loaded && recipes.isEmpty()) {
                EmptyState("No recipes of your own yet", "Write one out, or import one from a recipe website with the + button.", Icons.Outlined.Book)
            }
            for (recipe in recipes) {
                androidx.compose.runtime.key(recipe.id) {
                    SwipeToDelete(recipe.id, onDelete = {
                        recipes = recipes.filter { it.id != recipe.id }
                        scope.launch {
                            try { Api.send<Ok>("recipes/${recipe.id}", "DELETE") } catch (e: Throwable) { error = Api.message(e); load() }
                        }
                    }) {
                        ListRow({ nav.push(Route.Recipe(recipe.id)) }) {
                            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                                RecipePhoto(recipe.photoPath, corner = 10.dp)
                                Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                    Text(recipe.name, style = Theme.rowTitle, color = Theme.ink, maxLines = 2)
                                    recipe.cookingMinutes?.let { Text("$it min", style = Theme.subtitle, color = Theme.muted) }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    form?.let { mode ->
        Sheet(onDismiss = { form = null }) {
            RecipeFormView(mode) { id -> form = null; scope.launch { load(); nav.push(Route.Recipe(id)) } }
        }
    }
}

private class StepDraft(text: String = "") {
    var text by mutableStateOf(text)
}

/** Write a recipe box by box, or read one off a public recipe page and check it before saving. */
@Composable
private fun RecipeFormView(mode: RecipeFormMode, onSaved: (Int) -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var url by remember { mutableStateOf("") }
    var importing by remember { mutableStateOf(false) }
    var imported by remember { mutableStateOf(false) }
    var typing by remember { mutableStateOf(false) }
    var name by remember { mutableStateOf("") }
    var servings by remember { mutableStateOf(4) }
    var minutes by remember { mutableStateOf("") }
    var ingredients by remember { mutableStateOf("") }
    val steps = remember { mutableStateListOf(StepDraft()) }
    var saving by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var source by remember { mutableStateOf("") }
    /** The imported page's photo, copied for this kitchen on save (its link is kept too). */
    var siteImage by remember { mutableStateOf("") }
    /** The user's own photo, used instead of the site's. */
    var ownPhoto by remember { mutableStateOf<Bitmap?>(null) }

    val showBoxes = mode == RecipeFormMode.Write || imported || typing
    val canSave = name.isNotBlank() && !saving && !importing

    val picker = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            val image = withContext(Dispatchers.IO) { loadBitmap(context, uri) }
            if (image == null) error = "Couldn't read that photo." else { ownPhoto = image; error = null }
        }
    }

    fun runImport() {
        val link = url.trim()
        if (link.isEmpty() || importing) return
        importing = true
        error = null
        scope.launch {
            try {
                val draft: RecipeDraft = Api.send("recipes/import", "POST", mapOf("url" to link))
                name = draft.name
                servings = draft.servings ?: 4
                minutes = draft.cookingMinutes?.toString() ?: ""
                ingredients = draft.ingredientLines.joinToString("\n")
                steps.clear()
                val read = draft.instructions.map { StepDraft(it.displayText) }
                steps.addAll(read.ifEmpty { listOf(StepDraft()) })
                url = draft.sourceUrl ?: link
                siteImage = draft.imageUrl ?: ""
                imported = true
            } catch (e: Throwable) {
                error = Api.message(e)
            } finally {
                importing = false
            }
        }
    }

    fun save() {
        saving = true
        error = null
        scope.launch {
            try {
                val lines = ingredients.lines().map { it.trim() }.filter { it.isNotEmpty() }
                val body = mutableMapOf<String, Any?>(
                    "name" to name.trim(),
                    "servings" to servings,
                    "cooking_minutes" to minutes.trim().toIntOrNull(),
                    "source_url" to (if (mode == RecipeFormMode.ImportUrl) url else source).trim(),
                    // The server splits "2 cloves garlic" into its amount and item.
                    "ingredients" to lines.map { mapOf("quantity" to "", "name" to it) },
                    "instructions" to steps.map { it.text.trim() }.filter { it.isNotEmpty() }.map { mapOf("text" to it, "prep" to false, "ings" to "") },
                    "cookware" to emptyList<String>(),
                    "tags" to listOf(if (mode == RecipeFormMode.ImportUrl) "imported" else "custom"),
                    "imported" to imported,
                    "photo_url" to if (imported) siteImage else "",
                )
                ownPhoto?.let { photo -> withContext(Dispatchers.Default) { jpegDataUrl(photo, 2000, listOf(85, 70, 50)) }?.let { body["photo_data"] = it } }
                val created: CreatedRecipe = Api.send("recipes", "POST", body)
                onSaved(created.id)
            } catch (e: Throwable) {
                error = Api.message(e)
            } finally {
                saving = false
            }
        }
    }

    Column(Modifier.fillMaxSize().background(Theme.bg)) {
        SheetBar(
            if (mode == RecipeFormMode.Write) "New recipe" else "Import a recipe",
            confirm = if (showBoxes) (if (saving) "Saving…" else "Save") else null, confirmEnabled = canSave, onConfirm = ::save,
        )
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
            error?.let { FormSection { Text(it, style = Theme.body, color = Theme.accent, modifier = Modifier.padding(vertical = 12.dp)) } }
            if (mode == RecipeFormMode.ImportUrl) {
                FormSection("Recipe page", footer = {
                    if (imported) Text("Check it over before you save. The ingredients and steps came from that site.")
                    else if (!typing) Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text("Paste a link to a recipe on a public website.")
                        Text("Type it in instead", color = Theme.accent, modifier = Modifier.clickable { typing = true })
                    }
                }) {
                    FormField(
                        url, { url = it }, "https://",
                        KeyboardOptions(keyboardType = KeyboardType.Uri, capitalization = KeyboardCapitalization.None, autoCorrectEnabled = false, imeAction = ImeAction.Go),
                        actions = KeyboardActions(onGo = { runImport() }),
                    )
                    Hairline()
                    val enabled = !importing && url.isNotBlank()
                    Box(Modifier.fillMaxWidth().heightIn(min = 44.dp).clickable(enabled = enabled) { runImport() }, contentAlignment = Alignment.CenterStart) {
                        Text(if (importing) "Reading…" else if (imported) "Read again" else "Import", style = Theme.body, color = if (enabled) Theme.accent else Theme.muted.copy(alpha = 0.5f))
                    }
                }
            }
            if (showBoxes) {
                FormSection("Recipe") {
                    FormField(name, { name = it }, "Name")
                    Hairline()
                    Row(Modifier.fillMaxWidth().heightIn(min = 44.dp), verticalAlignment = Alignment.CenterVertically) {
                        Text("Servings: $servings", style = Theme.body, color = Theme.ink, modifier = Modifier.weight(1f))
                        Stepper(servings, 1..50, "servings") { servings = it }
                    }
                    Hairline()
                    FormField(minutes, { minutes = it.filter(Char::isDigit) }, "Minutes (optional)", KeyboardOptions(keyboardType = KeyboardType.Number))
                }
                FormSection("Ingredients", footer = { Text("One per line, amount first.") }) {
                    FormField(ingredients, { ingredients = it }, "1 onion\n2 cloves garlic", minLines = 5)
                }
                FormSection("Photo", footer = {
                    if (ownPhoto == null && imported && siteImage.isNotEmpty()) Text("This is the photo from that page, saved for your kitchen only. Don't like it? Choose your own.")
                    else if (ownPhoto == null) Text("Add a photo you took or one you're free to use.")
                }) {
                    val own = ownPhoto
                    if (own != null) {
                        Image(own.asImageBitmap(), null, contentScale = ContentScale.Crop, modifier = Modifier.padding(top = 10.dp).size(140.dp).clip(RoundedCornerShape(12.dp)))
                    } else if (imported && siteImage.isNotEmpty()) {
                        AsyncImage(siteImage, null, contentScale = ContentScale.Crop, modifier = Modifier.padding(top = 10.dp).size(140.dp).clip(RoundedCornerShape(12.dp)).background(Theme.chip))
                    }
                    Box(
                        Modifier.fillMaxWidth().heightIn(min = 44.dp).clickable { picker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) },
                        contentAlignment = Alignment.CenterStart,
                    ) { Text(if (ownPhoto == null) "Choose your own photo" else "Choose a different photo", style = Theme.body, color = Theme.accent) }
                    if (ownPhoto != null) {
                        Hairline()
                        Box(Modifier.fillMaxWidth().heightIn(min = 44.dp).clickable { ownPhoto = null }, contentAlignment = Alignment.CenterStart) {
                            Text(if (imported && siteImage.isNotEmpty()) "Use the site's photo" else "Remove photo", style = Theme.body, color = Theme.destructive)
                        }
                    }
                }
                if (mode == RecipeFormMode.Write) {
                    FormSection("Source (optional)", footer = { Text("Where this recipe came from.") }) {
                        FormField(source, { source = it }, "https://", KeyboardOptions(keyboardType = KeyboardType.Uri, capitalization = KeyboardCapitalization.None, autoCorrectEnabled = false))
                    }
                }
                FormSection("Steps") {
                    steps.forEachIndexed { index, step ->
                        if (index > 0) Hairline()
                        Row(verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text("${index + 1}.", style = Theme.count, color = Theme.muted, modifier = Modifier.padding(top = 14.dp))
                            Box(Modifier.weight(1f)) { FormField(step.text, { step.text = it }, "What to do", minLines = 2) }
                            if (steps.size > 1) IconAction(Icons.Outlined.Delete, "Delete step ${index + 1}", tint = Theme.muted, size = 20.dp) { steps.removeAt(index) }
                        }
                    }
                    Hairline()
                    Row(
                        Modifier.fillMaxWidth().heightIn(min = 44.dp).clickable { steps.add(StepDraft()) },
                        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp),
                    ) {
                        Icon(Icons.Filled.Add, null, tint = Theme.accent, modifier = Modifier.size(20.dp))
                        Text("Add step", style = Theme.body, color = Theme.accent)
                    }
                }
            }
        }
    }
}
