// SPDX-License-Identifier: MIT
package me.jxl.kiosk.plugins.partymode;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.Rect;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.os.SystemClock;
import android.text.TextPaint;
import android.text.TextUtils;
import android.view.View;
import android.widget.FrameLayout;
import android.view.MotionEvent;
import java.util.ArrayList;
import java.util.List;
import java.util.function.Consumer;
import java.util.Collections;
import java.util.Map;

final class PartyView extends FrameLayout {
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.FILTER_BITMAP_FLAG);
    private final TextPaint text = new TextPaint(Paint.ANTI_ALIAS_FLAG);
    private final RectF rect = new RectF();
    private final Path clip = new Path();
    private final boolean fullscreen;
    private PartyQueueModel model = new PartyQueueModel(Collections.emptyList(), 0, 0, "");
    private Map<String, Bitmap> artwork = Collections.emptyMap();
    private Bitmap background;
    private String backgroundKey = "";
    private String message = "Henter afspilningskø…";
    private long anchor;
    private boolean playing;
    private String effect = "off";
    private boolean queueVisible = true;
    private Bitmap guestQr;
    private String guestText = "", guestStatus = "";
    private final PartyEffects effects = new PartyEffects();
    private boolean framePending;
    private long lastDraw;
    private View queueCanvas, progressCanvas;
    private boolean hardwareCanvas;
    boolean hardwareCanvas() { return hardwareCanvas; }
    void setEconomy(boolean economy) { effects.setEconomy(economy); }
    double elapsedSeconds() { return model.elapsed + (playing ? Math.max(0, SystemClock.elapsedRealtime() - anchor) / 1000.0 : 0); }
    private void dirtyQueue() { if (queueCanvas != null) queueCanvas.invalidate(); if (progressCanvas != null) progressCanvas.invalidate(); }
    private final RectF progressRect = new RectF();
    private final List<RectF> hitRects = new ArrayList<>();
    private final List<String> hitIds = new ArrayList<>();
    private Consumer<String> trackAction;
    private float scrollOffset, maxScroll, touchY, lastTouchY;
    private boolean scrolling;
    private String currentId = "";
    private final Runnable redraw = () -> { framePending = false; invalidate(); if (progressCanvas != null) progressCanvas.invalidate(); };
    private void requestFrame() {
        if (framePending) return;
        framePending = true;
        long delay = Math.max(0, effects.frameDelay() - (SystemClock.elapsedRealtime() - lastDraw));
        postOnAnimationDelayed(redraw, delay);
    }
    void setTrackAction(Consumer<String> action) { trackAction = action; dirtyQueue(); requestFrame(); }
    @Override public boolean onTouchEvent(MotionEvent event) {
        switch (event.getActionMasked()) {
            case MotionEvent.ACTION_DOWN:
                touchY = lastTouchY = event.getY(); scrolling = false; return true;
            case MotionEvent.ACTION_MOVE:
                if (Math.abs(event.getY() - touchY) > 8 * getResources().getDisplayMetrics().density) scrolling = true;
                if (scrolling && maxScroll > 0) {
                    scrollOffset = Math.max(0, Math.min(maxScroll, scrollOffset + lastTouchY - event.getY()));
                    dirtyQueue(); requestFrame();
                }
                lastTouchY = event.getY(); return true;
            case MotionEvent.ACTION_UP:
                if (!scrolling && trackAction != null) for (int i = 0; i < hitRects.size(); i++)
                    if (hitRects.get(i).contains(event.getX(), event.getY())) { performClick(); trackAction.accept(hitIds.get(i)); break; }
                return true;
            case MotionEvent.ACTION_CANCEL: return true;
        }
        return super.onTouchEvent(event);
    }
    @Override public boolean performClick() { super.performClick(); return true; }
    @Override protected void onSizeChanged(int w, int h, int oldw, int oldh) {
        dirtyQueue();  super.onSizeChanged(w, h, oldw, oldh);
    }

    PartyView(Context context, boolean fullscreen) {
        super(context); this.fullscreen = fullscreen;
        setContentDescription(fullscreen ? "Party Mode" : "Kompakt Party-kø"); setWillNotDraw(false);
        setLayerType(View.LAYER_TYPE_NONE, null); // Use the host's hardware Canvas without a full-screen offscreen layer.
        queueCanvas = new View(context) {
            @Override protected void onDraw(Canvas canvas) {
                progressRect.setEmpty(); hitRects.clear(); hitIds.clear(); drawQueue(canvas); progressCanvas.invalidate();
            }
        };
        progressCanvas = new View(context) {
            @Override protected void onDraw(Canvas canvas) { drawProgress(canvas); }
        };
        queueCanvas.setClickable(false); progressCanvas.setClickable(false);
        addView(queueCanvas, new FrameLayout.LayoutParams(-1, -1)); addView(progressCanvas, new FrameLayout.LayoutParams(-1, -1));
    }

    void setQueue(PartyQueueModel model, Map<String, Bitmap> artwork, boolean playing) {
        if (this.model != model || this.playing != playing) anchor = SystemClock.elapsedRealtime();
        if (!sameTracks(this.model, model) || !this.artwork.equals(artwork)) dirtyQueue();
        String selected = ""; for (PartyQueueModel.Track track : model.tracks) if (track.current) selected = track.id;
        if (!selected.equals(currentId)) { currentId = selected; scrollOffset = -1; }
        this.model = model; this.artwork = artwork; this.playing = playing;
        String key = "";
        for (PartyQueueModel.Track track : model.tracks) if (track.current) key = track.artwork;
        Bitmap cover = artwork.get(key);
        if (cover != null && !key.equals(backgroundKey)) {
            Bitmap small = Bitmap.createScaledBitmap(cover, 18, 18, true);
            background = Bitmap.createBitmap(18, 18, Bitmap.Config.ARGB_8888);
            Canvas blend = new Canvas(background); blend.drawColor(0xFF15171A);
            Paint tint = new Paint(Paint.FILTER_BITMAP_FLAG); tint.setAlpha("off".equals(effect) ? 130 : 45);
            blend.drawBitmap(small, 0, 0, tint); blend.drawColor(0xA8000000);
            backgroundKey = key;
        } else if (key.isEmpty() || !key.equals(backgroundKey)) {
            background = null; backgroundKey = "";
        }
        if (model.tracks.isEmpty()) message = "Afspilningskøen er tom";
        requestFrame();
    }

    void setMessage(String value) { if (!value.equals(message)) { message = value; dirtyQueue(); requestFrame(); } }

    void setPresentation(String effect, boolean queueVisible) {
        String next = PartySignal.effect(effect);
        if (!next.equals(this.effect) || this.queueVisible != queueVisible) dirtyQueue();
        this.effect = next; this.queueVisible = queueVisible; requestFrame();
    }
    void setGuests(Bitmap qr, String caption, String status) {
        if (guestQr != qr || !guestText.equals(caption)) { guestQr = qr; guestText = caption; dirtyQueue(); requestFrame(); }
    }
    void acceptAudio(float[] bands, float[] wave, int fps, boolean demo) {
        effects.accept(bands, wave, fps, demo); if (playing) requestFrame();
    }
    @Override protected void onDetachedFromWindow() {
        removeCallbacks(redraw); framePending = false;  super.onDetachedFromWindow();
    }

    @Override protected void onDraw(Canvas canvas) {
        super.onDraw(canvas); lastDraw = SystemClock.elapsedRealtime(); hardwareCanvas = canvas.isHardwareAccelerated();
        float density = getResources().getDisplayMetrics().density;
        float sp = getResources().getDisplayMetrics().scaledDensity;
        if (fullscreen) {
            if (background != null) {
                paint.setAlpha(255); rect.set(0, 0, getWidth(), getHeight()); canvas.drawBitmap(background, null, rect, paint);
            } else canvas.drawColor(0xFF15171A);
            if (!"off".equals(effect)) {
                effects.draw(canvas, getWidth(), getHeight(), effect, playing);

                String status = effects.status();
                if (!"lyrics".equals(effect) && !status.isEmpty()) line(canvas, status, 14 * density, getHeight() - 14 * density,
                        getWidth() - 82 * density, 12 * sp, false, 0xDDFFFFFF);
            }
        }
        if (playing && !"off".equals(effect) && effects.fresh()) requestFrame();
        else if (playing && !framePending) { framePending = true; postDelayed(redraw, 1000); }
    }
    private static boolean sameTracks(PartyQueueModel a, PartyQueueModel b) {
        if (a.tracks.size() != b.tracks.size()) return false;
        for (int i = 0; i < a.tracks.size(); i++) {
            PartyQueueModel.Track x = a.tracks.get(i), y = b.tracks.get(i);
            if (!x.id.equals(y.id) || !x.title.equals(y.title) || !x.artist.equals(y.artist) || !x.artwork.equals(y.artwork) || x.current != y.current) return false;
        }
        return true;
    }
    private void drawProgress(Canvas canvas) {
        if (progressRect.isEmpty() || model.duration <= 0) return;
        float progress = (float) Math.max(0, Math.min(1, elapsedSeconds() / model.duration));
        paint.setColor(0x4465E5CF); canvas.drawRect(progressRect, paint);
        paint.setColor(PartyUi.ACCENT); canvas.drawRect(progressRect.left, progressRect.top, progressRect.left + progressRect.width() * progress, progressRect.bottom, paint);
    }
    private void drawQueue(Canvas canvas) {
        float density = getResources().getDisplayMetrics().density;
        float sp = getResources().getDisplayMetrics().scaledDensity;
        float areaLeft = 0, areaTop = 0, areaWidth = getWidth(), areaHeight = getHeight();
        if (fullscreen && guestQr != null && !"lyrics".equals(effect)) {
            boolean landscape = getWidth() >= getHeight();
            float side = Math.min(getWidth() * (landscape ? 0.27f : 0.46f), getHeight() * (landscape ? 0.55f : 0.26f));
            float x = landscape ? Math.max(16 * density, getWidth() * 0.035f) : (getWidth() - side) / 2;
            float y = landscape ? (getHeight() - side) / 2 - 18 * density : 64 * density;
            rect.set(x, y, x + side, y + side);
            paint.setAlpha(255); paint.setFilterBitmap(false);
            canvas.drawBitmap(guestQr, null, rect, paint);
            paint.setFilterBitmap(true);
            line(canvas, guestText, x, y + side + 25 * density,
                    Math.max(side, getWidth() * 0.30f), 14 * sp, false, Color.WHITE);
            if (landscape) {
                areaLeft = x + side + 24 * density;
                areaWidth = getWidth() - areaLeft;
            } else {
                areaTop = y + side + 44 * density;
                areaHeight = getHeight() - areaTop;
            }
        }
        if (model.tracks.isEmpty()) {
            line(canvas, message, areaLeft + 20 * density, areaTop + areaHeight / 2f, areaWidth - 40 * density,
                    (fullscreen ? 20 : 15) * sp, false, Color.WHITE);
            return;
        }
        java.util.List<PartyQueueModel.Track> tracks = model.tracks;
        if (fullscreen && (!queueVisible || "lyrics".equals(effect))) {
            java.util.List<PartyQueueModel.Track> selected = new java.util.ArrayList<>();
            for (PartyQueueModel.Track track : tracks) if (track.current) selected.add(track);
            tracks = selected;
        }
        float margin = (fullscreen ? 32 : 4) * density;
        float width = areaWidth - margin * 2;
        float neighbor = (fullscreen ? 56 : 30) * density;
        float current = (fullscreen ? queueVisible ? 112 : 88 : 76) * density;
        float gap = 4 * density;
        float desired = current + neighbor * (tracks.size() - 1) + gap * (tracks.size() - 1);
        float maxHeight = Math.max(1, areaHeight - (fullscreen ? 32 : 8) * density);
        float total = desired;
        maxScroll = Math.max(0, total - maxHeight);
        int currentIndex = 0;
        for (int i = 0; i < tracks.size(); i++) if (tracks.get(i).current) currentIndex = i;
        if (scrollOffset < 0) scrollOffset = Math.max(0, Math.min(maxScroll, currentIndex * (neighbor + gap) - (maxHeight - current) / 2));
        scrollOffset = Math.max(0, Math.min(maxScroll, scrollOffset));
        float y = "lyrics".equals(effect) ? Math.max(0, getHeight() - current - 14 * density) : areaTop + (maxScroll > 0 ? 16 * density - scrollOffset : (areaHeight - total) / 2);
        int queueSave = canvas.save(); canvas.clipRect(areaLeft, areaTop, areaLeft + areaWidth, areaTop + areaHeight);
        for (int i = 0; i < tracks.size(); i++) {
            PartyQueueModel.Track track = tracks.get(i);
            boolean active = track.current;
            float height = active ? current : neighbor;
            float inset = active ? 0 : width * (float)(0.28 * (1 - Math.exp(-Math.abs(i - currentIndex) * 0.24)));
            float x = areaLeft + margin + inset;
            float cardWidth = width - inset * 2;
            int alpha = active ? 235 : Math.max(95, 200 - Math.abs(i - currentIndex) * 13);
            if (!active && trackAction != null && !track.id.isEmpty()) {
                hitRects.add(new RectF(x, Math.max(areaTop, y), x + cardWidth, Math.min(areaTop + areaHeight, y + height)));
                hitIds.add(track.id);
            }
            paint.setColor(Color.argb(alpha, 28, 38, 49));
            rect.set(x, y, x + cardWidth, y + height);
            canvas.drawRoundRect(rect, 9 * density, 9 * density, paint);
            float pad = (active ? 6 : 3) * density;
            float coverSize = Math.max(1, height - pad * 2);
            float coverX = x + pad;
            float coverY = y + pad;
            Bitmap cover = artwork.get(track.artwork);
            rect.set(coverX, coverY, coverX + coverSize, coverY + coverSize);
            paint.setColor(0xFF35383D);
            canvas.drawRoundRect(rect, 5 * density, 5 * density, paint);
            if (cover != null) {
                int side = Math.min(cover.getWidth(), cover.getHeight());
                Rect crop = new Rect((cover.getWidth() - side) / 2, (cover.getHeight() - side) / 2,
                        (cover.getWidth() + side) / 2, (cover.getHeight() + side) / 2);
                clip.reset(); clip.addRoundRect(rect, 5 * density, 5 * density, Path.Direction.CW);
                int save = canvas.save(); canvas.clipPath(clip);
                paint.setAlpha(active ? 255 : 190);
                canvas.drawBitmap(cover, crop, rect, paint);
                paint.setAlpha(255); canvas.restoreToCount(save);
            }
            float tx = coverX + coverSize + 10 * density;
            float textWidth = Math.max(1, x + cardWidth - tx - 12 * density);
            float titleSize = (active ? fullscreen ? 28 : 19 : fullscreen ? 18 : 13.5f) * sp;
            float titleY = active ? y + height * 0.40f : y + height * 0.66f;
            line(canvas, track.title, tx, titleY, textWidth, titleSize, active,
                    active ? Color.WHITE : 0xDDFFFFFF);
            if (active && !track.artist.isEmpty()) {
                line(canvas, track.artist, tx, y + height * 0.71f, textWidth,
                        (fullscreen ? 18 : 13) * sp, false, 0xFFE0E0E0);
            }
            if (active && model.duration > 0 && y + height <= areaTop + areaHeight && y + height >= areaTop)
                progressRect.set(x, y + height - 3 * density, x + cardWidth, y + height);
            y += height + gap;
        }
        canvas.restoreToCount(queueSave);
    }

    private void line(Canvas canvas, String value, float x, float baseline, float width,
            float size, boolean bold, int color) {
        text.setTextSize(size); text.setColor(color);
        text.setTypeface(bold ? Typeface.DEFAULT_BOLD : Typeface.DEFAULT);
        canvas.drawText(TextUtils.ellipsize(value, text, width, TextUtils.TruncateAt.END).toString(), x, baseline, text);
    }
}
