package build.computerscience.dinnerdesk.ui

import android.content.Context
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.Assignment
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material.icons.filled.RadioButtonChecked
import androidx.compose.material.icons.outlined.AddCircleOutline
import androidx.compose.material.icons.outlined.RadioButtonUnchecked
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
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.layout.positionInParent
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import build.computerscience.dinnerdesk.data.Copy
import build.computerscience.dinnerdesk.data.MissingPrepMeal
import build.computerscience.dinnerdesk.data.MissingPrepStep
import build.computerscience.dinnerdesk.data.PrepMeal
import build.computerscience.dinnerdesk.data.PrepMealGroup
import build.computerscience.dinnerdesk.data.PrepMealPresentation
import build.computerscience.dinnerdesk.data.PrepMealTask
import build.computerscience.dinnerdesk.data.PrepReason
import build.computerscience.dinnerdesk.data.PrepTask
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private data class PrepSection(val key: String, val title: String, val short: String)

private val prepSections = listOf(
    PrepSection("veg", "Vegetables", "Veg"),
    PrepSection("herbs", "Aromatics, herbs & citrus", "Aromatics"),
    PrepSection("protein", "Protein", "Protein"),
    PrepSection("cheese", "Cheese & dairy", "Cheese"),
    PrepSection("sauce", "Sauces & dressings", "Sauce"),
    PrepSection("other", Copy.text("ui.more.prep"), "More"),
)

private class PrepGroup(val section: PrepSection, val all: List<PrepTask>, val shown: List<PrepTask>) {
    val done get() = all.count { it.done }
}

/**
 * Weekend prep (#21). "By meal" (default) shows one card per meal with a row per task, whose ring
 * checks that meal's steps; "By task" groups by what the food is (mirrors web .pz-view). One row per item however many meals use it.
 * A progress ring and one bar per section up top; collapsible sections; 👍/👎 on the open item;
 * a done item leaves its section unless "Show completed" is on, and a short-lived bar offers Undo.
 */
@Composable
fun PrepView() {
    val store = LocalStore.current
    val nav = LocalNav.current
    val selectTab = LocalSelectTab.current
    val dismiss = LocalDismiss.current
    val context = LocalContext.current
    val prefs = remember { context.getSharedPreferences("dinnerdesk", Context.MODE_PRIVATE) }
    var showDone by remember { mutableStateOf(prefs.getBoolean("prep.showDone", false)) }
    var closed by remember { mutableStateOf(prefs.getString("prep.closed", "")!!.split(",").filter { it.isNotEmpty() }.toSet()) }
    var whyOpen by remember { mutableStateOf<Int?>(null) }
    var whyNote by remember { mutableStateOf("") }
    var detailsOpen by remember { mutableStateOf(setOf<Int>()) }
    var toast by remember { mutableStateOf<Int?>(null) }
    var missingOpen by remember { mutableStateOf(false) }
    var prepView by remember { mutableStateOf(prefs.getString("prep.view", "meal") ?: "meal") }
    var openMealTask by remember { mutableStateOf<String?>(null) }
    val scroll = rememberScrollState()
    val scope = rememberCoroutineScope()
    val reduceMotion = isReduceMotion
    val offsets = remember { mutableMapOf<String, Int>() }

    LaunchedEffect(Unit) { store.loadPrep(onlyIfStale = true) }
    LaunchedEffect(toast) {
        val id = toast ?: return@LaunchedEffect
        delay(4000)
        if (toast == id) toast = null
    }

    val tasks = store.prepTasks
    val doneCount = tasks.count { it.done }
    val groups = prepSections.mapNotNull { s ->
        val all = tasks.filter { (it.section ?: "other") == s.key }
        if (all.isEmpty()) null else {
            val left = all.filter { !it.done }
            PrepGroup(s, all, if (showDone) left + all.filter { it.done } else left)
        }
    }

    fun toggleDetails(task: PrepTask) {
        if (task.id in detailsOpen) {
            detailsOpen = detailsOpen - task.id
            if (whyOpen == task.id) whyOpen = null
        } else detailsOpen = detailsOpen + task.id
    }

    Box(Modifier.fillMaxSize().background(Theme.bg)) {
        Column(Modifier.fillMaxSize()) {
            if (nav.canPop) NavBar()
            RefreshBox({ store.loadPrep() }) {
                Column(Modifier.fillMaxSize().verticalScroll(scroll).padding(horizontal = 16.dp).padding(top = 4.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                    Text(Copy.text("tour.how.4.title"), style = Theme.bigTitle, color = Theme.ink, modifier = Modifier.semantics { heading() })
                    store.error?.let { ErrorBanner(it) }
                    if (tasks.isEmpty()) {
                        EmptyState(Copy.text("ui.no.prep.yet"), Copy.text("ui.add.meals.on.plan.makeahead"), Icons.AutoMirrored.Outlined.Assignment)
                        if (store.plan?.slots?.isEmpty() != false) {
                            Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) { CreateMealPlanButton { store.launch { openSuggestions() } } }
                        } else {
                            LinkButton(Copy.text("ui.back.to.plan"), Modifier.fillMaxWidth()) { selectTab(AppTab.Plan); dismiss() }
                        }
                    } else {
                        PrepHeader(tasks.size, doneCount, groups, showDone, onToggleDone = {
                            showDone = !showDone
                            prefs.edit().putBoolean("prep.showDone", showDone).apply()
                        }, prepView = prepView, onSelectView = { next ->
                            prepView = next
                            prefs.edit().putString("prep.view", next).apply()
                        }) { key ->
                            // The section bars jump to By task sections.
                            if (prepView != "task") {
                                prepView = "task"
                                prefs.edit().putString("prep.view", "task").apply()
                            }
                            scope.launch {
                                delay(50)
                                offsets[key]?.let { y -> if (reduceMotion) scroll.scrollTo(y) else scroll.animateScrollTo(y) }
                            }
                        }
                        if (prepView == "meal") {
                            for (g in PrepMealPresentation(tasks).mealGroups) {
                                MealCard(
                                    g, showDone, openKey = openMealTask,
                                    onOpen = { key -> openMealTask = if (openMealTask == key) null else key },
                                    openRecipe = { nav.push(Route.Recipe(it)) },
                                ) { task, keys, done -> store.launch { setPrepMealSteps(task.taskId, g.id, keys, done) } }
                            }
                        }
                        if (prepView == "task") for (g in groups) {
                            Box(Modifier.onGloballyPositioned { offsets[g.section.key] = it.positionInParent().y.toInt() }) {
                                SectionBlock(
                                    g, open = g.section.key !in closed,
                                    onToggle = {
                                        closed = if (g.section.key in closed) closed - g.section.key else closed + g.section.key
                                        prefs.edit().putString("prep.closed", closed.sorted().joinToString(",")).apply()
                                    },
                                ) { task ->
                                    PrepRow(
                                        task, open = task.id in detailsOpen, whyOpen = whyOpen == task.id, whyNote = whyNote,
                                        onWhyNote = { whyNote = it },
                                        onCheck = {
                                            val next = !task.done
                                            store.launch { togglePrep(task) }
                                            toast = if (next) task.id else null
                                        },
                                        onToggleDetails = { toggleDetails(task) },
                                        onRate = { next ->
                                            whyOpen = if (next < 0) task.id else null
                                            whyNote = task.reasonNote ?: ""
                                            store.launch { ratePrepTask(task.id, next, reason = if (next < 0) (task.reason ?: "") else "") }
                                        },
                                        onReason = { reason -> store.launch { ratePrepTask(task.id, -1, reason = reason) } },
                                        onWhyDone = {
                                            val words = whyNote.trim()
                                            whyOpen = null
                                            store.launch { ratePrepTask(task.id, -1, reason = task.reason ?: "", note = words) }
                                        },
                                        openRecipe = { nav.push(Route.Recipe(it)) },
                                    )
                                }
                            }
                        }
                        MissingButton { missingOpen = true }
                    }
                    // Room so the check-off bar never covers the last row.
                    Spacer(Modifier.height(if (toast == null) 8.dp else 72.dp))
                }
            }
        }
        val toastTask = toast?.let { id -> tasks.firstOrNull { it.id == id } }
        AnimatedVisibility(
            toastTask != null, Modifier.align(Alignment.BottomCenter),
            // Reduce Motion: fade the check-off bar in place instead of sliding it up.
            enter = if (reduceMotion) fadeIn() else slideInVertically { it } + fadeIn(),
            exit = if (reduceMotion) fadeOut() else slideOutVertically { it } + fadeOut(),
        ) {
            val task = toastTask ?: return@AnimatedVisibility
            Row(
                Modifier.padding(horizontal = 12.dp).padding(bottom = 12.dp).fillMaxWidth()
                    .shadow(14.dp, RoundedCornerShape(20.dp), spotColor = Theme.ink.copy(alpha = 0.25f))
                    .background(Theme.ink, RoundedCornerShape(20.dp)).padding(start = 16.dp, end = 6.dp, top = 8.dp, bottom = 8.dp),
                verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Icon(Icons.Filled.CheckCircle, null, tint = Theme.coral, modifier = Modifier.size(20.dp))
                Text("${task.name} checked off", style = Theme.subtitle, color = Theme.surface, maxLines = 2, modifier = Modifier.weight(1f))
                Text(
                    "Undo", style = Theme.action.copy(textDecoration = TextDecoration.Underline), color = Theme.coralTint,
                    modifier = Modifier.heightIn(min = 44.dp).clickable { store.launch { togglePrep(task) }; toast = null }.padding(top = 11.dp),
                )
                IconAction(Icons.Filled.Close, "Dismiss", tint = Theme.aubergineTint, size = 18.dp) { toast = null }
            }
        }
    }
    if (missingOpen) Sheet(onDismiss = { missingOpen = false }) { MissingPrepSheet() }
}

/** By meal / By task switch (mirrors .pz-view on web): compact, sized to its labels. */
@Composable
private fun PrepViewSwitch(selected: String, onSelect: (String) -> Unit) {
    Row(
        Modifier.heightIn(min = 44.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Row(
            Modifier.background(Theme.aubergineTint, CircleShape).padding(3.dp),
            horizontalArrangement = Arrangement.spacedBy(2.dp),
        ) {
            for ((key, label) in listOf("meal" to "By meal", "task" to "By task")) {
                val on = selected == key
                Box(
                    Modifier.heightIn(min = 30.dp).clip(CircleShape)
                        .background(if (on) Theme.ink else Color.Transparent)
                        .clickable { onSelect(key) }
                        .padding(horizontal = 12.dp)
                        .semantics { contentDescription = if (on) "$label, selected" else label },
                    contentAlignment = Alignment.Center,
                ) { Text(label, style = Theme.count.copy(fontWeight = FontWeight.SemiBold), color = if (on) Theme.surface else Theme.ink, maxLines = 1) }
            }
        }
    }
}

@Composable
private fun MealCard(
    g: PrepMealGroup, showDone: Boolean, openKey: String?, onOpen: (String) -> Unit,
    openRecipe: (Int) -> Unit, onCheck: (PrepMealTask, List<String?>, Boolean) -> Unit,
) {
    val shown = if (showDone) g.tasks else g.tasks.filter { !it.done }
    val left = g.tasks.count { !it.done }
    Column(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(Theme.surface)
            .border(1.dp, Theme.line, RoundedCornerShape(16.dp))
            .padding(start = 16.dp, end = 16.dp, top = 14.dp, bottom = 4.dp),
    ) {
        Column(
            Modifier.fillMaxWidth().heightIn(min = 44.dp).clickable { openRecipe(g.id) }.padding(bottom = 8.dp),
            verticalArrangement = Arrangement.spacedBy(2.dp),
        ) {
            Text(g.name, style = Theme.action, color = Theme.ink)
            Text(listOfNotNull(g.day, if (left > 0) "$left to prep" else Copy.text("ui.all.prepped")).joinToString(" · "), style = Theme.subtitle, color = Theme.muted)
        }
        for (t in shown) {
            Box(Modifier.fillMaxWidth().height(1.dp).background(Theme.line))
            MealTaskRow(g, t, open = openKey == "${g.id}:${t.taskId}", onOpen = { onOpen("${g.id}:${t.taskId}") }, onCheck = onCheck)
        }
    }
}

@Composable
private fun MealTaskRow(
    g: PrepMealGroup, t: PrepMealTask, open: Boolean, onOpen: () -> Unit,
    onCheck: (PrepMealTask, List<String?>, Boolean) -> Unit,
) {
    val done = t.steps.count { it.done }
    val total = t.steps.size.coerceAtLeast(1)
    val summary = if (t.quantities.isNotEmpty()) t.quantities.joinToString(" · ")
        else if (t.steps.size == 1) "1 step" else "${t.steps.size} steps"
    val progress = if (done > 0 && !t.done) "$done of ${t.steps.size} · " else ""
    Column {
        Row(Modifier.fillMaxWidth().heightIn(min = 64.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(
                Modifier.size(44.dp).clip(CircleShape).clickable { onCheck(t, t.steps.map { it.key }, !t.done) }
                    .semantics { contentDescription = "${if (t.done) "Mark not done" else Copy.text("ui.mark.done")}: ${t.title} for ${g.name}" },
                contentAlignment = Alignment.Center,
            ) {
                Canvas(Modifier.size(24.dp)) {
                    val w = 2.4.dp.toPx()
                    val arc = Size(size.width - w, size.height - w)
                    val at = Offset(w / 2, w / 2)
                    drawCircle(if (t.done) Theme.coral else Theme.surface)
                    drawArc(if (t.done) Theme.coral else Theme.dash, 0f, 360f, false, at, arc, style = Stroke(w))
                    if (done > 0 && !t.done) drawArc(Theme.coral, -90f, 360f * done / total, false, at, arc, style = Stroke(w))
                }
                if (t.done) Icon(Icons.Filled.Check, null, tint = Theme.ink, modifier = Modifier.size(14.dp))
            }
            Row(
                Modifier.weight(1f).heightIn(min = 64.dp).clickable(onClick = onOpen).padding(start = 4.dp, top = 10.dp, bottom = 10.dp)
                    .semantics { contentDescription = "${t.title}, $progress$summary, ${if (open) "expanded" else "collapsed"}" },
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text(
                        t.title, style = Theme.action, color = if (t.done) Theme.muted else Theme.bodyInk,
                        textDecoration = if (t.done) TextDecoration.LineThrough else null,
                    )
                    Text(progress + summary, style = Theme.stepText, color = Theme.muted)
                }
                Icon(
                    Icons.Filled.KeyboardArrowDown, null, tint = Theme.muted,
                    modifier = Modifier.size(22.dp).rotate(if (open) 180f else 0f),
                )
            }
        }
        if (open) {
            Column(Modifier.padding(start = 44.dp, bottom = 12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                for (step in t.steps) {
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        val key = step.key
                        Box(
                            Modifier.size(36.dp).clip(CircleShape)
                                .then(if (key != null) Modifier.clickable { onCheck(t, listOf(key), !step.done) } else Modifier)
                                .semantics { contentDescription = "${if (step.done) "Mark not done" else Copy.text("ui.mark.done")}: ${step.text}" },
                            contentAlignment = Alignment.Center,
                        ) {
                            Box(
                                Modifier.size(22.dp).clip(CircleShape)
                                    .background(if (step.done) Theme.coral else Theme.surface)
                                    .border(1.5.dp, if (step.done) Theme.coral else Theme.dash, CircleShape),
                                contentAlignment = Alignment.Center,
                            ) { if (step.done) Icon(Icons.Filled.Check, null, tint = Theme.ink, modifier = Modifier.size(12.dp)) }
                        }
                        Column(Modifier.weight(1f).padding(top = 7.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Text(
                                step.text, style = Theme.stepText, color = if (step.done) Theme.muted else Theme.bodyInk,
                                textDecoration = if (step.done) TextDecoration.LineThrough else null,
                            )
                            if (step.quantities.isNotEmpty()) Text(step.quantities.joinToString(" · "), style = Theme.subtitle, color = Theme.muted)
                            if (step.added) Text(Copy.text("ui.added.by.you"), style = Theme.subtitle, color = Theme.muted)
                        }
                    }
                }
                if (t.storage.isNotEmpty()) Text(t.storage, style = Theme.subtitle, color = Theme.muted, modifier = Modifier.padding(top = 4.dp))
            }
        }
    }
}

@Composable
private fun PrepHeader(
    total: Int, doneCount: Int, groups: List<PrepGroup>, showDone: Boolean, onToggleDone: () -> Unit,
    prepView: String, onSelectView: (String) -> Unit, jump: (String) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
            Box(Modifier.size(56.dp).semantics { contentDescription = "$doneCount of $total prep items done" }, contentAlignment = Alignment.Center) {
                Canvas(Modifier.size(56.dp)) {
                    val w = 7.dp.toPx()
                    val inset = w / 2
                    val arc = Size(size.width - w, size.height - w)
                    drawArc(Theme.aubergineTint, 0f, 360f, false, Offset(inset, inset), arc, style = Stroke(w))
                    if (total > 0) drawArc(Theme.coral, -90f, 360f * doneCount / total, false, Offset(inset, inset), arc, style = Stroke(w))
                }
                Text("$doneCount/$total", style = Theme.count.copy(fontWeight = FontWeight.Bold), color = Theme.ink, maxLines = 1)
            }
            Text(Copy.text("prep.about"), style = Theme.subtitle, color = Theme.muted, modifier = Modifier.weight(1f))
        }
        // One bar per section. Tap to jump there. At large text the bars stack so their labels stay readable.
        val bar: @Composable (PrepGroup, Modifier) -> Unit = { g, m ->
            Column(
                m.heightIn(min = 44.dp).clickable { jump(g.section.key) }.semantics { contentDescription = "${g.section.title}, ${g.done} of ${g.all.size} done" },
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Box(Modifier.fillMaxWidth().height(8.dp).clip(CircleShape).background(Theme.aubergineTint)) {
                    Box(Modifier.fillMaxWidth(g.done.toFloat() / g.all.size).height(8.dp).clip(CircleShape).background(Theme.coral))
                }
                // Name and count on their own lines, matching iOS.
                Text(g.section.short, style = Theme.count.copy(fontWeight = FontWeight.Bold), color = Theme.ink, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text("${g.done}/${g.all.size}", style = Theme.count, color = Theme.muted, maxLines = 1)
            }
        }
        if (isAccessibilitySize) Column(verticalArrangement = Arrangement.spacedBy(8.dp)) { for (g in groups) bar(g, Modifier.fillMaxWidth()) }
        else Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) { for (g in groups) bar(g, Modifier.weight(1f)) }
        // View switch and Show/Hide completed share one row; they stack at the largest text sizes.
        val toggle: @Composable () -> Unit = {
            if (doneCount > 0) Box(Modifier.heightIn(min = 44.dp).clickable(onClick = onToggleDone).padding(horizontal = 4.dp), contentAlignment = Alignment.Center) {
                Text(
                    if (showDone) Copy.text("ui.hide.completed") else "Show completed ($doneCount)",
                    style = Theme.count.copy(fontWeight = FontWeight.SemiBold), color = Theme.accent, maxLines = 1,
                )
            }
        }
        if (isAccessibilitySize) Column(verticalArrangement = Arrangement.spacedBy(8.dp)) { PrepViewSwitch(prepView, onSelectView); toggle() }
        else Row(verticalAlignment = Alignment.CenterVertically) {
            PrepViewSwitch(prepView, onSelectView)
            Spacer(Modifier.weight(1f))
            toggle()
        }
    }
}

@Composable
private fun SectionBlock(g: PrepGroup, open: Boolean, onToggle: () -> Unit, row: @Composable (PrepTask) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(
            Modifier.fillMaxWidth().heightIn(min = 44.dp).clickable(onClick = onToggle).semantics { heading(); contentDescription = "${g.section.title}, ${if (open) "Expanded" else "Collapsed"}" },
            verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text(g.section.title, style = Theme.recipeTitle, color = Theme.ink, modifier = Modifier.weight(1f))
            Text("${g.done} of ${g.all.size}", style = Theme.count, color = Theme.muted)
            Box(Modifier.size(32.dp).background(Theme.aubergineTint, CircleShape), contentAlignment = Alignment.Center) {
                Icon(Icons.Filled.KeyboardArrowUp, null, tint = Theme.ink, modifier = Modifier.size(20.dp).rotate(if (open) 0f else 180f))
            }
        }
        if (open) {
            if (g.shown.isEmpty()) {
                Text(
                    Copy.text("ui.all.prepped.here"), style = Theme.subtitle, color = Theme.muted,
                    modifier = Modifier.fillMaxWidth().dashedBorder(Theme.line, 16.dp, dash = 4f, gap = 4f).padding(14.dp),
                )
            } else {
                Column(
                    Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(Theme.surface).border(1.dp, Theme.line, RoundedCornerShape(16.dp)),
                ) {
                    g.shown.forEachIndexed { index, task ->
                        if (index > 0) Hairline()
                        androidx.compose.runtime.key(task.id) { row(task) }
                    }
                }
            }
        }
    }
}

@Composable
private fun PrepRow(
    task: PrepTask, open: Boolean, whyOpen: Boolean, whyNote: String, onWhyNote: (String) -> Unit,
    onCheck: () -> Unit, onToggleDetails: () -> Unit, onRate: (Int) -> Unit, onReason: (String) -> Unit,
    onWhyDone: () -> Unit, openRecipe: (Int) -> Unit,
) {
    val sub = task.quantities.filter { it.isNotEmpty() }.joinToString(" · ")
    val disliked = (task.rating ?: 0) < 0
    Column(Modifier.fillMaxWidth().background(if (task.done) Theme.bg else Theme.surface), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(Modifier.padding(start = 4.dp, end = 6.dp, top = 6.dp, bottom = 6.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Box(
                Modifier.size(44.dp).clickable(onClick = onCheck).semantics { contentDescription = if (task.done) "Uncheck ${task.name}" else "Check off ${task.name}" },
                contentAlignment = Alignment.Center,
            ) { CheckCircle(task.done, 28.dp, Theme.coral) }
            Column(Modifier.weight(1f).alpha(if (task.done) 0.6f else 1f).clickable(onClick = onToggleDetails), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(task.name, style = Theme.mealName.copy(textDecoration = if (task.done) TextDecoration.LineThrough else null), color = Theme.ink)
                if (sub.isNotEmpty()) Text(sub, style = Theme.subtitle, color = Theme.muted)
            }
            // 👍/👎 only on the open item (#78 D); closed rows stay quiet.
            if (open) ThumbsControl(task.rating ?: 0, "prepping ${task.name} ahead", onRate = onRate)
            Box(
                Modifier.size(44.dp).clickable(onClick = onToggleDetails).semantics { contentDescription = if (open) "Hide steps for ${task.name}" else "Show steps for ${task.name}" },
                contentAlignment = Alignment.Center,
            ) {
                Box(Modifier.size(32.dp).background(if (open) Theme.aubergineTint else Color.Transparent, CircleShape), contentAlignment = Alignment.Center) {
                    Icon(Icons.Filled.KeyboardArrowDown, null, tint = if (open) Theme.ink else Theme.muted, modifier = Modifier.size(20.dp).rotate(if (open) 180f else 0f))
                }
            }
        }
        Column(Modifier.padding(end = 14.dp, bottom = if (whyOpen || open || disliked) 14.dp else 0.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            if (whyOpen) {
                Column(Modifier.padding(start = 54.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(Copy.text("ui.why.not"), style = Theme.action, color = Theme.ink)
                    Flow(6.dp) { for (reason in PrepReason.entries) ReasonChip(reason.label, task.reason == reason.id) { onReason(reason.id) } }
                    // Same as "Missing a prep step?": the user's own words go with the 👎.
                    Text(Copy.text("ui.anything.to.add.optional"), style = Theme.action, color = Theme.ink)
                    TextBox(whyNote, onWhyNote, Copy.text("ui.what.would.you.do.instead"), style = Theme.subtitle, minLines = 2, maxLines = 5, contentDescription = Copy.text("ui.anything.to.add.optional.2"))
                    ReasonChip("Done", false, onWhyDone)
                }
            } else if (disliked && (!task.reason.isNullOrEmpty() || !task.reasonNote.isNullOrEmpty())) {
                Column(Modifier.padding(start = 54.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    PrepReason.of(task.reason)?.let {
                        Text(
                            it.label, style = Theme.count.copy(fontWeight = FontWeight.SemiBold), color = Theme.coralInk,
                            modifier = Modifier.background(Theme.coralTint, RoundedCornerShape(6.dp)).padding(horizontal = 8.dp, vertical = 3.dp),
                        )
                    }
                    val words = task.reasonNote
                    if (!words.isNullOrEmpty()) Text("“$words”", style = Theme.subtitle.copy(fontStyle = FontStyle.Italic), color = Theme.muted)
                }
            }
            if (open) {
                // #78 D: the cook day on the left, the step, then each meal as a light pill link.
                Column(Modifier.padding(start = 14.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                    for (group in build.computerscience.dinnerdesk.data.PrepTaskPresentation(task).instructionGroups) {
                        val text = group.text
                        val meals = group.meals
                        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            Text(
                                (meals.firstOrNull()?.day ?: "").uppercase(), style = Theme.count.copy(fontWeight = FontWeight.Bold, letterSpacing = 0.5.sp),
                                color = Theme.ink, textAlign = TextAlign.Center, modifier = Modifier.width(34.dp).padding(top = 2.dp),
                            )
                            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                                Text(text, style = Theme.stepText, color = Theme.bodyInk)
                                if (group.quantities.isNotEmpty()) Text(group.quantities.joinToString(" · "), style = Theme.subtitle, color = Theme.muted)
                                if (group.added) Text(Copy.text("ui.added.by.you"), style = Theme.count, color = Theme.muted)
                                for (meal in meals) {
                                    Row(
                                        Modifier.heightIn(min = 32.dp).clip(CircleShape).background(Theme.pill).clickable { openRecipe(meal.id) }
                                            .semantics { contentDescription = meal.name + (meal.day?.let { ", $it" } ?: "") }
                                            .padding(start = 10.dp, end = 8.dp, top = 5.dp, bottom = 5.dp),
                                        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp),
                                    ) {
                                        Text(meal.name, style = Theme.count.copy(fontWeight = FontWeight.SemiBold), color = Theme.ink, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f, fill = false))
                                        Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, null, tint = Theme.ink.copy(alpha = 0.6f), modifier = Modifier.size(14.dp))
                                    }
                                }
                            }
                        }
                    }
                    task.storage?.takeIf { it.isNotEmpty() }?.let {
                        Text(it, style = Theme.subtitle, color = Theme.muted)
                    }
                }
            }
        }
    }
}

@Composable
private fun ReasonChip(text: String, on: Boolean, onClick: () -> Unit) {
    Box(
        Modifier.heightIn(min = 44.dp).clip(CircleShape).background(if (on) Theme.ink else Theme.surface)
            .border(1.dp, if (on) Theme.ink else Theme.line, CircleShape).clickable(onClick = onClick).padding(horizontal = 14.dp),
        contentAlignment = Alignment.Center,
    ) { Text(text, style = Theme.chipLabel, color = if (on) Theme.surface else Theme.ink) }
}

@Composable
private fun MissingButton(onClick: () -> Unit) {
    Row(
        Modifier.padding(top = 8.dp).fillMaxWidth().heightIn(min = 44.dp).dashedBorder(Theme.dash, 16.dp, 1.5.dp, 5f, 4f)
            .clip(RoundedCornerShape(16.dp)).clickable(onClick = onClick).padding(16.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Icon(Icons.Outlined.AddCircleOutline, null, tint = Theme.accent, modifier = Modifier.size(24.dp))
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(Copy.text("ui.missing.a.prep.step"), style = Theme.action, color = Theme.accent)
            Text(Copy.text("ui.pick.a.step.from.this"), style = Theme.subtitle, color = Theme.muted)
        }
    }
}

/** "Missing a prep step?": pick the meal, then the step that should have been prep, optionally say why. */
@Composable
private fun MissingPrepSheet() {
    val store = LocalStore.current
    val dismiss = LocalDismiss.current
    val scope = rememberCoroutineScope()
    var meals by remember { mutableStateOf<List<MissingPrepMeal>?>(null) }
    var failed by remember { mutableStateOf(false) }
    var mealId by remember { mutableStateOf<Int?>(null) }
    var stepKey by remember { mutableStateOf<String?>(null) }
    var note by remember { mutableStateOf("") }
    var saving by remember { mutableStateOf(false) }
    var added by remember { mutableStateOf<Pair<String, String>?>(null) }

    suspend fun load() {
        failed = false
        meals = store.loadMissingPrep()
        failed = meals == null
    }
    LaunchedEffect(Unit) { load() }
    val meal = meals?.firstOrNull { it.id == mealId }
    val step = meal?.steps?.firstOrNull { it.key == stepKey }

    fun save(m: MissingPrepMeal, s: MissingPrepStep, adding: Boolean) {
        saving = true
        scope.launch {
            val text = if (adding) note.trim() else ""
            if (store.setMissingPrep(m.id, s.key, text, adding)) {
                meals = meals?.map { mm -> if (mm.id != m.id) mm else mm.copy(steps = mm.steps.map { if (it.key == s.key) it.copy(added = adding, note = text) else it }) }
                if (adding) added = m.name to s.text
                stepKey = null
                note = ""
            }
            saving = false
        }
    }

    @Composable
    fun label(text: String) = Text(text.uppercase(), style = Theme.count.copy(fontWeight = FontWeight.Bold, letterSpacing = 0.8.sp), color = Theme.muted, modifier = Modifier.semantics { heading() })

    @Composable
    fun dayText(day: String?) = Text((day ?: "").uppercase(), style = Theme.count.copy(fontWeight = FontWeight.Bold, letterSpacing = 0.5.sp), color = Theme.ink, modifier = Modifier.width(36.dp))

    Column(Modifier.fillMaxSize().background(Theme.bg)) {
        Box(Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
            IconAction(Icons.Filled.Close, "Close", tint = Theme.accent) { dismiss() }
            Text(Copy.text("ui.missing.a.prep.step"), style = Theme.navTitle, color = Theme.ink, modifier = Modifier.align(Alignment.Center))
        }
        Column(Modifier.verticalScroll(rememberScrollState()).padding(horizontal = 20.dp).padding(bottom = 28.dp), verticalArrangement = Arrangement.spacedBy(18.dp)) {
            Text(
                Copy.text("ui.tell.us.a.step.that"),
                style = Theme.subtitle, color = Theme.muted,
            )
            val done = added
            val list = meals
            when {
                done != null -> Column(
                    Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(Theme.surface).border(1.dp, Theme.line, RoundedCornerShape(16.dp)).padding(20.dp),
                    horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    Box(Modifier.size(48.dp).background(Theme.coral, CircleShape), contentAlignment = Alignment.Center) { Icon(Icons.Filled.Check, null, tint = Theme.ink) }
                    Text(Copy.text("ui.added.to.your.prep"), style = Theme.tourTitle, color = Theme.ink, textAlign = TextAlign.Center)
                    Text(done.second, style = Theme.subtitle, color = Theme.ink, textAlign = TextAlign.Center)
                    Text("${done.first} · marked “Added by you”", style = Theme.subtitle, color = Theme.muted, textAlign = TextAlign.Center)
                    Row(Modifier.padding(top = 6.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        Box(
                            Modifier.weight(1f).heightIn(min = 44.dp).border(1.dp, Theme.line, CircleShape).clip(CircleShape)
                                .clickable { added = null; mealId = null; stepKey = null; note = "" },
                            contentAlignment = Alignment.Center,
                        ) { Text(Copy.text("ui.add.another"), style = Theme.action, color = Theme.ink) }
                        FilledButton("Done", Modifier.weight(1f), color = Theme.ink, textColor = Theme.surface, shape = CircleShape, minHeight = 44.dp) { dismiss() }
                    }
                }
                list != null -> if (list.isEmpty()) {
                    Text(Copy.text("ui.every.step.of.this.weeks"), style = Theme.subtitle, color = Theme.muted)
                } else {
                    // 1 · Meal: the full list until one is picked, then just that meal with Change.
                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        label("1 · Meal")
                        if (meal != null) {
                            Row(
                                Modifier.fillMaxWidth().background(Theme.pill, RoundedCornerShape(16.dp)).padding(start = 14.dp, end = 8.dp, top = 6.dp, bottom = 6.dp),
                                verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp),
                            ) {
                                dayText(meal.day)
                                Text(meal.name, style = Theme.mealName, color = Theme.ink, modifier = Modifier.weight(1f))
                                LinkButton("Change") { mealId = null; stepKey = null; note = "" }
                            }
                        } else {
                            Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(Theme.surface).border(1.dp, Theme.line, RoundedCornerShape(16.dp))) {
                                list.forEachIndexed { index, m ->
                                    if (index > 0) Hairline()
                                    Row(
                                        Modifier.fillMaxWidth().heightIn(min = 64.dp).clickable { mealId = m.id; stepKey = null; note = "" }.padding(horizontal = 14.dp, vertical = 12.dp),
                                        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp),
                                    ) {
                                        dayText(m.day)
                                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                            Text(m.name, style = Theme.mealName, color = Theme.ink)
                                            Text(if (m.steps.size == 1) "1 step not in prep" else "${m.steps.size} steps not in prep", style = Theme.subtitle, color = Theme.muted)
                                        }
                                        Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, null, tint = Theme.muted)
                                    }
                                }
                            }
                        }
                    }
                    if (meal != null) {
                        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            label("2 · Step that should be prep")
                            for (s in meal.steps) {
                                if (s.added) {
                                    // Already added: no radio, just a way to take it back.
                                    Row(
                                        Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).background(Theme.surface).border(1.dp, Theme.line, RoundedCornerShape(14.dp)).padding(14.dp),
                                        horizontalArrangement = Arrangement.spacedBy(12.dp),
                                    ) {
                                        Icon(Icons.Filled.CheckCircle, null, tint = Theme.ink, modifier = Modifier.size(22.dp))
                                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                                            Text("Step ${s.step} · in your prep", style = Theme.subtitle, color = Theme.muted)
                                            Text(s.text, style = Theme.stepText, color = Theme.ink)
                                            LinkButton(Copy.text("ui.remove.from.prep"), enabled = !saving, style = Theme.count.copy(fontWeight = FontWeight.SemiBold)) { save(meal, s, adding = false) }
                                        }
                                    }
                                } else {
                                    val on = s.key == stepKey
                                    Row(
                                        Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).background(if (on) Theme.pill else Theme.surface)
                                            .border(if (on) 1.5.dp else 1.dp, if (on) Theme.ink else Theme.line, RoundedCornerShape(14.dp))
                                            .clickable { stepKey = s.key }.padding(14.dp),
                                        horizontalArrangement = Arrangement.spacedBy(12.dp),
                                    ) {
                                        Icon(if (on) Icons.Filled.RadioButtonChecked else Icons.Outlined.RadioButtonUnchecked, null, tint = if (on) Theme.ink else Theme.muted, modifier = Modifier.size(22.dp))
                                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                                            Text("Step ${s.step}", style = Theme.subtitle, color = Theme.muted)
                                            Text(s.text, style = Theme.stepText, color = Theme.ink)
                                        }
                                    }
                                }
                            }
                        }
                    }
                    if (meal != null && step != null) {
                        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                            label("3 · Why do it ahead? (optional)")
                            TextBox(note, { note = it }, "e.g. Tofu needs 15 min to press — no time on a weeknight", style = Theme.subtitle, minLines = 2, maxLines = 5, contentDescription = Copy.text("ui.why.do.it.ahead.optional"))
                            FilledButton(if (saving) "Adding…" else Copy.text("ui.add.to.prep"), enabled = !saving, color = Theme.ink, textColor = Theme.surface, shape = CircleShape) { save(meal, step, adding = true) }
                        }
                    }
                }
                failed -> Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text(Copy.text("ui.couldnt.load.the.recipes"), style = Theme.subtitle, color = Theme.muted)
                    LinkButton(Copy.text("ui.try.again")) { scope.launch { load() } }
                }
                else -> Spinner(Modifier.heightIn(min = 120.dp))
            }
        }
    }
}
