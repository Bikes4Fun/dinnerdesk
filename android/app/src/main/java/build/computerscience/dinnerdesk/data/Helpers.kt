package build.computerscience.dinnerdesk.data

import android.content.Context
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

/**
 * Shared user-facing text. The words live in ios/dinnerdesk/copy.json (also used by iOS and the
 * website), bundled as an asset at build time. `{app}` becomes the app name.
 */
object Copy {
    private var table: Map<String, String> = emptyMap()

    fun load(context: Context) {
        if (table.isNotEmpty()) return
        val raw = context.assets.open("copy.json").bufferedReader().use { it.readText() }
        val obj = Api.json.parseToJsonElement(raw) as JsonObject
        table = obj.mapNotNull { (k, v) -> (v as? JsonPrimitive)?.takeIf { it.isString }?.let { k to it.content } }.toMap()
        check(table["app.name"] != null) { "Missing app.name in copy.json" }
    }

    val appName: String get() = text("app.name")

    fun has(id: String) = table.containsKey(id)

    fun text(id: String): String {
        val value = table[id] ?: error("Missing copy key: $id")
        return value.replace("{app}", table.getValue("app.name"))
    }
}

/** Scale amounts and ranges while preserving units and package dimensions (Quantity.swift). */
fun scaleAmount(text: String, base: Int?, servings: Int): String {
    if (base == null || base <= 0 || base == servings) return text
    var normalized = text
    for ((glyph, fraction) in listOf(
        "¼" to "1/4", "½" to "1/2", "¾" to "3/4", "⅓" to "1/3", "⅔" to "2/3", "⅛" to "1/8", "⅜" to "3/8", "⅝" to "5/8", "⅞" to "7/8",
    )) normalized = normalized.replace(glyph, " $fraction ")
    normalized = normalized.replace(Regex("\\s+"), " ").trim()
    val amount = "(?:\\d+\\s+\\d+/\\d+|\\d+/\\d+|\\d+(?:\\.\\d+)?)"
    val match = Regex("^($amount)(?:\\s*([-–])\\s*($amount))?").find(normalized) ?: return text
    fun scaled(raw: String): String {
        val value = raw.split(Regex("\\s+")).filter { it.isNotEmpty() }.sumOf { part ->
            val pieces = part.split("/")
            if (pieces.size == 2) {
                val denominator = pieces[1].toDouble()
                require(denominator != 0.0) { "Invalid zero-denominator ingredient quantity" }
                pieces[0].toDouble() / denominator
            } else part.toDouble()
        } * servings / base
        return String.format(Locale.US, "%.3f", value).replace(Regex("\\.?0+$"), "")
    }
    var result = scaled(match.groupValues[1])
    if (match.groups[3] != null) result += match.groupValues[2] + scaled(match.groupValues[3])
    return result + normalized.substring(match.range.last + 1)
}

/** "Uses pantry" for recipe search: the same rule as the website and iOS (PantryMatch.swift). */
object PantryMatch {
    fun have(items: List<KitchenPantryItem>): Set<String> =
        items.filter { it.have && !it.neverShop }.map { norm(it.name) }.filter { it.isNotEmpty() }.toSet()

    fun uses(ingredients: List<String>, have: Set<String>): Boolean {
        if (have.isEmpty()) return false
        val names = ingredients.map(::norm).filter { it.isNotEmpty() }
        if (names.isEmpty()) return false
        val hits = names.count { hit(it, have) }
        return hits >= 2 || (hits >= 1 && hits.toDouble() / names.size >= 0.4)
    }

    private fun hit(ingredient: String, have: Set<String>): Boolean {
        if (ingredient in have) return true
        return have.any { p ->
            p.length >= 3 && (ingredient.startsWith("$p ") || ingredient.endsWith(" $p") || ingredient.contains(" $p "))
        }
    }

    fun norm(text: String): String =
        text.lowercase().map { c -> if (c.code < 128 && c.isLetterOrDigit()) c else ' ' }.joinToString("")
            .split(" ").filter { it.isNotEmpty() }.joinToString(" ")
}

fun planDate(value: String): LocalDate? = try { LocalDate.parse(value) } catch (_: Exception) { null }

private val shortDay = DateTimeFormatter.ofPattern("MMM d", Locale.getDefault())
private val longDay = DateTimeFormatter.ofPattern("EEEE, MMM d", Locale.getDefault())

fun shortDate(date: LocalDate): String = date.format(shortDay)

fun dayTitle(start: String, index: Int): String {
    val date = planDate(start) ?: return "Day ${index + 1}"
    return date.plusDays(index.toLong()).format(longDay)
}

fun String.capitalizedWords(): String = split(" ").joinToString(" ") { w -> w.replaceFirstChar { it.titlecase(Locale.getDefault()) } }
