package build.computerscience.dinnerdesk.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.outlined.FavoriteBorder
import androidx.compose.material.icons.outlined.Bookmark
import androidx.compose.material.icons.outlined.BookmarkBorder
import androidx.compose.material.icons.outlined.Flag
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material.icons.outlined.Verified
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import build.computerscience.dinnerdesk.data.Copy

/**
 * Shared RecipeTile template — not wired to screens yet.
 *
 * Future callers: Plan list/grid, Recipes browse, My Recipes, suggested plan, swap,
 * Taste Lab (larger + swipe wrapper), Hidden, plan strip, grocery “used in” rows.
 *
 * Structure:
 *  1. Photo (* square crop, shared corner radius; options: size, opacity, open-on-tap)
 *  2. Overlays via RecipeTilePhotoOverlay (* standard circle; options: shown, where,
 *     interactive vs static; content inside the circle)
 *  3. Body = name (* RecipeCardName) + meta (view under|beside; named content types)
 *  4. Context menu (option): press-and-hold; Favorite / plan / To try / Hide / cooked + extras
 *
 * * = always-on default. Without * = page option.
 * REVIEW: defaults — cook time + kitchen-tested meta on with reserved height; servings off;
 *         no overlays / no context menu until a page opts in.
 * REVIEW: kitchen-tested as photo badge vs body meta — both supported.
 * Copy: feature name stays "To try" (not "To Try").
 *
 * Browse still uses BrowseRecipeTile in RecipesView until migrate.
 */

enum class RecipeTileCorner { TopLeading, TopTrailing, BottomLeading, BottomTrailing, Center }

enum class RecipeTileOverlayMode { Interactive, Static }

data class RecipeTileMenuItem(
    val id: String,
    val title: String,
    val destructive: Boolean = false,
    val action: () -> Unit,
) {
    companion object {
        fun favorite(on: Boolean, action: () -> Unit) =
            RecipeTileMenuItem("favorite", if (on) "Unfavorite" else "Favorite", action = action)
        fun plan(on: Boolean, action: () -> Unit) =
            RecipeTileMenuItem("plan", if (on) "Remove from plan" else "Add to plan", action = action)
        fun toTry(on: Boolean, action: () -> Unit) =
            RecipeTileMenuItem("toTry", if (on) "Remove from To try" else "To try", action = action)
        fun hide(on: Boolean, action: () -> Unit) =
            RecipeTileMenuItem("hide", if (on) "Unhide recipe" else "Hide recipe", destructive = !on, action = action)
        fun cooked(on: Boolean, action: () -> Unit) =
            RecipeTileMenuItem("cooked", if (on) "Mark as not cooked" else "Mark as cooked", action = action)
        fun extra(id: String, title: String, destructive: Boolean = false, action: () -> Unit) =
            RecipeTileMenuItem(id, title, destructive, action)
    }
}

data class RecipeTileMeta(
    val placement: Placement = Placement.Under,
    val showCookTime: Boolean = true,
    val showKitchenTested: Boolean = true,
    val showServings: Boolean = false,
    val showYourSelection: Boolean = false,
    val showSchedule: Boolean = false,
    val servings: Int? = null,
    val yourSelection: Boolean = false,
    val scheduleLabel: String? = null,
) {
    enum class Placement { Under, Beside }
}

/** Universal overlay chrome: * standard-size circle + hit target. */
@Composable
fun RecipeTilePhotoOverlay(
    corner: RecipeTileCorner = RecipeTileCorner.TopTrailing,
    mode: RecipeTileOverlayMode = RecipeTileOverlayMode.Interactive,
    label: String? = null,
    onClick: (() -> Unit)? = null,
    on: Boolean = false,
    content: @Composable () -> Unit,
) {
    val align = when (corner) {
        RecipeTileCorner.TopLeading -> Alignment.TopStart
        RecipeTileCorner.TopTrailing -> Alignment.TopEnd
        RecipeTileCorner.BottomLeading -> Alignment.BottomStart
        RecipeTileCorner.BottomTrailing -> Alignment.BottomEnd
        RecipeTileCorner.Center -> Alignment.Center
    }
    Box(Modifier.fillMaxSize(), contentAlignment = align) {
        val mod = Modifier
            .padding(4.dp)
            .size(44.dp)
            .semantics { if (label != null) contentDescription = label }
            .then(
                if (mode == RecipeTileOverlayMode.Interactive && onClick != null) Modifier.clickable(onClick = onClick)
                else Modifier,
            )
        Box(mod, contentAlignment = Alignment.Center) {
            Box(
                Modifier
                    .size(28.dp)
                    .shadow(2.dp, CircleShape)
                    .background(if (on) Theme.ink else Color.White, CircleShape),
                contentAlignment = Alignment.Center,
            ) { content() }
        }
    }
}

@Composable
fun RecipeTileAddButton(onPlan: Boolean, onClick: () -> Unit, corner: RecipeTileCorner = RecipeTileCorner.TopTrailing) {
    RecipeTilePhotoOverlay(
        corner = corner, mode = RecipeTileOverlayMode.Interactive,
        label = if (onPlan) "Remove from this plan" else "Add to this plan",
        onClick = onClick, on = onPlan,
    ) {
        Icon(
            if (onPlan) Icons.Filled.Check else Icons.Filled.Add, null,
            tint = if (onPlan) Theme.surface else Theme.ink, modifier = Modifier.size(16.dp),
        )
    }
}

@Composable
fun RecipeTileHeartButton(on: Boolean, onClick: () -> Unit, corner: RecipeTileCorner = RecipeTileCorner.TopLeading) {
    RecipeTilePhotoOverlay(
        corner = corner, mode = RecipeTileOverlayMode.Interactive,
        label = if (on) "Remove from your favorites" else "Save to your favorites",
        onClick = onClick,
    ) {
        Icon(
            if (on) Icons.Filled.Favorite else Icons.Outlined.FavoriteBorder, null,
            tint = if (on) Color(0xFFE11D48) else Theme.muted, modifier = Modifier.size(16.dp),
        )
    }
}

@Composable
fun RecipeTileSwapButton(onClick: () -> Unit, enabled: Boolean = true, corner: RecipeTileCorner = RecipeTileCorner.TopTrailing) {
    RecipeTilePhotoOverlay(
        corner = corner, mode = RecipeTileOverlayMode.Interactive,
        label = "Swap meal", onClick = if (enabled) onClick else null,
    ) {
        Icon(Icons.Outlined.Refresh, null, tint = Theme.accent, modifier = Modifier.size(16.dp).alpha(if (enabled) 1f else 0.4f))
    }
}

@Composable
fun RecipeTileSaveForLaterButton(on: Boolean, onClick: () -> Unit, corner: RecipeTileCorner = RecipeTileCorner.TopLeading) {
    RecipeTilePhotoOverlay(
        corner = corner, mode = RecipeTileOverlayMode.Interactive,
        label = if (on) "Remove from To try" else "Save to To try",
        onClick = onClick,
    ) {
        Icon(
            if (on) Icons.Outlined.Bookmark else Icons.Outlined.BookmarkBorder, null,
            tint = if (on) Theme.accent else Theme.muted, modifier = Modifier.size(16.dp),
        )
    }
}

@Composable
fun RecipeTileCookedButton(on: Boolean, onClick: () -> Unit, corner: RecipeTileCorner = RecipeTileCorner.TopTrailing) {
    RecipeTilePhotoOverlay(
        corner = corner, mode = RecipeTileOverlayMode.Interactive,
        label = if (on) "Mark as not cooked" else "Mark as cooked",
        onClick = onClick, on = on,
    ) {
        Icon(Icons.Filled.Check, null, tint = if (on) Theme.surface else Theme.muted, modifier = Modifier.size(16.dp))
    }
}

@Composable
fun RecipeTileFlagButton(onClick: () -> Unit, corner: RecipeTileCorner = RecipeTileCorner.TopTrailing) {
    RecipeTilePhotoOverlay(
        corner = corner, mode = RecipeTileOverlayMode.Interactive,
        label = "Report photo", onClick = onClick,
    ) {
        Icon(Icons.Outlined.Flag, null, tint = Theme.muted, modifier = Modifier.size(16.dp))
    }
}

@Composable
fun RecipeTileKitchenTestedBadge(corner: RecipeTileCorner = RecipeTileCorner.TopLeading) {
    RecipeTilePhotoOverlay(
        corner = corner, mode = RecipeTileOverlayMode.Static,
        label = Copy.text("recipe.reviewed.description"),
    ) {
        Icon(Icons.Outlined.Verified, null, tint = Theme.ink, modifier = Modifier.size(16.dp))
    }
}

@Composable
fun RecipeTileComingSoonBadge() {
    Text("Coming soon", style = Theme.body, color = Color.White, fontWeight = FontWeight.Bold)
}

@Composable
fun RecipeTileTagBadge(label: String, corner: RecipeTileCorner = RecipeTileCorner.BottomLeading) {
    RecipeTilePhotoOverlay(corner = corner, mode = RecipeTileOverlayMode.Static, label = label) {
        Text(label, style = Theme.chipLabel, color = Theme.ink, maxLines = 1)
    }
}

@Composable
private fun RecipeTileMetaBlock(minutes: Int?, reviewed: Boolean, meta: RecipeTileMeta) {
    val statusVisible =
        (meta.showCookTime && (minutes ?: 0) > 0) || (meta.showKitchenTested && reviewed)
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(2.dp)) {
        if (meta.showCookTime || meta.showKitchenTested) {
            // * Reserved height so missing time / kitchen-tested does not shift tiles in a row.
            Box(Modifier.heightIn(min = 16.dp).alpha(if (statusVisible) 1f else 0f)) {
                RecipeStatusLine(
                    if (meta.showCookTime) minutes else null,
                    meta.showKitchenTested && reviewed,
                )
            }
        }
        if (meta.showServings) {
            Box(Modifier.heightIn(min = 16.dp).alpha(if (meta.servings != null) 1f else 0f)) {
                RecipeCardServings(meta.servings ?: 0)
            }
        }
        if (meta.showYourSelection) {
            Box(Modifier.heightIn(min = 16.dp).alpha(if (meta.yourSelection) 1f else 0f)) {
                Text("Your selection", style = Theme.subtitle, color = Theme.muted)
            }
        }
        if (meta.showSchedule) {
            Box(Modifier.heightIn(min = 16.dp).alpha(if (meta.scheduleLabel != null) 1f else 0f)) {
                Text(meta.scheduleLabel ?: "Schedule", style = Theme.subtitle, color = Theme.muted)
            }
        }
    }
}

/** Shared recipe tile. Overlays are drawn on the photo; pass empty menuItems to omit the hold menu. */
@OptIn(ExperimentalFoundationApi::class)
@Composable
fun RecipeTile(
    name: String,
    photoPath: String? = null,
    photoSide: Dp? = null,
    photoOpacity: Float = 1f,
    comingSoon: Boolean = false,
    openEnabled: Boolean = true,
    nameLineLimit: Int = 2,
    minutes: Int? = null,
    reviewed: Boolean = false,
    meta: RecipeTileMeta = RecipeTileMeta(),
    menuItems: List<RecipeTileMenuItem> = emptyList(),
    onOpen: (() -> Unit)? = null,
    overlays: @Composable () -> Unit = {},
) {
    val canOpen = openEnabled && !comingSoon
    var menu by remember { mutableStateOf(false) }

    @Composable
    fun photo() {
        val base = Modifier
            .then(if (photoSide != null) Modifier.size(photoSide) else Modifier.fillMaxWidth())
            .aspectRatio(1f)
            .clip(RoundedCornerShape(12.dp))
        Box(base) {
            Box(Modifier.fillMaxSize().alpha(if (comingSoon) minOf(photoOpacity, 0.55f) else photoOpacity)) {
                RecipePhoto(photoPath, fill = true, corner = 12.dp)
            }
            if (comingSoon) {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { RecipeTileComingSoonBadge() }
            }
            overlays()
        }
    }

    @Composable
    fun body() {
        Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            if (comingSoon) {
                Text(name, style = Theme.recipeCardServing, color = Theme.muted, maxLines = nameLineLimit)
            } else {
                RecipeCardName(name, lineLimit = nameLineLimit, reservesSpace = true)
            }
            RecipeTileMetaBlock(minutes, reviewed, meta)
        }
    }

    val rootMod = Modifier
        .fillMaxWidth()
        .then(
            if (menuItems.isNotEmpty() || canOpen) {
                Modifier.combinedClickable(
                    onClick = { if (canOpen) onOpen?.invoke() },
                    onLongClick = { if (menuItems.isNotEmpty()) menu = true },
                )
            } else Modifier,
        )

    Box {
        if (meta.placement == RecipeTileMeta.Placement.Beside) {
            Row(rootMod, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                photo()
                body()
            }
        } else {
            Column(rootMod, verticalArrangement = Arrangement.spacedBy(8.dp)) {
                photo()
                body()
            }
        }
        DropdownMenu(expanded = menu, onDismissRequest = { menu = false }, containerColor = Theme.surface) {
            for (item in menuItems) {
                DropdownMenuItem(
                    { Text(item.title, style = Theme.body, color = if (item.destructive) Theme.destructive else Theme.ink) },
                    { menu = false; item.action() },
                )
            }
        }
    }
}
