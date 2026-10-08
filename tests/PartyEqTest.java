package me.jxl.kiosk.plugins.partymode;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.HashMap;
import java.util.Map;
public final class PartyEqTest {
    public static void main(String[] args) throws Exception {
        JSONObject group = player("group", "ugp--one").put("group_members", new JSONArray().put("sonos").put("kiosk").put("offline"));
        Map<String, JSONObject> members = new HashMap<>();
        members.put("sonos", player("sonos", "sonos_s1--one")); members.put("kiosk", player("kiosk", "sendspin--one"));
        members.put("offline", player("offline", "sonos_s1--one").put("available", false));
        check(PartyEq.targets(group, members).size() == 1 && PartyEq.targets(group, members).get(0).equals("sonos"), "only online Sonos members");
        check(PartyEq.targets(player("s", "sonos_s1--one").put("group_members", new JSONArray().put("s").put("other")), members).isEmpty(), "native Sonos group DSP unsupported");
        check(PartyEq.targets(player("s", "sonos_s1--one"), members).size() == 1, "standalone Sonos supported");
        check(PartyEq.targets(player("kiosk", "sendspin--one"), members).isEmpty(), "never adjust kiosk DSP");
        JSONObject config = PartyEq.punch();
        check(config.getBoolean("enabled") && config.getDouble("input_gain") == -5, "headroom before boost");
        JSONArray bands = config.getJSONArray("filters").getJSONObject(0).getJSONArray("bands");
        check(bands.length() == 4 && bands.getJSONObject(1).getDouble("frequency") == 95, "punch band");
        check(bands.getJSONObject(0).getString("channel").equals("ALL"), "MA channel enum");
        check(!PartyDsp.valid(new JSONObject().put("error_code", 5)), "API errors rejected");
        check(!PartyDsp.valid(new JSONObject().put("enabled", "true").put("filters", new JSONArray())), "typed DSP response required");
        JSONObject disabled = PartyDsp.enabled(config, false);
        check(config.getBoolean("enabled") && !disabled.getBoolean("enabled") && disabled.getJSONArray("filters").toString().equals(config.getJSONArray("filters").toString()), "toggle preserves original filter chain without mutation");
        JSONArray presets = new JSONArray().put(new JSONObject().put("preset_id", "first").put("name", "Bass").put("config", config))
            .put(new JSONObject().put("preset_id", "second").put("name", "Bass").put("config", config)).put(JSONObject.NULL)
            .put(new JSONObject().put("preset_id", "bad").put("name", "Bad").put("config", new JSONObject()));
        Map<String,String> choices=PartyDsp.presets(presets);
        check(choices.size()==2 && choices.containsValue("first") && choices.containsValue("second"), "duplicate preset names retain distinct verified IDs; malformed rows omitted");
        check("MA · Bass".equals(PartyDsp.selected(new JSONObject(config.toString()).put("preset_id", "first"), choices)), "reports actual MA preset");
        check(PartyDsp.CUSTOM.equals(PartyDsp.selected(config, choices)) && PartyDsp.OFF.equals(PartyDsp.selected(disabled, choices)), "custom and disabled state truthful");
        System.out.println(config.toString());
        System.out.println("Party EQ checks passed");
    }
    static JSONObject player(String id, String provider) throws Exception { return new JSONObject().put("player_id", id).put("provider", provider).put("available", true); }
    static void check(boolean value, String message) { if (!value) throw new AssertionError(message); }
}
