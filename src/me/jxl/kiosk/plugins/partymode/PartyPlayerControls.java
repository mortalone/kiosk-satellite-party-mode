// SPDX-License-Identifier: MIT
package me.jxl.kiosk.plugins.partymode;

import org.json.JSONObject;

/** Requests always target the selected MA queue/group, never a kiosk audio output. */
final class PartyPlayerControls {
    static final class Request {
        final String command;
        final JSONObject args;
        Request(String command, JSONObject args) { this.command = command; this.args = args; }
    }
    static Request playback(String queue, boolean playing) throws Exception {
        return new Request(playing ? "player_queues/pause" : "player_queues/play",
                new JSONObject().put("queue_id", queue(queue)));
    }
    static Request stop(String queue) throws Exception {
        return new Request("player_queues/stop", new JSONObject().put("queue_id", queue(queue)));
    }
    static Request volume(String queue, int level) throws Exception {
        return new Request("players/cmd/group_volume", new JSONObject().put("player_id", queue(queue))
                .put("volume_level", Math.max(0, Math.min(100, level))));
    }
    static int volume(JSONObject player) {
        if (player == null || !player.optBoolean("available", true)) return -1;
        Object value = player.opt("group_volume");
        if (!(value instanceof Number)) value = player.opt("volume_level");
        if (!(value instanceof Number)) return -1;
        double level = ((Number) value).doubleValue();
        if (Double.isNaN(level) || Double.isInfinite(level)) return -1;
        return (int) Math.round(Math.max(0, Math.min(100, level)));
    }
    static boolean accepted(Object response) {
        if (response == null || Boolean.FALSE.equals(response)) return false;
        if (response instanceof JSONObject) {
            JSONObject object = (JSONObject) response;
            return (!object.has("error") || object.isNull("error")) &&
                    (!object.has("error_code") || object.optInt("error_code", 0) == 0);
        }
        return true; // MA void commands return JSON null (JSONObject.NULL), not Java null.
    }
    private static String queue(String queue) {
        if (queue == null || queue.trim().isEmpty() || "unknown".equals(queue) || "unavailable".equals(queue))
            throw new IllegalArgumentException("Selected MA queue unavailable");
        return queue;
    }
}
