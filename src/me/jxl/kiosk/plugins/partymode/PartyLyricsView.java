// SPDX-License-Identifier: MIT
package me.jxl.kiosk.plugins.partymode;
import android.content.Context;
import android.graphics.Typeface;
import android.graphics.Color;
import android.view.Gravity;
import android.os.SystemClock;
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
    private final boolean disco;
    private long lastPulse;
    PartyLyricsView(Context context, boolean disco) {
        super(context); this.disco = disco; setFillViewport(true); setClipToPadding(false); setVerticalScrollBarEnabled(false);
        rows = new LinearLayout(context); rows.setOrientation(LinearLayout.VERTICAL);
        rows.setPadding(PartyUi.dp(context, 24), PartyUi.dp(context, 100), PartyUi.dp(context, 24), PartyUi.dp(context, 110));
        addView(rows, new ScrollView.LayoutParams(-1, -2)); setContentDescription("Sangtekst fra Music Assistant");
    }
    void setLyrics(PartyLyrics value) {
        if (lyrics == value) return; lyrics = value; selected = -2; plainPage = 0; rows.removeAllViews(); labels.clear();
        if (value.lines.isEmpty()) { rows.addView(PartyUi.text(getContext(), "Ingen sangtekst fra Music Assistant endnu", 20, PartyUi.MUTED)); return; }
        if (!value.synced) rows.addView(PartyUi.text(getContext(), "Sangtekst · uden tidskoder", 12, PartyUi.MUTED));
        // Bound native view count; synced songs retain a moving window around the current line.
        renderWindow(value.synced ? 0 : -1);
    }
    private int windowStart, plainPage;
    private void renderWindow(int center) {
        rows.removeAllViews(); labels.clear();
        if (!lyrics.synced) rows.addView(PartyUi.text(getContext(), "Sangtekst · uden tidskoder", 12, PartyUi.MUTED));
        windowStart = lyrics.synced ? Math.max(0, center - 12) : plainPage * 160;
        int end = Math.min(lyrics.lines.size(), windowStart + (lyrics.synced ? 36 : 160));
        for (int i = windowStart; i < end; i++) {
            TextView t = PartyUi.text(getContext(), lyrics.lines.get(i).text.isEmpty() ? "♪" : lyrics.lines.get(i).text, disco ? 34 : 24, lyrics.synced ? PartyUi.MUTED : PartyUi.INK);
            if (disco) { t.setGravity(Gravity.CENTER); t.setAlpha(lyrics.synced ? 0.45f : 1f); }
            t.setPadding(0, PartyUi.dp(getContext(), 10), 0, PartyUi.dp(getContext(), 10)); rows.addView(t); labels.add(t);
        }
        if (!lyrics.synced && plainPage > 0) {
            TextView previous = PartyUi.action(getContext(), "← Tidligere linjer", false); rows.addView(previous);
            previous.setOnClickListener(v -> { plainPage--; renderWindow(-1); scrollTo(0, 0); });
        }
        if (!lyrics.synced && end < lyrics.lines.size()) {
            TextView more = PartyUi.action(getContext(), "Flere linjer →", false); rows.addView(more);
            more.setOnClickListener(v -> { plainPage++; renderWindow(-1); scrollTo(0, 0); });
        }
    }
    void updatePosition(double elapsed) {
        int next = lyrics.index(elapsed); if (!lyrics.synced || next == selected) return;
        if (next >= 0 && (next < windowStart || next >= windowStart + labels.size() - 3)) renderWindow(next);
        selected = next;
        for (int i = 0; i < labels.size(); i++) {
            boolean active = i + windowStart == next; TextView t = labels.get(i);
            if (disco) { t.setAlpha(active ? 1f : 0.45f); t.setScaleX(1f); t.setScaleY(1f); t.setShadowLayer(active ? 14f : 0f, 0, 0, PartyUi.ACCENT); }
            t.setTextColor(active ? PartyUi.ACCENT : PartyUi.MUTED); t.setTypeface(active ? Typeface.DEFAULT_BOLD : Typeface.DEFAULT);
        }
        if (next >= windowStart && next - windowStart < labels.size()) {
            TextView target = labels.get(next - windowStart); post(() -> smoothScrollTo(0, Math.max(0, target.getTop() - getHeight() / 3)));
        }
    }
    void acceptAudio(float[] bands) {
        if (!disco || !lyrics.synced || selected < windowStart || selected - windowStart >= labels.size()) return;
        long now = SystemClock.elapsedRealtime(); if (now - lastPulse < 80) return; lastPulse = now;
        float energy = 0; int count = bands == null ? 0 : Math.min(8, bands.length);
        for (int i = 0; i < count; i++) if (!Float.isNaN(bands[i]) && !Float.isInfinite(bands[i])) energy += Math.max(0, Math.min(1, bands[i]));
        energy = count == 0 ? 0 : energy / count;
        TextView active = labels.get(selected - windowStart);
        int neon = Color.HSVToColor(new float[]{(selected * 47) % 360, 0.65f, 1f});
        active.setTextColor(neon); active.setShadowLayer(6 + 14 * energy, 0, 0, neon);
        float scale = 1 + 0.06f * energy; active.setScaleX(scale); active.setScaleY(scale);
    }

}
