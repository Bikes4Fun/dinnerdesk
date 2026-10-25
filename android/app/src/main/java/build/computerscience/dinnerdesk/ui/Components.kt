package build.computerscience.dinnerdesk.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBackIos
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.RadioButtonChecked
import androidx.compose.material.icons.filled.Remove
import androidx.compose.material.icons.filled.ThumbDown
import androidx.compose.material.icons.filled.ThumbUp
import androidx.compose.material.icons.outlined.AutoAwesome
import androidx.compose.material.icons.outlined.Image
import androidx.compose.material.icons.outlined.RadioButtonUnchecked
import androidx.compose.material.icons.outlined.Restaurant
import androidx.compose.material.icons.outlined.ThumbDown
import androidx.compose.material.icons.outlined.ThumbUp
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.SheetState
import androidx.compose.material3.SwipeToDismissBox
import androidx.compose.material3.SwipeToDismissBoxValue
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.material3.rememberSwipeToDismissBoxState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import build.computerscience.dinnerdesk.data.Api
import build.computerscience.dinnerdesk.data.Copy
import coil.compose.SubcomposeAsyncImage
import kotlinx.coroutines.launch

// Shared building blocks. Each mirrors a SwiftUI view of the same name in ios/dinnerdesk.

@Composable
fun Hairline(modifier: Modifier = Modifier, start: Dp = 0.dp) {
    Box(modifier.padding(start = start).fillMaxWidth().height(1.dp).background(Theme.line))
}

@Composable
fun ErrorBanner(message: String, modifier: Modifier = Modifier) {
    Text(
        message, style = Theme.subtitle, color = Theme.errorText,
        modifier = modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp)).background(Theme.errorBg)
            .padding(horizontal = 14.dp, vertical = 11.dp),
    )
}

@Composable
fun EmptyState(title: String, message: String, icon: ImageVector = Icons.Outlined.Restaurant, modifier: Modifier = Modifier) {
    Column(
        modifier.fillMaxWidth().padding(vertical = 28.dp, horizontal = 20.dp),
        horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Icon(icon, null, tint = Theme.accent, modifier = Modifier.size(34.dp))
        Text(title, style = Theme.mealName, color = Theme.ink, textAlign = TextAlign.Center)
        Text(message, style = Theme.subtitle, color = Theme.muted, textAlign = TextAlign.Center)
    }
}

/** A tip: help text with a purple sparkle on a pale purple card, beside what it explains. */
@Composable
fun StarTip(id: String, modifier: Modifier = Modifier) {
    Row(
        modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).background(Theme.aubergineTint)
            .padding(horizontal = 14.dp, vertical = 10.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Icon(Icons.Outlined.AutoAwesome, null, tint = Theme.star, modifier = Modifier.padding(top = 2.dp).size(14.dp))
        Text(Copy.text(id), style = Theme.subtitle, color = Theme.ink)
    }
}

/** Small grey all-caps section header, like PRODUCE on the grocery list. */
@Composable
fun ThemeHeader(text: String, modifier: Modifier = Modifier) {
    Text(
        text.uppercase(), style = Theme.sectionHeader.copy(letterSpacing = 0.8.sp), color = Theme.muted.copy(alpha = 0.85f),
        modifier = modifier.padding(top = 6.dp).semantics { heading() },
    )
}

/** Section header inside a themed list. */
@Composable
fun ListHeader(text: String) {
    ThemeHeader(text, Modifier.padding(start = 20.dp, end = 20.dp, top = 18.dp, bottom = 4.dp))
}

/** Grey outline icon, bold label, optional grey value on the right. */
@Composable
fun ThemeIconRow(title: String, icon: ImageVector, value: String? = null) {
    if (isAccessibilitySize) {
        Row(Modifier.heightIn(min = 44.dp), horizontalArrangement = Arrangement.spacedBy(14.dp)) {
            Icon(icon, null, tint = Theme.muted, modifier = Modifier.padding(top = 6.dp).size(24.dp))
            Column(Modifier.weight(1f)) {
                Text(title, style = Theme.mealName, color = Theme.ink)
                if (value != null) Text(value, style = Theme.body, color = Theme.muted)
            }
        }
    } else {
        Row(Modifier.heightIn(min = 44.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
            Icon(icon, null, tint = Theme.muted, modifier = Modifier.width(26.dp).size(22.dp))
            Text(title, style = Theme.mealName, color = Theme.ink, modifier = Modifier.weight(1f))
            if (value != null) Text(value, style = Theme.body, color = Theme.muted, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
    }
}

/** A row in a themed list: 56 high, hairline under it, chevron when it opens another screen. */
@Composable
fun ListRow(
    onClick: (() -> Unit)? = null,
    chevron: Boolean = onClick != null,
    divider: Boolean = true,
    padding: PaddingValues = PaddingValues(horizontal = 20.dp, vertical = 6.dp),
    background: Color = Theme.bg,
    content: @Composable RowScope.() -> Unit,
) {
    Column(Modifier.fillMaxWidth().background(background)) {
        Row(
            Modifier.fillMaxWidth().heightIn(min = 56.dp)
                .then(if (onClick != null) Modifier.clickable(onClick = onClick) else Modifier)
                .padding(padding),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Row(Modifier.weight(1f), verticalAlignment = Alignment.CenterVertically) { content() }
            if (chevron) Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, null, tint = Theme.muted.copy(alpha = 0.6f), modifier = Modifier.padding(start = 8.dp).size(20.dp))
        }
        if (divider) Hairline(start = 20.dp)
    }
}

/** "+ Add item" row in the accent color. */
@Composable
fun ThemeAddRow(title: String, enabled: Boolean = true, onClick: () -> Unit) {
    ListRow(onClick = if (enabled) onClick else null, chevron = false) {
        Row(Modifier.alpha(if (enabled) 1f else 0.45f), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Icon(Icons.Filled.Add, null, tint = Theme.accent, modifier = Modifier.size(22.dp))
            Text(title, style = Theme.mealName, color = Theme.accent)
        }
    }
}

/** Plain themed list page with pull-to-refresh. */
@Composable
fun ThemeList(onRefresh: (suspend () -> Unit)? = null, content: @Composable ColumnScope.() -> Unit) {
    RefreshBox(onRefresh) {
        Column(Modifier.fillMaxSize().background(Theme.bg).verticalScroll(rememberScrollState()).padding(bottom = 24.dp)) { content() }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RefreshBox(onRefresh: (suspend () -> Unit)?, modifier: Modifier = Modifier, content: @Composable BoxScope.() -> Unit) {
    if (onRefresh == null) {
        Box(modifier.fillMaxSize(), content = content)
        return
    }
    var refreshing by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    PullToRefreshBox(
        isRefreshing = refreshing,
        onRefresh = { scope.launch { refreshing = true; try { onRefresh() } finally { refreshing = false } } },
        modifier = modifier.fillMaxSize(),
        content = content,
    )
}

/** A navigation bar: back chevron, inline title, trailing actions. */
@Composable
fun NavBar(
    title: String? = null,
    back: Boolean = LocalNav.current.canPop,
    leading: (@Composable RowScope.() -> Unit)? = null,
    actions: @Composable RowScope.() -> Unit = {},
) {
    val nav = LocalNav.current
    Box(Modifier.fillMaxWidth().background(Theme.bg).heightIn(min = 48.dp).padding(horizontal = 4.dp)) {
        Row(Modifier.align(Alignment.CenterStart), verticalAlignment = Alignment.CenterVertically) {
            if (leading != null) leading()
            else if (back) {
                Row(
                    Modifier.heightIn(min = 44.dp).clip(RoundedCornerShape(8.dp)).clickable { nav.pop() }.padding(horizontal = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(Icons.AutoMirrored.Filled.ArrowBackIos, "Back", tint = Theme.accent, modifier = Modifier.size(20.dp))
                }
            }
        }
        if (title != null) {
            Text(
                title, style = Theme.navTitle, color = Theme.ink, maxLines = 1, overflow = TextOverflow.Ellipsis,
                modifier = Modifier.align(Alignment.Center).padding(horizontal = 96.dp).semantics { heading() },
            )
        }
        Row(Modifier.align(Alignment.CenterEnd), verticalAlignment = Alignment.CenterVertically) { actions() }
    }
}

/** Fraunces large title at the top of a screen's content. */
@Composable
fun LargeTitle(text: String, modifier: Modifier = Modifier) {
    Text(text, style = Theme.bigTitle, color = Theme.ink, modifier = modifier.padding(horizontal = 16.dp).padding(top = 4.dp, bottom = 8.dp).semantics { heading() })
}

/** A text button in the accent color (iOS bar buttons and links). */
@Composable
fun LinkButton(
    text: String, modifier: Modifier = Modifier, enabled: Boolean = true, color: Color = Theme.accent,
    style: TextStyle = Theme.action, onClick: () -> Unit,
) {
    Box(
        modifier.heightIn(min = 44.dp).clip(RoundedCornerShape(8.dp)).clickable(enabled = enabled, onClick = onClick).padding(horizontal = 10.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(text, style = style, color = if (enabled) color else color.copy(alpha = 0.4f))
    }
}

@Composable
fun IconAction(icon: ImageVector, label: String, tint: Color = Theme.accent, size: Dp = 24.dp, enabled: Boolean = true, onClick: () -> Unit) {
    Box(
        Modifier.size(44.dp).clip(CircleShape).clickable(enabled = enabled, role = Role.Button, onClick = onClick).semantics { contentDescription = label },
        contentAlignment = Alignment.Center,
    ) {
        Icon(icon, null, tint = if (enabled) tint else tint.copy(alpha = 0.4f), modifier = Modifier.size(size))
    }
}

/** One appearance and label for every suggestion entry point. */
@Composable
fun CreateMealPlanButton(modifier: Modifier = Modifier, onClick: () -> Unit) {
    Row(
        modifier.heightIn(min = 44.dp).clip(CircleShape).background(Theme.accent).clickable(onClick = onClick)
            .padding(horizontal = 20.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Icon(Icons.Outlined.AutoAwesome, null, tint = Color.White, modifier = Modifier.size(18.dp))
        Text(CREATE_MEAL_PLAN, style = Theme.body, color = Color.White, textAlign = TextAlign.Center)
    }
}

const val CREATE_MEAL_PLAN = "New meal plan"

@Composable
fun RecipeCardName(name: String, modifier: Modifier = Modifier, lineLimit: Int? = null, reservesSpace: Boolean = false) {
    Text(
        name, style = Theme.recipeCardName, color = Theme.ink,
        maxLines = lineLimit ?: Int.MAX_VALUE, minLines = if (reservesSpace && lineLimit != null) lineLimit else 1,
        overflow = TextOverflow.Ellipsis, modifier = modifier.fillMaxWidth(),
    )
}

@Composable
fun RecipeCardServings(servings: Int) {
    Text("$servings servings", style = Theme.recipeCardServing, color = Theme.muted)
}

/** Square photo from the server, cached in memory and on disk (Coil), grey photo icon while loading. */
@Composable
fun RecipePhoto(
    path: String?, modifier: Modifier = Modifier, large: Boolean = false, fill: Boolean = false,
    hideUnavailable: Boolean = false, corner: Dp = if (large) 16.dp else 8.dp,
) {
    val url = Api.photoUrl(path)
    if (hideUnavailable && url == null) return
    var failed by remember(url) { mutableStateOf(false) }
    if (hideUnavailable && failed) return
    val base = if (fill || large) modifier.fillMaxWidth() else modifier.size(56.dp)
    Box(base.aspectRatio(1f).clip(RoundedCornerShape(corner)).background(Theme.line)) {
        if (url != null) {
            SubcomposeAsyncImage(
                model = url, contentDescription = null, contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxSize(),
                loading = { PhotoPlaceholder(large) },
                error = { failed = true; PhotoPlaceholder(large) },
            )
        } else {
            PhotoPlaceholder(large)
        }
    }
}

@Composable
private fun PhotoPlaceholder(large: Boolean) {
    Box(Modifier.fillMaxSize().background(Theme.line), contentAlignment = Alignment.Center) {
        Icon(Icons.Outlined.Image, null, tint = Theme.muted, modifier = Modifier.size(if (large) 28.dp else 20.dp))
    }
}

/** Thumbs up / down. `rating` is 1, -1 or 0; tapping the lit thumb again clears it. */
@Composable
fun ThumbsControl(rating: Int, subject: String, size: Dp = 19.dp, onRate: (Int) -> Unit) {
    Row {
        for (up in listOf(true, false)) {
            val value = if (up) 1 else -1
            val on = rating == value
            val icon = when {
                up && on -> Icons.Filled.ThumbUp
                up -> Icons.Outlined.ThumbUp
                on -> Icons.Filled.ThumbDown
                else -> Icons.Outlined.ThumbDown
            }
            Box(
                Modifier.size(width = 44.dp, height = 36.dp).clickable(role = Role.Button) { onRate(if (on) 0 else value) }
                    .semantics { contentDescription = if (up) "Like $subject" else "Dislike $subject"; selected = on },
                contentAlignment = Alignment.Center,
            ) {
                Icon(icon, null, tint = if (on) (if (up) Theme.ink else Theme.accent) else Theme.muted, modifier = Modifier.size(size))
            }
        }
    }
}

/** Capsule chip: accent when on, pale tint when off (Recipes and Grocery filters). */
@Composable
fun Chip(title: String, on: Boolean, onClick: () -> Unit) {
    Text(
        title, style = Theme.chipLabel, color = if (on) Color.White else Theme.ink,
        modifier = Modifier.clip(CircleShape).background(if (on) Theme.accent else Theme.chip).clickable(onClick = onClick)
            .semantics { selected = on }.padding(horizontal = 12.dp, vertical = 7.dp),
    )
}

/** Shared preference chip: pale tint, filled coral when on. Tour and Filters both use this. */
@Composable
fun FilterChip(label: String, on: Boolean, onClick: () -> Unit) {
    Box(
        Modifier.heightIn(min = 40.dp).clip(CircleShape).background(if (on) Theme.accent else Theme.aubergineTint).clickable(onClick = onClick)
            .semantics { selected = on }.padding(horizontal = 13.dp, vertical = 9.dp),
        contentAlignment = Alignment.CenterStart,
    ) {
        Text(label, style = Theme.chipLabel, color = if (on) Color.White else Theme.ink)
    }
}

/** Rounded chip used by the grocery-store page. `count` shows a grey number after the text. */
@Composable
fun KitchenChip(text: String, count: Int?, selected: Boolean, dashed: Boolean = false, onClick: () -> Unit) {
    val shape = CircleShape
    Row(
        Modifier.heightIn(min = 36.dp).clip(shape)
            .background(if (selected) Theme.accent else if (dashed) Color.Transparent else Theme.chip)
            .then(if (dashed) Modifier.dashedBorder(Theme.accent.copy(alpha = 0.6f), 18.dp) else Modifier)
            .clickable(onClick = onClick).padding(horizontal = 14.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Text(text, style = Theme.chipLabel, color = if (selected) Color.White else if (dashed) Theme.accent else Theme.ink, maxLines = 1)
        if (count != null) Text("$count", style = Theme.count, color = if (selected) Color.White.copy(alpha = 0.8f) else Theme.muted)
    }
}

fun Modifier.dashedBorder(color: Color, radius: Dp, width: Dp = 1.dp, dash: Float = 4f, gap: Float = 3f): Modifier = drawBehind {
    val stroke = Stroke(width = width.toPx(), pathEffect = PathEffect.dashPathEffect(floatArrayOf(dash * density, gap * density)))
    drawRoundRect(color = color, style = stroke, cornerRadius = CornerRadius(radius.toPx()))
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun Flow(spacing: Dp = 8.dp, modifier: Modifier = Modifier, content: @Composable () -> Unit) {
    FlowRow(
        modifier, horizontalArrangement = Arrangement.spacedBy(spacing), verticalArrangement = Arrangement.spacedBy(spacing),
    ) { content() }
}

/** iOS-style segmented control: grey track, white selected segment. */
@Composable
fun <T> Segmented(options: List<Pair<T, String>>, current: T, modifier: Modifier = Modifier, onSelect: (T) -> Unit) {
    Row(modifier.fillMaxWidth().clip(RoundedCornerShape(9.dp)).background(Color(0x1F767680)).padding(2.dp)) {
        for ((value, label) in options) {
            val on = value == current
            Box(
                Modifier.weight(1f).heightIn(min = 32.dp)
                    .then(if (on) Modifier.shadow(1.dp, RoundedCornerShape(7.dp)).background(Color.White, RoundedCornerShape(7.dp)) else Modifier)
                    .clip(RoundedCornerShape(7.dp)).clickable { onSelect(value) }.semantics { selected = on }.padding(horizontal = 6.dp, vertical = 6.dp),
                contentAlignment = Alignment.Center,
            ) {
                Text(label, style = Theme.subtitle.copy(fontWeight = if (on) androidx.compose.ui.text.font.FontWeight.SemiBold else androidx.compose.ui.text.font.FontWeight.Medium), color = Theme.ink, textAlign = TextAlign.Center)
            }
        }
    }
}

/** − / + stepper in one rounded box. */
@Composable
fun Stepper(value: Int, range: IntRange, label: String, onChange: (Int) -> Unit) {
    Row(
        Modifier.clip(RoundedCornerShape(8.dp)).background(Color(0x1F767680)),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        IconAction(Icons.Filled.Remove, "Decrease $label", tint = Theme.ink, size = 20.dp, enabled = value > range.first) { onChange(value - 1) }
        Box(Modifier.width(1.dp).height(18.dp).background(Theme.muted.copy(alpha = 0.3f)))
        IconAction(Icons.Filled.Add, "Increase $label", tint = Theme.ink, size = 20.dp, enabled = value < range.last) { onChange(value + 1) }
    }
}

@Composable
fun ThemeSwitch(checked: Boolean, onChange: (Boolean) -> Unit) {
    Switch(
        checked, onChange,
        colors = SwitchDefaults.colors(
            checkedThumbColor = Color.White, checkedTrackColor = Theme.accent, checkedBorderColor = Theme.accent,
            uncheckedThumbColor = Color.White, uncheckedTrackColor = Color(0xFFE9E9EA), uncheckedBorderColor = Color(0xFFE9E9EA),
        ),
    )
}

/** Label on the left, switch on the right. */
@Composable
fun SwitchRow(label: String, checked: Boolean, style: TextStyle = Theme.rowTitle, divider: Boolean = true, onChange: (Boolean) -> Unit) {
    ListRow(onClick = { onChange(!checked) }, chevron = false, divider = divider) {
        Text(label, style = style, color = Theme.ink, modifier = Modifier.weight(1f))
        ThemeSwitch(checked, onChange)
    }
}

/** Full-width filled button: ink by default (Approve plan, Send report). */
@Composable
fun FilledButton(
    text: String, modifier: Modifier = Modifier, enabled: Boolean = true, color: Color = Theme.ink, textColor: Color = Theme.bg,
    shape: Shape = RoundedCornerShape(14.dp), minHeight: Dp = 50.dp, onClick: () -> Unit,
) {
    Box(
        modifier.fillMaxWidth().heightIn(min = minHeight).clip(shape).background(if (enabled) color else Theme.muted)
            .clickable(enabled = enabled, onClick = onClick).padding(horizontal = 12.dp),
        contentAlignment = Alignment.Center,
    ) { Text(text, style = Theme.action, color = textColor, textAlign = TextAlign.Center) }
}

/** Full-width outlined button: surface with a hairline border. */
@Composable
fun OutlinedButton(text: String, modifier: Modifier = Modifier, enabled: Boolean = true, shape: Shape = RoundedCornerShape(14.dp), minHeight: Dp = 50.dp, onClick: () -> Unit) {
    Box(
        modifier.fillMaxWidth().heightIn(min = minHeight).clip(shape).background(Theme.surface).border(1.5.dp, Theme.line, shape)
            .clickable(enabled = enabled, onClick = onClick).padding(horizontal = 12.dp),
        contentAlignment = Alignment.Center,
    ) { Text(text, style = Theme.action, color = Theme.ink, textAlign = TextAlign.Center) }
}

/** Capsule prominent button in the accent color (tour, sign in). */
@Composable
fun AccentButton(text: String, modifier: Modifier = Modifier, enabled: Boolean = true, busy: Boolean = false, onClick: () -> Unit) {
    Box(
        modifier.fillMaxWidth().heightIn(min = 50.dp).clip(CircleShape).background(if (enabled) Theme.accent else Theme.accent.copy(alpha = 0.4f))
            .clickable(enabled = enabled && !busy, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        if (busy) CircularProgressIndicator(color = Color.White, strokeWidth = 2.dp, modifier = Modifier.size(22.dp))
        else Text(text, style = Theme.action, color = Color.White)
    }
}

/** Rounded text box on the surface color with a hairline border. */
@Composable
fun TextBox(
    value: String, onChange: (String) -> Unit, placeholder: String, modifier: Modifier = Modifier,
    style: TextStyle = Theme.body, minLines: Int = 1, maxLines: Int = if (minLines > 1) 8 else 1,
    keyboard: KeyboardOptions = KeyboardOptions.Default, actions: KeyboardActions = KeyboardActions.Default,
    password: Boolean = false, corner: Dp = 12.dp, background: Color = Theme.surface, border: Color = Theme.line,
    contentDescription: String? = null, leading: (@Composable () -> Unit)? = null, trailing: (@Composable () -> Unit)? = null,
) {
    BasicTextField(
        value = value, onValueChange = onChange, textStyle = style.copy(color = Theme.ink),
        minLines = minLines, maxLines = maxLines, singleLine = maxLines == 1,
        keyboardOptions = keyboard, keyboardActions = actions,
        visualTransformation = if (password) PasswordVisualTransformation() else VisualTransformation.None,
        cursorBrush = SolidColor(Theme.accent),
        modifier = modifier.fillMaxWidth().then(if (contentDescription != null) Modifier.semantics { this.contentDescription = contentDescription } else Modifier),
        decorationBox = { inner ->
            Row(
                Modifier.clip(RoundedCornerShape(corner)).background(background).border(1.dp, border, RoundedCornerShape(corner))
                    .heightIn(min = 44.dp).padding(start = if (leading != null) 12.dp else 12.dp, end = if (trailing != null) 0.dp else 12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                if (leading != null) { leading(); Spacer(Modifier.width(8.dp)) }
                Box(Modifier.weight(1f).padding(vertical = 12.dp)) {
                    if (value.isEmpty()) Text(placeholder, style = style, color = Theme.muted.copy(alpha = 0.7f))
                    inner()
                }
                if (trailing != null) trailing()
            }
        },
    )
}

/** A form field row: grey placeholder, no box (iOS Form text field). */
@Composable
fun FormField(
    value: String, onChange: (String) -> Unit, placeholder: String, keyboard: KeyboardOptions = KeyboardOptions.Default,
    password: Boolean = false, minLines: Int = 1, actions: KeyboardActions = KeyboardActions.Default, modifier: Modifier = Modifier,
) {
    BasicTextField(
        value = value, onValueChange = onChange, textStyle = Theme.body.copy(color = Theme.ink),
        minLines = minLines, maxLines = if (minLines > 1) 30 else 1, singleLine = minLines == 1,
        keyboardOptions = keyboard, keyboardActions = actions, cursorBrush = SolidColor(Theme.accent),
        visualTransformation = if (password) PasswordVisualTransformation() else VisualTransformation.None,
        modifier = modifier.fillMaxWidth(),
        decorationBox = { inner ->
            Box(Modifier.heightIn(min = 44.dp).padding(vertical = 11.dp), contentAlignment = Alignment.CenterStart) {
                if (value.isEmpty()) Text(placeholder, style = Theme.body, color = Theme.muted.copy(alpha = 0.6f))
                inner()
            }
        },
    )
}

/** A grouped form card (iOS inset grouped Form section). */
@Composable
fun FormSection(
    header: String? = null, footer: (@Composable () -> Unit)? = null, background: Color = Theme.surface,
    content: @Composable ColumnScope.() -> Unit,
) {
    Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp)) {
        if (header != null) Text(header.uppercase(), style = Theme.subtitle, color = Theme.muted, modifier = Modifier.padding(start = 16.dp, bottom = 6.dp))
        Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp)).background(background).padding(horizontal = 16.dp), content = content)
        if (footer != null) {
            Box(Modifier.padding(start = 16.dp, end = 16.dp, top = 6.dp)) {
                CompositionLocalProvider(androidx.compose.material3.LocalTextStyle provides Theme.subtitle, androidx.compose.material3.LocalContentColor provides Theme.muted) { footer() }
            }
        }
    }
}

@Composable
fun Muted(text: String, modifier: Modifier = Modifier, style: TextStyle = Theme.subtitle) {
    Text(text, style = style, color = Theme.muted, modifier = modifier)
}

/** Round check: filled accent when on. */
@Composable
fun CheckCircle(checked: Boolean, size: Dp = 24.dp, color: Color = Theme.accent) {
    Icon(
        if (checked) Icons.Filled.CheckCircle else Icons.Outlined.RadioButtonUnchecked, null,
        tint = if (checked) color else Theme.muted, modifier = Modifier.size(size),
    )
}

/** Swipe left to delete, like `.onDelete` in a SwiftUI list. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SwipeToDelete(key: Any, enabled: Boolean = true, onDelete: () -> Unit, content: @Composable () -> Unit) {
    if (!enabled) { content(); return }
    val state = rememberSwipeToDismissBoxState(confirmValueChange = {
        if (it == SwipeToDismissBoxValue.EndToStart) { onDelete(); true } else false
    })
    SwipeToDismissBox(
        state = state, enableDismissFromStartToEnd = false,
        backgroundContent = {
            Box(Modifier.fillMaxSize().background(Theme.destructive).padding(end = 20.dp), contentAlignment = Alignment.CenterEnd) {
                Text("Delete", style = Theme.action, color = Color.White)
            }
        },
    ) { content() }
}

@OptIn(ExperimentalMaterial3Api::class)
class SheetController(val state: SheetState, private val launch: (suspend () -> Unit) -> Unit, private val onDismiss: () -> Unit) {
    fun dismiss() = launch { state.hide(); onDismiss() }
}

/**
 * A sheet that slides up over the screen (SwiftUI `.sheet`). `LocalDismiss` inside closes it.
 * Pass `nav` content with NavStack for sheets that push their own screens.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun Sheet(onDismiss: () -> Unit, full: Boolean = true, background: Color = Theme.bg, content: @Composable ColumnScope.() -> Unit) {
    val state = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    val scope = rememberCoroutineScope()
    val controller = remember(state) { SheetController(state, { block -> scope.launch { block() } }, onDismiss) }
    ModalBottomSheet(
        onDismissRequest = onDismiss, sheetState = state, containerColor = background,
        shape = RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp),
        dragHandle = { Box(Modifier.padding(top = 6.dp, bottom = 2.dp).size(width = 36.dp, height = 5.dp).clip(CircleShape).background(Theme.muted.copy(alpha = 0.35f))) },
    ) {
        CompositionLocalProvider(LocalDismiss provides { controller.dismiss() }) {
            Column(
                (if (full) Modifier.fillMaxHeight() else Modifier).fillMaxWidth().imePadding().navigationBarsPadding(),
                content = content,
            )
        }
    }
}

/** The bar across a sheet's top: Cancel on the left, the title, a confirm action on the right. */
@Composable
fun SheetBar(
    title: String, cancel: String? = "Cancel", onCancel: (() -> Unit)? = null,
    confirm: String? = null, confirmEnabled: Boolean = true, onConfirm: (() -> Unit)? = null,
) {
    val dismiss = LocalDismiss.current
    Box(Modifier.fillMaxWidth().heightIn(min = 48.dp).padding(horizontal = 6.dp)) {
        if (cancel != null) LinkButton(cancel, Modifier.align(Alignment.CenterStart), style = Theme.body) { (onCancel ?: dismiss)() }
        Text(title, style = Theme.navTitle, color = Theme.ink, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.align(Alignment.Center).padding(horizontal = 90.dp))
        if (confirm != null && onConfirm != null) LinkButton(confirm, Modifier.align(Alignment.CenterEnd), enabled = confirmEnabled, onClick = onConfirm)
    }
}

/** One row in a ⋯ menu sheet. */
data class MenuItem(
    val title: String,
    val icon: ImageVector,
    val destructive: Boolean = false,
    val dismissOnSelection: Boolean = true,
    val isOn: Boolean? = null,
    val status: String? = null,
    val createsMealPlan: Boolean = false,
    val action: () -> Unit,
)

/** Reusable ⋯ menu: a short bottom sheet of outline-icon rows with hairlines and a round × to close. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MenuSheet(onDismiss: () -> Unit, items: List<MenuItem>) {
    val state = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    val scope = rememberCoroutineScope()
    // The tapped row's action runs after the sheet is gone, so it can push screens or open other sheets.
    fun pick(item: MenuItem) {
        if (item.dismissOnSelection) scope.launch { state.hide(); onDismiss(); item.action() } else item.action()
    }
    ModalBottomSheet(
        onDismissRequest = onDismiss, sheetState = state, containerColor = Theme.surface,
        shape = RoundedCornerShape(topStart = 24.dp, topEnd = 24.dp), dragHandle = null,
    ) {
        Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).navigationBarsPadding().padding(bottom = 8.dp)) {
            Row(Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, top = 14.dp, bottom = 6.dp), horizontalArrangement = Arrangement.End) {
                Box(
                    Modifier.size(32.dp).clip(CircleShape).background(Theme.chip).clickable { scope.launch { state.hide(); onDismiss() } }
                        .semantics { contentDescription = "Close" },
                    contentAlignment = Alignment.Center,
                ) { Icon(Icons.Filled.Close, null, tint = Theme.muted, modifier = Modifier.size(16.dp)) }
            }
            items.forEachIndexed { index, item ->
                if (item.createsMealPlan) {
                    CreateMealPlanButton(Modifier.padding(horizontal = 16.dp).padding(bottom = 8.dp)) { pick(item) }
                } else {
                    Row(
                        Modifier.fillMaxWidth().heightIn(min = 60.dp).clickable { pick(item) }.padding(horizontal = 20.dp, vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(16.dp),
                    ) {
                        Icon(item.icon, null, tint = if (item.destructive) Theme.destructive else Theme.muted, modifier = Modifier.width(28.dp).size(24.dp))
                        Text(item.title, style = Theme.rowTitle, color = if (item.destructive) Theme.destructive else Theme.ink, modifier = Modifier.weight(1f))
                        item.isOn?.let { CheckCircle(it, 22.dp) }
                        item.status?.let { Text(it, style = Theme.subtitle, color = Theme.accent) }
                    }
                }
                if (index < items.size - 1 && !item.createsMealPlan) Hairline(start = 64.dp)
            }
        }
    }
}

/** An alert with one text field (SwiftUI `.alert` with a TextField). */
@Composable
fun TextFieldAlert(
    title: String, value: String, onValue: (String) -> Unit, placeholder: String, confirm: String,
    onConfirm: () -> Unit, onDismiss: () -> Unit, message: String? = null,
) {
    AlertDialog(
        onDismissRequest = onDismiss, containerColor = Theme.surface,
        title = { Text(title, style = Theme.title, color = Theme.ink) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                if (message != null) Text(message, style = Theme.body, color = Theme.muted)
                TextBox(value, onValue, placeholder)
            }
        },
        confirmButton = { TextButton(onClick = { onConfirm(); onDismiss() }) { Text(confirm, style = Theme.action, color = Theme.accent) } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel", style = Theme.body, color = Theme.accent) } },
    )
}

/** A yes/no question with a possibly destructive action (alert or confirmation dialog). */
@Composable
fun ConfirmDialog(
    title: String, confirm: String, onConfirm: () -> Unit, onDismiss: () -> Unit,
    message: String? = null, destructive: Boolean = true,
) {
    AlertDialog(
        onDismissRequest = onDismiss, containerColor = Theme.surface,
        title = { Text(title, style = Theme.title, color = Theme.ink) },
        text = message?.let { { Text(it, style = Theme.body, color = Theme.muted) } },
        confirmButton = {
            TextButton(onClick = { onConfirm(); onDismiss() }) {
                Text(confirm, style = Theme.action, color = if (destructive) Theme.destructive else Theme.accent)
            }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel", style = Theme.body, color = Theme.accent) } },
    )
}

/** A short notice in a capsule at the bottom ("Added to this plan"). */
@Composable
fun Notice(text: String, modifier: Modifier = Modifier) {
    Text(
        text, style = Theme.body, color = Theme.ink,
        modifier = modifier.padding(bottom = 16.dp).shadow(4.dp, CircleShape).background(Theme.bg, CircleShape).padding(16.dp),
    )
}

@Composable
fun Spinner(modifier: Modifier = Modifier) {
    Box(modifier.fillMaxWidth().padding(16.dp), contentAlignment = Alignment.Center) {
        CircularProgressIndicator(color = Theme.muted, strokeWidth = 2.dp, modifier = Modifier.size(24.dp))
    }
}

/** A radio row: filled ring when picked. */
@Composable
fun RadioRow(selected: Boolean, onClick: () -> Unit, content: @Composable RowScope.() -> Unit) {
    Row(
        Modifier.fillMaxWidth().heightIn(min = 44.dp).clickable(onClick = onClick).semantics { this.selected = selected },
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Icon(
            if (selected) Icons.Filled.RadioButtonChecked else Icons.Outlined.RadioButtonUnchecked,
            null, tint = if (selected) Theme.accent else Theme.muted, modifier = Modifier.size(22.dp),
        )
        content()
    }
}

/** Opens a link in the browser (or the matching app). */
@Composable
fun rememberOpenUrl(): (String) -> Unit {
    val context = LocalContext.current
    return remember(context) {
        { url ->
            if (build.computerscience.dinnerdesk.AppUrls.canOpenExternal(url)) {
                try {
                    context.startActivity(android.content.Intent(android.content.Intent.ACTION_VIEW, android.net.Uri.parse(url)).addCategory(android.content.Intent.CATEGORY_BROWSABLE))
                } catch (_: android.content.ActivityNotFoundException) {
                    android.widget.Toast.makeText(context, "No app is available to open this link.", android.widget.Toast.LENGTH_LONG).show()
                }
            }
        }
    }
}

/** The system share sheet, for plain text. */
fun shareText(context: android.content.Context, text: String, title: String? = null) {
    val send = android.content.Intent(android.content.Intent.ACTION_SEND).setType("text/plain").putExtra(android.content.Intent.EXTRA_TEXT, text)
    if (title != null) send.putExtra(android.content.Intent.EXTRA_SUBJECT, title)
    context.startActivity(android.content.Intent.createChooser(send, null))
}
