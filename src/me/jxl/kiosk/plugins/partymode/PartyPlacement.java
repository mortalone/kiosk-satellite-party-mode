// SPDX-License-Identifier: MIT
package me.jxl.kiosk.plugins.partymode;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.HashSet;
import java.util.Set;

/** Refuse ambiguous edits rather than moving another person's queue item. */
final class PartyPlacement {
    static int tailOffset(JSONObject queue) { return Math.max(0, queue.optInt("items", 0) - 16); }
    static PartyPlayerControls.Request move(JSONObject before, JSONArray oldTail, JSONObject after, JSONArray newTail, int offset, int position, String expectedUri) throws Exception {
        if (position < 1 || position > 100 || before.optBoolean("shuffle_enabled") || after.optBoolean("shuffle_enabled")) return null;
        if (!before.optString("queue_id").equals(after.optString("queue_id")) || after.optInt("items") != before.optInt("items") + 1) return null;
        JSONObject oldCurrent = before.optJSONObject("current_item"), current = after.optJSONObject("current_item");
        if (oldCurrent == null || current == null || !oldCurrent.optString("queue_item_id").equals(current.optString("queue_item_id"))) return null;
        if (oldTail == null || newTail == null || oldTail.length() != before.optInt("items") - offset || newTail.length() != oldTail.length() + 1) return null;
        Set<String> ids = new HashSet<>();
        for (int i = 0; i < oldTail.length(); i++) {
            JSONObject a = oldTail.optJSONObject(i), b = newTail.optJSONObject(i);
            if (a == null || b == null || !a.optString("queue_item_id").equals(b.optString("queue_item_id"))) return null;
            ids.add(a.optString("queue_item_id"));
        }
        JSONObject added = newTail.optJSONObject(newTail.length() - 1);
        if (added == null || added.optString("queue_item_id").isEmpty() || ids.contains(added.optString("queue_item_id"))) return null;
        JSONObject media = added.optJSONObject("media_item");
        String actualUri = media == null ? added.optString("uri", "") : media.optString("uri", added.optString("uri", ""));
        if (expectedUri == null || expectedUri.isEmpty() || !expectedUri.equals(actualUri)) return null;
        int source = after.optInt("items") - 1;
        int destination = Math.min(source, after.optInt("current_index", 0) + position);
        if (destination == source) return new PartyPlayerControls.Request("", new JSONObject());
        // Already buffered audio cannot be retroactively reordered.
        if (after.has("index_in_buffer") && !after.isNull("index_in_buffer") && destination <= after.optInt("index_in_buffer")) return null;
        return new PartyPlayerControls.Request("player_queues/move_item", new JSONObject().put("queue_id", after.getString("queue_id"))
                .put("queue_item_id", added.getString("queue_item_id")).put("pos_shift", destination - source));
    }
}
