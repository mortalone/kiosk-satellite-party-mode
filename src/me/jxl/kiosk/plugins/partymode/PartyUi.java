// SPDX-License-Identifier: MIT
package me.jxl.kiosk.plugins.partymode;

import android.app.Activity;
import android.app.Dialog;
import android.content.Context;
import android.content.res.ColorStateList;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.view.Gravity;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

final class PartyUi {
    static final int ACCENT = 0xFF65E5CF, INK = 0xFFF4F6F8, MUTED = 0xFF9CA7B6, SURFACE = 0xFF171D26;
    static int dp(Context c, float v) { return Math.round(v * c.getResources().getDisplayMetrics().density); }
    static GradientDrawable shape(Context c, int color, int radius, boolean border) {
        GradientDrawable bg = new GradientDrawable(); bg.setColor(color); bg.setCornerRadius(dp(c, radius));
        if (border) bg.setStroke(dp(c, 1), 0xFF313C49); return bg;
    }
    static TextView text(Context c, String value, float size, int color) {
        TextView t = new TextView(c); t.setText(value); t.setTextSize(size); t.setTextColor(color); return t;
    }
    static TextView action(Context c, String label, boolean chosen) {
        TextView t = text(c, label, 15, chosen ? ACCENT : INK); t.setGravity(Gravity.CENTER_VERTICAL);
        t.setPadding(dp(c, 16), dp(c, 12), dp(c, 16), dp(c, 12)); t.setMinHeight(dp(c, 48));
        t.setBackground(new RippleDrawable(ColorStateList.valueOf(0x3365E5CF), shape(c, chosen ? 0xFF213F3D : 0xFF222C38, 16, true), null));
        return t;
    }
    static ImageView icon(Context c, String kind, String description) {
        ImageView v = new ImageView(c); v.setImageDrawable(new Glyph(kind)); v.setContentDescription(description);
        v.setPadding(dp(c, 13), dp(c, 13), dp(c, 13), dp(c, 13));
        v.setBackground(new RippleDrawable(ColorStateList.valueOf(0x3365E5CF), shape(c, 0xD9222C38, 24, false), null));
        return v;
    }
    static Dialog sheet(Activity a, String title, LinearLayout contents, boolean drawer) {
        Dialog d = new Dialog(a); d.requestWindowFeature(Window.FEATURE_NO_TITLE);
        LinearLayout shell = new LinearLayout(a); shell.setOrientation(LinearLayout.VERTICAL);
        shell.setPadding(dp(a, 16), dp(a, 14), dp(a, 16), dp(a, 16)); shell.setBackground(shape(a, SURFACE, 26, true));
        LinearLayout header = new LinearLayout(a); header.setGravity(Gravity.CENTER_VERTICAL);
        ImageView back = icon(a, "back", "Luk panel"); header.addView(back, new LinearLayout.LayoutParams(dp(a, 48), dp(a, 48)));
        TextView heading = text(a, title, 22, INK); heading.setPadding(dp(a, 12), 0, 0, 0);
        header.addView(heading, new LinearLayout.LayoutParams(0, dp(a, 56), 1)); heading.setGravity(Gravity.CENTER_VERTICAL);
        shell.addView(header); shell.addView(contents, new LinearLayout.LayoutParams(-1, 0, 1));
        back.setOnClickListener(v -> d.dismiss()); d.setContentView(shell);
        Window w = d.getWindow();
        if (w != null) {
            w.setBackgroundDrawableResource(android.R.color.transparent); w.addFlags(WindowManager.LayoutParams.FLAG_DIM_BEHIND);
            WindowManager.LayoutParams lp = w.getAttributes(); lp.dimAmount = 0.5f;
            lp.width = Math.min(dp(a, drawer ? 420 : 560), a.getResources().getDisplayMetrics().widthPixels - dp(a, 24));
            lp.height = Math.min(dp(a, 720), a.getResources().getDisplayMetrics().heightPixels - dp(a, 64));
            lp.gravity = drawer ? Gravity.RIGHT | Gravity.CENTER_VERTICAL : Gravity.CENTER;
            w.setAttributes(lp); w.setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE | WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_HIDDEN);
            w.setNavigationBarColor(SURFACE);
        }
        d.setOnShowListener(dialog -> {
            if (drawer) { shell.setTranslationX(dp(a, 96)); shell.animate().translationX(0).setDuration(190).start(); }
            else { shell.setTranslationY(dp(a, 24)); shell.animate().translationY(0).setDuration(170).start(); }
        });
        d.setCanceledOnTouchOutside(true); return d;
    }
    static final class Glyph extends Drawable {
        final String kind; final Paint p = new Paint(Paint.ANTI_ALIAS_FLAG); final Path path = new Path();
        Glyph(String kind) { this.kind = kind; }
        @Override public void draw(Canvas c) {
            int save = c.save(); c.translate(getBounds().left, getBounds().top); c.scale(getBounds().width() / 24f, getBounds().height() / 24f);
            p.setColor(INK); p.setStrokeWidth(1.9f); p.setStyle(Paint.Style.STROKE); p.setStrokeCap(Paint.Cap.ROUND); p.setStrokeJoin(Paint.Join.ROUND);
            path.reset();
            if ("search".equals(kind)) { c.drawCircle(10, 10, 6.6f, p); c.drawLine(15, 15, 21, 21, p); }
            else if ("close".equals(kind)) { c.drawLine(6, 6, 18, 18, p); c.drawLine(18, 6, 6, 18, p); }
            else if ("minus".equals(kind) || "plus".equals(kind)) { c.drawLine(5, 12, 19, 12, p); if ("plus".equals(kind)) c.drawLine(12, 5, 12, 19, p); }
            else if ("back".equals(kind)) { path.moveTo(13, 5); path.lineTo(6, 12); path.lineTo(13, 19); c.drawPath(path, p); c.drawLine(6, 12, 20, 12, p); }
            else if ("play".equals(kind)) { p.setStyle(Paint.Style.FILL); path.moveTo(8, 4); path.lineTo(21, 12); path.lineTo(8, 20); path.close(); c.drawPath(path, p); }
            else if ("pause".equals(kind)) { p.setStyle(Paint.Style.FILL); c.drawRoundRect(6, 4, 10, 20, 1, 1, p); c.drawRoundRect(14, 4, 18, 20, 1, 1, p); }
            else if ("stop".equals(kind)) { p.setStyle(Paint.Style.FILL); c.drawRoundRect(5, 5, 19, 19, 2, 2, p); }
            else if ("playlist".equals(kind)) { for (int i = 0; i < 3; i++) c.drawLine(4, 6 + i * 5, 14, 6 + i * 5, p); c.drawLine(20, 8, 20, 18, p); c.drawCircle(17.5f, 18, 2.5f, p); }
            else { c.drawCircle(12, 12, 4, p); for (int i = 0; i < 8; i++) { double angle = i * Math.PI / 4; c.drawLine(12 + (float)Math.cos(angle) * 8, 12 + (float)Math.sin(angle) * 8, 12 + (float)Math.cos(angle) * 10, 12 + (float)Math.sin(angle) * 10, p); } c.drawCircle(12, 12, 8, p); }
            c.restoreToCount(save);
        }
        @Override public void setAlpha(int alpha) { p.setAlpha(alpha); }
        @Override public void setColorFilter(android.graphics.ColorFilter filter) { p.setColorFilter(filter); }
        @Override public int getOpacity() { return android.graphics.PixelFormat.TRANSLUCENT; }
    }
}
