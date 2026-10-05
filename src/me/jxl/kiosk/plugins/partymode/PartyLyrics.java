// SPDX-License-Identifier: MIT
package me.jxl.kiosk.plugins.partymode;
import org.json.JSONObject;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

final class PartyLyrics {
    static final class Line { final double at; final String text; Line(double at, String text) { this.at = at; this.text = text; } }
    final List<Line> lines; final boolean synced;
    PartyLyrics(List<Line> lines, boolean synced) { this.lines = Collections.unmodifiableList(lines); this.synced = synced; }
    static PartyLyrics fromMedia(JSONObject media) {
        JSONObject metadata = media == null ? null : media.optJSONObject("metadata");
        return parse(metadata == null ? "" : metadata.optString("lrc_lyrics", ""), metadata == null ? "" : metadata.optString("lyrics", ""));
    }
    /** MA metadata/get_track_lyrics returns [plain lyrics, synchronized LRC]. */
    static PartyLyrics fromLookup(Object response) {
        if (!(response instanceof org.json.JSONArray)) return parse("", "");
        org.json.JSONArray values = (org.json.JSONArray) response;
        Object plain = values.opt(0), timed = values.opt(1);
        return parse(timed instanceof String ? (String) timed : "", plain instanceof String ? (String) plain : "");
    }
    static PartyLyrics parse(String lrc, String plain) {
        lrc = bounded(lrc); plain = bounded(plain); if (lrc.isEmpty() && plain.matches("(?s).*\\[\\d{1,3}:\\d{2}.*")) lrc = plain;
        List<Line> result = new ArrayList<>();
        Pattern stamp = Pattern.compile("\\[(\\d{1,3}):(\\d{2}(?:[.,]\\d{1,3})?)\\]");
        Matcher off = Pattern.compile("\\[offset:([+-]?\\d+)\\]", Pattern.CASE_INSENSITIVE).matcher(lrc);
        double offset = off.find() ? Math.max(-60000, Math.min(60000, Double.parseDouble(off.group(1)))) / 1000 : 0;
        for (String row : bounded(lrc).split("\\r?\\n")) {
            Matcher match = stamp.matcher(row); String value = stamp.matcher(row).replaceAll("").trim();
            while (match.find() && result.size() < 2000) {
                double seconds = Double.parseDouble(match.group(2).replace(',', '.'));
                if (seconds < 60) result.add(new Line(Math.max(0, Integer.parseInt(match.group(1)) * 60 + seconds + offset), value));
            }
        }
        if (!result.isEmpty()) { Collections.sort(result, Comparator.comparingDouble(line -> line.at)); return new PartyLyrics(result, true); }
        for (String row : bounded(plain).split("\\r?\\n")) if (result.size() < 2000 && !row.trim().isEmpty()) result.add(new Line(0, row.trim()));
        return new PartyLyrics(result, false);
    }
    int index(double elapsed) {
        if (!synced || lines.isEmpty() || elapsed < lines.get(0).at) return -1;
        int low = 0, high = lines.size() - 1;
        while (low < high) { int middle = (low + high + 1) / 2; if (lines.get(middle).at <= elapsed) low = middle; else high = middle - 1; }
        return low;
    }
    private static String bounded(String s) { return s == null || "null".equals(s) ? "" : s.substring(0, Math.min(65536, s.length())); }
}
