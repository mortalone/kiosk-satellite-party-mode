// SPDX-License-Identifier: MIT
package me.jxl.kiosk.plugins.partymode;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

final class PartyEq {
    static boolean sonos(JSONObject player) { return player.optString("provider", "").startsWith("sonos"); }
    static List<String> targets(JSONObject player, Map<String, JSONObject> members) {
        List<String> result = new ArrayList<>();
        if (!player.optBoolean("available", true)) return result;
        String provider = player.optString("provider", "");
        JSONArray ids = player.optJSONArray("group_members");
        if (provider.startsWith("ugp") || provider.startsWith("universal_group")) {
            if (ids != null) for (int i = 0; i < ids.length(); i++) {
                String id = ids.optString(i, ""); JSONObject member = members.get(id);
                if (member != null && member.optBoolean("available", true) && sonos(member)) result.add(id);
            }
        } else if (sonos(player) && (ids == null || ids.length() <= 1)) {
            String id = player.optString("player_id", ""); if (!id.isEmpty()) result.add(id);
        }
        return result;
    }
    static JSONObject punch() throws Exception {
        JSONArray bands = new JSONArray();
        bands.put(band(60, 1.5, 0.7, "low_shelf"));
        bands.put(band(95, 2.5, 0.9, "peak"));
        bands.put(band(220, -1.5, 0.8, "peak"));
        bands.put(band(7000, 0.5, 0.7, "peak"));
        JSONObject filter = new JSONObject().put("enabled", true).put("type", "parametric_eq").put("preamp", 0).put("bands", bands);
        return new JSONObject().put("enabled", true).put("input_gain", -5).put("output_gain", 0).put("filters", new JSONArray().put(filter));
    }
    private static JSONObject band(double hz, double db, double q, String type) throws Exception {
        return new JSONObject().put("frequency", hz).put("gain", db).put("q", q).put("type", type).put("enabled", true).put("channel", "ALL");
    }
}
