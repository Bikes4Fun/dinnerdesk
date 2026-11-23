package build.computerscience.dinnerdesk.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.selection.toggleable
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.ui.semantics.Role
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.ui.Modifier
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import build.computerscience.dinnerdesk.data.Copy

/**
 * The short version of the privacy policy: what we keep, what we never collect, who else can see it.
 * Words: privacy.* in copy.json, shared with web (PrivacySummary.jsx) and iOS (PrivacySummaryView).
 * Full at the top of Privacy; [compact] is the one-screen version for first open: the don't-sell line,
 * four "We keep" bullets, the household sharing note, and one "We never collect" sentence.
 */
@Composable
fun PrivacySummary(compact: Boolean = false) {
    if (compact) { ShortPrivacySummary(); return }
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(
            Copy.text("privacy.sell"), style = Theme.action, color = Theme.bg,
            modifier = Modifier.fillMaxWidth().background(Theme.ink, RoundedCornerShape(14.dp)).padding(14.dp),
        )

        PrivacyHeader("privacy.keep.title")
        PrivacyRows("privacy.keep", 4, compact)
        Text(Copy.text("privacy.keep.use"), style = Theme.subtitle, color = Theme.muted)

        PrivacyHeader("privacy.never.title")
        Copy.text("privacy.never").split(" · ").chunked(2).forEach { pair ->
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                pair.forEach { item ->
                    Text(
                        item, style = Theme.chipLabel, color = Theme.ink,
                        modifier = Modifier.weight(1f)
                            .background(Theme.surface, RoundedCornerShape(12.dp))
                            .border(1.dp, Theme.line, RoundedCornerShape(12.dp))
                            .padding(horizontal = 12.dp, vertical = 10.dp),
                    )
                }
            }
        }
        Text(
            Copy.text("privacy.health"), style = Theme.subtitle, color = Theme.ink,
            modifier = Modifier.fillMaxWidth().background(Theme.aubergineTint, RoundedCornerShape(12.dp)).padding(12.dp),
        )

        PrivacyHeader("privacy.shared.title")
        PrivacyRows("privacy.shared", 3, compact)
    }
}

/** "Your household can see all of it, including your allergies, likes, dislikes and Taste Lab history." */
@Composable
fun HouseholdSharingNote() {
    Text(
        buildAnnotatedString {
            withStyle(SpanStyle(fontWeight = FontWeight.SemiBold)) { append(Copy.text("privacy.household.lead")) }
            append(" ")
            append(Copy.text("privacy.household"))
        },
        style = Theme.subtitle, color = Theme.ink,
        modifier = Modifier.fillMaxWidth().background(Theme.aubergineTint, RoundedCornerShape(12.dp)).padding(12.dp),
    )
}

/** The one-screen version for first open and sign up: privacy.short.* in copy.json. */
@Composable
private fun ShortPrivacySummary() {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(
            Copy.text("privacy.short.sell"), style = Theme.action, color = Theme.bg,
            modifier = Modifier.fillMaxWidth().background(Theme.ink, RoundedCornerShape(14.dp)).padding(14.dp),
        )
        PrivacyHeader("privacy.short.keep.title")
        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
            for (i in 1..4) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("•", style = Theme.body, color = Theme.muted)
                    Text(
                        buildAnnotatedString {
                            append(Copy.text("privacy.short.keep.$i"))
                            if (i == 3) {
                                append(" ")
                                withStyle(SpanStyle(color = Theme.muted)) { append(Copy.text("privacy.short.keep.3.note")) }
                            }
                        },
                        style = Theme.body, color = Theme.ink,
                    )
                }
            }
        }
        HouseholdSharingNote()
        PrivacyHeader("privacy.short.never.title")
        Text(Copy.text("privacy.short.never"), style = Theme.body, color = Theme.ink)
    }
}

@Composable
private fun PrivacyHeader(id: String) {
    Text(Copy.text(id).uppercase(), style = Theme.sectionHeader, color = Theme.muted, modifier = Modifier.padding(top = 10.dp))
}

@Composable
private fun PrivacyRows(prefix: String, count: Int, compact: Boolean) {
    Column {
        for (i in 1..count) {
            Column(Modifier.fillMaxWidth().padding(vertical = if (compact) 6.dp else 10.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(Copy.text("$prefix.$i.title"), style = Theme.rowTitle, color = Theme.ink)
                Text(Copy.text("$prefix.$i"), style = Theme.subtitle, color = Theme.muted)
            }
            if (i < count) HorizontalDivider(color = Theme.line)
        }
    }
}


/** The whole privacy policy for screens outside the app's navigation (sign up, first open). */
@Composable
fun PrivacyPolicyDialog(onClose: () -> Unit) {
    Dialog(onDismissRequest = onClose, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Column(Modifier.fillMaxSize().background(Theme.bg)) {
            Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp)) {
                Text("Privacy", style = Theme.title, color = Theme.ink, modifier = Modifier.weight(1f).padding(vertical = 10.dp))
                Text(
                    "Done", style = Theme.action, color = Theme.accent,
                    modifier = Modifier.heightIn(min = 44.dp).clickable(onClick = onClose).padding(10.dp),
                )
            }
            Column(
                Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Text(Copy.text("privacy.intro"), style = Theme.body, color = Theme.ink)
                PrivacySummary()
                for ((title, body) in privacySections) {
                    Column(Modifier.padding(top = 8.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text(title, style = Theme.title, color = Theme.ink)
                        Text(body, style = Theme.body, color = Theme.muted)
                    }
                }
            }
        }
    }
}

/** A square checkbox row for agreeing to the privacy policy: the whole row toggles it. */
@Composable
fun AgreeCheckbox(checked: Boolean, onChange: (Boolean) -> Unit, label: String) {
    Row(
        Modifier.fillMaxWidth().heightIn(min = 44.dp)
            .toggleable(value = checked, role = Role.Checkbox, onValueChange = onChange)
            .padding(vertical = 6.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Checkbox(
            checked = checked, onCheckedChange = null,
            colors = CheckboxDefaults.colors(checkedColor = Theme.ink, uncheckedColor = Theme.muted),
        )
        Text(label, style = Theme.subtitle, color = Theme.ink, modifier = Modifier.weight(1f).padding(top = 12.dp))
    }
}
