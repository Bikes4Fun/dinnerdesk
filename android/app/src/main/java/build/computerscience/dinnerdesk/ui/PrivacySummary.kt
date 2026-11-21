package build.computerscience.dinnerdesk.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import build.computerscience.dinnerdesk.data.Copy

/**
 * The short version of the privacy policy: what we keep, what we never collect, who else can see it.
 * Shown at the top of Privacy, on sign up, and on the first-open agreement screen. Words: privacy.*
 * in copy.json, shared with web (PrivacySummary.jsx) and iOS (PrivacySummaryView).
 * [compact] leaves out "Who else can see it" where space is tight.
 */
@Composable
fun PrivacySummary(compact: Boolean = false) {
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

        if (!compact) {
            PrivacyHeader("privacy.shared.title")
            PrivacyRows("privacy.shared", 3, compact)
        }
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
