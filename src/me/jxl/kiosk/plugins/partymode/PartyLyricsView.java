// SPDX-License-Identifier: MIT
package me.jxl.kiosk.plugins.partymode;
import android.content.Context;
import android.graphics.Typeface;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.util.ArrayList;
import java.util.List;

final class PartyLyricsView extends ScrollView {
    private final LinearLayout rows;
    private final List<TextView> labels = new ArrayList<>();
    private PartyLyrics lyrics = PartyLyrics.parse("", "");
    private int selected = -2;
    PartyLyricsView(Context context) {
        super(context); setFillViewport(true); setClipToPadding(false); setVerticalScrollBarEnabled(false);
        rows = new LinearLayout(context); rows.setOrientation(LinearLayout.VERTICAL);
        rows.setPadding(PartyUi.dp(context, 24), PartyUi.dp(context, 100), PartyUi.dp(context, 24), PartyUi.dp(context, 110));
        addView(rows, new ScrollView.LayoutParams(-1, -2)); setContentDescription("Sangtekst fra Music Assistant");
    }
    void setLyrics(PartyLyrics value) {
        if (lyrics == value) return; lyrics = value; selected = -2; rows.removeAllViews(); labels.clear();
        if (value.lines.isEmpty()) { rows.addView(PartyUi.text(getContext(), "Ingen sangtekst fra Music Assistant endnu", 20, PartyUi.MUTED)); return; }
        if (!value.synced) rows.addView(PartyUi.text(getContext(), "Sangtekst · uden tidskoder", 12, PartyUi.MUTED));
        // Bound native view count; synced songs retain a moving window around the current line.
        renderWindow(value.synced ? 0 : -1);
    }
    private int windowStart;
    private void renderWindow(int center) {
        rows.removeAllViews(); labels.clear();
        if (!lyrics.synced) rows.addView(PartyUi.text(getContext(), "Sangtekst · uden tidskoder", 12, PartyUi.MUTED));
        windowStart = lyrics.synced ? Math.max(0, center - 12) : 0;
        int end = Math.min(lyrics.lines.size(), windowStart + (lyrics.synced ? 36 : 160));
        for (int i = windowStart; i < end; i++) {
            TextView t = PartyUi.text(getContext(), lyrics.lines.get(i).text.isEmpty() ? "♪" : lyrics.lines.get(i).text, 24, lyrics.synced ? PartyUi.MUTED : PartyUi.INK);
            t.setPadding(0, PartyUi.dp(getContext(), 10), 0, PartyUi.dp(getContext(), 10)); rows.addView(t); labels.add(t);
        }
        if (!lyrics.synced && end < lyrics.lines.size()) rows.addView(PartyUi.text(getContext(), "Sangteksten er forkortet på denne skærm", 12, PartyUi.MUTED));
    }
    void updatePosition(double elapsed) {
        int next = lyrics.index(elapsed); if (!lyrics.synced || next == selected) return;
        if (next >= 0 && (next < windowStart || next >= windowStart + labels.size() - 3)) renderWindow(next);
        selected = next;
        for (int i = 0; i < labels.size(); i++) {
            boolean active = i + windowStart == next; TextView t = labels.get(i);
            t.setTextColor(active ? PartyUi.ACCENT : PartyUi.MUTED); t.setTypeface(active ? Typeface.DEFAULT_BOLD : Typeface.DEFAULT);
        }
        if (next >= windowStart && next - windowStart < labels.size()) {
            TextView target = labels.get(next - windowStart); post(() -> smoothScrollTo(0, Math.max(0, target.getTop() - getHeight() / 3)));
        }
    }
}
