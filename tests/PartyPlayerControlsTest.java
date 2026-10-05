package me.jxl.kiosk.plugins.partymode;
import org.json.JSONObject;

public final class PartyPlayerControlsTest {
    public static void main(String[] args) throws Exception {
        String group = "ugp_stueetagen";
        PartyPlayerControls.Request play = PartyPlayerControls.playback(group, false);
        check(play.command.equals("player_queues/play") && play.args.getString("queue_id").equals(group), "play selected queue");
        check(PartyPlayerControls.playback(group, true).command.equals("player_queues/pause"), "pause when playing");
        check(PartyPlayerControls.stop(group).command.equals("player_queues/stop"), "stop queue");
        PartyPlayerControls.Request volume = PartyPlayerControls.volume(group, 140);
        check(volume.command.equals("players/cmd/group_volume") && volume.args.getString("player_id").equals(group), "MA group volume target");
        check(volume.args.getInt("volume_level") == 100, "upper bound");
        check(PartyPlayerControls.volume(group, -10).args.getInt("volume_level") == 0, "lower bound");
        for (String missing : new String[] {"", "  ", "unavailable", "unknown"}) {
            boolean rejected = false;
            try { PartyPlayerControls.playback(missing, false); } catch (IllegalArgumentException expected) { rejected = true; }
            check(rejected, "missing queue never falls back to another player");
        }
        check(PartyPlayerControls.volume(new JSONObject().put("volume_level", 42)) == 42, "normal MA volume");
        check(PartyPlayerControls.volume(new JSONObject().put("group_volume", 60).put("volume_level", 42)) == 60, "group volume priority");
        check(PartyPlayerControls.volume(new JSONObject().put("available", false).put("volume_level", 40)) == -1, "offline volume disabled");
        check(PartyPlayerControls.volume(new JSONObject()) == -1, "unknown volume disabled");
        check(PartyPlayerControls.accepted(JSONObject.NULL), "successful void response");
        check(!PartyPlayerControls.accepted(null), "HTTP failure");
        check(!PartyPlayerControls.accepted(new JSONObject().put("error_code", 403)), "permission error");
        System.out.println("Party MA playback and group-volume checks passed");
    }
    private static void check(boolean ok, String text) { if (!ok) throw new AssertionError(text); }
}
