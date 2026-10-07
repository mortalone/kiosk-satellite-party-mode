package me.jxl.kiosk.plugins.partymode;

import java.awt.image.BufferedImage;
import java.io.File;
import javax.imageio.ImageIO;

/** Desktop harness for the same pixel renderer used on Android. No network or live guest tokens. */
public final class PartyQrArtTest {
    public static void main(String[] args) throws Exception {
        BufferedImage source = ImageIO.read(new File("artwork/guest-speaker.png"));
        int[] art = new int[PartyQrArt.SIDE * PartyQrArt.SIDE];
        for(int y=0;y<PartyQrArt.SIDE;y++)for(int x=0;x<PartyQrArt.SIDE;x++)
            art[y*PartyQrArt.SIDE+x]=source.getRGB(x*source.getWidth()/PartyQrArt.SIDE,y*source.getHeight()/PartyQrArt.SIDE);
        String[] urls={
            "http://192.168.0.18:8103/guest/",
            "http://127.0.0.1:18095/guest/#token=fixture-queue-capability-0123456789abcdef0123456789abcdef",
            "https://smart.e-cart.dk/music/guest?player=fixture-group&token=0123456789abcdef0123456789abcdef",
            "http://192.168.0.18:8095/guest?player_id=fixture-party-player",
            "https://party.example.test/guest/#token=fixture_ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789_ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789_ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789"
        };
        File out=new File("dist/qa/qr-art");out.mkdirs();
        for(int i=0;i<urls.length;i++){
            int[] pixels=PartyQrArt.render(urls[i],art);
            if(pixels[0]!=0)throw new AssertionError("quiet zone must be transparent");
            BufferedImage image=new BufferedImage(PartyQrArt.SIDE,PartyQrArt.SIDE,BufferedImage.TYPE_INT_ARGB);
            image.setRGB(0,0,PartyQrArt.SIDE,PartyQrArt.SIDE,pixels,0,PartyQrArt.SIDE);
            ImageIO.write(image,"PNG",new File(out,i+".png"));
            java.nio.file.Files.write(new File(out,i+".txt").toPath(),urls[i].getBytes(java.nio.charset.StandardCharsets.UTF_8));
        }
        System.out.println("Native artwork renderer fixtures written");
    }
}
