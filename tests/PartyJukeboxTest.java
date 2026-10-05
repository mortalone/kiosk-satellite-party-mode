package me.jxl.kiosk.plugins.partymode;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.List;
public final class PartyJukeboxTest {
    public static void main(String[] args) throws Exception {
        JSONArray tracks = new JSONArray().put(track("spotify://track/one", true)).put(track("spotify://track/one", true))
                .put(track("spotify://track/no", false)).put(track("invalid", true));
        List<PartyJukebox.Result> found = PartyJukebox.results(new JSONObject().put("tracks", tracks), "http://ma.test");
        check(found.size() == 1 && found.get(0).track.title.equals("A song"), "available tracks deduplicated by URI");
        for (int i = 0; i < 50; i++) tracks.put(track("spotify://track/" + i, true));
        check(PartyJukebox.results(new JSONObject().put("tracks", tracks), "http://ma.test").size() == 20, "results bounded");
        check(PartyJukebox.results(new JSONObject().put("albums", tracks), "http://ma.test").isEmpty(), "tracks only");
        PartyPlayerControls.Request jump = PartyJukebox.playItem("living-group", "stable-item-id");
        check(jump.command.equals("player_queues/play_index") && jump.args.getString("index").equals("stable-item-id"), "jump uses stable queue item ID");
        check(jump.args.getString("queue_id").equals("living-group"), "jump selected group");
        check(PartyJukebox.enqueue("living-group", "spotify://track/one", false).args.getString("option").equals("add"), "add preserves existing queue");
        check(PartyJukebox.enqueue("living-group", "spotify://track/one", true).args.getString("option").equals("play"), "immediate playback explicit");
        JSONObject queue = new JSONObject().put("current_index", 10).put("current_item", item(10));
        JSONArray window = new JSONArray(); for (int i = 0; i < 21; i++) window.put(item(i));
        PartyQueueModel full = PartyQueueModel.parse(queue, window, "http://ma.test", 10, 10);
        check(full.tracks.size() == 21 && full.tracks.get(10).current, "ten before and ten after");
        check(PartyQueueModel.limit(queue, 1000, 1000) == 21, "count cap");
        check(PartyQueueModel.parse(queue, new JSONArray().put(item(10)), "", 0, 0).tracks.size() == 1, "current song only");
        queue.put("next_item", item(11));
        check(PartyQueueModel.parse(queue, null, "", 0, 0).tracks.size() == 1, "fallback respects zero next count");
        queue.put("current_index", 0).put("current_item", item(0));
        check(PartyQueueModel.limit(queue, 10, 10) == 11, "queue beginning clipped correctly");
        System.out.println("Party jukebox checks passed");
    }
    static JSONObject track(String uri, boolean available) throws Exception { return new JSONObject().put("uri", uri).put("available", available).put("name", "A song"); }
    static JSONObject item(int i) throws Exception { return new JSONObject().put("queue_item_id", "item" + i).put("name", "Song " + i); }
    static void check(boolean value, String message) { if (!value) throw new AssertionError(message); }
}
