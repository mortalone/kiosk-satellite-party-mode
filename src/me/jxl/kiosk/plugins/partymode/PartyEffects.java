// SPDX-License-Identifier: MIT
package me.jxl.kiosk.plugins.partymode;

import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RectF;
import android.os.SystemClock;

/** Native bounded spectrum effects; movement amplitude comes from the shared analyzer. */
final class PartyEffects {
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Path path = new Path();
    private final RectF rect = new RectF();
    private final int[] palette = new int[256];
    private float[] target, levels, waveform, cosines, sines;
    private boolean economy;
    PartyEffects() {
        float[] hsv = new float[] {0, 0.88f, 1};
        for (int i = 0; i < palette.length; i++) { hsv[0] = 165 + i * 185f / 255; palette[i] = Color.HSVToColor(hsv); }
        setEconomy(false);
    }
    void setEconomy(boolean enabled) {
        economy = enabled; int count = enabled ? 32 : 48;
        target = new float[count]; levels = new float[count]; waveform = new float[enabled ? 64 : 96];
        cosines = new float[count]; sines = new float[count];
        for (int i = 0; i < count; i++) { double angle = Math.PI * 2 * i / count - Math.PI / 2; cosines[i] = (float)Math.cos(angle); sines[i] = (float)Math.sin(angle); }
    }
    boolean fresh() { return SystemClock.elapsedRealtime() - lastFrame < 1500; }
    private long lastFrame;
    private int fps = 20;
    private boolean demo;

    void accept(float[] bands, float[] wave, int rate, boolean animated) {
        PartyMotion.sample(bands, target, false); PartyMotion.sample(wave, waveform, true);
        lastFrame = SystemClock.elapsedRealtime();
        fps = Math.max(10, Math.min(30, rate)); demo = animated;
    }
    int frameDelay() { return 1000 / fps; }
    String status() {
        if (SystemClock.elapsedRealtime() - lastFrame > 1500) return "Venter på lyddata fra Visualizer";
        return demo ? "Demo · ikke lydstyret" : "";
    }
    void draw(Canvas c, float width, float height, String mode, boolean playing) {
        boolean fresh = playing && SystemClock.elapsedRealtime() - lastFrame <= 1000;
        float energy = 0;
        for (int i = 0; i < levels.length; i++) {
            float value = fresh ? target[i] : 0;
            levels[i] = levels[i] * (value > levels[i] ? 0.35f : 0.82f) + value * (value > levels[i] ? 0.65f : 0.18f);
            energy += levels[i];
        }
        if (levels.length == 0) return;
        energy /= levels.length;
        double time = SystemClock.elapsedRealtime() / 1000.0;
        paint.setStyle(Paint.Style.FILL);
        if ("spectrum".equals(mode) || "mirror".equals(mode) || "lyrics".equals(mode)) {
            float cell = width / levels.length;
            boolean mirror = "mirror".equals(mode);
            float baseline = mirror ? height * 0.54f : height * 0.92f;
            for (int i = 0; i < levels.length; i++) {
                float x = i * cell, amplitude = levels[i] * height * ("lyrics".equals(mode) ? 0.12f : mirror ? 0.40f : 0.75f);
                paint.setColor(color(i / (float) levels.length, "lyrics".equals(mode) ? 70 : 215));
                c.drawRect(x + cell * 0.15f, baseline - amplitude, x + cell * 0.85f, baseline, paint);
                if (mirror) {
                    paint.setAlpha(85);
                    c.drawRect(x + cell * 0.15f, baseline, x + cell * 0.85f, baseline + amplitude * 0.7f, paint);
                    paint.setAlpha(255);
                }
            }
        } else if ("radial".equals(mode)) {
            float radius = Math.min(width, height) * (0.19f + energy * 0.08f);
            paint.setStyle(Paint.Style.STROKE); paint.setStrokeCap(Paint.Cap.ROUND);
            paint.setStrokeWidth(Math.max(2, Math.min(width, height) / 220));
            for (int i = 0; i < levels.length; i++) {
                float extent = radius + levels[i] * Math.min(width, height) * 0.28f;
                paint.setColor(color(i / (float) levels.length, 220));
                c.drawLine(width / 2 + cosines[i] * radius, height / 2 + sines[i] * radius,
                        width / 2 + cosines[i] * extent, height / 2 + sines[i] * extent, paint);
            }
        } else if ("wave".equals(mode)) {
            paint.setStyle(Paint.Style.STROKE); paint.setStrokeCap(Paint.Cap.ROUND);
            for (int layer = 0; layer < 3; layer++) {
                path.reset();
                for (int i = 0; i < waveform.length; i++) {
                    float x = width * i / Math.max(1, waveform.length - 1);
                    float y = height * 0.52f + (fresh ? waveform[i] : 0) * height * (0.28f - layer * 0.045f);
                    if (i == 0) path.moveTo(x, y); else path.lineTo(x, y);
                }
                paint.setColor(color(0.30f + layer * 0.25f, layer == 0 ? 220 : 95));
                paint.setStrokeWidth(layer == 0 ? 3 : 8); c.drawPath(path, paint);
            }
        } else if ("particles".equals(mode)) {
            for (int i = 0; i < (economy ? 28 : 48); i++) {
                float strength = levels[i % levels.length];
                float phase = (float)((time * (0.08f + strength * 0.13f) + i * 0.618034f) % 1);
                double angle = i * 2.39996 + time * 0.08;
                float distance = phase * Math.max(width, height) * 0.70f;
                float x = width / 2 + (float) Math.cos(angle) * distance;
                float y = height / 2 + (float) Math.sin(angle) * distance;
                paint.setColor(color(i / 48f, (int) (220 * strength * (1 - phase))));
                c.drawCircle(x, y, 2 + strength * 12, paint);
            }
        } else if ("tunnel".equals(mode)) {
            paint.setStyle(Paint.Style.STROKE); paint.setStrokeWidth(2 + energy * 9);
            for (int ring = 0; ring < (economy ? 7 : 10); ring++) {
                float phase = (float)((ring / 10f + time * 0.07f) % 1);
                float radius = phase * Math.max(width, height) * 0.7f;
                paint.setColor(color(ring / 10f, (int) (200 * levels[ring % levels.length] * (1 - phase))));
                rect.set(width / 2 - radius, height / 2 - radius, width / 2 + radius, height / 2 + radius);
                c.drawOval(rect, paint);
            }
        }
        paint.setAlpha(255); paint.setStrokeCap(Paint.Cap.BUTT); paint.setStyle(Paint.Style.FILL);
    }
    private int color(float position, int alpha) {
        int index = Math.max(0, Math.min(255, Math.round(position * 255)));
        return (Math.max(0, Math.min(255, alpha)) << 24) | (palette[index] & 0x00FFFFFF);
    }
}
