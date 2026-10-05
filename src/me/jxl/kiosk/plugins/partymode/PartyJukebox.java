// SPDX-License-Identifier: MIT
package me.jxl.kiosk.plugins.partymode;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

final class PartyJukebox {
    static final class Result {
        final String uri;
        final PartyQueueModel.Track track;
        Result(String uri, PartyQueueModel.Track track) { this.uri = uri; this.track = track; }
    }
    static List<Result> results(JSONObject response, String base) throws Exception {
        List<Result> result = new ArrayList<>(); Set<String> seen = new HashSet<>();
        JSONArray tracks = response == null ? null : response.optJSONArray("tracks");
        if (tracks == null) return result;
        for (int i = 0; i < tracks.length() && result.size() < 20; i++) {
            JSONObject media = tracks.optJSONObject(i);
            if (media == null || !media.optBoolean("available", true)) continue;
            String uri = media.optString("uri", "");
            if (uri.length() > 2048 || !uri.contains("://") || !seen.add(uri)) continue;
            result.add(new Result(uri, PartyQueueModel.track(new JSONObject().put("media_item", media), base, false)));
        }
        return result;
    }
    static PartyPlayerControls.Request playItem(String queue, String id) throws Exception {
        if (queue.isEmpty() || id.isEmpty()) throw new IllegalArgumentException();
        return new PartyPlayerControls.Request("player_queues/play_index", new JSONObject().put("queue_id", queue).put("index", id));
    }
    static PartyPlayerControls.Request enqueue(String queue, String uri, boolean now) throws Exception {
        if (queue.isEmpty() || uri.isEmpty()) throw new IllegalArgumentException();
        return new PartyPlayerControls.Request("player_queues/play_media", new JSONObject().put("queue_id", queue).put("media", uri).put("option", now ? "play" : "add"));
    }
}
