package build.computerscience.dinnerdesk.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.Assignment
import androidx.compose.material.icons.automirrored.outlined.MenuBook
import androidx.compose.material.icons.automirrored.outlined.OpenInNew
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.outlined.AutoAwesome
import androidx.compose.material.icons.outlined.Bolt
import androidx.compose.material.icons.outlined.CalendarToday
import androidx.compose.material.icons.outlined.Computer
import androidx.compose.material.icons.outlined.Copyright
import androidx.compose.material.icons.outlined.Gesture
import androidx.compose.material.icons.outlined.Image
import androidx.compose.material.icons.outlined.Inventory2
import androidx.compose.material.icons.outlined.MoveToInbox
import androidx.compose.material.icons.outlined.PhotoCamera
import androidx.compose.material.icons.outlined.RadioButtonUnchecked
import androidx.compose.material.icons.outlined.Restaurant
import androidx.compose.material.icons.outlined.ShoppingCart
import androidx.compose.material.icons.outlined.Watch
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import build.computerscience.dinnerdesk.R
import build.computerscience.dinnerdesk.data.Api
import build.computerscience.dinnerdesk.data.Copy
import build.computerscience.dinnerdesk.data.KitchenApi
import build.computerscience.dinnerdesk.data.Tour
import build.computerscience.dinnerdesk.data.obj
import build.computerscience.dinnerdesk.data.string
import build.computerscience.dinnerdesk.data.strings
import kotlinx.coroutines.launch

private enum class TourStep { Welcome, Filters, Ai, How }

private class HowStep(val id: Int, val title: String, val icon: ImageVector, val text: String)

// Text lives in copy.json (tour.how.N.title / tour.how.N), shared with the website and iOS tours.
private val howIcons = listOf(
    Icons.AutoMirrored.Outlined.MenuBook, Icons.Outlined.CalendarToday, Icons.Outlined.MoveToInbox, Icons.Outlined.ShoppingCart,
    Icons.Outlined.Inventory2, Icons.AutoMirrored.Outlined.Assignment, Icons.Outlined.Restaurant, Icons.Outlined.AutoAwesome,
    Icons.Outlined.Watch, Icons.Outlined.Gesture,
)
private val aiIcons = listOf(Icons.Outlined.Image, Icons.Outlined.Copyright, Icons.Outlined.Computer, Icons.Outlined.PhotoCamera)

private fun steps(prefix: String, icons: List<ImageVector>) = icons.mapIndexedNotNull { i, icon ->
    val key = "$prefix.${i + 1}"
    if (Copy.has(key) && Copy.has("$key.title")) HowStep(i, Copy.text("$key.title"), icon, Copy.text(key)) else null
}

/** Real screenshots for how-to cards, by card index; drawn pictures for the next two. */
private val shots = mapOf(0 to R.drawable.tour_suggestions, 1 to R.drawable.tour_schedule, 2 to R.drawable.tour_draft, 3 to R.drawable.tour_stores)
private val drawings = mapOf(4 to 2, 5 to 3)
/** The tips card shows a real tip instead of a picture. */
private const val TIPS_CARD = 6

/**
 * First-run tour (mirrors web/src/Tour.jsx and TourView.swift). Welcome → Quick start (filters, how we
 * use AI, then how-to) or Taste Lab, or Skip. Full screen over the app.
 */
@Composable
fun TourView() {
    val session = LocalSession.current
    val scope = rememberCoroutineScope()
    val openUrl = rememberOpenUrl()
    val how = remember { steps("tour.how", howIcons) }
    val ai = remember { steps("tour.ai", aiIcons) }
    var step by remember { mutableStateOf(TourStep.Welcome) }
    var diets by remember { mutableStateOf(setOf("omnivore")) }
    var avoids by remember { mutableStateOf(setOf<String>()) }
    var time by remember { mutableStateOf("any") }
    var showTasteLab by remember { mutableStateOf(false) }
    var saving by remember { mutableStateOf(false) }
    var isUpdate by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val pager = rememberPagerState { how.size }
    val o = FilterOptions

    LaunchedEffect(Unit) {
        try {
            val prefs = KitchenApi.prefs()
            val seen = Tour.seen(prefs)
            isUpdate = (seen > 0 && seen < Tour.VERSION) || Tour.isNewBuild
            val saved = prefs.obj("filters") ?: return@LaunchedEffect
            saved.strings("diets")?.takeIf { it.isNotEmpty() }?.let { diets = o.cleaned(it) }
            saved.strings("avoids")?.let { avoids = it.toSet() }
            saved.string("time")?.let { time = it }
        } catch (e: Throwable) {
            if (!Api.isCancellation(e)) error = Api.message(e)
        }
    }

    suspend fun markDone(filters: Map<String, Any?>?): Boolean {
        Tour.noteBuild()
        val patch = mutableMapOf<String, Any?>("tour_done" to true, "tour_version" to Tour.VERSION)
        if (filters != null) patch["filters"] = filters
        return try {
            KitchenApi.savePrefs(patch)
            error = null
            true
        } catch (e: Throwable) {
            error = Api.message(e)
            false
        }
    }

    fun finish(saveFilters: Boolean) {
        saving = true
        scope.launch {
            val body = mapOf(
                "diets" to o.diets.filter { it in diets },
                // Keep Other words saved in Settings or Taste Lab; allergies aren't sent, so the server keeps them.
                "avoids" to o.avoids.filter { it in avoids } + avoids.filter { it !in o.avoids }.sorted(),
                "time" to time,
            )
            val ok = markDone(if (saveFilters) body else null)
            saving = false
            // Skip always closes; a failed save of chosen filters keeps the tour open so nothing is lost.
            if (ok || !saveFilters) session.showTour = false
        }
    }

    fun goBack() {
        when (step) {
            TourStep.Welcome -> Unit
            TourStep.Filters -> step = TourStep.Welcome
            TourStep.Ai -> step = TourStep.Filters
            TourStep.How -> if (pager.currentPage > 0) scope.launch { pager.animateScrollToPage(pager.currentPage - 1) } else step = TourStep.Ai
        }
    }

    BackHandler {
        if (showTasteLab) showTasteLab = false else goBack()
    }

    Box(Modifier.fillMaxSize().background(Theme.bg).navigationBarsPadding()) {
        if (showTasteLab) {
            val tasteNav = remember { Nav(Route.TasteLab()) }
            Column(Modifier.fillMaxSize()) {
                Box(Modifier.fillMaxWidth()) {
                    LinkButton("Done", Modifier.align(Alignment.CenterEnd)) { session.showTour = false }
                }
                NavStack(tasteNav, Modifier.weight(1f)) { RouteContent(it) }
            }
            return@Box
        }
        Column(Modifier.fillMaxSize()) {
            if (step != TourStep.Welcome) {
                Box(Modifier.fillMaxWidth().heightIn(min = 48.dp).padding(horizontal = 6.dp)) {
                    LinkButton("Back", Modifier.align(Alignment.CenterStart), style = Theme.body) { goBack() }
                    LinkButton("Skip", Modifier.align(Alignment.CenterEnd), color = Theme.muted, style = Theme.body) { finish(false) }
                }
            }
            error?.let { Box(Modifier.padding(horizontal = 16.dp)) { ErrorBanner(it) } }
            when (step) {
                TourStep.Welcome -> Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                    Column(Modifier.padding(bottom = 8.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text(if (isUpdate) Copy.text("tour.update.title") else "Welcome to ${Copy.appName}", style = Theme.bigTitle, color = Theme.ink)
                        Text(if (isUpdate) Copy.text("tour.update") else Copy.text("app.tagline"), style = Theme.body, color = Theme.muted)
                    }
                    ChoiceCard("Quick start", "Tell us what you eat, then a 1-minute how-to.", Icons.Outlined.Bolt) { step = TourStep.Filters }
                    ChoiceCard("Taste Lab", "Swipe through dishes so ${Copy.appName} learns what you like.", Icons.Outlined.Gesture) {
                        scope.launch { markDone(null); showTasteLab = true }
                    }
                    LinkButton("Skip for now", Modifier.fillMaxWidth().padding(top = 8.dp), color = Theme.muted, style = Theme.body) { finish(false) }
                }
                TourStep.Filters -> TourPage({ AccentButton("Next") { step = TourStep.Ai } }) {
                    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text("What do you eat?", style = Theme.tourTitle, color = Theme.ink)
                        Text("You can change this later in Settings › Filters.", style = Theme.subtitle, color = Theme.muted)
                    }
                    ChipGroup("Diet") {
                        for (item in o.diets) FilterChip(item.replaceFirstChar { it.uppercase() }, item in diets) { diets = o.toggled(diets, item) }
                    }
                    ChipGroup("Avoid") {
                        FilterChip("None", avoids.isEmpty()) { avoids = emptySet() }
                        for (item in o.avoids) FilterChip(item.split(" ").joinToString(" ") { w -> w.replaceFirstChar { it.uppercase() } }, item in avoids) {
                            avoids = if (item in avoids) avoids - item else avoids + item
                        }
                    }
                    ChipGroup("Cook time") {
                        for ((id, label) in o.times) FilterChip(label, time == id) { time = id }
                    }
                }
                TourStep.Ai -> TourPage({ AccentButton("Next") { step = TourStep.How } }) {
                    Text(Copy.text("tour.ai.title"), style = Theme.tourTitle, color = Theme.ink)
                    for (item in ai) {
                        Row(horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                            Icon(item.icon, null, tint = Theme.accent, modifier = Modifier.width(28.dp).size(24.dp))
                            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text(item.title, style = Theme.mealName, color = Theme.ink)
                                Text(item.text, style = Theme.body, color = Theme.ink)
                            }
                        }
                    }
                    // The full explanation lives on the website's Help & support page.
                    Row(
                        Modifier.heightIn(min = 44.dp).clickable { openUrl(Api.url("support") + "#ai") },
                        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Icon(Icons.AutoMirrored.Outlined.OpenInNew, null, tint = Theme.accent, modifier = Modifier.size(20.dp))
                        Text(Copy.text("tour.ai.more"), style = Theme.action, color = Theme.accent)
                    }
                }
                TourStep.How -> Column(Modifier.fillMaxSize()) {
                    HorizontalPager(pager, Modifier.weight(1f)) { page -> HowCard(how[page]) }
                    Row(Modifier.fillMaxWidth().padding(bottom = 4.dp), horizontalArrangement = Arrangement.spacedBy(6.dp, Alignment.CenterHorizontally)) {
                        for (i in how.indices) {
                            Box(Modifier.size(width = if (i == pager.currentPage) 18.dp else 6.dp, height = 6.dp).background(if (i == pager.currentPage) Theme.accent else Theme.line, CircleShape))
                        }
                    }
                    Box(Modifier.padding(horizontal = 20.dp, vertical = 12.dp)) {
                        if (pager.currentPage < how.size - 1) AccentButton("Next") { scope.launch { pager.animateScrollToPage(pager.currentPage + 1) } }
                        else AccentButton(if (saving) "Saving…" else "Start planning", enabled = !saving) { finish(true) }
                    }
                }
            }
        }
    }
}

@Composable
private fun TourPage(button: @Composable () -> Unit, content: @Composable ColumnScope.() -> Unit) {
    Column(Modifier.fillMaxSize()) {
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(20.dp), content = content)
        Box(Modifier.padding(horizontal = 20.dp, vertical = 12.dp)) { button() }
    }
}

@Composable
private fun ChipGroup(title: String, content: @Composable () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        ThemeHeader(title)
        Flow(8.dp) { content() }
    }
}

@Composable
private fun HowCard(item: HowStep) {
    val large = isAccessibilitySize
    Column(
        Modifier.fillMaxSize().padding(horizontal = 20.dp, vertical = 12.dp)
            .shadow(10.dp, RoundedCornerShape(18.dp), spotColor = Theme.ink.copy(alpha = 0.06f), ambientColor = Theme.ink.copy(alpha = 0.06f))
            .background(Theme.surface, RoundedCornerShape(18.dp)).padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Icon(item.icon, null, tint = Theme.accent, modifier = Modifier.size(26.dp))
            Text(item.title, style = Theme.tourTitle, color = Theme.ink)
        }
        // Smaller than body text so the picture of the screen gets the room.
        Text(item.text, style = Theme.body.copy(fontSize = 14.sp, lineHeight = 19.sp), color = Theme.ink)
        if (!large) {
            val shot = shots[item.id]
            val drawing = drawings[item.id]
            when {
                shot != null -> {
                    if (item.id == 0) NewPlanHint()
                    Image(
                        painterResource(shot), null, contentScale = ContentScale.Fit,
                        modifier = Modifier.fillMaxWidth().weight(1f).clip(RoundedCornerShape(14.dp)),
                    )
                }
                drawing != null -> Box(Modifier.fillMaxWidth().heightIn(min = 160.dp, max = 280.dp).padding(top = 4.dp)) { TourScreenPicture(drawing) }
                item.id == TIPS_CARD -> StarTip("recipes.ai-photo", Modifier.padding(top = 4.dp))
            }
        }
        Spacer(Modifier.weight(0.001f))
    }
}

/** Where suggestions come from: Plan's New meal plan button, drawn like the real one and ringed. */
@Composable
private fun NewPlanHint() {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("On Plan, tap", style = Theme.body.copy(fontSize = 14.sp), color = Theme.ink)
        Box(Modifier.border(3.dp, Theme.accent.copy(alpha = 0.45f), CircleShape).padding(4.dp)) {
            Row(
                Modifier.heightIn(min = 34.dp).background(Theme.accent, CircleShape).padding(horizontal = 14.dp),
                verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Icon(Icons.Outlined.AutoAwesome, null, tint = Color.White, modifier = Modifier.size(16.dp))
                Text(CREATE_MEAL_PLAN, style = Theme.chipLabel, color = Color.White)
            }
        }
    }
}

@Composable
private fun ChoiceCard(title: String, detail: String, icon: ImageVector, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().shadow(10.dp, RoundedCornerShape(16.dp), spotColor = Theme.ink.copy(alpha = 0.06f), ambientColor = Theme.ink.copy(alpha = 0.06f))
            .background(Theme.surface, RoundedCornerShape(16.dp)).clip(RoundedCornerShape(16.dp)).clickable(onClick = onClick).padding(18.dp),
        horizontalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Icon(icon, null, tint = Theme.accent, modifier = Modifier.width(28.dp).size(24.dp))
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(title, style = Theme.mealName, color = Theme.ink)
            Text(detail, style = Theme.subtitle, color = Theme.muted)
        }
        Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, null, tint = Theme.muted, modifier = Modifier.align(Alignment.CenterVertically))
    }
}

/**
 * A small drawn picture of the screen a quick-start card describes (#25). Drawn, not a screenshot,
 * so it never goes stale. Decorative. Mirrors TourScreenPicture.swift and web/src/TourPicture.jsx.
 */
@Composable
private fun TourScreenPicture(index: Int) {
    val warm = Color(0xFFF3EBE8)
    Column(
        Modifier.fillMaxSize().clip(RoundedCornerShape(14.dp)).background(Theme.bg).border(1.dp, Theme.line, RoundedCornerShape(14.dp)).padding(14.dp),
        verticalArrangement = Arrangement.spacedBy(9.dp),
    ) {
        when (index) {
            2 -> {
                PicLabel("PRODUCE")
                PicCheckRow(false, 0.5f, Theme.accent); PicCheckRow(false, 0.35f, Theme.accent); PicCheckRow(true, 0.45f, Theme.accent)
                PicLabel("PANTRY")
                PicCheckRow(true, 0.4f, Theme.accent)
            }
            3 -> {
                PicLabel("CHOP & SLICE")
                PicCheckRow(true, 0.4f, Theme.coral, pill = false); PicCheckRow(false, 0.55f, Theme.coral, pill = false); PicCheckRow(false, 0.35f, Theme.coral, pill = false)
                PicLabel("SAUCES")
                PicCheckRow(false, 0.6f, Theme.coral, pill = false)
            }
            else -> {
                PicLabel("THIS WEEK")
                for ((tint, w) in listOf(Theme.coralTint to 0.75f, Theme.aubergineTint to 0.55f, warm to 0.65f)) {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        Box(Modifier.size(40.dp).background(tint, RoundedCornerShape(7.dp)))
                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) { PicLine(w, Theme.ink.copy(alpha = 0.35f)); PicLine(0.3f) }
                    }
                }
            }
        }
    }
}

@Composable
private fun PicLabel(text: String) = Text(text, style = Theme.count.copy(fontSize = 10.sp, fontWeight = FontWeight.Bold, letterSpacing = 0.6.sp), color = Theme.muted)

@Composable
private fun PicLine(fraction: Float, color: Color = Theme.line) {
    BoxWithConstraints(Modifier.fillMaxWidth().height(7.dp)) {
        Box(Modifier.width(maxWidth * fraction).fillMaxHeight().background(color, CircleShape))
    }
}

@Composable
private fun PicCheckRow(checked: Boolean, fraction: Float, color: Color, pill: Boolean = true) {
    Row(Modifier.fillMaxWidth().alpha(if (checked) 0.6f else 1f), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        Icon(if (checked) Icons.Filled.CheckCircle else Icons.Outlined.RadioButtonUnchecked, null, tint = if (checked) color else Theme.muted, modifier = Modifier.size(16.dp))
        Box(Modifier.weight(1f)) { PicLine(fraction, if (checked) Theme.line else Theme.ink.copy(alpha = 0.35f)) }
        if (pill) Box(Modifier.size(width = 26.dp, height = 7.dp).background(Theme.line, CircleShape))
    }
}

