package build.computerscience.dinnerdesk.ui

import androidx.compose.foundation.text.selection.LocalTextSelectionColors
import androidx.compose.foundation.text.selection.TextSelectionColors
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import build.computerscience.dinnerdesk.R

/**
 * One look for the whole app: warm background, aubergine for dominant actions and primary text,
 * deep coral for link/text actions, and subtle tints for specialized UI states. Mirrors ios/dinnerdesk/Theme.swift.
 */
object Theme {
    val bg = Color(0xFFFFFBF6)
    val surface = Color(0xFFFFFDF9)
    val line = Color(0xFFECE2DC)
    val ink = Color(0xFF4A1646)
    val muted = Color(0xFF7A6A76)
    val accent = Color(0xFFC2462A)
    val aubergineTint = Color(0xFFF1E7EF)
    val ok = Color(0xFF3F6B4A)
    val chip = aubergineTint

    // Shared extras used by several screens.
    val coral = Color(0xFFFA7E5A)
    val coralTint = Color(0xFFFDE6DD)
    val coralInk = Color(0xFF8A3A22)
    val bodyInk = Color(0xFF2E1A2C)
    val pill = Color(0xFFF6EEF5)
    val dash = Color(0xFFDCCDD8)
    val star = Color(0xFF7A3B73)
    val destructive = Color(0xFFFF3B30)
    val errorText = Color(0xFFB33B32)
    val errorBg = Color(0xFFF8E4E0)

    val dmSans = FontFamily(
        Font(R.font.dmsans_regular, FontWeight.Normal),
        Font(R.font.dmsans_medium, FontWeight.Medium),
        Font(R.font.dmsans_semibold, FontWeight.SemiBold),
        Font(R.font.dmsans_bold, FontWeight.Bold),
    )
    val fraunces = FontFamily(
        Font(R.font.fraunces_semibold, FontWeight.SemiBold),
        Font(R.font.fraunces_bold, FontWeight.Bold),
    )

    private fun dm(weight: FontWeight, size: Int) = TextStyle(fontFamily = dmSans, fontWeight = weight, fontSize = size.sp)

    val bigTitle = TextStyle(fontFamily = fraunces, fontWeight = FontWeight.Bold, fontSize = 34.sp, lineHeight = 40.sp)
    val tourTitle = TextStyle(fontFamily = fraunces, fontWeight = FontWeight.SemiBold, fontSize = 28.sp, lineHeight = 34.sp)
    val recipeTitle = TextStyle(fontFamily = fraunces, fontWeight = FontWeight.SemiBold, fontSize = 26.sp, lineHeight = 32.sp)
    val title = dm(FontWeight.Bold, 20)
    val action = dm(FontWeight.SemiBold, 17)
    val mealName = action
    val recipeCardName = dm(FontWeight.SemiBold, 15)
    val recipeCardServing = dm(FontWeight.Normal, 12)
    val rowTitle = dm(FontWeight.Medium, 17)
    val body = dm(FontWeight.Normal, 17)
    val chipLabel = dm(FontWeight.SemiBold, 15)
    val subtitle = dm(FontWeight.Normal, 13)
    val count = dm(FontWeight.Medium, 13)
    /** Small all-caps section headers (aisles, days, settings groups). */
    val sectionHeader = dm(FontWeight.Bold, 14)
    val navTitle = dm(FontWeight.SemiBold, 17)
    val stepText = dm(FontWeight.Normal, 15)
}

/** Large text sizes (iOS accessibility sizes): layouts stack instead of squeezing. */
val isAccessibilitySize: Boolean
    @Composable @ReadOnlyComposable get() = LocalDensity.current.fontScale >= 1.5f

@Composable
fun DinnerdeskTheme(content: @Composable () -> Unit) {
    val scheme = lightColorScheme(
        primary = Theme.accent,
        onPrimary = Color.White,
        secondary = Theme.ink,
        onSecondary = Color.White,
        background = Theme.bg,
        onBackground = Theme.ink,
        surface = Theme.surface,
        onSurface = Theme.ink,
        surfaceVariant = Theme.aubergineTint,
        onSurfaceVariant = Theme.muted,
        surfaceContainerLow = Theme.surface,
        surfaceContainer = Theme.surface,
        surfaceContainerHigh = Theme.surface,
        surfaceContainerHighest = Theme.aubergineTint,
        surfaceContainerLowest = Theme.surface,
        outline = Theme.line,
        outlineVariant = Theme.line,
        error = Theme.destructive,
        primaryContainer = Theme.coralTint,
        onPrimaryContainer = Theme.coralInk,
        secondaryContainer = Theme.aubergineTint,
        onSecondaryContainer = Theme.ink,
    )
    val type = Typography(
        bodyLarge = Theme.body,
        bodyMedium = Theme.body,
        bodySmall = Theme.subtitle,
        titleLarge = Theme.title,
        titleMedium = Theme.action,
        titleSmall = Theme.chipLabel,
        labelLarge = Theme.action,
        labelMedium = Theme.count,
        labelSmall = Theme.subtitle,
        headlineLarge = Theme.bigTitle,
        headlineMedium = Theme.tourTitle,
        headlineSmall = Theme.recipeTitle,
    )
    MaterialTheme(colorScheme = scheme, typography = type) {
        CompositionLocalProvider(
            LocalContentColor provides Theme.ink,
            LocalTextSelectionColors provides TextSelectionColors(Theme.accent, Theme.accent.copy(alpha = 0.3f)),
            content = content,
        )
    }
}
