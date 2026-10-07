package me.jxl.kiosk.plugins.partymode;
import android.app.Activity;
import android.app.Dialog;
import android.os.Bundle;
import android.os.Handler;
import android.os.SystemClock;
import android.content.*;
import android.graphics.*;
import android.view.*;
import android.view.inputmethod.EditorInfo;
import android.widget.*;
import me.jxl.kiosk.plugins.PluginHost;
import org.json.*;
import java.net.*;
import java.io.*;
import java.lang.reflect.*;
import java.util.*;

/** Emulator-only harness. Never packaged in the plugin or connected to a real HA/MA. */
public final class PartyQaActivity extends Activity {
    private final Handler main = new Handler();
    private final PartyModePlugin plugin = new PartyModePlugin();
    private ServerSocket server;
    private boolean publishedPartyState;
    private final Map<String, Boolean> switches = new HashMap<>();
    private final BroadcastReceiver receiver = new BroadcastReceiver() {
        @Override public void onReceive(Context c, Intent intent) {
            String mode = intent.getStringExtra("mode");
            try {
                call("dismissSearch");
                if ("search".equals(mode) || "placement".equals(mode) || "ai".equals(mode) || "similar".equals(mode)) {
                    call("showSearch"); Dialog dialog = (Dialog)field("searchDialog");
                    if ("ai".equals(mode) && findText(dialog.getWindow().getDecorView(), "AI DJ") == null) throw new AssertionError("AI tab absent");
                    if ("ai".equals(mode)) findText(dialog.getWindow().getDecorView(), "AI DJ").performClick();
                    if ("similar".equals(mode)) findText(dialog.getWindow().getDecorView(), "Similar").performClick();
                    EditText input = findEdit(dialog.getWindow().getDecorView()); input.setText("party"); input.onEditorAction(EditorInfo.IME_ACTION_SEARCH);
                    if ("placement".equals(mode)) main.postDelayed(() -> { Dialog d = (Dialog)field("searchDialog"); TextView t = findText(d.getWindow().getDecorView(), "Aftenlys"); if (t == null) throw new AssertionError("search results absent"); ((View)t.getParent().getParent()).performClick(); }, 700);
                } else if ("searchswitches".equals(mode)) {
                    plugin.onEvent("switch.search_ai", Collections.singletonMap("on", false));
                    main.postDelayed(() -> { try { call("showSearch"); } catch (Exception e) { throw new RuntimeException(e); } }, 300);
                } else if ("settings".equals(mode)) call("showPartyMenu", View.class, new View(PartyQaActivity.this));
                else if ("menucategories".equals(mode)) {
                    plugin.onEvent("switch.menu_visuals", Collections.singletonMap("on", false));
                    plugin.onEvent("switch.menu_guests", Collections.singletonMap("on", false));
                    main.postDelayed(() -> { try { call("showPartyMenu", View.class, new View(PartyQaActivity.this)); } catch(Exception e) { throw new RuntimeException(e); } }, 300);
                } else if ("guestpage".equals(mode)) {
                    plugin.onEvent("select.guest_page", Collections.singletonMap("option", "Party guest page"));
                }
                else if ("playlists".equals(mode)) call("showPlaylists");
                else if ("dj".equals(mode)) call("configureDj");
                else if ("lyrics".equals(mode) || "discolyrics".equals(mode)) call("setPartyEffect", String.class, mode);
                else if ("switch".equals(mode)) {
                    plugin.onEvent("switch.active", Collections.singletonMap("on", false));
                    main.postDelayed(() -> {
                        if (publishedPartyState || Boolean.TRUE.equals(field("partyFullscreen"))) throw new AssertionError("HA switch did not stop Party");
                        plugin.onEvent("switch.active", Collections.singletonMap("on", true));
                    }, 150);
                }
                else if ("main".equals(mode)) call("setPartyEffect", String.class, "mirror");
                main.postDelayed(() -> {
                    PartyView view = (PartyView)field("partyView");
                    if ("searchswitches".equals(mode)) {
                        Dialog panel = (Dialog)field("searchDialog");
                        if (panel == null || hasText(panel.getWindow().getDecorView(), "AI DJ") || !Boolean.FALSE.equals(switches.get("search_ai"))) throw new AssertionError("AI switch did not hide the pill");
                    }
                    if ("menucategories".equals(mode)) {
                        View menu = ((Dialog)field("searchDialog")).getWindow().getDecorView();
                        if (hasText(menu, "VISUALISERING") || hasText(menu, "GÆSTER") || !hasText(menu, "SKÆRM")) throw new AssertionError("hidden categories remained visible");
                        if (!Boolean.FALSE.equals(switches.get("menu_visuals")) || !Boolean.FALSE.equals(switches.get("menu_guests"))) throw new AssertionError("category switches missing");
                    }
                    if ("guestpage".equals(mode) && (!String.valueOf(field("partyGuestUrl")).startsWith("http://127.0.0.1:18095/guest/#token=") || String.valueOf(field("partyGuestUrl")).contains("fixture-token") || field("partyQr") == null)) throw new AssertionError("custom guest QR absent or contains host token");
                    if ("switch".equals(mode) && !publishedPartyState) throw new AssertionError("HA switch did not report Party active");
                    if (view == null) throw new AssertionError("Party root missing");
                    if ("main".equals(mode) && (!switches.containsKey("search_ai") || !switches.containsKey("search_similar") || !switches.containsKey("search_library") || !switches.containsKey("current_similar"))) throw new AssertionError("search switches absent");
                    if ("main".equals(mode) && field("partyQr") == null) throw new AssertionError("MA guest QR absent");
                    if ("main".equals(mode) && hasDescription(getWindow().getDecorView(), "Afslut Party Mode")) throw new AssertionError("default Close visible");
                    if ("settings".equals(mode) && !hasText(((Dialog)field("searchDialog")).getWindow().getDecorView(), "VISUALISERING")) throw new AssertionError("new menu missing");
                    if ("playlists".equals(mode) && !hasText(((Dialog)field("searchDialog")).getWindow().getDecorView(), "Fredagsfest")) throw new AssertionError("favorites missing");
                    if (("lyrics".equals(mode) || "discolyrics".equals(mode)) && (!((PartyLyrics)field("lyrics")).synced || ((PartyLyrics)field("lyrics")).lines.isEmpty())) throw new AssertionError("on-demand MA lyrics not displayed");
                    if ("ai".equals(mode) && !hasText(((Dialog)field("searchDialog")).getWindow().getDecorView(), "Aftenlys")) throw new AssertionError("native AI API results absent");
                    if ("placement".equals(mode) && field("selectionDialog") == null) throw new AssertionError("placement panel missing");
                    android.util.Log.i("PARTY_QA", "QA_READY " + mode + " hardware=" + view.hardwareCanvas());
                }, 1600);
            } catch (Throwable error) { throw new AssertionError("QA " + mode, error); }
        }
    };
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);
        setContentView(new FrameLayout(this)); startServer();
        getSharedPreferences("party_mode_presentation", MODE_PRIVATE).edit().putString("dj_url", "http://127.0.0.1:18095/#token=public-emulator-dj-fixture-token").putBoolean("search_ai", true).commit();
        getSharedPreferences("FlutterSharedPreferences", MODE_PRIVATE).edit().putString("flutter.ks.sendspin.ma_url", "http://127.0.0.1:18095").putString("flutter.ks.sendspin.ma_token", "public-emulator-fixture").commit();
        Map<String,Object> settings = new HashMap<>(); settings.put("speakerEntity", "media_player.qa"); settings.put("startAutomatically", true); settings.put("showGuestQr", true);
        settings.put("screenControls", "Menu only"); settings.put("effect", "mirror"); settings.put("allowSearch", true); settings.put("allowQueueTap", true); settings.put("extraControls", "Playlists and EQ");
        settings.put("volumeControls", "Buttons"); settings.put("tracksBefore", 4); settings.put("tracksAfter", 4);
        plugin.start(new PluginHost() {
            @Override public void executeCommand(String command, Map<String,Object> args, CommandCallback callback) {
                if ("getHaEntityState".equals(command)) {
                    Map<String,Object> attrs = new HashMap<>(); attrs.put("active_queue", "qa-group"); attrs.put("media_title", "Aftenlys"); attrs.put("media_artist", "Natteholdet"); attrs.put("media_content_id", "library://track/4"); attrs.put("media_position", 39); attrs.put("media_duration", 220);
                    Map<String,Object> response = new HashMap<>(); response.put("state", "playing"); response.put("attributes", attrs); callback.onResult(true, response, null);
                } else callback.onResult(true, Collections.emptyMap(), null);
            }
            @Override public void publishSelect(String key, String name, String[] options, String value) {}
            @Override public void publishSwitch(String key, String name, boolean state) { switches.put(key, state); if ("active".equals(key)) publishedPartyState = state; }
            @Override public void subscribe(String event) {} @Override public void unsubscribe(String event) {}
            @Override public void showWindow(String a, String b, String c) {} @Override public void hideWindow() {}
            @Override public void log(String message) { android.util.Log.i("PARTY_QA", message); }
            @Override public void status(String message, boolean error) { android.util.Log.i("PARTY_QA", message); }
        }, settings);
        main.postDelayed(() -> { try { Field f=PartyModePlugin.class.getDeclaredField("currentActivity");f.setAccessible(true);f.set(plugin,this);call("updatePresentation"); }catch(Exception e){throw new RuntimeException(e);} },500);
        registerReceiver(receiver, new IntentFilter("party.qa.MODE"));
        main.postDelayed(new Runnable() { @Override public void run() {
            float[] bands = new float[64], wave = new float[128]; double time = SystemClock.elapsedRealtime() / 800.0;
            for(int i=0;i<bands.length;i++) bands[i]=(float)(0.2+0.7*Math.abs(Math.sin(time+i*0.12)));
            for(int i=0;i<wave.length;i++) wave[i]=(float)(0.5*Math.sin(time+i*0.3));
            sendBroadcast(new Intent("me.jxl.kiosk.plugins.PARTY_AUDIO_FRAME").setPackage(getPackageName()).putExtra("at",SystemClock.elapsedRealtime()).putExtra("bands",bands).putExtra("waveform",wave).putExtra("fps",20));
            main.postDelayed(this,50);
        }}, 1000);
    }
    private Object field(String name) { try { Field f=PartyModePlugin.class.getDeclaredField(name);f.setAccessible(true);return f.get(plugin); } catch(Exception e){throw new RuntimeException(e);} }
    private void call(String name) throws Exception { Method m=PartyModePlugin.class.getDeclaredMethod(name);m.setAccessible(true);m.invoke(plugin); }
    private void call(String name, Class<?> type, Object arg) throws Exception { Method m=PartyModePlugin.class.getDeclaredMethod(name,type);m.setAccessible(true);m.invoke(plugin,arg); }
    private EditText findEdit(View root) { if(root instanceof EditText)return (EditText)root; if(root instanceof ViewGroup)for(int i=0;i<((ViewGroup)root).getChildCount();i++){EditText r=findEdit(((ViewGroup)root).getChildAt(i));if(r!=null)return r;}return null; }
    private TextView findText(View root,String value) { if(root instanceof TextView && value.contentEquals(((TextView)root).getText()))return (TextView)root; if(root instanceof ViewGroup)for(int i=0;i<((ViewGroup)root).getChildCount();i++){TextView r=findText(((ViewGroup)root).getChildAt(i),value);if(r!=null)return r;}return null; }
    private boolean hasText(View v,String s){return findText(v,s)!=null;}
    private boolean hasDescription(View root,String value){if(value.contentEquals(root.getContentDescription()==null?"":root.getContentDescription()))return true;if(root instanceof ViewGroup)for(int i=0;i<((ViewGroup)root).getChildCount();i++)if(hasDescription(((ViewGroup)root).getChildAt(i),value))return true;return false;}
    private JSONObject media(int i) throws Exception {
        String[] names={"Kom indenfor","Efterglød","Nattens puls","Varm vind","Aftenlys","Stjernestøv","Midnat","På vej hjem","Den sidste dans"};
        JSONObject meta=new JSONObject().put("images",new JSONArray().put(new JSONObject().put("type","thumb").put("path","http://127.0.0.1:18095/cover/"+i).put("remotely_accessible",true)));
        // Deliberately no stored lyrics: real MA may return text only on demand.
        return new JSONObject().put("uri","library://track/"+i).put("provider","library").put("item_id",""+i).put("name",names[i%names.length]).put("artists",new JSONArray().put(new JSONObject().put("name","Natteholdet"))).put("metadata",meta).put("available",true);
    }
    private Object response(JSONObject request) throws Exception {
        String cmd=request.optString("command");JSONObject args=request.optJSONObject("args");
        if(cmd.equals("player_queues/get"))return new JSONObject().put("queue_id","qa-group").put("current_index",4).put("items",9).put("elapsed_time",39).put("state","playing").put("current_item",item(4)).put("next_item",item(5));
        if(cmd.equals("player_queues/items")){JSONArray items=new JSONArray();for(int i=args.optInt("offset");i<Math.min(9,args.optInt("offset")+args.optInt("limit"));i++)items.put(item(i));return items;}
        if(cmd.equals("party/player")) return "qa-group";
        if(cmd.equals("party/url")) return "http://192.168.0.18:8095/?join=public-test-code";
        if(cmd.equals("party/config")) return new JSONObject().put("qr_text", "Scan og ønsk musik");
        if(cmd.equals("players/get"))return new JSONObject().put("player_id","qa-group").put("available",true).put("group_volume",42);
        if(cmd.equals("music/search")){JSONArray tracks=new JSONArray();for(int i=4;i<9;i++)tracks.put(media(i));return new JSONObject().put("tracks",tracks);}
        if(cmd.equals("music/playlists/library_items")){JSONArray items=new JSONArray();String[] names={"Fredagsfest","Rolig aften","Sommer i haven"};for(int i=0;i<3;i++)items.put(media(i).put("name",names[i]).put("uri","library://playlist/"+i).put("favorite",true));return items;}
        if(cmd.equals("music/tracks/get"))return media(4);
        if(cmd.equals("metadata/get_track_lyrics")) {
            if (!"library://track/4".equals(args.getJSONObject("track").optString("uri"))) throw new AssertionError("wrong lyrics track");
            return new JSONArray().put(JSONObject.NULL).put("[00:00]Vi tænder lys i byen\n[00:30]Og danser gennem natten\n[00:46]Her er plads til alle\n[01:00]Musikken finder vej\n[01:20]Vi mødes under stjernerne\n[01:40]Og bliver lidt endnu");
        }
        return JSONObject.NULL;
    }
    private JSONObject item(int i)throws Exception{return new JSONObject().put("queue_item_id","q"+i).put("media_item",media(i)).put("duration",220);}
    private void startServer() {
        try { server=new ServerSocket(18095); }catch(IOException error){throw new RuntimeException(error);}
        new Thread(()->{while(!server.isClosed())try{Socket socket=server.accept();new Thread(()->serve(socket)).start();}catch(IOException e){break;}},"qa-ma").start();
    }
    private void serve(Socket socket) { try(Socket s=socket){
        BufferedReader in=new BufferedReader(new InputStreamReader(s.getInputStream(),"UTF-8"));String first=in.readLine(),header,auth="";int length=0;
        while((header=in.readLine())!=null&&!header.isEmpty()) {
            if(header.toLowerCase().startsWith("content-length:"))length=Integer.parseInt(header.substring(15).trim());
            if(header.toLowerCase().startsWith("authorization:"))auth=header.substring(14).trim();
        }
        byte[] data;String content;
        if(first.contains("/api/guest-link")) {
            if (!"Bearer public-emulator-dj-fixture-token".equals(auth)) throw new AssertionError("guest link needs host auth");
            char[] body=new char[length]; int read=0,n; while(read<length&&(n=in.read(body,read,length-read))>0)read+=n;
            JSONObject request=new JSONObject(new String(body,0,read));
            if (!"qa-group".equals(request.optString("queue_id"))) throw new AssertionError("wrong guest queue");
            data=new JSONObject().put("path", "/guest/#token=abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG").toString().getBytes("UTF-8"); content="application/json";
        } else if(first.contains("/api/suggest") || first.contains("/api/jobs/")) {
            if (!"Bearer public-emulator-dj-fixture-token".equals(auth)) throw new AssertionError("DJ API token not sent");
            JSONObject result = new JSONObject().put("id", "fixture-job");
            if (first.contains("/api/jobs/")) result.put("state", "ready").put("tracks", new JSONArray().put(media(4)).put(media(5)));
            data=result.toString().getBytes("UTF-8"); content="application/json";
        }else if(first.startsWith("GET")){
            Bitmap bitmap=Bitmap.createBitmap(160,160,Bitmap.Config.ARGB_8888);Canvas c=new Canvas(bitmap);Paint p=new Paint(3);int i=Character.getNumericValue(first.split(" ")[1].charAt(first.split(" ")[1].length()-1));
            p.setShader(new LinearGradient(0,0,160,160,new int[]{Color.HSVToColor(new float[]{i*37%360,.65f,.85f}),0xFF131A2A},null,Shader.TileMode.CLAMP));c.drawRect(0,0,160,160,p);p.setShader(null);p.setColor(0x8065E5CF);c.drawCircle(80,80,42,p);
            p.setColor(Color.WHITE);p.setTextSize(48);c.drawText("♪",58,98,p);ByteArrayOutputStream bytes=new ByteArrayOutputStream();bitmap.compress(Bitmap.CompressFormat.PNG,100,bytes);data=bytes.toByteArray();content="image/png";
        }else{char[] body=new char[length];int read=0,n;while(read<length&&(n=in.read(body,read,length-read))>0)read+=n;JSONObject request=new JSONObject(new String(body,0,read));data=new JSONObject().put("result",response(request)).toString().getBytes("UTF-8");content="application/json";}
        OutputStream out=s.getOutputStream();out.write(("HTTP/1.1 200 OK\r\nContent-Type: "+content+"\r\nContent-Length: "+data.length+"\r\nConnection: close\r\n\r\n").getBytes("UTF-8"));out.write(data);out.flush();
    }catch(Exception error){android.util.Log.e("PARTY_QA","Mock MA failed",error);} }
}
