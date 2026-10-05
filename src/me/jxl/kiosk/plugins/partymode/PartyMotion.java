// SPDX-License-Identifier: MIT
package me.jxl.kiosk.plugins.partymode;
final class PartyMotion {
    static void sample(float[] source, float[] result, boolean wave) {
        int count = source == null ? 0 : Math.min(128, source.length);
        for (int i = 0; i < result.length; i++) {
            int from = i * count / result.length, to = Math.max(from + 1, (i + 1) * count / result.length);
            float sum = 0; int n = 0;
            for (int j = from; j < to && j < count; j++) {
                float v = source[j]; if (!Float.isFinite(v)) v = 0;
                sum += Math.max(wave ? -1 : 0, Math.min(1, v)); n++;
            }
            result[i] = n == 0 ? 0 : sum / n;
        }
    }
}
