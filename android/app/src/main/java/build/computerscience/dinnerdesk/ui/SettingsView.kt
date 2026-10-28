package build.computerscience.dinnerdesk.ui

import android.annotation.SuppressLint
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.util.Base64
import android.view.ViewGroup
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.HelpOutline
import androidx.compose.material.icons.filled.Cancel
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.outlined.AccountCircle
import androidx.compose.material.icons.outlined.AddPhotoAlternate
import androidx.compose.material.icons.outlined.Explore
import androidx.compose.material.icons.outlined.Feedback
import androidx.compose.material.icons.outlined.Forum
import androidx.compose.material.icons.outlined.IosShare
import androidx.compose.material.icons.outlined.Key
import androidx.compose.material.icons.outlined.PanTool
import androidx.compose.material.icons.outlined.WifiOff
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import build.computerscience.dinnerdesk.AppUrls
import build.computerscience.dinnerdesk.data.Api
import build.computerscience.dinnerdesk.data.ApiError
import build.computerscience.dinnerdesk.data.AuthApi
import build.computerscience.dinnerdesk.data.Copy
import build.computerscience.dinnerdesk.data.HouseholdMember
import build.computerscience.dinnerdesk.data.KitchenApi
import build.computerscience.dinnerdesk.data.KitchenItemSearch
import build.computerscience.dinnerdesk.data.Ok
import build.computerscience.dinnerdesk.data.ResponseCache
import build.computerscience.dinnerdesk.data.obj
import build.computerscience.dinnerdesk.data.string
import build.computerscience.dinnerdesk.data.strings
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream
import java.time.LocalDate
import kotlin.math.max
import kotlin.math.min

/** Settings: account & household, privacy, help. */
@Composable
fun SettingsView() {
    val session = LocalSession.current
    val nav = LocalNav.current
    val openUrl = rememberOpenUrl()
    Column(Modifier.fillMaxSize().background(Theme.bg)) {
        NavBar()
        ThemeList {
            LargeTitle("Settings")
            ListRow({ nav.push(Route.Account) }) { ThemeIconRow("Account & security", Icons.Outlined.AccountCircle, session.status?.email ?: "Guest") }
            ListRow({ nav.push(Route.Privacy) }) { ThemeIconRow("Privacy", Icons.Outlined.PanTool) }
            ListRow({ openUrl(Api.url("support")) }, chevron = false) { ThemeIconRow("Help & support", Icons.AutoMirrored.Outlined.HelpOutline) }
            ListRow({ nav.push(Route.Feedback) }) { ThemeIconRow("Report a bug or suggest a feature", Icons.Outlined.Feedback) }
            ListRow({ openUrl("https://dinnerdesk.computerscience.build") }, chevron = false) { ThemeIconRow("${Copy.appName} on the web", Icons.Outlined.Explore) }
            ListRow({ openUrl("https://x.com/DinnerDesk") }, chevron = false) { ThemeIconRow("Twitter", Icons.Outlined.Forum, "@DinnerDesk") }
            ListHeader("About recipes & photos")
            Box(Modifier.padding(horizontal = 20.dp, vertical = 6.dp)) { StarTip("settings.gold-star") }
        }
    }
}

/** What you eat: diet, allergies, things to avoid, cook time. Saved to household prefs.filters. */
object FilterOptions {
    val diets = listOf("omnivore", "pescatarian", "vegetarian", "vegan", "gluten-free", "dairy-free")
    /** Pick one of these. The others (gluten-free, dairy-free) combine with it. */
    val exclusiveDiets = setOf("omnivore", "pescatarian", "vegetarian", "vegan")
    val allergens = listOf(
        "soy" to "Soy", "peanut" to "Peanut", "tree-nuts" to "Tree nuts", "dairy" to "Dairy", "egg" to "Egg",
        "gluten" to "Gluten", "sesame" to "Sesame", "fish" to "Fish", "shellfish" to "Shellfish",
        "poultry" to "Poultry", "red-meat" to "Red meat",
    )
    val avoids = listOf(
        "fish", "cilantro", "mushrooms", "onions", "bell peppers", "olives", "goat cheese", "nuts",
        "beans", "tofu", "eggplant", "brussels sprouts", "coconut", "spicy",
    )
    val who = listOf("beginner" to "Beginner", "family" to "Family", "kids" to "Kids", "entertaining" to "Entertaining")
    val cuisines = listOf("italian" to "Italian", "mexican" to "Mexican", "asian" to "Asian", "american" to "American", "mediterranean" to "Mediterranean")
    val proteins = listOf("chicken" to "Chicken", "beef" to "Beef", "pork" to "Pork", "seafood" to "Seafood", "turkey" to "Turkey")
    val times = listOf("any" to "Any time", "30" to "30 min or less", "45" to "45 min or less")
    val dietLabels = mapOf(
        "omnivore" to "Omnivore", "pescatarian" to "Pescatarian", "vegetarian" to "Vegetarian", "vegan" to "Vegan",
        "gluten-free" to "Gluten-free", "dairy-free" to "Dairy-free",
    )

    /** Omnivore, pescatarian, vegetarian and vegan rule each other out; the others toggle on their own. */
    fun toggled(diets: Set<String>, item: String): Set<String> =
        if (item in exclusiveDiets) diets - exclusiveDiets + item else if (item in diets) diets - item else diets + item

    /** Older saves could hold several of omnivore / vegetarian / vegan; keep the strictest. */
    fun cleaned(saved: List<String>): Set<String> {
        val picked = listOf("vegan", "vegetarian", "pescatarian", "omnivore").firstOrNull { it in saved }
        return saved.toSet() - exclusiveDiets + listOfNotNull(picked)
    }
}

@Composable
fun FiltersView() {
    val store = LocalStore.current
    val selectTab = LocalSelectTab.current
    val scope = rememberCoroutineScope()
    var diets by remember { mutableStateOf(setOf("omnivore")) }
    var allergens by remember { mutableStateOf(setOf<String>()) }
    var avoids by remember { mutableStateOf(setOf<String>()) }
    var otherAllergens by remember { mutableStateOf(listOf<String>()) }
    var otherAvoids by remember { mutableStateOf(listOf<String>()) }
    var time by remember { mutableStateOf("any") }
    var who by remember { mutableStateOf(setOf<String>()) }
    var cuisines by remember { mutableStateOf(setOf<String>()) }
    var proteinMore by remember { mutableStateOf(setOf<String>()) }
    var proteinLess by remember { mutableStateOf(setOf<String>()) }
    var loaded by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var otherAllergenOpen by remember { mutableStateOf(false) }
    var saveCount by remember { mutableIntStateOf(0) }
    var saveJob by remember { mutableStateOf<Job?>(null) }
    val o = FilterOptions

    val filterCount = (if (diets == setOf("omnivore")) 0 else 1) + allergens.size + otherAllergens.size + avoids.size + otherAvoids.size +
        who.size + cuisines.size + proteinMore.size + proteinLess.size + (if (time != "any") 1 else 0)

    LaunchedEffect(Unit) {
        try {
            val filters = KitchenApi.prefs().obj("filters")
            if (filters != null) {
                filters.strings("diets")?.takeIf { it.isNotEmpty() }?.let { diets = o.cleaned(it) }
                filters.strings("allergens")?.let { a ->
                    val known = o.allergens.map { it.first }
                    allergens = a.filter { it in known }.toSet()
                    otherAllergens = a.filter { it !in known }
                }
                filters.strings("avoids")?.let { a ->
                    avoids = a.filter { it in o.avoids }.toSet()
                    otherAvoids = a.filter { it !in o.avoids }
                }
                filters.string("time")?.let { time = it }
                filters.strings("who")?.let { who = it.toSet() }
                filters.strings("cuisines")?.let { cuisines = it.toSet() }
                filters.strings("protein_more")?.let { proteinMore = it.toSet() }
                filters.strings("protein_less")?.let { proteinLess = it.toSet() }
            }
            loaded = true
            error = null
        } catch (e: Throwable) {
            if (!Api.isCancellation(e)) error = Api.message(e)
        }
    }

    fun save() {
        if (!loaded) return
        val body = mapOf(
            "diets" to o.diets.filter { it in diets },
            "allergens" to o.allergens.map { it.first }.filter { it in allergens } + otherAllergens,
            "avoids" to o.avoids.filter { it in avoids } + otherAvoids,
            "time" to time,
            "who" to o.who.map { it.first }.filter { it in who },
            "cuisines" to o.cuisines.map { it.first }.filter { it in cuisines },
            "protein_more" to o.proteins.map { it.first }.filter { it in proteinMore },
            "protein_less" to o.proteins.map { it.first }.filter { it in proteinLess },
        )
        saveCount += 1
        val mine = saveCount
        val previous = saveJob
        saveJob = scope.launch {
            previous?.join()
            if (mine != saveCount) return@launch
            try {
                KitchenApi.savePrefs(mapOf("filters" to body))
                error = null
                // Recipes follow the filters, so refresh the list behind this screen.
                store.searchRecipes("")
            } catch (e: Throwable) {
                error = Api.message(e)
            }
        }
    }

    fun reset() {
        diets = setOf("omnivore"); allergens = emptySet(); otherAllergens = emptyList(); avoids = emptySet(); otherAvoids = emptyList()
        who = emptySet(); cuisines = emptySet(); proteinMore = emptySet(); proteinLess = emptySet(); time = "any"; otherAllergenOpen = false
        save()
    }

    Column(Modifier.fillMaxSize().background(Theme.bg)) {
        NavBar("Filters", actions = { LinkButton("Reset") { reset() } })
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(horizontal = 20.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(28.dp)) {
            error?.let { ErrorBanner(it) }
            // Hides meals
            Column(
                Modifier.fillMaxWidth().clip(RoundedCornerShape(20.dp)).background(Theme.surface).border(1.dp, Theme.line, RoundedCornerShape(20.dp)).padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(22.dp),
            ) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("Hides meals", style = Theme.chipLabel, color = Theme.coralInk, modifier = Modifier.background(Theme.coralTint, CircleShape).padding(horizontal = 10.dp, vertical = 3.dp))
                    Text("Strict — never shown", style = Theme.subtitle, color = Theme.muted)
                }
                ChipSection("Diet") {
                    for (item in o.diets) ChoiceChip(o.dietLabels[item] ?: item, item in diets) { diets = o.toggled(diets, item); save() }
                }
                ChipSection("Allergies") {
                    for ((id, label) in o.allergens) ChoiceChip(label, id in allergens) { allergens = if (id in allergens) allergens - id else allergens + id; save() }
                    for (name in otherAllergens) ChoiceChip("$name ✕", true) { otherAllergens = otherAllergens - name; save() }
                    ChoiceChip("Other", otherAllergenOpen) { otherAllergenOpen = !otherAllergenOpen }
                }
                if (otherAllergenOpen) {
                    OtherField("Other allergies", selected = otherAllergens, onSelected = { otherAllergens = it }) {
                        val known = o.allergens.map { it.first }
                        allergens = allergens + otherAllergens.filter { it in known }
                        otherAllergens = otherAllergens.filter { it !in known }
                        save()
                    }
                }
                ChipSection("I avoid") {
                    for (name in avoids.sorted() + otherAvoids) ChoiceChip("$name ✕", true) { avoids = avoids - name; otherAvoids = otherAvoids - name; save() }
                }
                OtherField("Foods to avoid", "Add an ingredient…", dashed = true, presets = o.avoids, taken = avoids, selected = otherAvoids, onSelected = { otherAvoids = it }) {
                    avoids = avoids + otherAvoids.filter { it in o.avoids }
                    otherAvoids = otherAvoids.filter { it !in o.avoids }
                    save()
                }
            }
            // Shapes suggestions
            Column(verticalArrangement = Arrangement.spacedBy(22.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("Shapes suggestions", style = Theme.chipLabel, color = Theme.ink, modifier = Modifier.background(Theme.aubergineTint, CircleShape).padding(horizontal = 10.dp, vertical = 3.dp))
                    Text("Show me more of these", style = Theme.subtitle, color = Theme.muted)
                }
                ChipSection("Who it's for") {
                    for ((id, label) in o.who) ChoiceChip(label, id in who) { who = if (id in who) who - id else who + id; save() }
                }
                if ("omnivore" in diets || "pescatarian" in diets) {
                    val choices = o.proteins.filter { "omnivore" in diets || it.first == "seafood" }
                    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Text("Proteins", style = Theme.body, color = Theme.ink)
                        for (row in choices.chunked(2)) {
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                for ((id, name) in row) Box(Modifier.weight(1f)) {
                                    ProteinTile(name, id in proteinMore, id in proteinLess) {
                                        when (id) {
                                            in proteinMore -> { proteinMore = proteinMore - id; proteinLess = proteinLess + id }
                                            in proteinLess -> proteinLess = proteinLess - id
                                            else -> proteinMore = proteinMore + id
                                        }
                                        save()
                                    }
                                }
                                if (row.size == 1) Spacer(Modifier.weight(1f))
                            }
                        }
                    }
                }
                ChipSection("Cuisines") {
                    for ((id, label) in o.cuisines) ChoiceChip(label, id in cuisines) { cuisines = if (id in cuisines) cuisines - id else cuisines + id; save() }
                }
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("Cook time", style = Theme.body, color = Theme.ink)
                    Row(Modifier.fillMaxWidth().background(Theme.aubergineTint, RoundedCornerShape(16.dp)).padding(4.dp), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                        for ((id, _) in o.times) {
                            val on = time == id
                            Box(
                                Modifier.weight(1f).heightIn(min = 44.dp)
                                    .then(if (on) Modifier.shadow(2.dp, RoundedCornerShape(12.dp), spotColor = Theme.ink.copy(alpha = 0.15f)).background(Theme.surface, RoundedCornerShape(12.dp)) else Modifier)
                                    .clip(RoundedCornerShape(12.dp)).clickable { time = id; save() },
                                contentAlignment = Alignment.Center,
                            ) { Text(if (id == "any") "Any" else "$id min", style = Theme.chipLabel, color = if (on) Theme.ink else Theme.muted) }
                        }
                    }
                }
            }
        }
        Column(Modifier.fillMaxWidth().background(Theme.surface)) {
            Hairline()
            Row(Modifier.padding(horizontal = 20.dp).padding(top = 14.dp, bottom = 12.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                LinkButton("Clear all") { reset() }
                Row(
                    Modifier.weight(1f).heightIn(min = 52.dp).clip(CircleShape).background(Theme.ink).clickable { selectTab(AppTab.Recipes) },
                    horizontalArrangement = Arrangement.spacedBy(10.dp, Alignment.CenterHorizontally), verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text("Show meals", style = Theme.action, color = Theme.surface)
                    Text(
                        if (filterCount == 0) "All" else if (filterCount == 1) "1 filter" else "$filterCount filters",
                        style = Theme.count, color = Theme.ink, modifier = Modifier.background(Theme.coral, CircleShape).padding(horizontal = 10.dp, vertical = 3.dp),
                    )
                }
            }
        }
    }
}

@Composable
private fun ChipSection(title: String, chips: @Composable () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text(title, style = Theme.body, color = Theme.ink)
        Flow(8.dp) { chips() }
    }
}

@Composable
private fun ChoiceChip(label: String, on: Boolean, onClick: () -> Unit) {
    Box(
        Modifier.heightIn(min = 44.dp).clip(CircleShape).background(if (on) Theme.ink else Theme.surface)
            .border(1.dp, if (on) Theme.ink else Theme.line, CircleShape).clickable(onClick = onClick).padding(horizontal = 16.dp),
        contentAlignment = Alignment.Center,
    ) { Text(label, style = Theme.chipLabel, color = if (on) Theme.surface else Theme.bodyInk) }
}

@Composable
private fun ProteinTile(name: String, more: Boolean, less: Boolean, onClick: () -> Unit) {
    val on = more || less
    Row(
        Modifier.fillMaxWidth().heightIn(min = 56.dp).clip(RoundedCornerShape(14.dp)).background(if (on) Theme.coralTint else Theme.surface)
            .border(if (on) 1.5.dp else 1.dp, if (on) Theme.accent else Theme.line, RoundedCornerShape(14.dp)).clickable(onClick = onClick).padding(horizontal = 14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(if (more) "More ${name.lowercase()}" else if (less) "Less ${name.lowercase()}" else name, style = Theme.chipLabel, color = Theme.bodyInk, modifier = Modifier.weight(1f))
        if (on) Box(Modifier.size(22.dp).background(Theme.coral, CircleShape), contentAlignment = Alignment.Center) {
            Icon(Icons.Filled.Check, null, tint = Theme.ink, modifier = Modifier.size(14.dp))
        }
    }
}

/** Words that aren't in the list: search foods, tap a match to add it. */
@Composable
private fun OtherField(
    label: String, placeholder: String = "Search foods, e.g. bell peppers or ground", dashed: Boolean = false,
    presets: List<String> = emptyList(), taken: Set<String> = emptySet(), selected: List<String>, onSelected: (List<String>) -> Unit,
    onCommit: () -> Unit,
) {
    var query by remember { mutableStateOf("") }
    var matches by remember { mutableStateOf<List<String>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(query) {
        matches = emptyList()
        error = null
        if (query.isBlank()) { loading = false; return@LaunchedEffect }
        loading = true
        try {
            delay(250)
            matches = Api.get<KitchenItemSearch>("filter-items", mapOf("q" to query), reportErrors = false).items.map { it.name }
            loading = false
        } catch (e: Throwable) {
            if (!Api.isCancellation(e)) { error = "Couldn't search foods. Please try again."; loading = false }
        }
    }

    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        TextBox(
            query, { query = it }, placeholder, corner = if (dashed) 23.dp else 12.dp,
            background = if (dashed) Color(0xFFFBF6EE) else Theme.surface, border = if (dashed) Color(0xFFD9C9D3) else Theme.line,
            keyboard = KeyboardOptions(capitalization = KeyboardCapitalization.None, autoCorrectEnabled = false),
            contentDescription = "Search ${label.lowercase()}",
        )
        if (loading) Spinner()
        error?.let { Text(it, style = Theme.subtitle, color = Theme.ink) }
        // Matches as chips (#85): tap one to add it; it moves up with the other picked chips.
        Flow(6.dp) {
            val q = query.trim()
            if (q.isNotEmpty()) {
                for (name in presets.filter { it.contains(q, ignoreCase = true) && it !in selected && it !in taken }) {
                    FilterChip("+ $name", false) { onSelected(selected + name); query = ""; onCommit() }
                }
            }
            for (name in matches.filter { it !in selected }) FilterChip("+ $name", false) { onSelected(selected + name); onCommit() }
        }
        if (!loading && error == null && query.isNotEmpty() && matches.isEmpty()) Text("No matching foods. Try another name.", style = Theme.subtitle, color = Theme.ink)
    }
}

/** Sign in/out, password, household invites and members. */
@Composable
fun AccountView() {
    val store = LocalStore.current
    val session = LocalSession.current
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var members by remember { mutableStateOf<List<HouseholdMember>>(emptyList()) }
    var householdName by remember { mutableStateOf("") }
    var inviteUrl by remember { mutableStateOf<String?>(null) }
    var signingIn by remember { mutableStateOf(false) }
    var confirmEverywhere by remember { mutableStateOf(false) }
    var deletingAccount by remember { mutableStateOf(false) }
    var joinToken by remember { mutableStateOf("") }
    var homePassword by remember { mutableStateOf("") }
    var confirmLeave by remember { mutableStateOf(false) }
    var confirmJoin by remember { mutableStateOf(false) }
    var deletingHome by remember { mutableStateOf(false) }
    var successor by remember { mutableStateOf<HouseholdMember?>(null) }
    var busy by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<String?>(null) }

    val email = session.status?.email
    val otherMembers = members.filter { it.email != email }
    val myRole = members.firstOrNull { it.email == email }?.householdRole
    val canManage = myRole == "owner" || myRole == "admin"
    val signedIn = session.status?.authenticated == true

    suspend fun loadMembers() {
        if (session.status?.authenticated != true) return
        try {
            householdName = Api.jsonObject("household").string("name") ?: ""
            members = KitchenApi.members()
        } catch (e: Throwable) {
            if (!Api.isCancellation(e)) error = Api.message(e)
        }
    }
    LaunchedEffect(Unit) { loadMembers() }

    fun action(work: suspend () -> Unit) {
        busy = true
        scope.launch {
            try { work() } catch (e: Throwable) { error = Api.message(e) } finally { busy = false }
        }
    }

    fun saveHouseholdName() {
        val name = householdName.trim()
        if (name.isEmpty()) return
        action {
            Api.jsonObject("household", "PUT", mapOf("name" to name))
            householdName = name
            message = "Household name saved."
            error = null
        }
    }

    fun householdAction(work: suspend () -> Unit) = action {
        work()
        joinToken = ""
        homePassword = ""
        deletingHome = false
        ResponseCache.clear()
        session.refresh()
        loadMembers()
        store.switchAccount()
        error = null
        message = "Household updated."
    }

    Column(Modifier.fillMaxSize().background(Theme.bg)) {
        NavBar("Account & security")
        ThemeList {
            message?.let { Text(it, style = Theme.body, color = Theme.ok, modifier = Modifier.padding(horizontal = 20.dp, vertical = 10.dp)) }
            error?.let { Box(Modifier.padding(16.dp)) { ErrorBanner(it) } }
            if (signedIn) {
                ListHeader("Signed in")
                ListRow {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        Icon(Icons.Outlined.AccountCircle, null, tint = Theme.accent)
                        Text(email ?: "", style = Theme.body, color = Theme.ink)
                    }
                }
                ListHeader("Password")
                if (session.status?.hasEmail == false) {
                    ListRow {
                        Text("This account has a username instead of an email, so there's no reset link. If you forget your password, the account can't be recovered.", style = Theme.subtitle, color = Theme.muted)
                    }
                } else {
                    ListRow(onClick = if (busy) null else ({
                        action {
                            AuthApi.forgotPassword(email ?: return@action)
                            message = "Check your email for a password reset link."
                            error = null
                        }
                    }), chevron = false) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                            Icon(Icons.Outlined.Key, null, tint = Theme.accent)
                            Text("Reset password", style = Theme.body, color = Theme.accent)
                        }
                    }
                    ListRow { Text("Email a reset link to your signed-in address.", style = Theme.subtitle, color = Theme.muted) }
                }
                ListHeader("Household")
                ListRow {
                    FormField(householdName, { householdName = it.take(80) }, "Household name",
                        actions = KeyboardActions(onDone = { saveHouseholdName() }),
                        keyboard = KeyboardOptions(imeAction = ImeAction.Done))
                }
                ActionRow("Save household name", enabled = !busy && householdName.isNotBlank()) { saveHouseholdName() }
                val invite = inviteUrl
                if (invite != null) {
                    ListRow({ shareText(context, invite) }, chevron = false) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                            Icon(Icons.Outlined.IosShare, null, tint = Theme.accent)
                            Text("Share invite link", style = Theme.body, color = Theme.accent)
                        }
                    }
                    Box(Modifier.padding(horizontal = 20.dp, vertical = 6.dp)) { StarTip("settings.invite-link") }
                } else {
                    ActionRow("Invite someone to this household", enabled = !busy) { action { inviteUrl = KitchenApi.createInvite(); error = null } }
                }
                for (member in otherMembers) {
                    androidx.compose.runtime.key(member.id) {
                        SwipeToDelete(member.id, enabled = canManage && member.householdRole != "owner", onDelete = {
                            members = members.filter { it.id != member.id }
                            scope.launch { try { KitchenApi.removeMember(member.id) } catch (e: Throwable) { error = Api.message(e); loadMembers() } }
                        }) {
                            ListRow {
                                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                    Text(member.email, style = Theme.body, color = Theme.ink)
                                    Text(member.householdRole ?: "member", style = Theme.subtitle, color = Theme.muted)
                                    if (myRole == "owner") {
                                        Text("Transfer ownership", style = Theme.body, color = Theme.accent, modifier = Modifier.clickable { successor = member }.padding(vertical = 4.dp))
                                        Text(
                                            if (member.householdRole == "admin") "Remove admin role" else "Make admin", style = Theme.body, color = Theme.accent,
                                            modifier = Modifier.clickable {
                                                householdAction { KitchenApi.setRole(member.id, if (member.householdRole == "admin") "member" else "admin") }
                                            }.padding(vertical = 4.dp),
                                        )
                                    }
                                }
                            }
                        }
                    }
                }
                Spacer(Modifier.height(16.dp))
                ActionRow("Sign out") { scope.launch { session.signOut() } }
                ActionRow("Sign out everywhere", destructive = true) { confirmEverywhere = true }
                Box(Modifier.padding(horizontal = 20.dp, vertical = 6.dp)) { StarTip("settings.sign-out-everywhere") }
                ListHeader("Household membership")
                ListRow {
                    Text("Leaving creates an empty solo household. Your account stays active. Shared plans and kitchen data stay with the household.", style = Theme.subtitle, color = Theme.ink)
                }
                ActionRow("Leave household", enabled = !busy) { confirmLeave = true }
                ListRow { FormField(joinToken, { joinToken = it }, "Invite link or token", KeyboardOptions(capitalization = KeyboardCapitalization.None, autoCorrectEnabled = false)) }
                ActionRow("Join household", enabled = !busy && joinToken.isNotBlank()) { confirmJoin = true }
                if (canManage) {
                    ActionRow("Delete household", destructive = true) { deletingHome = !deletingHome }
                    if (deletingHome) {
                        ListRow {
                            Text("Permanently removes this kitchen and its plans. Everyone keeps their account and receives an empty solo household. Anonymous meal votes are retained.", style = Theme.subtitle, color = Theme.ink)
                        }
                        ListRow { FormField(homePassword, { homePassword = it }, "Your password", password = true) }
                        ActionRow("Confirm household deletion", destructive = true, enabled = !busy && homePassword.isNotEmpty()) {
                            val password = homePassword
                            householdAction { KitchenApi.deleteHousehold(password) }
                        }
                    }
                }
                Spacer(Modifier.height(16.dp))
                ActionRow("Delete account", destructive = true) { deletingAccount = true }
                Text(
                    if (otherMembers.isEmpty()) "Deletes your account and this household’s plans, pantry, grocery list and your own recipes. This can’t be undone."
                    else "Deletes your account. The household stays for the other members.",
                    style = Theme.subtitle, color = Theme.muted, modifier = Modifier.padding(horizontal = 20.dp, vertical = 6.dp),
                )
            } else {
                Text(
                    "You're using ${Copy.appName} as a guest. Create an account to keep your plan and share it with your household.",
                    style = Theme.subtitle, color = Theme.muted, modifier = Modifier.padding(horizontal = 20.dp, vertical = 12.dp),
                )
                ListRow({ signingIn = true }, chevron = false) { Text("Sign in or create account", style = Theme.mealName, color = Theme.accent) }
            }
        }
    }

    if (signingIn) Sheet(onDismiss = { signingIn = false; scope.launch { loadMembers() } }) { AuthView(isSheet = true) }
    if (confirmLeave) ConfirmDialog("Leave this household and start an empty solo household?", "Leave household", onConfirm = {
        householdAction { KitchenApi.leaveHousehold() }
    }, onDismiss = { confirmLeave = false })
    if (confirmJoin) ConfirmDialog("Join this household? Your current solo kitchen will be removed; shared kitchens stay with their members.", "Join household", destructive = false, onConfirm = {
        val token = joinToken.trim().split("/").lastOrNull() ?: ""
        householdAction { KitchenApi.joinHousehold(token) }
    }, onDismiss = { confirmJoin = false })
    successor?.let { member ->
        ConfirmDialog("Transfer household ownership?", "Transfer", message = "The selected member becomes the creator. You become an admin.", destructive = false, onConfirm = {
            householdAction { KitchenApi.setRole(member.id, "owner") }
        }, onDismiss = { successor = null })
    }
    if (deletingAccount) {
        Sheet(onDismiss = { deletingAccount = false }) {
            DeleteAccountSheet(alone = otherMembers.isEmpty()) {
                deletingAccount = false
                scope.launch { session.accountDeleted() }
            }
        }
    }
    if (confirmEverywhere) ConfirmDialog("Sign out on every device?", "Sign out everywhere", onConfirm = {
        scope.launch {
            try { AuthApi.logoutEverywhere() } catch (e: Throwable) { error = Api.message(e) }
            session.signOut()
        }
    }, onDismiss = { confirmEverywhere = false })
}

@Composable
private fun ActionRow(title: String, enabled: Boolean = true, destructive: Boolean = false, onClick: () -> Unit) {
    ListRow(onClick = if (enabled) onClick else null, chevron = false) {
        Text(title, style = Theme.body, color = (if (destructive) Theme.destructive else Theme.accent).copy(alpha = if (enabled) 1f else 0.4f))
    }
}

/** Password check before deleting the account (#65). */
@Composable
private fun DeleteAccountSheet(alone: Boolean, onDeleted: () -> Unit) {
    val scope = rememberCoroutineScope()
    var password by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    fun delete() {
        if (password.isEmpty() || busy) return
        busy = true
        scope.launch {
            try { AuthApi.deleteAccount(password); onDeleted() } catch (e: Throwable) { error = Api.message(e) } finally { busy = false }
        }
    }
    Column(Modifier.fillMaxSize().background(Theme.bg)) {
        SheetBar("Delete account")
        ThemeList {
            error?.let { Box(Modifier.padding(16.dp)) { ErrorBanner(it) } }
            ListRow {
                Text(
                    if (alone) "This deletes your account and everything in this household: plans, pantry, grocery list, ratings and recipes you added. It can’t be undone."
                    else "This deletes your account and your sign-ins. The household and its plans stay for the other members.",
                    style = Theme.body, color = Theme.ink,
                )
            }
            ListRow { Text("Anonymous meal votes are retained without account identifiers.", style = Theme.subtitle, color = Theme.ink) }
            ListRow { FormField(password, { password = it }, "Your password", password = true, actions = KeyboardActions(onDone = { delete() })) }
            Spacer(Modifier.height(16.dp))
            ActionRow("Delete account", destructive = true, enabled = !busy && password.isNotEmpty()) { delete() }
        }
    }
}

/** Taste Lab stays a web page (the swipe engine lives on the server); shown in a web view. */
@SuppressLint("SetJavaScriptEnabled")
@Composable
fun TasteLabView(swipe: Boolean = false) {
    val openUrl = rememberOpenUrl()
    var loading by remember { mutableStateOf(true) }
    var failed by remember { mutableStateOf<String?>(null) }
    var attempt by remember { mutableIntStateOf(0) }
    val url = Api.origin.newBuilder().addPathSegments("tastelab/").addQueryParameter("chrome", "app")
        .apply { if (swipe) addQueryParameter("swipe", "1") }.build()

    Column(Modifier.fillMaxSize().background(Theme.bg)) {
        NavBar("Taste Lab")
        Box(Modifier.weight(1f).fillMaxWidth()) {
            androidx.compose.runtime.key(attempt) {
                AndroidView(
                    factory = { ctx ->
                        WebView(ctx).apply {
                            layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
                            setBackgroundColor(android.graphics.Color.rgb(255, 251, 246))
                            settings.javaScriptEnabled = true
                            settings.domStorageEnabled = true
                            settings.allowFileAccess = false
                            settings.allowContentAccess = false
                            webViewClient = object : WebViewClient() {
                                override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                                    val target = request.url.toString()
                                    if (AppUrls.isInternal(target)) return false
                                    openUrl(target)
                                    return true
                                }

                                override fun onPageFinished(view: WebView, url: String?) { loading = false }

                                override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                                    if (request.isForMainFrame) {
                                        loading = false
                                        failed = error.description?.toString() ?: "Couldn’t connect to the server."
                                    }
                                }
                            }
                            // The app's HTTP client holds the sign-in cookie. The web view needs it too.
                            Api.cookies.syncToWebView(url)
                            loadUrl(url.toString())
                        }
                    },
                    modifier = Modifier.fillMaxSize(),
                )
            }
            if (loading && failed == null) Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator(color = Theme.muted, strokeWidth = 2.dp) }
            failed?.let { message ->
                Column(Modifier.fillMaxSize().background(Theme.bg), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(12.dp, Alignment.CenterVertically)) {
                    EmptyState("Taste Lab didn't load", message, Icons.Outlined.WifiOff)
                    Text(
                        "Try again", style = Theme.action, color = Theme.bg,
                        modifier = Modifier.clip(RoundedCornerShape(12.dp)).background(Theme.ink).clickable { failed = null; loading = true; attempt++ }
                            .padding(horizontal = 22.dp, vertical = 12.dp),
                    )
                }
            }
        }
    }
}

/** Bug reports and feature requests (#145). Ids match app/models.py FEEDBACK_KINDS. */
private enum class FeedbackKind(val id: String, val label: String, val prompt: String) {
    Bug("bug", "Report a bug", "What went wrong?"),
    Feature("feature", "Suggest a feature", "What would you like?");

    val help: String get() = if (this == Bug) "Something broke or didn't work the way it should." else "Something you wish ${Copy.appName} did."
    val placeholder: String
        get() = if (this == Bug) "What happened, and what did you expect? e.g. I checked off milk and it came back after a refresh."
        else "e.g. Let me plan lunches too, not just dinners."
}

private const val MAX_SHOTS = 3

/** "Report a bug or suggest a feature". The server keeps it with the app build that sent it. */
@Composable
fun FeedbackView() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var kind by remember { mutableStateOf(FeedbackKind.Bug) }
    var note by remember { mutableStateOf("") }
    var sending by remember { mutableStateOf(false) }
    var sent by remember { mutableStateOf<FeedbackKind?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var shots by remember { mutableStateOf<List<Bitmap>>(emptyList()) }
    val trimmed = note.trim()

    val picker = rememberLauncherForActivityResult(ActivityResultContracts.PickMultipleVisualMedia(MAX_SHOTS)) { uris ->
        scope.launch {
            val loaded = withContext(Dispatchers.IO) { uris.mapNotNull { loadBitmap(context, it) } }
            shots = (shots + loaded).take(MAX_SHOTS)
        }
    }

    Column(Modifier.fillMaxSize().background(Theme.bg)) {
        NavBar("Bugs & ideas")
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            error?.let { ErrorBanner(it) }
            val done = sent
            if (done != null) {
                Text(if (done == FeedbackKind.Bug) "Thanks. We'll look into it." else "Thanks for the idea. We read every one.", style = Theme.body, color = Theme.ink)
                LinkButton("Send another") { sent = null }
            } else {
                Text("What's this about?", style = Theme.action, color = Theme.ink)
                for (option in FeedbackKind.entries) {
                    RadioRow(kind == option, { kind = option }) {
                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Text(option.label, style = Theme.body, color = Theme.ink)
                            Text(option.help, style = Theme.subtitle, color = Theme.muted)
                        }
                    }
                }
                Text(kind.prompt, style = Theme.action, color = Theme.ink)
                TextBox(note, { note = it.take(2000) }, kind.placeholder, style = Theme.subtitle, minLines = 4, maxLines = 10)
                if (shots.isNotEmpty()) {
                    Row(Modifier.horizontalScroll(rememberScrollState()).padding(top = 14.dp, end = 14.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        shots.forEachIndexed { index, image ->
                            Box {
                                Image(
                                    image.asImageBitmap(), "Screenshot ${index + 1}", contentScale = ContentScale.Crop,
                                    modifier = Modifier.size(width = 80.dp, height = 110.dp).clip(RoundedCornerShape(8.dp)).border(1.dp, Theme.line, RoundedCornerShape(8.dp)),
                                )
                                Box(
                                    Modifier.align(Alignment.TopEnd).offset(x = 14.dp, y = (-14).dp).size(44.dp)
                                        .clickable { shots = shots.filterIndexed { i, _ -> i != index } }.semantics { contentDescription = "Remove screenshot ${index + 1}" },
                                    contentAlignment = Alignment.Center,
                                ) {
                                    Box(Modifier.size(20.dp).background(Theme.surface, CircleShape))
                                    Icon(Icons.Filled.Cancel, null, tint = Theme.ink, modifier = Modifier.size(24.dp))
                                }
                            }
                        }
                    }
                }
                if (shots.size < MAX_SHOTS) {
                    Row(
                        Modifier.heightIn(min = 44.dp).clickable {
                            try { picker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) }
                            catch (_: Exception) { Toast.makeText(context, "A photo picker isn’t available on this device.", Toast.LENGTH_LONG).show() }
                        },
                        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Icon(Icons.Outlined.AddPhotoAlternate, null, tint = Theme.accent)
                        Text(if (shots.isEmpty()) "Add a screenshot (optional)" else "Add another screenshot", style = Theme.action, color = Theme.accent)
                    }
                }
                FilledButton(if (sending) "Sending…" else "Send", enabled = trimmed.isNotEmpty() && !sending) {
                    sending = true
                    scope.launch {
                        try {
                            val images = withContext(Dispatchers.Default) { shots.mapNotNull { jpegDataUrl(it, 2000, listOf(85)) } }
                            Api.send<Ok>("feedback", "POST", mapOf("kind" to kind.id, "note" to trimmed, "screen" to "settings", "screenshots" to images))
                            error = null
                            note = ""
                            shots = emptyList()
                            sent = kind
                        } catch (e: Throwable) {
                            error = Api.message(e)
                        } finally {
                            sending = false
                        }
                    }
                }
            }
        }
    }
}

/** Reads a picked photo, scaled down so even large camera files fit in memory. */
fun loadBitmap(context: android.content.Context, uri: Uri): Bitmap? = try {
    val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
    context.contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, bounds) }
    var sample = 1
    while (max(bounds.outWidth, bounds.outHeight) / (sample * 2) >= 2000) sample *= 2
    context.contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, BitmapFactory.Options().apply { inSampleSize = sample }) }
} catch (_: Exception) {
    null
}

/** A JPEG data URL at most `longest` px on its long side, under the server's 5 MB photo limit. */
fun jpegDataUrl(image: Bitmap, longest: Int, qualities: List<Int>): String? {
    val scale = min(1f, longest.toFloat() / max(1, max(image.width, image.height)))
    val resized = if (scale < 1f) Bitmap.createScaledBitmap(image, (image.width * scale).toInt(), (image.height * scale).toInt(), true) else image
    for (quality in qualities) {
        val out = ByteArrayOutputStream()
        resized.compress(Bitmap.CompressFormat.JPEG, quality, out)
        if (out.size() < 4_800_000) return "data:image/jpeg;base64," + Base64.encodeToString(out.toByteArray(), Base64.NO_WRAP)
    }
    return null
}

@Composable
fun PrivacyView() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var exportData by remember { mutableStateOf<ByteArray?>(null) }
    var exporting by remember { mutableStateOf(false) }
    var exportError by remember { mutableStateOf<String?>(null) }
    val saver = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/json")) { uri ->
        val bytes = exportData ?: return@rememberLauncherForActivityResult
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            val ok = withContext(Dispatchers.IO) {
                try { context.contentResolver.openOutputStream(uri, "w")?.use { it.write(bytes) } != null } catch (_: Exception) { false }
            }
            Toast.makeText(context, if (ok) "File saved" else "Couldn’t save this file. Please try again.", Toast.LENGTH_LONG).show()
        }
    }

    Column(Modifier.fillMaxSize().background(Theme.bg)) {
        NavBar("Privacy")
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp).navigationBarsPadding(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            // "Download my data" (#64): everything stored for this household as one JSON file.
            Column(Modifier.padding(bottom = 8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Your data", style = Theme.title, color = Theme.ink)
                Text(
                    "Get a copy of everything we store for your household: plans, grocery lists, pantry, filters, ratings, prep votes, Taste Lab answers and the recipes you added. Passwords and sign-in tokens are never included.",
                    style = Theme.body, color = Theme.muted,
                )
                if (exportData != null) {
                    Row(
                        Modifier.heightIn(min = 44.dp).clickable { saver.launch("dinnerdesk-data-${LocalDate.now()}.json") },
                        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Icon(Icons.Outlined.IosShare, null, tint = Theme.accent)
                        Text("Save your data", style = Theme.action, color = Theme.accent)
                    }
                } else {
                    Row(
                        Modifier.heightIn(min = 44.dp).clickable(enabled = !exporting) {
                            exporting = true
                            exportError = null
                            scope.launch {
                                try {
                                    exportData = Api.getData("household/export")
                                } catch (e: Throwable) {
                                    exportError = when {
                                        e is ApiError && e.code == 401 -> "Please sign in again to continue."
                                        e is ApiError && e.code == 404 -> "Data export needs the updated Dinnerdesk server. Please try again after the server update."
                                        else -> "Couldn’t prepare your data. Please try again."
                                    }
                                } finally {
                                    exporting = false
                                }
                            }
                        },
                        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        if (exporting) CircularProgressIndicator(color = Theme.accent, strokeWidth = 2.dp, modifier = Modifier.size(16.dp))
                        Text(if (exporting) "Preparing…" else "Download my data", style = Theme.action, color = Theme.accent)
                    }
                }
                exportError?.let { Text(it, style = Theme.subtitle, color = Theme.accent) }
            }
            Text("Dinnerdesk is a meal planner for a household. This is what we store, and what we do with it.", style = Theme.body, color = Theme.ink)
            for ((title, body) in privacySections) {
                Column(Modifier.padding(top = 8.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(title, style = Theme.title, color = Theme.ink)
                    Text(body, style = Theme.body, color = Theme.muted)
                }
            }
        }
    }
}

private val privacySections = listOf(
    "Account" to """
        If you create an account we store your email (or the username you chose instead), a hash of your password (not the password), and your household name. A sign-in session lasts 30 days. You can sign out of this device, or every device, from Account & security.

        Forgot-password emails are sent by Resend. We store a hash of the reset link, not the link. The link works once, for one hour. We answer the same way whether or not that email has an account.

        If you subscribe to the email newsletter, we store that choice with your household and may email you DinnerDesk Deals. Turn it off anytime from Settings.
    """.trimIndent(),
    "Your kitchen" to """
        Plans, grocery lists, pantry, recipe edits, favorites, hides, to-try marks, filters, and store or aisle choices are stored for your household. Taste Lab stores the meals you like or pass, plus diet, allergy, and dislike choices. When you are signed in, those answers are tied to your account and used to suggest meals. Thumbs up or down on a planned meal, and on a prep step, are stored for your household and used to choose future meal suggestions. Prep step votes are kept so we can improve prep suggestions.

        Someone you invite joins that same household and can see and change it. Invite links expire after 7 days. You can remove a member from Account & security. Removing them ends their access.
    """.trimIndent(),
    "Without an account" to """
        Guests use a private kitchen identified by a random device/browser cookie. All normal features work without an account. Reinstalling the app or clearing browser data can lose access to guest data. Create an account to protect it.
    """.trimIndent(),
    "What we don’t collect" to """
        We don’t sell your data. We don’t take payment, location, or health data. Nutrition-tracker sync is not built. We don’t run ads or analytics.

        Recipe photos in the app are ones we have marked as ours to use. We don’t collect photos, reviews, or comments from cooks yet.
    """.trimIndent(),
    "Deleting data" to """
        Download a copy of your data at the top of this page. Delete your account from Account & security after confirming your password. Your sign-ins and reset links are removed. If other members remain, a household creator must transfer ownership before deleting their account. The last member’s deletion also removes their solo kitchen. The household creator or a designated household admin can separately delete a household: its kitchen and plans are removed, but members keep their accounts and receive empty solo households. Leaving or being removed from a household also preserves your account. Meal votes may be retained without account, household, browser, or session identifiers, grouped as individual history or household history.
    """.trimIndent(),
)
