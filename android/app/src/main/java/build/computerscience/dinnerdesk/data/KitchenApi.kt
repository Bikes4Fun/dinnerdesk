package build.computerscience.dinnerdesk.data

import kotlinx.serialization.json.JsonObject

/** Sign-in, account, and session calls (AuthAPI.swift). */
object AuthApi {
    suspend fun status(): AuthStatus = Api.get("auth/status")

    suspend fun login(email: String, password: String) {
        Api.send<Ok>("auth/login", "POST", mapOf("email" to email, "password" to password))
    }

    suspend fun signup(email: String, password: String, householdName: String) {
        Api.send<Ok>("auth/signup", "POST", mapOf("email" to email, "password" to password, "household_name" to householdName))
    }

    /** Emails a reset link if the address has an account. Same answer either way. */
    suspend fun forgotPassword(email: String) {
        Api.send<Ok>("auth/forgot-password", "POST", mapOf("email" to email))
    }

    suspend fun logout() { Api.send<Ok>("auth/logout", "POST") }

    suspend fun logoutEverywhere() { Api.send<Ok>("auth/logout-everywhere", "POST") }

    /** Deletes this account; shared-household creators must transfer ownership first. */
    suspend fun deleteAccount(password: String) {
        Api.send<Ok>("auth/delete-account", "POST", mapOf("password" to password))
    }
}

/** Kitchen / household prefs, pantry, stores (KitchenAPI.swift). */
object KitchenApi {
    suspend fun prefs(): JsonObject {
        val household = Api.jsonObject("household")
        return household["prefs"] as? JsonObject ?: throw ApiError(200, "Missing or invalid household preferences")
    }

    /** Server merges top-level keys, so send only what changed. */
    suspend fun savePrefs(patch: Map<String, Any?>) {
        Api.jsonObject("household", "PUT", mapOf("prefs" to patch))
    }

    /** Change part of prefs.grocery without wiping the rest of it. */
    suspend fun saveGroceryPrefs(patch: Map<String, Any?>) {
        val grocery = (prefs()["grocery"] as? JsonObject)?.toMutableMap<String, Any?>() ?: mutableMapOf()
        grocery.putAll(patch)
        savePrefs(mapOf("grocery" to grocery))
    }

    suspend fun members(): List<HouseholdMember> = Api.get<HouseholdMembers>("household/members").members

    suspend fun createInvite(): String {
        val invite: HouseholdInvite = Api.send("household/invites", "POST")
        return Api.url("join/${invite.token}")
    }

    suspend fun leaveHousehold() { Api.send<Ok>("household/leave", "POST") }

    suspend fun joinHousehold(token: String) { Api.send<Ok>("household/join", "POST", mapOf("token" to token)) }

    suspend fun deleteHousehold(password: String) {
        Api.send<Ok>("household/delete", "POST", mapOf("password" to password))
    }

    suspend fun setRole(id: Int, role: String) { Api.send<Ok>("household/members/$id/role", "PUT", mapOf("role" to role)) }

    suspend fun removeMember(id: Int) { Api.send<Ok>("household/members/$id", "DELETE") }

    suspend fun pantry(): List<KitchenPantryItem> = Api.get<KitchenPantryList>("pantry").items

    suspend fun upsertPantry(name: String, have: Boolean, neverShop: Boolean): KitchenPantryItem =
        Api.send("pantry/items", "POST", mapOf("name" to name, "have" to have, "never_shop" to neverShop, "zone" to "dry"))

    suspend fun patchPantry(id: Int, have: Boolean? = null, neverShop: Boolean? = null, quantity: String? = null): KitchenPantryItem =
        Api.send("pantry/items/$id", "PATCH", buildMap {
            if (have != null) put("have", have)
            if (neverShop != null) put("never_shop", neverShop)
            if (quantity != null) put("quantity", quantity)
        })

    suspend fun searchItems(query: String): List<String> {
        val box: KitchenItemSearch = Api.get("grocery-items", mapOf("q" to query, "limit" to "12"))
        val names = box.items.map { it.name }.toMutableList()
        val custom = box.custom
        if (!custom.isNullOrEmpty() && custom !in names) names.add(custom)
        return names
    }

    suspend fun overrides(): List<KitchenOverride> = Api.get<KitchenOverrideList>("overrides").items

    suspend fun addOverride(from: String, to: String): List<KitchenOverride> =
        Api.send<KitchenOverrideList>("overrides", "POST", mapOf("from_name" to from, "to_name" to to)).items

    suspend fun deleteOverride(id: Int): List<KitchenOverride> = Api.send<KitchenOverrideList>("overrides/$id", "DELETE").items

    suspend fun placements(): List<ItemPlacement> =
        Api.get<ItemPlaceList>("grocery/places").items.map { ItemPlacement(it.name, it.store ?: "", it.aisle ?: "other") }

    suspend fun setPlacement(item: ItemPlacement, store: String? = null, aisle: String? = null) {
        Api.jsonObject("grocery/places", "PUT", buildMap {
            put("name", item.name)
            if (store != null) put("store", store)
            if (aisle != null) put("aisle", aisle)
        })
    }
}

object KitchenDefaults {
    fun stores(prefs: JsonObject): List<ShopStore> = Household(prefs = prefs).stores ?: ShopStore.defaults

    fun aisles(prefs: JsonObject): List<ShopAisle> = Household(prefs = prefs).aisles?.takeIf { it.isNotEmpty() } ?: ShopAisle.defaults

    fun storesJson(stores: List<ShopStore>) = stores.map { mapOf("id" to it.id, "name" to it.name) }

    fun aislesJson(aisles: List<ShopAisle>) = aisles.map { mapOf("id" to it.id, "name" to it.name, "number" to it.number) }

    fun slug(name: String): String {
        val out = StringBuilder()
        var lastDash = false
        for (ch in name.lowercase()) {
            if (ch.isLetterOrDigit()) {
                out.append(ch)
                lastDash = false
            } else if (!lastDash && out.isNotEmpty()) {
                out.append('-')
                lastDash = true
            }
        }
        while (out.endsWith("-")) out.setLength(out.length - 1)
        if (out.isEmpty()) throw ApiError(400, """{"detail":"A name must contain a letter or number"}""")
        return out.toString()
    }
}
