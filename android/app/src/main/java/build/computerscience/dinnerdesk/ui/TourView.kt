package build.computerscience.dinnerdesk.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.outlined.Checklist
import androidx.compose.material.icons.outlined.Eco
import androidx.compose.material.icons.outlined.SwapHoriz
import androidx.compose.material.icons.outlined.Timer
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import build.computerscience.dinnerdesk.data.Api
import build.computerscience.dinnerdesk.data.Copy
import build.computerscience.dinnerdesk.data.KitchenApi
import build.computerscience.dinnerdesk.data.Plan
import build.computerscience.dinnerdesk.data.PlanSlot
import build.computerscience.dinnerdesk.data.SuggestionCapabilities
import build.computerscience.dinnerdesk.data.Tour
import build.computerscience.dinnerdesk.data.bool
import build.computerscience.dinnerdesk.data.int
import build.computerscience.dinnerdesk.data.obj
import build.computerscience.dinnerdesk.data.string
import build.computerscience.dinnerdesk.data.strings
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject

private enum class TourStep { Welcome, Household, Avoid, Week, Ready }

/** Settings shows the first six "I avoid" foods as chips; the tour shows the same six. */
private val commonAvoids = FilterOptions.avoids.take(6)
private const val MAX_DINNERS = 7
private val small = Theme.chipLabel.copy(fontWeight = FontWeight.Normal)

/**
 * Quick start (mirrors web/src/Tour.jsx and TourView.swift): five full screens, one job each, each
 * fitting one phone screen without scrolling at default text size (down to 360×780).
 * Welcome → Who's eating → Anything to avoid → Here's your week → Your week is ready.
 * Replayed from Settings, it skips Welcome.
 */
@Composable
fun TourView() {
    val session = LocalSession.current
    val store = LocalStore.current
    val scope = rememberCoroutineScope()
    val openUrl = rememberOpenUrl()
    val o = FilterOptions
    var step by remember { mutableStateOf(TourStep.Welcome) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var isUpdate by remember { mutableStateOf(false) }
    var showTasteLab by remember { mutableStateOf(false) }
    // The household's saved filters, so saving keeps the ones the tour doesn't show.
    var savedFilters by remember { mutableStateOf<Map<String, JsonElement>>(emptyMap()) }
    var people by remember { mutableStateOf(2) }
    var time by remember { mutableStateOf("any") }
    var diets by remember { mutableStateOf(setOf("omnivore")) }
    var allergens by remember { mutableStateOf(setOf<String>()) }
    var avoids by remember { mutableStateOf(setOf<String>()) }
    var dinners by remember { mutableStateOf(3) }
    var proposal by remember { mutableStateOf<Plan?>(null) }
    var plan by remember { mutableStateOf<Plan?>(null) }
    var toBuy by remember { mutableStateOf<Int?>(null) }

    LaunchedEffect(Unit) {
        try {
            val prefs = KitchenApi.prefs()
            val seen = Tour.seen(prefs)
            isUpdate = (seen > 0 && seen < Tour.VERSION) || Tour.isNewBuild
            // Replayed from Settings: skip Welcome, even right after an app update.
            if (session.tourReplay) step = TourStep.Household
            prefs.int("family_portions")?.takeIf { it >= 1 }?.let { people = minOf(12, it) }
            val saved = prefs.obj("filters") ?: return@LaunchedEffect
            savedFilters = saved
            saved.strings("diets")?.takeIf { it.isNotEmpty() }?.let { diets = o.cleaned(it) }
            saved.strings("allergens")?.let { allergens = it.toSet() }
            saved.strings("avoids")?.let { avoids = it.toSet() }
            saved.string("time")?.let { time = it }
        } catch (e: Throwable) {
            if (!Api.isCancellation(e)) error = Api.message(e)
        }
    }

    fun run(work: suspend () -> Unit) {
        busy = true
        error = null
        scope.launch {
            try { work() } catch (e: Throwable) { if (!Api.isCancellation(e)) error = Api.message(e) }
            busy = false
        }
    }

    suspend fun markDone() {
        Tour.noteBuild()
        KitchenApi.savePrefs(mapOf("tour_done" to true, "tour_version" to Tour.VERSION))
    }

    /** Ends the tour. A suggested plan that wasn't approved stays on Plan for review. */
    fun finish() = run {
        markDone()
        session.tourReplay = false
        session.showTour = false
        store.loadAll()
    }

    fun saveHousehold() = run {
        val filters = savedFilters + mapOf("time" to Api.toJson(time))
        KitchenApi.savePrefs(mapOf("family_portions" to people, "filters" to filters))
        savedFilters = filters
        step = TourStep.Avoid
    }

    // Saves the filters, then asks for a suggested plan that respects them.
    fun saveFilters() = run {
        val filters = savedFilters + mapOf(
            "diets" to Api.toJson(o.diets.filter { it in diets }),
            "allergens" to Api.toJson(allergens.toList()),
            "avoids" to Api.toJson(avoids.toList()),
            "time" to Api.toJson(time),
        )
        KitchenApi.savePrefs(mapOf("filters" to filters))
        savedFilters = filters
        val caps: SuggestionCapabilities = Api.get("suggestions/capabilities")
        if (caps.version < 2 || !caps.review || !caps.resize || !caps.swap) {
            throw IllegalStateException("Meal planning needs the updated server. Please try again after the server update.")
        }
        val created: Plan = Api.send("plans", "POST", mapOf("title" to "This week", "meal_count" to dinners, "keep_current" to false))
        proposal = created
        dinners = created.slots.size
        step = TourStep.Week
    }

    fun resize(n: Int) {
        val p = proposal ?: return
        run { dinners = n; proposal = Api.send<Plan>("plans/${p.id}/resize", "POST", mapOf("meal_count" to n)) }
    }

    // Swap brings in the next-best match; the server records it as a pass for Taste Lab.
    fun swap(slot: PlanSlot) {
        val p = proposal ?: return
        run { proposal = Api.send<Plan>("plans/${p.id}/swap/${slot.id}", "POST", emptyMap()) }
    }

    fun approve() {
        val p = proposal ?: return
        run {
            val approved: Plan = if (p.status == "suggested") Api.send("plans/${p.id}/decision/approve", "POST", emptyMap()) else p
            plan = approved
            step = TourStep.Ready
            toBuy = try {
                val lines = Api.jsonObject("plans/${approved.id}/grocery")["lines"] as? kotlinx.serialization.json.JsonArray
                lines?.count { (it as? JsonObject)?.let { l -> l.bool("checked") != true && l.bool("never_shop") != true } == true }
            } catch (e: Throwable) { null }
        }
    }

    val back = when (step) { TourStep.Avoid -> TourStep.Household; TourStep.Week -> TourStep.Avoid; else -> null }
    BackHandler {
        when {
            showTasteLab -> showTasteLab = false
            back != null && !busy -> { error = null; step = back }
        }
    }

    Box(Modifier.fillMaxSize().background(Theme.bg).statusBarsPadding().navigationBarsPadding()) {
        if (showTasteLab) {
            val tasteNav = remember { Nav(Route.TasteLab()) }
            Column(Modifier.fillMaxSize()) {
                Box(Modifier.fillMaxWidth()) {
                    LinkButton("Done", Modifier.align(Alignment.CenterEnd)) { session.tourReplay = false; session.showTour = false; scope.launch { store.loadAll() } }
                }
                NavStack(tasteNav, Modifier.weight(1f)) { RouteContent(it) }
            }
            return@Box
        }
        Column(Modifier.fillMaxSize().padding(horizontal = 20.dp).padding(bottom = 12.dp)) {
            if (step != TourStep.Welcome) {
                Row(Modifier.fillMaxWidth().heightIn(min = 48.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Box(Modifier.size(44.dp).clip(CircleShape).then(if (back != null) Modifier.clickable(role = Role.Button) { error = null; step = back }.semantics { contentDescription = "Back" } else Modifier), contentAlignment = Alignment.Center) {
                        if (back != null) Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, null, tint = Theme.ink)
                    }
                    Row(Modifier.weight(1f).semantics { contentDescription = "Step ${step.ordinal + 1} of ${TourStep.entries.size}" }, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                        for (s in TourStep.entries) Box(Modifier.weight(1f).height(4.dp).clip(CircleShape).background(if (s.ordinal <= step.ordinal) Theme.ink else Theme.line))
                    }
                    if (step != TourStep.Ready) LinkButton("Skip", enabled = !busy, style = Theme.chipLabel) { finish() } else Spacer(Modifier.size(44.dp))
                }
            }
            when (step) {
                TourStep.Welcome -> {
                    Column(Modifier.weight(1f).fillMaxWidth().verticalScroll(rememberScrollState()), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
                        Text("Free. No ads, ever.", style = Theme.chipLabel, color = Theme.ink,
                            modifier = Modifier.clip(CircleShape).background(Theme.aubergineTint).padding(horizontal = 14.dp, vertical = 6.dp))
                        Spacer(Modifier.height(16.dp))
                        Text("Custom meal plans in 5 minutes.", style = Theme.bigTitle, color = Theme.ink, textAlign = TextAlign.Center)
                        Spacer(Modifier.height(28.dp))
                        Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
                            Benefit(Icons.Outlined.Checklist, "Grocery list built for you")
                            Benefit(Icons.Outlined.Timer, "Prep-ahead steps for busy nights")
                            Benefit(Icons.Outlined.Eco, "Less waste, using your pantry")
                        }
                        if (isUpdate) {
                            Spacer(Modifier.height(20.dp))
                            Text(Copy.text("tour.update"), style = Theme.subtitle, color = Theme.muted)
                        }
                    }
                    Primary("Get started", error, busy) { step = TourStep.Household }
                    LinkButton("Skip, I’ll look around", Modifier.fillMaxWidth(), enabled = !busy, style = Theme.chipLabel) { finish() }
                    LinkButton(Copy.text("tour.ai.more"), Modifier.fillMaxWidth(), style = Theme.chipLabel) { openUrl(Api.url("support") + "#ai") }
                }
                TourStep.Household -> {
                    Page {
                        Heading("Who’s eating dinner?", "We’ll size recipes and the grocery list to match.")
                        Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(Theme.surface).border(1.dp, Theme.line, RoundedCornerShape(18.dp)).padding(vertical = 22.dp),
                            horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(10.dp)) {
                            Stepper(people, 1, 12, "people", big = true, busy = busy) { people = it }
                            Text("people, most nights", style = Theme.body, color = Theme.ink)
                        }
                        Text("Weeknight cook time", style = Theme.chipLabel, color = Theme.ink, modifier = Modifier.padding(top = 22.dp, bottom = 8.dp))
                        Row(Modifier.fillMaxWidth().clip(CircleShape).background(Theme.surface).border(1.dp, Theme.line, CircleShape).padding(3.dp)) {
                            for ((id, label) in o.times) {
                                val on = time == id
                                Box(Modifier.weight(1f).heightIn(min = 40.dp).clip(CircleShape).background(if (on) Theme.ink else Color.Transparent)
                                    .clickable(role = Role.RadioButton) { time = id }.semantics { selected = on }, contentAlignment = Alignment.Center) {
                                    Text(label.replace(" or less", "").replace("Any time", "Any"), style = small, color = if (on) Color.White else Theme.ink)
                                }
                            }
                        }
                        Text("Feeding a crowd one night? Change servings on any single meal later.", style = small, color = Theme.ink,
                            modifier = Modifier.padding(top = 18.dp).fillMaxWidth().clip(RoundedCornerShape(14.dp)).background(Theme.aubergineTint).padding(14.dp))
                    }
                    Primary(if (busy) "Saving…" else "Next", error, busy) { saveHousehold() }
                }
                TourStep.Avoid -> {
                    Page {
                        Heading("Anything to avoid?", null)
                        Group("Diet", "Only show recipes that fit.")
                        Flow(6.dp) { for (d in o.diets) TourChip(o.dietLabels[d] ?: d, d in diets) { diets = o.toggled(diets, d) } }
                        Group("Allergies", "Never shown. We check every ingredient.")
                        Flow(6.dp) { for ((id, label) in o.allergens) TourChip(label, id in allergens) { allergens = if (id in allergens) allergens - id else allergens + id } }
                        Group("I avoid", "Left out of picks. More in Settings → Filters.")
                        Flow(6.dp) { for (id in commonAvoids) TourChip(id.split(" ").joinToString(" ") { w -> w.replaceFirstChar { it.uppercase() } }, id in avoids) { avoids = if (id in avoids) avoids - id else avoids + id } }
                    }
                    Primary(if (busy) "Planning your week…" else "Next", error, busy) { saveFilters() }
                }
                TourStep.Week -> {
                    Page {
                        Heading("Here’s your week", "Picked for you. Swap anything that doesn’t sound good.")
                        Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(Theme.surface).border(1.dp, Theme.line, RoundedCornerShape(18.dp)).padding(start = 16.dp, top = 6.dp, end = 6.dp, bottom = 6.dp),
                            verticalAlignment = Alignment.CenterVertically) {
                            Text("Dinners this week", style = Theme.action, color = Theme.ink, modifier = Modifier.weight(1f))
                            Stepper(dinners, 1, MAX_DINNERS, "dinners", big = false, busy = busy) { resize(it) }
                        }
                        Spacer(Modifier.height(12.dp))
                        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            for (slot in proposal?.slots.orEmpty()) {
                                Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(Theme.surface).border(1.dp, Theme.line, RoundedCornerShape(16.dp)).padding(8.dp),
                                    verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                                    RecipePhoto(slot.photoPath)
                                    Column(Modifier.weight(1f)) {
                                        Text(slot.recipeName, style = Theme.chipLabel, color = Theme.ink, maxLines = 3)
                                        slot.cookingMinutes?.let { Text("$it min", style = Theme.subtitle, color = Theme.muted) }
                                    }
                                    if (proposal?.suggestedRecipeIds?.contains(slot.recipeId) == true) {
                                        Row(Modifier.heightIn(min = 44.dp).clip(CircleShape).background(Theme.bg).border(1.dp, Theme.line, CircleShape)
                                            .clickable(enabled = !busy, role = Role.Button) { swap(slot) }.semantics { contentDescription = "Swap ${slot.recipeName}" }
                                            .padding(horizontal = 12.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                            Icon(Icons.Outlined.SwapHoriz, null, tint = Theme.accent, modifier = Modifier.size(16.dp))
                                            Text("Swap", style = Theme.chipLabel, color = Theme.accent)
                                        }
                                    }
                                }
                            }
                        }
                    }
                    Primary("Looks good", error, busy || proposal?.slots.isNullOrEmpty()) { approve() }
                }
                TourStep.Ready -> {
                    val count = (plan ?: proposal)?.slots?.size ?: 0
                    val sub = "$count dinner${if (count == 1) "" else "s"} for $people" + (toBuy?.let { " · $it thing${if (it == 1) "" else "s"} to buy" } ?: "")
                    Page {
                        Heading("Your week is ready", sub)
                        Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
                            Tip(1, "Plan", "Give meals a day when you know it. No rush, they stay on your list.")
                            Tip(2, "Grocery", "Your list builds itself. Check things off in the store.")
                            Tip(3, "Prep ahead", "Got time on the weekend? See what you can chop and cook early.")
                        }
                        Column(Modifier.padding(top = 24.dp).fillMaxWidth().clip(RoundedCornerShape(14.dp)).background(Theme.aubergineTint).padding(horizontal = 14.dp, vertical = 4.dp)) {
                            Text("Want better picks next week?", style = small, color = Theme.ink, modifier = Modifier.padding(top = 8.dp))
                            LinkButton("Try Taste Lab (about 2 min)", enabled = !busy, style = Theme.chipLabel) {
                                run { markDone(); showTasteLab = true }
                            }
                        }
                    }
                    Primary("Done", error, busy) { finish() }
                }
            }
        }
    }
}

/** Fills the space above the button; scrolls only if large text needs the room. */
@Composable
private fun ColumnScope.Page(content: @Composable ColumnScope.() -> Unit) {
    Column(Modifier.weight(1f).fillMaxWidth().verticalScroll(rememberScrollState()), content = content)
}

@Composable
private fun Heading(title: String, sub: String?) {
    Column(Modifier.padding(top = 8.dp, bottom = 16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(title, style = Theme.tourTitle, color = Theme.ink)
        sub?.let { Text(it, style = small, color = Theme.muted) }
    }
}

@Composable
private fun Group(title: String, note: String) {
    Column(Modifier.padding(top = 12.dp, bottom = 8.dp)) {
        Text(title, style = Theme.chipLabel, color = Theme.ink)
        Text(note, style = Theme.subtitle, color = Theme.muted)
    }
}

/** A filter chip short enough that the Quick start filters fit one screen. */
@Composable
private fun TourChip(label: String, on: Boolean, onClick: () -> Unit) {
    Box(
        Modifier.heightIn(min = 34.dp).clip(CircleShape).background(if (on) Theme.ink else Theme.surface)
            .border(1.dp, if (on) Theme.ink else Theme.line, CircleShape)
            .clickable(role = Role.Checkbox, onClick = onClick).semantics { selected = on }
            .padding(horizontal = 12.dp, vertical = 7.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(label, style = small.copy(fontWeight = FontWeight.Medium, fontSize = 14.sp), color = if (on) Color.White else Theme.ink)
    }
}

@Composable
private fun Stepper(value: Int, min: Int, max: Int, label: String, big: Boolean, busy: Boolean, onChange: (Int) -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(if (big) 18.dp else 10.dp)) {
        RoundButton("−", "Fewer $label", if (big) 48 else 44, !busy && value > min) { onChange(value - 1) }
        Text("$value", style = Theme.action.copy(fontSize = if (big) 40.sp else 22.sp, fontWeight = FontWeight.Bold), color = Theme.ink,
            textAlign = TextAlign.Center, modifier = Modifier.widthIn(min = if (big) 36.dp else 26.dp))
        RoundButton("+", "More $label", if (big) 48 else 44, !busy && value < max) { onChange(value + 1) }
    }
}

@Composable
private fun RoundButton(text: String, label: String, size: Int, enabled: Boolean, onClick: () -> Unit) {
    Box(
        Modifier.size(size.dp).clip(CircleShape).background(Theme.bg).border(1.dp, Theme.line, CircleShape)
            .clickable(enabled = enabled, role = Role.Button, onClick = onClick).semantics { contentDescription = label },
        contentAlignment = Alignment.Center,
    ) {
        Text(text, style = Theme.action.copy(fontSize = 22.sp), color = if (enabled) Theme.ink else Theme.ink.copy(alpha = 0.4f))
    }
}

@Composable
private fun Benefit(icon: ImageVector, text: String) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
        Box(Modifier.size(40.dp).clip(CircleShape).background(Theme.aubergineTint), contentAlignment = Alignment.Center) {
            Icon(icon, null, tint = Theme.ink, modifier = Modifier.size(20.dp))
        }
        Text(text, style = Theme.body, color = Theme.ink)
    }
}

@Composable
private fun Tip(n: Int, title: String, text: String) {
    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        Box(Modifier.size(26.dp).clip(CircleShape).background(Theme.coral), contentAlignment = Alignment.Center) {
            Text("$n", style = Theme.subtitle.copy(fontWeight = FontWeight.Bold), color = Theme.ink)
        }
        Column {
            Text(title, style = Theme.chipLabel, color = Theme.ink)
            Text(text, style = small, color = Theme.ink)
        }
    }
}

@Composable
private fun Primary(text: String, error: String?, disabled: Boolean, onClick: () -> Unit) {
    Column(Modifier.padding(top = 8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        error?.let { Text(it, style = Theme.subtitle, color = Theme.errorText) }
        AccentButton(text, Modifier.fillMaxWidth(), enabled = !disabled, onClick = onClick)
    }
}
