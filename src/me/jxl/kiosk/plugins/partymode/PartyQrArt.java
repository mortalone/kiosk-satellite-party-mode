package me.jxl.kiosk.plugins.partymode;

import io.nayuki.qrcodegen.QrCode;
import io.nayuki.qrcodegen.QrSegment;

/** Deterministic approved small-dot artwork renderer. Called only when the join URL changes. */
final class PartyQrArt {
    static final int SIDE = 1254;
    static int[] render(String url, int[] illustration) {
        if (illustration.length != SIDE * SIDE) throw new IllegalArgumentException("Artwork dimensions");
        QrCode qr = QrCode.encodeSegments(QrSegment.makeSegments(url), QrCode.Ecc.HIGH, 4, 40, -1, false);
        double cell = 1000.0 / qr.size;
        double dotRadius = Math.min(.32, .16 * qr.size / 33.0);
        double contrastEdge = .14 * qr.size / 33.0;
        int[] out = new int[illustration.length];
        for (int y = 127; y < 1127; y++) for (int x = 127; x < 1127; x++) {
            int gx = (int)((x - 127) / cell), gy = (int)((y - 127) / cell);
            double px = 127 + (gx + .5) * cell, py = 127 + (gy + .5) * cell;
            boolean reserved = (gx < 8 && gy < 8) || (gx >= qr.size - 8 && gy < 8) || (gx < 8 && gy >= qr.size - 8);
            int index = y * SIDE + x;
            if (reserved) continue;
            boolean center = ellipse(px, py), bit = qr.getModule(gx, gy);
            double distance = Math.hypot(x - px, y - py) / cell;
            double alpha = center || bit ? 1 : Math.max(0, Math.min(1, (distance - dotRadius) / contrastEdge));
            int art = illustration[index];
            int color = ((int)((art >>> 24) * alpha) << 24) | (art & 0xffffff);
            if (ellipse(x, y)) color = art;
            if (bit && !center && distance <= dotRadius) {
                int sample = illustration[Math.min(SIDE - 1, (int)py) * SIDE + Math.min(SIDE - 1, (int)px)];
                if ((sample >>> 24) < 80) sample = 0xff000000 | ((170 + 80 * gy / qr.size) << 16) | ((230 - 45 * gy / qr.size) << 8) | 255;
                color = 0xff000000 | (light(sample >> 16) << 16) | (light(sample >> 8) << 8) | light(sample);
            }
            out[index] = color;
        }
        for (int[] origin : new int[][]{{0,0},{qr.size-7,0},{0,qr.size-7}}) {
            double left=127+origin[0]*cell, top=127+origin[1]*cell;
            for (int y=(int)top; y<Math.ceil(top+7*cell); y++) for (int x=(int)left; x<Math.ceil(left+7*cell); x++) {
                double dx=x-left,dy=y-top;
                boolean ring=round(dx,dy,7*cell,.6*cell) && !round(dx-cell,dy-cell,5*cell,.3*cell);
                if (ring || round(dx-2*cell,dy-2*cell,3*cell,.4*cell)) out[y*SIDE+x]=gradient(x,y);
            }
        }
        // Keep alignment markers crisp even when artwork crosses their positions.
        int count = qr.version / 7 + 2;
        int step = (qr.version * 8 + count * 3 + 5) / (count * 4 - 4) * 2;
        int[] positions = new int[count]; positions[0] = 6;
        for (int i=count-1,p=qr.size-7;i>=1;i--,p-=step) positions[i]=p;
        for (int i=0;i<count;i++) for(int j=0;j<count;j++) {
            if ((i==0&&j==0)||(i==0&&j==count-1)||(i==count-1&&j==0)) continue;
            double left=127+(positions[i]-2)*cell,top=127+(positions[j]-2)*cell;
            for(int y=(int)Math.ceil(top);y<Math.ceil(top+5*cell);y++)for(int x=(int)Math.ceil(left);x<Math.ceil(left+5*cell);x++) {
                double dx=(x-left)/cell,dy=(y-top)/cell;
                boolean border=dx<1||dy<1||dx>=4||dy>=4;
                out[y*SIDE+x] = border || (dx>=2&&dx<3&&dy>=2&&dy<3) ? gradient(x,y) : 0;
            }
        }
        return out;
    }
    private static int light(int value) { return (int)Math.round((value & 255) * .25 + 255 * .75); }
    private static boolean ellipse(double x,double y) { return Math.pow((x-700)/135,2)+Math.pow((y-670)/160,2)<1; }
    private static boolean round(double x,double y,double side,double radius) {
        if(x<0||y<0||x>=side||y>=side)return false;
        double dx=Math.max(radius-x,Math.max(0,x-(side-radius))),dy=Math.max(radius-y,Math.max(0,y-(side-radius)));
        return dx*dx+dy*dy<=radius*radius;
    }
    private static int gradient(int x,int y) {
        double t=Math.max(0,Math.min(1,(x+y-254)/2000.0));
        int a=t<.5?0xadfff5:0xc4b5ff,b=t<.5?0xc4b5ff:0xfface4;
        double k=t<.5?t*2:(t-.5)*2;
        int r=(int)(((a>>16)&255)*(1-k)+((b>>16)&255)*k),g=(int)(((a>>8)&255)*(1-k)+((b>>8)&255)*k),blue=(int)((a&255)*(1-k)+(b&255)*k);
        return 0xff000000 | r<<16 | g<<8 | blue;
    }
}
