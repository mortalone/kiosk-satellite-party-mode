// SPDX-License-Identifier: MIT
package me.jxl.kiosk.plugins.partymode;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.LinkedHashMap;
import java.util.Map;

/** MA owns preset definitions; the kiosk only lists and applies their verified IDs. */
final class PartyDsp {
    static final String CUSTOM = "Tilpasset EQ", OFF = "DSP fra", RESTORE = "Gendan oprindelig EQ";
    static boolean valid(Object raw) {
        return raw instanceof JSONObject && ((JSONObject)raw).opt("enabled") instanceof Boolean
                && ((JSONObject)raw).opt("filters") instanceof JSONArray;
    }
    static Map<String, String> presets(JSONArray rows) {
        Map<String, String> result = new LinkedHashMap<>();
        if (rows == null) return result;
        for (int i = 0; i < rows.length() && result.size() < 29; i++) {
            JSONObject row = rows.optJSONObject(i);
            if (row == null || !valid(row.opt("config"))) continue;
            String id = row.optString("preset_id", ""), name = row.optString("name", "").trim();
            if (id.isEmpty() || id.length() > 80 || "null".equals(id) || name.isEmpty() || result.containsValue(id)) continue;
            // Prefix separates user names from action labels; ID suffix disambiguates duplicates.
            String label = "MA · " + name.substring(0, Math.min(55, name.length()));
            if (result.containsKey(label)) label += " · " + id.substring(0, Math.min(12, id.length()));
            if (!result.containsKey(label)) result.put(label, id);
        }
        return result;
    }
    static String selected(JSONObject config, Map<String, String> presets) {
        if (!config.optBoolean("enabled")) return OFF;
        String id = config.optString("preset_id", "");
        for (Map.Entry<String, String> entry : presets.entrySet()) if (entry.getValue().equals(id)) return entry.getKey();
        return CUSTOM;
    }
    static JSONObject enabled(JSONObject config, boolean on) throws Exception {
        if (!valid(config)) throw new IllegalArgumentException("Invalid MA DSP config");
        return new JSONObject(config.toString()).put("enabled", on);
    }
}
