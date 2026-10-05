package me.jxl.kiosk.plugins.partymode;
import org.json.JSONArray;
import org.json.JSONObject;
public final class PartyFeaturesTest {
    public static void main(String[] args) throws Exception {
        PartyLyrics lyrics = PartyLyrics.parse("[00:03.00]One\n[00:08.5][00:11.500]Two\n[00:15.00]\n[offset:250]", "");
        check(lyrics.synced && lyrics.lines.size() == 4, "multiple timestamps and instrumental breaks");
        check(lyrics.index(0) == -1 && lyrics.index(3.25) == 0 && lyrics.index(8.75) == 1 && lyrics.index(11.75) == 2, "timing and offset");
        check(lyrics.index(4) == 0, "seek backwards supported");
        check(!PartyLyrics.parse("", "A\nB").synced && PartyLyrics.parse("", "A\nB").lines.size() == 2, "plain lyrics never invent synchronization");
        check(PartyLyrics.parse(null, null).lines.isEmpty(), "missing metadata");
        check(PartyLyrics.parse("", "[00:05]Embedded").synced, "timed lyrics in plain metadata supported");
        PartyLyrics lookup = PartyLyrics.fromLookup(new JSONArray().put(JSONObject.NULL).put("[00:03]API line"));
        check(lookup.synced && lookup.index(3) == 0, "on-demand MA tuple: null plain and timed lyrics");
        check(PartyLyrics.fromLookup(new JSONArray().put("Plain API text").put(JSONObject.NULL)).lines.size() == 1, "on-demand plain fallback");
        check(PartyLyrics.fromLookup(new JSONArray().put("Plain").put("[00:00]Timed")).synced, "prefer synchronized API result");
        check(PartyLyrics.fromLookup(new JSONArray().put(JSONObject.NULL).put(JSONObject.NULL)).lines.isEmpty(), "no matching lyrics");
        check(PartyLyrics.fromLookup(new JSONObject().put("error_code", 5)).lines.isEmpty(), "API errors are not lyrics");
        float[] samples = new float[2]; PartyMotion.sample(new float[]{-9, Float.NaN, Float.POSITIVE_INFINITY, 8}, samples, false);
        check(samples[0] == 0 && samples[1] == 0.5f, "bounded reusable spectrum buffers");
        PartyMotion.sample(new float[]{-1, 1}, samples, true); check(samples[0] == -1 && samples[1] == 1, "waveform sign preserved");
        PartyMotion.sample(null, samples, true); check(samples[0] == 0 && samples[1] == 0, "empty audio clears previous samples");
        JSONObject before = queue(8, 2), after = queue(9, 2);
        JSONArray old = items(8), added = items(9);
        PartyPlayerControls.Request move = PartyPlacement.move(before, old, after, added, 0, 3, "spotify://track/same");
        check(move != null && move.args.getString("queue_item_id").equals("id8") && move.args.getInt("pos_shift") == -3, "third future item by stable ID");
        check(PartyPlacement.move(before, old, after, added, 0, 100, "spotify://track/same").command.isEmpty(), "already last never sends MA's special zero shift");
        check(PartyPlacement.move(before, old, after, added, 0, 3, "spotify://track/other") == null, "concurrent different track never moved");
        after.put("shuffle_enabled", true); check(PartyPlacement.move(before, old, after, added, 0, 3, "spotify://track/same") == null, "shuffle rejects precise ordering"); after.put("shuffle_enabled", false);
        after.put("index_in_buffer", 5); check(PartyPlacement.move(before, old, after, added, 0, 3, "spotify://track/same") == null, "buffered position refused"); after.remove("index_in_buffer");
        added.getJSONObject(0).put("queue_item_id", "changed"); check(PartyPlacement.move(before, old, after, added, 0, 3, "spotify://track/same") == null, "concurrent queue mutation refused"); added = items(9);
        after.put("current_item", new JSONObject().put("queue_item_id", "different")); check(PartyPlacement.move(before, old, after, added, 0, 3, "spotify://track/same") == null, "track changed while adding");
        JSONArray playlists = new JSONArray().put(new JSONObject().put("uri", "library://playlist/1").put("favorite", true).put("name", "Party"))
                .put(new JSONObject().put("uri", "library://playlist/2").put("favorite", false).put("name", "Other"));
        check(PartyJukebox.playlists(playlists, "").size() == 1, "only favorites displayed");
        check(PartySignal.effect("lyrics").equals("lyrics"), "lyrics visualization available");
        System.out.println("Lyrics, placement, favorites and reusable audio-buffer checks passed");
    }
    static JSONObject queue(int count, int current) throws Exception { return new JSONObject().put("queue_id", "living").put("items", count).put("current_index", current).put("current_item", new JSONObject().put("queue_item_id", "id" + current)); }
    static JSONArray items(int count) throws Exception { JSONArray a = new JSONArray(); for(int i = 0; i < count; i++) a.put(new JSONObject().put("queue_item_id", "id" + i).put("uri", "spotify://track/same")); return a; }
    static void check(boolean valid, String why) { if (!valid) throw new AssertionError(why); }
}
