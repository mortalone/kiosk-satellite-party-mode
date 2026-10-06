// SPDX-License-Identifier: MIT
package me.jxl.kiosk.plugins.partymode;

import org.json.JSONArray;
import org.json.JSONObject;

final class PartyGuestConfig {
    private PartyGuestConfig() {}
    static String matchingInstance(JSONArray configs, String queue) {
        if (configs == null || queue == null || queue.isEmpty()) return "";
        String matched = "";
        for (int i = 0; i < configs.length(); i++) {
            JSONObject config = configs.optJSONObject(i);
            if (config == null || !"party".equals(config.optString("domain")) || !config.optBoolean("enabled", true)) continue;
            JSONObject values = config.optJSONObject("values");
            Object player = values == null ? null : values.opt("player");
            if (player instanceof JSONObject) player = ((JSONObject) player).opt("value");
            if (!PartyGuestLink.matches(queue, player)) continue;
            String id = config.optString("instance_id", "");
            if (id.isEmpty() || !matched.isEmpty()) return "";
            matched = id;
        }
        return matched;
    }
    /** Null means unverified, never a guessed off state. */
    static Boolean guestAccess(JSONArray configs, String queue) {
        String instance = matchingInstance(configs, queue);
        if (instance.isEmpty()) return null;
        for (int i = 0; i < configs.length(); i++) {
            JSONObject config = configs.optJSONObject(i);
            if (config == null || !instance.equals(config.optString("instance_id", ""))) continue;
            JSONObject values = config.optJSONObject("values");
            // MA omits values equal to their defaults. Its Party provider declares
            // enable_guest_access default=False, so a missing key in a verified
            // matching provider is a confirmed off state, not an unknown target.
            if (values != null && !values.has("enable_guest_access")) return Boolean.FALSE;
            Object value = values == null ? null : values.opt("enable_guest_access");
            if (value instanceof JSONObject) value = ((JSONObject) value).opt("value");
            return value instanceof Boolean ? (Boolean) value : null;
        }
        return null;
    }

}
