package me.jxl.kiosk.plugins.partymode;
import org.json.JSONArray;
import org.json.JSONObject;

public final class PartyGuestConfigTest {
    public static void main(String[] args) throws Exception {
        JSONObject party = config("party_1", "group", true);
        check(PartyGuestConfig.matchingInstance(new JSONArray().put(party), "group").equals("party_1"), "matching explicit queue");
        check(PartyGuestConfig.matchingInstance(new JSONArray().put(config("other", "other-room", true)).put(party), "group").equals("party_1"), "skip other room");
        check(PartyGuestConfig.matchingInstance(new JSONArray().put(party).put(config("party_2", "group", true)), "group").isEmpty(), "ambiguous instance cannot be changed");
        check(PartyGuestConfig.matchingInstance(new JSONArray().put(config("party_1", "__auto__", true)), "group").isEmpty(), "auto queue not changed");
        check(PartyGuestConfig.matchingInstance(new JSONArray().put(config("party_1", "group", false)), "group").isEmpty(), "disabled plugin not changed");
        check(PartyGuestConfig.matchingInstance(new JSONArray().put(party.put("domain", "spotify")), "group").isEmpty(), "other provider never changed");

        JSONObject guest = config("guest", "group", true);
        guest.getJSONObject("values").put("enable_guest_access", true);
        check(Boolean.TRUE.equals(PartyGuestConfig.guestAccess(new JSONArray().put(guest), "group")), "flat enabled confirmed");
        guest.getJSONObject("values").put("enable_guest_access", false);
        check(Boolean.FALSE.equals(PartyGuestConfig.guestAccess(new JSONArray().put(guest), "group")), "flat disabled confirmed");
        guest.getJSONObject("values").put("enable_guest_access", new JSONObject().put("value", true));
        check(Boolean.TRUE.equals(PartyGuestConfig.guestAccess(new JSONArray().put(guest), "group")), "wrapped enabled confirmed");
        guest.getJSONObject("values").put("enable_guest_access", new JSONObject().put("value", false));
        check(Boolean.FALSE.equals(PartyGuestConfig.guestAccess(new JSONArray().put(guest), "group")), "wrapped disabled confirmed");
        check(PartyGuestConfig.guestAccess(new JSONArray().put(guest), "other") == null, "other queue not reported");
        check(PartyGuestConfig.guestAccess(new JSONArray().put(guest).put(config("other", "group", true)), "group") == null, "ambiguous target unknown");
        check(Boolean.FALSE.equals(PartyGuestConfig.guestAccess(new JSONArray().put(config("missing", "group", true)), "group")), "omitted MA false default confirmed");
        guest.getJSONObject("values").put("enable_guest_access", "false");
        check(PartyGuestConfig.guestAccess(new JSONArray().put(guest), "group") == null, "malformed value not guessed");
        check(PartyGuestConfig.guestAccess(null, "group") == null, "missing configs unknown");
        System.out.println("15 matching-provider and confirmed guest-state checks passed");
    }
    private static JSONObject config(String id, String player, boolean enabled) throws Exception {
        return new JSONObject().put("domain", "party").put("instance_id", id).put("enabled", enabled)
                .put("values", new JSONObject().put("player", new JSONObject().put("value", player)));
    }
    private static void check(boolean ok, String message) { if (!ok) throw new AssertionError(message); }
}
