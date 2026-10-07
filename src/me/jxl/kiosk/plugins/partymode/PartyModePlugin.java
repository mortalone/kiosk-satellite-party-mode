// SPDX-License-Identifier: MIT
package me.jxl.kiosk.plugins.partymode;

import android.app.Activity;
import android.app.Dialog;
import android.content.res.ColorStateList;
import android.graphics.Typeface;
import android.widget.ImageView;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.widget.EditText;
import android.widget.ScrollView;
import android.app.Application;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.SeekBar;
import android.widget.TextView;
import io.nayuki.qrcodegen.QrCode;
import me.jxl.kiosk.plugins.KioskPlugin;
import me.jxl.kiosk.plugins.PluginHost;
import org.json.JSONArray;
import org.json.JSONObject;
import org.json.JSONTokener;
import java.io.InputStream;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.net.HttpURLConnection;
import java.net.URL;
import java.time.LocalTime;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

/** Full-screen Party is independent of Now Playing and screensaver visibility. */
public final class PartyModePlugin implements KioskPlugin {
    private static final String PARTY_PREFS = "party_mode_presentation";
    private static final String PARTY_EVENT = "me.jxl.kiosk.plugins.PARTY_PRESENTATION_CHANGED";
    private final Handler main = new Handler(Looper.getMainLooper());
    private final PartyActivation activation = new PartyActivation();
    private PluginHost host;
    private Context context;
    private Application application;
    private Application.ActivityLifecycleCallbacks lifecycle;
    private Activity currentActivity, partyActivity;
    private ExecutorService io, artIo, partyPolicyIo;
    private BroadcastReceiver partyAudioReceiver;
    private FrameLayout partyRoot;
    private PartyView partyView;
    private boolean partyFullscreen, automatic, onlyPlaying, showPaused = true;
    private String screenControls = "All controls";
    private boolean showVolume = true, showPlayback = true, volumeDragging, playerCommandPending, playerVolumePending;
    private int playerVolume = -1;
    private long playerVolumeLastPoll, playerVolumeLastSuccess;
    private long playerVolumeRevision;
    private SeekBar volumeSlider;
    private TextView volumeLabel;
    private ImageView playbackButton, stopButton, volumeMinus, volumePlus;
    private String volumeStyle = "Buttons";
    private boolean showPlaylists = true;
    private String volumeDragQueue = "";
    private String nowPlayingEntity = "", visibilityEntity = "", visibilityCondition = "Always", visibilityValue = "", visibilityState = "";
    private String mediaState = "", mediaIdentity = "";
    private Map<?, ?> mediaAttributes = Collections.emptyMap();
    private boolean mediaPending, visibilityPending;
    private final Set<String> subscriptions = new HashSet<>();
    private String maBaseUrl = "", maToken = "", haBaseUrl = "";
    private String partyEffect = "off";
    private boolean partyGuestsFollow = true, partyQueueVisible = true;
    private int gain = 3, fps = 20;
    private boolean settingFpsEconomy;
    private boolean allowSearch = true, searchLibrary = true, searchSimilar = true, searchAi = true, currentSimilar = true, allowQueueTap, showQuickActions, showEqControls, eqPending;
    private int tracksBefore = 2, tracksAfter = 2;
    private Dialog searchDialog, selectionDialog;
    private PartyLyricsView lyricsView;
    private JSONObject partyTrackMedia;
    private PartyLyrics lyrics = PartyLyrics.parse("", "");
    private String lyricsTrack = "", lyricsContent = "";
    private boolean lyricsPending;
    private long lyricsLastPoll, lyricsGeneration;
    private final Runnable lyricTick = new Runnable() {
        @Override public void run() {
            if (host == null || !partyFullscreen || !PartySignal.lyrics(partyEffect) || lyricsView == null) return;
            lyricsView.updatePosition(partyView == null ? estimatedMediaPosition() : partyView.elapsedSeconds());
            main.postDelayed(this, 250);
        }
    };
    private long searchGeneration;
    private String reportedGuestStatus = "";
    private Boolean reportedPartyState;
    private Boolean guestAccessState, reportedGuestAccess, reportedGuestQr;
    private String guestAccessQueue = "";
    private boolean guestStatePending;
    private long guestStateLastPoll, guestAccessRevision;
    private String reportedPartyEffect;
    private String reportedSearchModes = "";
    private String guestPage = "Music Assistant", reportedGuestPage = "", reportedMenuCategories = "";
    private final String[] menuKeys = {"visuals", "music", "screen", "guests", "sound", "diagnostics"};
    private final String[] menuNames = {"Visualisering", "Musik og AI-forbindelse", "Skærm og betjening", "Gæster og QR", "Lyd og EQ", "Grafik og status"};
    private final Set<String> menuCategories = new HashSet<>();
    private long foregroundUntil, foregroundLastTry, partyPolicyLastPoll;
    private boolean partyPolicyPending;
    private String reportedPartyPolicy = "";
    private boolean partyPollPending, partyGuestPending, partyGuestChangePending;
    private long partyLastPoll, partyLastSuccess, partyGuestLastPoll, partyGuestLastSuccess, partyLastPostpone;
    private volatile long partyGeneration, partyGuestGeneration;
    private String partyTarget = "", partyGuestUrl = "", partyGuestStatus = "", partyGuestText = "Scan og tilføj musik til køen";
    private Bitmap partyQr;
    private PartyQueueModel partyModel;
    private final Map<String, Bitmap> partyArtwork = new HashMap<>();
    private final Set<String> partyArtworkPending = new HashSet<>();
    private double positionAnchor;
    private long positionAt;
    private double lastPosition = Double.NaN;
    private final Runnable tick = new Runnable() {
        @Override public void run() {
            if (host == null || context == null) return;
            pollMedia(); pollVisibility(); pollGuestAccessState(); pollPartyPolicy();
            updatePresentation();
            if (partyFullscreen) {
                updateParty(); pollPartyQueue(); pollPartyGuests(); pollPlayerVolume(); pollPartyLyrics();
                publishPresentation();
                if (activeKioskActivity() != null && SystemClock.elapsedRealtime() - partyLastPostpone > 15000) {
                    partyLastPostpone = SystemClock.elapsedRealtime(); partyHostCommand("postponeScreensaver");
                }
            }
            main.postDelayed(this, 1000);
        }
    };

    @Override public synchronized void start(PluginHost host, Map<String, Object> settings) {
        this.host = host; context = applicationContext(host);
        if (context == null) { host.status("Android application context unavailable.", true); return; }
        io = Executors.newFixedThreadPool(3); artIo = Executors.newFixedThreadPool(2); partyPolicyIo = Executors.newSingleThreadExecutor();
        main.post(() -> {
            registerLifecycle(); registerPartyAudioReceiver();
            currentActivity = findResumedActivity();
            removeStaleViews(currentActivity);
            context.getSharedPreferences(PARTY_PREFS, Context.MODE_PRIVATE).edit()
                    .putBoolean("party_fullscreen", false).putLong("party_until_ms", 0).apply();
            context.sendBroadcast(new Intent(PARTY_EVENT).setPackage(context.getPackageName()));
            reportedPartyPolicy = ""; partyPolicyLastPoll = 0; partyPolicyPending = false; reportedGuestPage = ""; reportedMenuCategories = ""; reportedSearchModes = ""; reportedPartyState = null; reportedPartyEffect = null; reportedGuestAccess = null; reportedGuestQr = null; guestAccessState = null; guestAccessQueue = ""; guestStateLastPoll = 0; publishPartyState();
            configureOnMain(settings);
            readKioskMusicAssistantConfig();
            host.executeCommand("getDashboardState", Collections.emptyMap(), (ok, data, error) -> {
                if (ok && data instanceof Map) main.post(() -> {
                    Object url = ((Map<?, ?>) data).get("haBaseUrl");
                    if (url == null) url = ((Map<?, ?>) data).get("homeAssistantUrl");
                    if (url != null) haBaseUrl = String.valueOf(url);
                });
            });
            main.post(tick);
            host.status("Party Mode ready. Start/stop and visibility are independent of Now Playing.", false);
        });
    }

    @Override public synchronized void configure(Map<String, Object> settings) {
        main.post(() -> { if (context != null && host != null) configureOnMain(settings); });
    }
    private void configureOnMain(Map<String, Object> settings) {
        String speaker = setting(settings, "speakerEntity", "");
        if (!speaker.equals(nowPlayingEntity)) {
            partyGeneration++; partyModel = null; partyTarget = ""; partyLastSuccess = 0;
            resetTrackLyrics(); mediaAttributes = Collections.emptyMap(); mediaState = ""; mediaIdentity = ""; lastPosition = Double.NaN;
            playerVolume = -1; playerVolumeLastSuccess = 0; playerVolumeLastPoll = 0;
            clearPartyGuests();
        }
        dismissSearch();
        int before = intSetting(settings, "tracksBefore", 2, 0, 10), after = intSetting(settings, "tracksAfter", 2, 0, 10);
        if (before != tracksBefore || after != tracksAfter) { partyGeneration++; partyModel = null; partyLastPoll = 0; }
        tracksBefore = before; tracksAfter = after;
        allowSearch = !Boolean.FALSE.equals(settings.get("allowSearch"));
        SharedPreferences searchPrefs = context.getSharedPreferences(PARTY_PREFS, Context.MODE_PRIVATE);
        searchLibrary = searchPrefs.getBoolean("search_library", true);
        searchSimilar = searchPrefs.getBoolean("search_similar", true);
        searchAi = searchPrefs.getBoolean("search_ai", true);
        currentSimilar = searchPrefs.getBoolean("current_similar", true);
        allowQueueTap = Boolean.TRUE.equals(settings.get("allowQueueTap"));
        showQuickActions = Boolean.TRUE.equals(settings.get("showQuickActions"));
        String extra = setting(settings, "extraControls", Boolean.TRUE.equals(settings.get("showEqControls")) ? "Playlists and EQ" : "Playlists");
        showEqControls = extra.contains("EQ"); showPlaylists = extra.contains("Playlists");
        nowPlayingEntity = speaker;
        automatic = Boolean.TRUE.equals(settings.get("startAutomatically"));
        onlyPlaying = Boolean.TRUE.equals(settings.get("onlyWhilePlaying"));
        showPaused = !Boolean.FALSE.equals(settings.get("showPaused"));
        visibilityEntity = setting(settings, "visibilityEntity", "");
        visibilityCondition = setting(settings, "visibilityCondition", "Always");
        visibilityValue = setting(settings, "visibilityValue", ""); visibilityState = "";
        gain = intSetting(settings, "gain", 3, 1, 10);
        try { fps = Integer.parseInt(setting(settings, "refreshRate", "20 FPS").split(" ")[0]); } catch (Exception ignored) { fps = 20; }
        fps = Math.max(10, Math.min(30, fps));
        settingFpsEconomy = setting(settings, "refreshRate", "20 FPS").contains("Eco");
        SharedPreferences prefs = context.getSharedPreferences(PARTY_PREFS, Context.MODE_PRIVATE);
        partyEffect = PartySignal.effect(savedChoice(prefs, "effect", setting(settings, "effect", "off")));
        screenControls = savedChoice(prefs, "controls", normalizeControls(setting(settings, "screenControls", "Menu only")));
        String configuredVolume = setting(settings, "volumeControls", "Buttons");
        if (!prefs.contains("configured_volume_style") && "Buttons".equals(configuredVolume) &&
                (Boolean.FALSE.equals(settings.get("showVolume")) || "false".equals(prefs.getString("configured_volume_visible", "true")))) configuredVolume = "Off";
        volumeStyle = savedChoice(prefs, "volume_style", configuredVolume);
        showVolume = Boolean.parseBoolean(savedChoice(prefs, "volume_visible", String.valueOf(!"Off".equals(configuredVolume))));
        showPlayback = Boolean.parseBoolean(savedChoice(prefs, "playback_visible", String.valueOf(!Boolean.FALSE.equals(settings.get("showPlaybackControls")))));
        partyQueueVisible = Boolean.parseBoolean(prefs.getString("queue_visible", "true"));
        guestPage = prefs.getString("guest_page", "Music Assistant");
        menuCategories.clear();
        for (String key : menuKeys) if (prefs.getBoolean("menu_" + key, true)) menuCategories.add(key);
        partyGuestsFollow = Boolean.parseBoolean(savedChoice(prefs, "guests_follow", String.valueOf(!Boolean.FALSE.equals(settings.get("showGuestQr")))));
        Set<String> wanted = new HashSet<>();
        if (!nowPlayingEntity.isEmpty()) wanted.add(nowPlayingEntity);
        if (!visibilityEntity.isEmpty()) wanted.add(visibilityEntity);
        for (String id : new HashSet<>(subscriptions)) if (!wanted.contains(id)) {
            host.unsubscribe("ha.entity." + id); subscriptions.remove(id);
        }
        for (String id : wanted) if (subscriptions.add(id)) host.subscribe("ha.entity." + id);
        if (partyFullscreen) { removePartyView(); publishPresentation(); }
        pollMedia(); pollVisibility(); updatePresentation(); publishPartyState();
    }
    private String savedChoice(SharedPreferences prefs, String key, String configured) {
        String previous = prefs.getString("configured_" + key, null);
        if (previous == null || !previous.equals(configured)) {
            prefs.edit().putString("configured_" + key, configured).putString(key, configured).apply();
            return configured;
        }
        return prefs.getString(key, configured);
    }

    @Override public synchronized void execute(String command, Map<String, Object> arguments) {
        main.post(() -> {
            if (host == null || context == null) return;
            if ("show".equals(command)) { activation.show(); pollMedia(); updatePresentation(); }
            else if ("hide".equals(command)) { activation.hide(); closePresentation(); }
            else if (command.startsWith("partyEffect")) setPartyEffect(command.substring(11).toLowerCase(java.util.Locale.ROOT));
            else if ("partyGuestsFollow".equals(command) || "partyGuestsHide".equals(command)) setPartyGuests("partyGuestsFollow".equals(command));
            else if ("partyGuestEnable".equals(command) || "partyGuestDisable".equals(command)) changePartyGuestAccess("partyGuestEnable".equals(command));
            else if ("partyQueueShow".equals(command) || "partyQueueHide".equals(command)) setPartyQueue("partyQueueShow".equals(command));
            else if ("volumeToggle".equals(command)) setPlayerControlsVisible(true, !showVolume);
            else if ("playbackToggle".equals(command)) setPlayerControlsVisible(false, !showPlayback);
            else if ("controlsAll".equals(command) || "controlsClose".equals(command) || "controlsHidden".equals(command)) {
                screenControls = "controlsAll".equals(command) ? "Menu and Close" : "controlsClose".equals(command) ? "Close only" : "Hidden";
                context.getSharedPreferences(PARTY_PREFS, Context.MODE_PRIVATE).edit().putString("controls", screenControls).apply();
                removePartyView(); updatePresentation();
            } else host.status("Unknown Party command: " + command, true);
        });
    }
    @Override public synchronized void onEvent(String event, Map<String, Object> payload) {
        if ("switch.continuous".equals(event) || "select.auto_method".equals(event) || "select.auto_count".equals(event) || "select.queue_placement".equals(event)) {
            main.post(() -> {
                if (host == null || context == null) return;
                try {
                    JSONObject changes = new JSONObject();
                    if ("switch.continuous".equals(event)) changes.put("continuous", Boolean.TRUE.equals(payload.get("on")));
                    else {
                        String value = String.valueOf(payload.get("option"));
                        if ("select.auto_method".equals(event)) changes.put("auto_method", "Favoritnumre".equals(value) ? "favorites" : "Samme stil (MA)".equals(value) ? "similar" : "AI-musikønske".equals(value) ? "ai" : "");
                        else if ("select.auto_count".equals(event)) changes.put("auto_count", Integer.parseInt(value));
                        else changes.put("queue_option", "Sidst i køen".equals(value) ? "add" : "Som næste".equals(value) ? "next" : "Spil straks".equals(value) ? "play" : "Erstat kommende".equals(value) ? "replace_next" : "");
                    }
                    changePartyPolicy(changes);
                } catch (Exception error) { host.status("Party-indstillingen kunne ikke ændres", true); }
            }); return;
        }
        if ("select.guest_page".equals(event)) {
            main.post(() -> { if (host != null && context != null) setGuestPage(String.valueOf(payload.get("option"))); }); return;
        }
        if (event.startsWith("switch.menu_")) {
            final String key = event.substring("switch.menu_".length());
            main.post(() -> { if (host != null && context != null) setMenuCategory(key, Boolean.TRUE.equals(payload.get("on"))); }); return;
        }
        if ("select.effect".equals(event)) {
            main.post(() -> { if (host != null && context != null) setPartyEffect(String.valueOf(payload.get("option"))); }); return;
        }
        if (event.startsWith("switch.search_") || "switch.current_similar".equals(event)) {
            final String key = event.substring("switch.".length());
            main.post(() -> { if (host != null && context != null) setSearchMode(key, Boolean.TRUE.equals(payload.get("on"))); }); return;
        }
        if ("switch.guest_access".equals(event)) {
            main.post(() -> { if (host != null) changePartyGuestAccess(Boolean.TRUE.equals(payload.get("on"))); }); return;
        }
        if ("switch.guest_qr".equals(event)) {
            main.post(() -> { if (host != null) setPartyGuests(Boolean.TRUE.equals(payload.get("on"))); }); return;
        }
        if ("switch.active".equals(event)) {
            execute(Boolean.TRUE.equals(payload.get("on")) ? "show" : "hide", Collections.emptyMap()); return;
        }
        if (!event.startsWith("ks.ha.entity.")) return;
        String id = payload.get("entityId") == null ? event.substring("ks.ha.entity.".length()) : String.valueOf(payload.get("entityId"));
        String state = payload.get("state") == null ? "" : String.valueOf(payload.get("state"));
        Object attributes = payload.get("attributes");
        Map<?, ?> attrs = attributes instanceof Map ? (Map<?, ?>) attributes : Collections.emptyMap();
        main.post(() -> {
            if (host == null) return;
            if (nowPlayingEntity.equals(id)) applyMedia(state, attrs);
            if (visibilityEntity.equals(id)) visibilityState = state;
            updatePresentation();
        });
    }
    @Override public synchronized void stop() {
        if (host != null) for (String id : subscriptions) try { host.unsubscribe("ha.entity." + id); } catch (Throwable ignored) {}
        subscriptions.clear();
        CountDownLatch done = new CountDownLatch(1);
        Runnable cleanup = () -> {
            try {
                main.removeCallbacksAndMessages(null); activation.hide(); closePresentation();
                if (context != null && partyAudioReceiver != null) context.unregisterReceiver(partyAudioReceiver);
                if (application != null && lifecycle != null) application.unregisterActivityLifecycleCallbacks(lifecycle);
                partyAudioReceiver = null; lifecycle = null;
            } catch (Throwable ignored) {} finally { done.countDown(); }
        };
        if (Looper.myLooper() == Looper.getMainLooper()) cleanup.run();
        else { main.post(cleanup); try { done.await(2, TimeUnit.SECONDS); } catch (InterruptedException e) { Thread.currentThread().interrupt(); } }
        if (io != null) io.shutdownNow(); if (artIo != null) artIo.shutdownNow(); if (partyPolicyIo != null) partyPolicyIo.shutdownNow(); io = null; artIo = null; partyPolicyIo = null; host = null;
    }

    private void pollMedia() {
        if (host == null || nowPlayingEntity.isEmpty() || mediaPending) return;
        final String id = nowPlayingEntity; mediaPending = true;
        host.executeCommand("getHaEntityState", Collections.singletonMap("entityId", id), (ok, data, error) -> main.post(() -> {
            mediaPending = false;
            if (host == null || !nowPlayingEntity.equals(id) || !ok || !(data instanceof Map)) return;
            Map<?, ?> snapshot = (Map<?, ?>) data;
            Object attrs = snapshot.get("attributes");
            applyMedia(String.valueOf(snapshot.get("state")), attrs instanceof Map ? (Map<?, ?>) attrs : Collections.emptyMap());
            updatePresentation();
        }));
    }
    private void pollVisibility() {
        if (host == null || visibilityEntity.isEmpty() || visibilityPending) return;
        final String id = visibilityEntity; visibilityPending = true;
        host.executeCommand("getHaEntityState", Collections.singletonMap("entityId", id), (ok, data, error) -> main.post(() -> {
            visibilityPending = false;
            if (host == null || !visibilityEntity.equals(id)) return;
            visibilityState = ok && data instanceof Map ? String.valueOf(((Map<?, ?>) data).get("state")) : "unavailable";
            updatePresentation();
        }));
    }
    private void applyMedia(String state, Map<?, ?> attrs) {
        String identity = attr(attrs, "media_content_id", attr(attrs, "media_title", ""));
        if (!identity.equals(mediaIdentity)) resetTrackLyrics();
        double position = numberAttr(attrs, "media_position", 0);
        if (!identity.equals(mediaIdentity) || !state.equals(mediaState) || Double.isNaN(lastPosition) || Math.abs(position - lastPosition) >= 0.5) {
            positionAnchor = "paused".equals(state) && identity.equals(mediaIdentity) && position == lastPosition ? estimatedMediaPosition() : position;
            positionAt = SystemClock.elapsedRealtime();
        }
        if (!attr(attrs, "active_queue", "").equals(attr(mediaAttributes, "active_queue", ""))) {
            partyGeneration++; partyModel = null; partyTarget = ""; partyLastSuccess = 0;
            resetTrackLyrics(); dismissSearch(); clearPartyGuests(); partyGuestLastPoll = 0;
            playerVolume = -1; playerVolumeLastSuccess = 0; playerVolumeLastPoll = 0;
        }
        mediaIdentity = identity; lastPosition = position; mediaState = state; mediaAttributes = attrs;
    }
    private double estimatedMediaPosition() {
        return Math.max(0, positionAnchor + ("playing".equalsIgnoreCase(mediaState) ? (SystemClock.elapsedRealtime() - positionAt) / 1000.0 : 0));
    }
    private boolean eligible() {
        return PartyVisibility.allowed(visibilityCondition, visibilityEntity, visibilityState, visibilityValue, LocalTime.now()) &&
                (!onlyPlaying || "playing".equalsIgnoreCase(mediaState) || showPaused && "paused".equalsIgnoreCase(mediaState));
    }
    private void updatePresentation() {
        if (host == null || context == null) return;
        boolean show = activation.visible(automatic, eligible());
        if (!show) { if (partyFullscreen) closePresentation(); return; }
        if (!partyFullscreen) {
            foregroundLastTry = 0; foregroundUntil = SystemClock.elapsedRealtime() + 5000; partyFullscreen = true; partyGuestLastPoll = 0; clearPartyGuests(); publishPresentation();
            partyHostCommand("stopScreensaver"); partyHostCommand("hideNowPlaying"); partyHostCommand("hideOverlayPage");
            bringPartyToFront();

        }
        if (SystemClock.elapsedRealtime() < foregroundUntil) bringPartyToFront();
        ensurePartyView(); updateParty();
    }
    private void bringPartyToFront() {
        Activity activity = activeKioskActivity();
        if (activity != null && (activity.hasWindowFocus() || (searchDialog != null && searchDialog.isShowing()))) return;
        long now = SystemClock.elapsedRealtime();
        if (now - foregroundLastTry < 500) return;
        foregroundLastTry = now;
        Intent launch = context.getPackageManager().getLaunchIntentForPackage(context.getPackageName());
        if (launch != null) {
            launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_REORDER_TO_FRONT | Intent.FLAG_ACTIVITY_SINGLE_TOP);
            try { context.startActivity(launch); } catch (Throwable error) { if (host != null) host.log("Party foreground request failed: " + error.getMessage()); }
        }
    }
    private void publishPartyState() {
        if (host == null) return;
        if (!guestPage.equals(reportedGuestPage)) {
            try { host.publishSelect("guest_page", "Guest QR destination", new String[]{"Music Assistant", "Party guest page"}, guestPage); reportedGuestPage = guestPage; }
            catch (Throwable error) { host.log("Guest destination select unavailable"); }
        }
        String categories = menuCategories.toString();
        if (!categories.equals(reportedMenuCategories)) {
            try { for (int i = 0; i < menuKeys.length; i++) host.publishSwitch("menu_" + menuKeys[i], "Party menu: " + menuNames[i], menuCategories.contains(menuKeys[i])); reportedMenuCategories = categories; }
            catch (Throwable error) { host.log("Menu category switches unavailable"); }
        }
        if (!partyEffect.equals(reportedPartyEffect)) {
            try {
                host.publishSelect("effect", "Party visualisering", new String[]{"off", "spectrum", "mirror", "radial", "wave", "particles", "tunnel", "lyrics", "discolyrics"}, partyEffect);
                reportedPartyEffect = partyEffect;
            } catch (Throwable error) { host.log("Party effect select unavailable: " + error.getMessage()); }
        }
        if (!Boolean.valueOf(partyGuestsFollow).equals(reportedGuestQr)) {
            try { host.publishSwitch("guest_qr", "Guest QR", partyGuestsFollow); reportedGuestQr = partyGuestsFollow; }
            catch (Throwable error) { host.log("Guest QR switch unavailable: " + error.getMessage()); }
        }
        if (guestAccessState != null && guestAccessQueue.equals(attr(mediaAttributes, "active_queue", ""))
                && !guestAccessState.equals(reportedGuestAccess)) {
            try { host.publishSwitch("guest_access", "Guest access", guestAccessState); reportedGuestAccess = guestAccessState; }
            catch (Throwable error) { host.log("Guest access switch unavailable: " + error.getMessage()); }
        }
        String modes = "" + searchLibrary + searchSimilar + searchAi + currentSimilar;
        if (!modes.equals(reportedSearchModes)) {
            try {
                host.publishSwitch("search_library", "Search: Library", searchLibrary);
                host.publishSwitch("search_similar", "Search: Similarity", searchSimilar);
                host.publishSwitch("search_ai", "Search: AI DJ", searchAi);
                host.publishSwitch("current_similar", "Similar to current track", currentSimilar);
                reportedSearchModes = modes;
            } catch (Throwable error) { host.log("Search switches unavailable"); }
        }
        if (Boolean.valueOf(partyFullscreen).equals(reportedPartyState)) return;
        try { host.publishSwitch("active", "Party Mode", partyFullscreen); reportedPartyState = partyFullscreen; }
        catch (Throwable error) { host.log("Party switch unavailable: " + error.getMessage()); }
    }
    private void publishPresentation() {
        publishPartyState();
        context.getSharedPreferences(PARTY_PREFS, Context.MODE_PRIVATE).edit()
                .putBoolean("party_fullscreen", partyFullscreen).putLong("party_until_ms", partyFullscreen ? System.currentTimeMillis() + 30000 : 0)
                .putString("effect", partyEffect).putInt("gain", gain).putInt("fps", fps)
                .putBoolean("allow_quick_actions", showQuickActions).apply();
        context.sendBroadcast(new Intent(PARTY_EVENT).setPackage(context.getPackageName()));
    }
    private void closePresentation() {
        foregroundUntil = 0;
        boolean was = partyFullscreen; partyFullscreen = false; partyGeneration++;
        dismissSearch(); removePartyView(); clearPartyGuests();
        if (context != null && was) publishPresentation();
    }
    private void partyHostCommand(String command) {
        if (host != null) try { host.executeCommand(command, Collections.emptyMap(), (ok, data, error) -> {}); } catch (Throwable ignored) {}
    }
    private void ensurePartyView() {
        Activity activity = activeKioskActivity();
        if (!partyFullscreen || activity == null) return;
        if (partyRoot != null && partyActivity != activity) removePartyView();
        if (partyRoot != null) return;
        View content = activity.findViewById(android.R.id.content);
        if (!(content instanceof FrameLayout)) { host.status("Kiosk content view unavailable.", true); return; }
        FrameLayout root = new FrameLayout(activity); root.setTag("party-mode:view"); root.setClickable(true); root.setKeepScreenOn(true);
        root.setBackgroundColor(0xFF15171A);
        root.setOnApplyWindowInsetsListener((v, insets) -> {
            v.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(), insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            return insets;
        });
        partyView = new PartyView(activity, true); partyView.setEconomy(settingFpsEconomy); partyView.setPresentation(partyEffect, partyQueueVisible);
        partyView.setTrackAction(allowQueueTap ? this::playQueueTrack : null);
        FrameLayout.LayoutParams body = new FrameLayout.LayoutParams(-1, -1);
        body.topMargin = "Hidden".equals(screenControls) && !allowSearch && !showPlaylists ? 0 : dp(70);
        body.bottomMargin = dp((showPlayback ? 60 : 0) + (showVolume ? 60 : 0));
        root.addView(partyView, body);
        if ("Menu and Close".equals(screenControls) || "Close only".equals(screenControls)) {
            ImageView close = PartyUi.icon(activity, "close", "Afslut Party Mode");
            FrameLayout.LayoutParams cp = new FrameLayout.LayoutParams(dp(48), dp(48), Gravity.TOP | Gravity.RIGHT);
            cp.topMargin = dp(10); cp.rightMargin = dp(12); root.addView(close, cp);
            close.setOnClickListener(v -> { activation.hide(); closePresentation(); });
        }
        if (menuVisible()) {
            ImageView menu = PartyUi.icon(activity, "settings", "Party-indstillinger og visualiseringer");
            FrameLayout.LayoutParams mp = new FrameLayout.LayoutParams(dp(48), dp(48), Gravity.TOP | Gravity.RIGHT);
            mp.topMargin = dp(10); mp.rightMargin = dp("Menu and Close".equals(screenControls) ? 68 : 12);
            root.addView(menu, mp); menu.setOnClickListener(v -> showPartyMenu(menu));
        }
        if (hasSearchModes()) {
            ImageView search = PartyUi.icon(activity, "search", "Søg efter musik i Music Assistant");
            FrameLayout.LayoutParams sp = new FrameLayout.LayoutParams(dp(48), dp(48), Gravity.TOP | Gravity.LEFT);
            sp.topMargin = dp(10); sp.leftMargin = dp(12); root.addView(search, sp);
            search.setOnClickListener(v -> showSearch());
        }
        if (showPlaylists) {
            ImageView playlists = PartyUi.icon(activity, "playlist", "Favoritplaylister fra Music Assistant");
            FrameLayout.LayoutParams pp = new FrameLayout.LayoutParams(dp(48), dp(48), Gravity.TOP | Gravity.LEFT);
            pp.topMargin = dp(10); pp.leftMargin = dp(hasSearchModes() ? 68 : 12); root.addView(playlists, pp);
            playlists.setOnClickListener(v -> showPlaylists());
        }
        if (PartySignal.lyrics(partyEffect)) {
            lyricsView = new PartyLyricsView(activity, "discolyrics".equals(partyEffect));
            FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(-1, -1);
            lp.topMargin = body.topMargin; lp.bottomMargin = body.bottomMargin + dp(116);
            root.addView(lyricsView, lp); lyricsView.setLyrics(lyrics);
            main.removeCallbacks(lyricTick); main.post(lyricTick);
        }
        addPlayerControls(root, activity);
        ((FrameLayout) content).addView(root, new FrameLayout.LayoutParams(-1, -1));
        root.setZ(100000f); root.bringToFront(); root.requestApplyInsets();
        partyRoot = root; partyActivity = activity;
        updatePlayerControls();
    }
    private static String normalizeControls(String value) { return "All controls".equals(value) ? "Menu only" : value; }
    private boolean menuVisible() { return !menuCategories.isEmpty() && ("Menu only".equals(screenControls) || "Menu and Close".equals(screenControls)); }
    private TextView button(Activity activity, String title, String description) {
        TextView view = PartyUi.action(activity, title, false); view.setContentDescription(description); return view;
    }
    private void setPlayerControlsVisible(boolean volume, boolean visible) {
        if (volume) showVolume = visible; else showPlayback = visible;
        context.getSharedPreferences(PARTY_PREFS, Context.MODE_PRIVATE).edit()
                .putString(volume ? "volume_visible" : "playback_visible", String.valueOf(visible)).apply();
        removePartyView(); updatePresentation();
        if (volume && visible) { playerVolumeLastPoll = 0; pollPlayerVolume(); }
    }
    private LinearLayout playerControlRow(Activity activity) {
        LinearLayout row = new LinearLayout(activity); row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL); row.setPadding(dp(4), dp(4), dp(4), dp(4));
        GradientDrawable background = new GradientDrawable(); background.setColor(0xE6353539);
        background.setCornerRadius(dp(16)); row.setBackground(background);
        return row;
    }
    private void addPlayerControls(FrameLayout root, Activity activity) {
        if (showPlayback) {
            LinearLayout row = playerControlRow(activity); row.setGravity(Gravity.CENTER);
            playbackButton = PartyUi.icon(activity, "play", "Afspil eller pause den valgte MA-kø");
            stopButton = PartyUi.icon(activity, "stop", "Stop den valgte MA-kø");
            for (ImageView view : new ImageView[] {playbackButton, stopButton}) {
                LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(dp(48), dp(48));
                params.leftMargin = dp(6); params.rightMargin = dp(6); row.addView(view, params);
            }
            playbackButton.setOnClickListener(v -> {
                try { sendPlayerCommand(PartyPlayerControls.playback(activeQueue(), "playing".equalsIgnoreCase(mediaState)), -1); }
                catch (Exception error) { reportPlayerCommandError(); }
            });
            stopButton.setOnClickListener(v -> {
                try { sendPlayerCommand(PartyPlayerControls.stop(activeQueue()), -1); }
                catch (Exception error) { reportPlayerCommandError(); }
            });
            FrameLayout.LayoutParams layout = new FrameLayout.LayoutParams(dp(144), dp(56), Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL);
            layout.bottomMargin = dp(8); root.addView(row, layout);
        }
        if (showVolume) {
            LinearLayout row = playerControlRow(activity); row.setGravity(Gravity.CENTER_VERTICAL);
            volumeLabel = PartyUi.text(activity, "—", 15, PartyUi.INK); volumeLabel.setGravity(Gravity.CENTER);
            if (!"Slider".equals(volumeStyle)) {
                volumeMinus = PartyUi.icon(activity, "minus", "Skru ned for højttalergruppen");
                volumePlus = PartyUi.icon(activity, "plus", "Skru op for højttalergruppen");
                row.addView(volumeMinus, new LinearLayout.LayoutParams(dp(48), dp(48)));
                row.addView(volumeLabel, new LinearLayout.LayoutParams(dp(72), dp(48)));
                row.addView(volumePlus, new LinearLayout.LayoutParams(dp(48), dp(48)));
                volumeMinus.setOnClickListener(v -> stepVolume(-3)); volumePlus.setOnClickListener(v -> stepVolume(3));
            } else {
                row.addView(volumeLabel, new LinearLayout.LayoutParams(dp(62), dp(48)));
                volumeSlider = new SeekBar(activity); volumeSlider.setMax(100);
                volumeSlider.setProgressTintList(ColorStateList.valueOf(PartyUi.ACCENT));
                volumeSlider.setThumbTintList(ColorStateList.valueOf(PartyUi.ACCENT));
                volumeSlider.setProgressBackgroundTintList(ColorStateList.valueOf(0xFF3B4857));
                volumeSlider.setContentDescription("Højttalergruppens volumen");
                row.addView(volumeSlider, new LinearLayout.LayoutParams(0, dp(48), 1));
                volumeSlider.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
                    @Override public void onProgressChanged(SeekBar bar, int progress, boolean fromUser) { if (fromUser && volumeLabel != null) volumeLabel.setText(progress + "%"); }
                    @Override public void onStartTrackingTouch(SeekBar bar) { volumeDragging = true; volumeDragQueue = activeQueue(); }
                    @Override public void onStopTrackingTouch(SeekBar bar) {
                        String queue = volumeDragQueue; volumeDragging = false; volumeDragQueue = "";
                        if (!queue.equals(activeQueue()) || queue.isEmpty()) { updatePlayerControls(); return; }
                        try { sendPlayerCommand(PartyPlayerControls.volume(queue, bar.getProgress()), bar.getProgress()); }
                        catch (Exception error) { reportPlayerCommandError(); }
                    }
                });
            }
            FrameLayout.LayoutParams layout = new FrameLayout.LayoutParams(dp("Slider".equals(volumeStyle) ? 286 : 180), dp(56), Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL);
            layout.bottomMargin = dp(showPlayback ? 68 : 8); root.addView(row, layout);
        }
    }
    private void stepVolume(int delta) {
        if (!playerControlsReady() || playerVolume < 0 || SystemClock.elapsedRealtime() - playerVolumeLastSuccess > 8000) return;
        try { sendPlayerCommand(PartyPlayerControls.volume(activeQueue(), playerVolume + delta), Math.max(0, Math.min(100, playerVolume + delta))); }
        catch (Exception error) { reportPlayerCommandError(); }
    }
    private String activeQueue() { return attr(mediaAttributes, "active_queue", "").trim(); }
    private boolean playerControlsReady() {
        return host != null && partyFullscreen && !activeQueue().isEmpty() &&
                !"unknown".equalsIgnoreCase(mediaState) && !"unavailable".equalsIgnoreCase(mediaState) &&
                !maBaseUrl.isEmpty() && !maToken.isEmpty() && !playerCommandPending;
    }
    private void updatePlayerControls() {
        boolean ready = playerControlsReady();
        if (playbackButton != null) {
            playbackButton.setImageDrawable(new PartyUi.Glyph("playing".equalsIgnoreCase(mediaState) ? "pause" : "play"));
            playbackButton.setEnabled(ready); playbackButton.setAlpha(ready ? 1f : 0.4f);
        }
        if (stopButton != null) { stopButton.setEnabled(ready); stopButton.setAlpha(ready ? 1f : 0.4f); }
        boolean known = playerVolume >= 0 && SystemClock.elapsedRealtime() - playerVolumeLastSuccess <= 8000;
        for (ImageView control : new ImageView[] {volumeMinus, volumePlus}) if (control != null) {
            control.setEnabled(ready && known); control.setAlpha(ready && known ? 1f : 0.4f);
        }
        if (volumeSlider != null) {
            volumeSlider.setEnabled(ready && known); volumeSlider.setAlpha(ready && known ? 1f : 0.4f);
            if (!volumeDragging && known) volumeSlider.setProgress(playerVolume);
        }
        if (volumeLabel != null && !volumeDragging) volumeLabel.setText(known ? playerVolume + "%" : "—");
    }
    private void reportPlayerCommandError() {
        if (host != null) host.status("MA-styring mislykkedes. Kontrollér højttalergruppe, forbindelse og tokenets rettigheder.", true);
    }
    private void sendPlayerCommand(PartyPlayerControls.Request request, int volume) {
        if (!playerControlsReady() || io == null) return;
        readKioskMusicAssistantConfig();
        final String queue = activeQueue(), entity = nowPlayingEntity;
        if (queue.isEmpty() || maBaseUrl.isEmpty() || maToken.isEmpty()) {
            partyGuestStatus = queue.isEmpty() ? "Gæste-QR: venter på den valgte afspiller" : "Gæste-QR: MA-adresse eller token mangler"; updateParty(); return;
        }
        final long generation = partyGeneration;
        final String base = maBaseUrl.trim().replaceFirst("^ws:", "http:").replaceFirst("^wss:", "https:").replaceAll("/+$", "");
        final String token = maToken;
        if (volume >= 0) playerVolumeRevision++;
        playerCommandPending = true; updatePlayerControls();
        io.execute(() -> {
            boolean accepted = false;
            try {
                if (generation == partyGeneration && queue.equals(activeQueue()))
                    accepted = PartyPlayerControls.accepted(partyRequest(base, token, request.command, request.args));
            } catch (Throwable ignored) {}
            final boolean ok = accepted;
            main.post(() -> {
                playerCommandPending = false;
                if (host == null || generation != partyGeneration || !entity.equals(nowPlayingEntity) || !queue.equals(activeQueue())) return;
                if (ok) {
                    if (volume >= 0) { playerVolume = volume; playerVolumeLastSuccess = SystemClock.elapsedRealtime(); playerVolumeLastPoll = playerVolumeLastSuccess; }
                    host.status("MA-højttalergruppen er opdateret.", false); pollMedia();
                } else reportPlayerCommandError();
                updatePlayerControls();
            });
        });
    }
    private void playQueueTrack(String id) {
        if (!allowQueueTap || !playerControlsReady() || partyModel == null ||
                SystemClock.elapsedRealtime() - partyLastSuccess > 8000) return;
        for (PartyQueueModel.Track track : partyModel.tracks) if (id.equals(track.id) && !track.current) {
            try { sendPlayerCommand(PartyJukebox.playItem(activeQueue(), id), -1); }
            catch (Exception error) { reportPlayerCommandError(); }
            return;
        }
    }
    private void dismissSearch() {
        searchGeneration++;
        Dialog selection = selectionDialog; selectionDialog = null; if (selection != null) selection.dismiss();
        Dialog search = searchDialog; searchDialog = null; if (search != null) search.dismiss();
    }
    private String maBase() { return maBaseUrl.trim().replaceFirst("^ws:", "http:").replaceFirst("^wss:", "https:").replaceAll("/+$", ""); }
    private LinearLayout panelBody(Activity a) { LinearLayout body = new LinearLayout(a); body.setOrientation(LinearLayout.VERTICAL); return body; }
    private void openSheet(Activity a, String title, LinearLayout body, boolean drawer) {
        dismissSearch(); final Dialog opened = PartyUi.sheet(a, title, body, drawer); searchDialog = opened;
        opened.setOnDismissListener(dialog -> {
            if (searchDialog != opened) return;
            searchGeneration++; searchDialog = null;
            Dialog selection = selectionDialog; selectionDialog = null; if (selection != null) selection.dismiss();
        });
        opened.show();
    }
    private void addPanelAction(LinearLayout rows, String title, boolean selected, Runnable action) {
        TextView choice = PartyUi.action(rows.getContext(), title, selected);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2); lp.bottomMargin = dp(8); rows.addView(choice, lp);
        choice.setOnClickListener(v -> action.run());
    }
    private void panelHeading(LinearLayout rows, String title) {
        TextView t = PartyUi.text(rows.getContext(), title, 12, PartyUi.MUTED); t.setPadding(dp(4), dp(16), 0, dp(10)); rows.addView(t);
    }
    private boolean validDjUrl(String url) {
        try { URL value = new URL(url); return url.length() <= 2048 && ("http".equals(value.getProtocol()) || "https".equals(value.getProtocol())) && !value.getHost().isEmpty() && value.getUserInfo() == null; }
        catch (Exception ignored) { return false; }
    }
    private void configureDj() {
        Activity a = activeKioskActivity(); if (a == null) return;
        LinearLayout body = panelBody(a);
        body.addView(PartyUi.text(a, "Adresse fra Party AI DJ-add-on: http://HA-IP:8101/#token=DIT_API_TOKEN", 15, PartyUi.MUTED));
        EditText field = new EditText(a); field.setSingleLine(false); field.setTextColor(PartyUi.INK);
        field.setText(context.getSharedPreferences(PARTY_PREFS, Context.MODE_PRIVATE).getString("dj_url", ""));
        body.addView(field, new LinearLayout.LayoutParams(-1, -2));
        addPanelAction(body, "Gem og åbn AI DJ", false, () -> {
            String url = field.getText().toString().trim(); if (!validDjUrl(url)) { field.setError("Angiv en http/https-adresse"); return; }
            context.getSharedPreferences(PARTY_PREFS, Context.MODE_PRIVATE).edit().putString("dj_url", url).apply(); clearPartyGuests(); showDj();
        });
        openSheet(a, "AI DJ · forbindelse", body, false);
    }
    private String guestConnection() {
        SharedPreferences prefs = context.getSharedPreferences(PARTY_PREFS, Context.MODE_PRIVATE);
        String saved = prefs.getString("guest_url", "");
        // Keep 0.1.12 installations working until the independent portal is configured.
        return saved.isEmpty() ? prefs.getString("dj_url", "") : saved;
    }
    private void publishPartyPolicy(JSONObject policy) throws Exception {
        String queue = activeQueue();
        if (!queue.equals(policy.optString("queue_id"))) return;
        String summary = policy.optBoolean("continuous") + ":" + policy.optString("auto_method") + ":" + policy.optInt("auto_count") + ":" + policy.optString("queue_option");
        if (summary.equals(reportedPartyPolicy)) return;
        host.publishSwitch("continuous", "Party: automatisk fortsættelse", policy.optBoolean("continuous"));
        String method = policy.optString("auto_method");
        host.publishSelect("auto_method", "Party: automatisk musik fra", new String[]{"Favoritnumre", "Samme stil (MA)", "AI-musikønske"}, "favorites".equals(method) ? "Favoritnumre" : "ai".equals(method) ? "AI-musikønske" : "Samme stil (MA)");
        host.publishSelect("auto_count", "Party: antal automatiske numre", new String[]{"1", "2", "3", "4", "5"}, String.valueOf(policy.optInt("auto_count", 1)));
        String placement = policy.optString("queue_option");
        host.publishSelect("queue_placement", "Party: gæsternes køplacering", new String[]{"Sidst i køen", "Som næste", "Spil straks", "Erstat kommende"}, "next".equals(placement) ? "Som næste" : "play".equals(placement) ? "Spil straks" : "replace_next".equals(placement) ? "Erstat kommende" : "Sidst i køen");
        reportedPartyPolicy = summary;
    }
    private void pollPartyPolicy() {
        if (host == null || context == null || partyPolicyIo == null || partyPolicyPending || activeQueue().isEmpty()) return;
        if (context.getSharedPreferences(PARTY_PREFS, Context.MODE_PRIVATE).getString("guest_url", "").isEmpty()) return;
        long now = SystemClock.elapsedRealtime();
        if (now - partyPolicyLastPoll < 10000) return;
        partyPolicyLastPoll = now; partyPolicyPending = true;
        final String connection = guestConnection();
        partyPolicyIo.execute(() -> {
            JSONObject result = null;
            try { result = companionRequest(connection, "Party Guest", "/api/party-settings", null); } catch (Exception ignored) {}
            final JSONObject policy = result;
            main.post(() -> { partyPolicyPending = false; if (host != null && context != null && policy != null && connection.equals(guestConnection())) try { publishPartyPolicy(policy); } catch (Exception ignored) {} });
        });
    }
    private void changePartyPolicy(JSONObject changes) throws Exception {
        if (partyPolicyIo == null) return;
        changes.put("queue_id", activeQueue());
        final String connection = guestConnection();
        partyPolicyIo.execute(() -> {
            try {
                JSONObject policy = companionRequest(connection, "Party Guest", "/api/party-settings", changes);
                main.post(() -> { if (host != null && context != null && connection.equals(guestConnection())) try { publishPartyPolicy(policy); } catch (Exception ignored) {} });
            } catch (Exception error) { main.post(() -> { if (host != null) host.status("Kontrollér Party Guest-forbindelsen og opdatér add-on til 0.2.0", true); }); }
        });
    }
    private void configureGuest() {
        Activity a = activeKioskActivity(); if (a == null) return;
        LinearLayout body = panelBody(a);
        body.addView(PartyUi.text(a, "Kiosk-forbindelse fra Party Guest ingress: http://HA-IP:8102/#token=PARTY_GUEST_API_TOKEN. AI DJ er valgfri og har sin egen adresse.", 15, PartyUi.MUTED));
        EditText field = new EditText(a); field.setSingleLine(false); field.setTextColor(PartyUi.INK);
        field.setText(context.getSharedPreferences(PARTY_PREFS, Context.MODE_PRIVATE).getString("guest_url", ""));
        body.addView(field, new LinearLayout.LayoutParams(-1, -2));
        addPanelAction(body, "Gem gæsteforbindelse", false, () -> {
            String url = field.getText().toString().trim();
            if (!validDjUrl(url)) { field.setError("Angiv Party Guest-adressen fra ingress"); return; }
            context.getSharedPreferences(PARTY_PREFS, Context.MODE_PRIVATE).edit().putString("guest_url", url).apply();
            syncGuestModes(); clearPartyGuests(); partyGuestLastPoll = 0; partyPolicyLastPoll = 0; reportedPartyPolicy = ""; dismissSearch(); updateParty(); pollPartyGuests(); pollPartyPolicy();
        });
        openSheet(a, "Party Guest · forbindelse", body, false);
    }
    private void showDj() { showSearch("ai"); }
    private boolean hasSearchModes() { return allowSearch && (searchLibrary || searchSimilar || searchAi); }
    private void setSearchMode(String key, boolean enabled) {
        if ("search_library".equals(key)) searchLibrary = enabled;
        else if ("search_similar".equals(key)) searchSimilar = enabled;
        else if ("search_ai".equals(key)) searchAi = enabled;
        else if ("current_similar".equals(key)) currentSimilar = enabled;
        else return;
        context.getSharedPreferences(PARTY_PREFS, Context.MODE_PRIVATE).edit().putBoolean(key, enabled).apply();
        syncGuestModes(); clearPartyGuests(); partyGuestLastPoll = 0; dismissSearch(); removePartyView(); updatePresentation(); publishPartyState();
    }
    private void syncGuestModes() {
        if (io == null || context == null) return;
        final String queue = activeQueue();
        final boolean library = allowSearch && searchLibrary, similar = allowSearch && searchSimilar,
                ai = allowSearch && searchAi, current = allowSearch && currentSimilar;
        if (queue.isEmpty()) return;
        io.execute(() -> {
            try { companionRequest(guestConnection(), "Party Guest", "/api/guest-link", new JSONObject().put("queue_id", queue).put("modes",
                    new JSONObject().put("library", library).put("similar", similar).put("ai", ai).put("current_similar", current))); }
            catch (Exception ignored) { /* Normal when the optional companion is not configured. */ }
        });
    }
    private void showSimilar(String uri) {
        Activity a = activeKioskActivity(); if (a == null || io == null || !allowSearch || !searchSimilar) return;
        final String queue = activeQueue(), base = maBase(), token = maToken; final long generation = partyGeneration;
        LinearLayout body = panelBody(a); ScrollView scroll = new ScrollView(a); LinearLayout rows = panelBody(a); scroll.addView(rows);
        body.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1)); TextView status = PartyUi.text(a, "Finder lignende numre…", 16, PartyUi.MUTED); rows.addView(status);
        openSheet(a, "Lignende numre", body, false); final long request = ++searchGeneration;
        io.execute(() -> {
            java.util.List<PartyJukebox.Result> found = null;
            try {
                java.net.URI reference = new java.net.URI(uri);
                Object response = partyRequest(base, token, "music/tracks/similar_tracks", new JSONObject()
                    .put("item_id", reference.getPath().substring(1)).put("provider_instance_id_or_domain", reference.getScheme()).put("limit", 20).put("allow_lookup", true));
                if (response instanceof JSONArray) found = PartyJukebox.results(new JSONObject().put("tracks", response), base);
            } catch (Throwable ignored) {}
            final java.util.List<PartyJukebox.Result> matches = found;
            main.post(() -> {
                if (!validPanel(queue, generation, request)) return; rows.removeAllViews();
                if (matches == null || matches.isEmpty()) { status.setText("Ingen lignende numre fra MA eller dine udbydere"); rows.addView(status); return; }
                for (PartyJukebox.Result match : matches) addMediaRow(a, rows, match, request, queue, generation, () -> chooseMedia(a, match, false, queue, generation));
            });
        });
    }

    private void showSearch() { showSearch(""); }
    private void showSearch(String preferred) {
        Activity activity = activeKioskActivity();
        if (!hasSearchModes() || !playerControlsReady() || activity == null) return;
        final String queue = activeQueue(); final long generation = partyGeneration;
        LinearLayout layout = panelBody(activity);
        LinearLayout field = new LinearLayout(activity); field.setGravity(Gravity.CENTER_VERTICAL);
        field.setBackground(PartyUi.shape(activity, 0xFF222C38, 18, true));
        EditText input = new EditText(activity); input.setSingleLine(true); input.setTextColor(PartyUi.INK); input.setHintTextColor(PartyUi.MUTED);
        final String[] selectedMode = {"ai".equals(preferred) && searchAi ? "ai" : searchLibrary ? "library" : searchSimilar ? "similar" : "ai"};
        input.setTextSize(17); input.setHint("Titel eller kunstner"); input.setBackgroundColor(Color.TRANSPARENT);
        input.setPadding(dp(14), 0, dp(4), 0); input.setImeOptions(EditorInfo.IME_ACTION_SEARCH);
        field.addView(input, new LinearLayout.LayoutParams(0, dp(56), 1));
        ImageView submit = PartyUi.icon(activity, "search", "Søg i Music Assistant"); field.addView(submit, new LinearLayout.LayoutParams(dp(48), dp(48)));
        LinearLayout.LayoutParams fl = new LinearLayout.LayoutParams(-1, dp(56)); fl.bottomMargin = dp(16); layout.addView(field, fl);
        LinearLayout pills = new LinearLayout(activity); pills.setGravity(Gravity.CENTER_VERTICAL);
        layout.addView(pills, new LinearLayout.LayoutParams(-1, dp(48)));
        TextView explanation = PartyUi.text(activity, "", 14, PartyUi.MUTED);
        LinearLayout.LayoutParams ep = new LinearLayout.LayoutParams(-1, -2); ep.topMargin = dp(8); ep.bottomMargin = dp(10); layout.addView(explanation, ep);
        TextView current = PartyUi.action(activity, "≈ Lignende det aktuelle nummer", false);
        layout.addView(current, new LinearLayout.LayoutParams(-1, dp(48)));
        current.setOnClickListener(v -> { if (partyTrackMedia != null) showSimilar(partyTrackMedia.optString("uri", "")); });
        ScrollView scroll = new ScrollView(activity); scroll.setVerticalScrollBarEnabled(false);
        LinearLayout results = panelBody(activity); scroll.addView(results); layout.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
        TextView status = PartyUi.text(activity, "Find et nummer til jukeboxen", 15, PartyUi.MUTED); results.addView(status);
        final TextView[] tabs = new TextView[3]; final String[] ids = {"library", "similar", "ai"};
        final String[] names = {"Søg", "Similar", "AI DJ"}; final boolean[] enabled = {searchLibrary, searchSimilar, searchAi};
        Runnable updateMode = () -> {
            boolean similar = "similar".equals(selectedMode[0]), ai = "ai".equals(selectedMode[0]);
            input.setHint(ai ? "Fx rolig jazz med saxofon" : similar ? "Fx calm jazz with saxophone" : "Titel eller kunstner");
            explanation.setText(ai ? "Beskriv dit musikønske. AI finder forslag, som matches i dine musikkilder." : similar ? "Find lydmæssigt lignende musik i dit analyserede bibliotek. Eller brug nummeret, der spiller nu." : "Find et bestemt nummer eller en kunstner i dine Music Assistant-kilder.");
            current.setVisibility(similar && currentSimilar && partyTrackMedia != null ? View.VISIBLE : View.GONE);
            for (int i = 0; i < 3; i++) if (tabs[i] != null) tabs[i].setBackground(PartyUi.shape(activity, ids[i].equals(selectedMode[0]) ? 0xFF25665A : 0xFF222C38, 22, true));
        };
        for (int i = 0; i < 3; i++) if (enabled[i]) {
            final String id = ids[i]; TextView tab = PartyUi.action(activity, names[i], false); tabs[i] = tab;
            LinearLayout.LayoutParams tp = new LinearLayout.LayoutParams(0, dp(44), 1); tp.rightMargin = dp(6); pills.addView(tab, tp);
            tab.setOnClickListener(v -> { selectedMode[0] = id; searchGeneration++; results.removeAllViews(); status.setText("Skriv dit ønske ovenfor"); results.addView(status); updateMode.run(); });
        }
        updateMode.run();
        openSheet(activity, "Find musik", layout, false);
        Runnable search = () -> {
            String query = input.getText().toString().trim(); if (query.isEmpty() || query.length() > 1000 || io == null) return;
            InputMethodManager keyboard = (InputMethodManager) activity.getSystemService(Context.INPUT_METHOD_SERVICE);
            if (keyboard != null) keyboard.hideSoftInputFromWindow(input.getWindowToken(), 0);
            input.clearFocus(); final long request = ++searchGeneration; final boolean aiDj = "similar".equals(selectedMode[0]);
            final String base = maBase(), token = maToken; results.removeAllViews(); status.setText("Søger…"); results.addView(status);
            if ("ai".equals(selectedMode[0])) { startAiSearch(activity, query, results, status, queue, generation, request); return; }
            io.execute(() -> {
                java.util.List<PartyJukebox.Result> found = null;
                try {
                    JSONObject args = new JSONObject().put("search_query", query).put("media_types", new JSONArray().put("track")).put("limit", 20);
                    if (aiDj) args.put("providers", new JSONArray().put("sonic_similarity"));
                    Object response = partyRequest(base, token, "music/search", args);
                    if (response instanceof JSONObject) found = PartyJukebox.results((JSONObject) response, base);
                } catch (Throwable ignored) {}
                final java.util.List<PartyJukebox.Result> matches = found;
                main.post(() -> {
                    if (!validPanel(queue, generation, request) || !allowSearch) return;
                    results.removeAllViews();
                    if (matches == null || matches.isEmpty()) {
                        status.setText(matches == null ? "Søgning mislykkedes. Kontrollér MA-forbindelsen." : aiDj ? "Ingen stemningsforslag endnu. Aktivér Sonic Similarity → free-text search i MA, analysér biblioteket og prøv igen efter modelindlæsning. Engelske beskrivelser anbefales i første test." : "Ingen numre fundet"); results.addView(status); return;
                    }
                    for (PartyJukebox.Result match : matches) addMediaRow(activity, results, match, request, queue, generation,
                            () -> { if (allowSearch) chooseMedia(activity, match, false, queue, generation); });
                });
            });
        };
        submit.setOnClickListener(v -> search.run()); input.setOnEditorActionListener((v, action, event) -> { if (action == EditorInfo.IME_ACTION_SEARCH) { search.run(); return true; } return false; });
    }
    private JSONObject djRequest(String path, JSONObject data) throws Exception {
        return companionRequest(context.getSharedPreferences(PARTY_PREFS, Context.MODE_PRIVATE).getString("dj_url", ""), "AI DJ", path, data);
    }
    private JSONObject companionRequest(String saved, String service, String path, JSONObject data) throws Exception {
        if (!validDjUrl(saved)) throw new java.io.IOException(service + " er ikke forbundet. Åbn forbindelsen i Party-indstillinger.");
        java.net.URI parsed = new java.net.URI(saved);
        String token = "";
        for (String part : (parsed.getRawFragment() == null ? "" : parsed.getRawFragment()).split("&")) {
            String[] pair = part.split("=", 2);
            if (pair.length == 2 && "token".equals(pair[0])) token = java.net.URLDecoder.decode(pair[1], "UTF-8");
        }
        if (token.length() < 24) throw new java.io.IOException(service + "-forbindelsen mangler et gyldigt token.");
        java.net.URI origin = new java.net.URI(parsed.getScheme(), null, parsed.getHost(), parsed.getPort(), path, null, null);
        HttpURLConnection c = (HttpURLConnection) origin.toURL().openConnection();
        c.setInstanceFollowRedirects(false); c.setConnectTimeout(2500); c.setReadTimeout(5000); c.setUseCaches(false);
        c.setRequestProperty("Authorization", "Bearer " + token);
        try {
            if (data != null) {
                c.setRequestMethod("POST"); c.setDoOutput(true); c.setRequestProperty("Content-Type", "application/json");
                byte[] bytes = data.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8); c.setFixedLengthStreamingMode(bytes.length);
                try (java.io.OutputStream out = c.getOutputStream()) { out.write(bytes); }
            }
            int code = c.getResponseCode();
            if (code != 200 && code != 202) throw new java.io.IOException(code == 401 ? service + " afviste forbindelsen. Kontrollér tokenet." : service + " svarede med fejl " + code + ". Prøv igen senere.");
            try (InputStream in = c.getInputStream()) {
                java.io.ByteArrayOutputStream bytes = new java.io.ByteArrayOutputStream(); byte[] chunk = new byte[4096]; int n;
                while ((n = in.read(chunk)) >= 0) { if (bytes.size() + n > 512 * 1024) throw new java.io.IOException(service + "-svaret er for stort"); bytes.write(chunk, 0, n); }
                return new JSONObject(bytes.toString("UTF-8"));
            }
        } finally { c.disconnect(); }
    }
    private void startAiSearch(Activity activity, String query, LinearLayout rows, TextView status, String queue, long generation, long request) {
        io.execute(() -> {
            try {
                JSONObject response = djRequest("/api/suggest", new JSONObject().put("prompt", query).put("count", 12));
                String id = response.getString("id");
                main.post(() -> pollAiSearch(activity, id, rows, status, queue, generation, request, SystemClock.elapsedRealtime()));
            } catch (Exception error) { main.post(() -> { if (validPanel(queue, generation, request)) status.setText(error.getMessage()); }); }
        });
    }
    private void pollAiSearch(Activity activity, String id, LinearLayout rows, TextView status, String queue, long generation, long request, long started) {
        if (!validPanel(queue, generation, request) || !searchAi || io == null) return;
        if (SystemClock.elapsedRealtime() - started > 180000) { status.setText("AI DJ brugte for lang tid. Prøv igen senere."); return; }
        io.execute(() -> {
            try {
                JSONObject response = djRequest("/api/jobs/" + id, null);
                main.post(() -> {
                    if (!validPanel(queue, generation, request) || !searchAi) return;
                    String state = response.optString("state");
                    if ("error".equals(state)) { status.setText(response.optString("error", "AI DJ kunne ikke finde musik")); return; }
                    if (!"ready".equals(state)) { status.setText(response.optString("progress", "AI finder musik…")); main.postDelayed(() -> pollAiSearch(activity, id, rows, status, queue, generation, request, started), 1500); return; }
                    rows.removeAllViews();
                    try {
                        java.util.List<PartyJukebox.Result> matches = PartyJukebox.results(response, maBase());
                        if (matches.isEmpty()) { status.setText("Ingen sikre matches i dine musikkilder"); rows.addView(status); }
                        for (PartyJukebox.Result match : matches) addMediaRow(activity, rows, match, request, queue, generation, () -> chooseMedia(activity, match, false, queue, generation));
                    } catch (Exception error) { status.setText("AI-resultatet kunne ikke læses"); rows.addView(status); }
                });
            } catch (Exception error) { main.post(() -> { if (validPanel(queue, generation, request)) status.setText(error.getMessage()); }); }
        });
    }
    private boolean validPanel(String queue, long generation, long request) {
        return host != null && partyFullscreen && searchDialog != null && request == searchGeneration && generation == partyGeneration && queue.equals(activeQueue());
    }
    private void addMediaRow(Activity a, LinearLayout rows, PartyJukebox.Result media, long request, String queue, long generation, Runnable action) {
        LinearLayout row = new LinearLayout(a); row.setGravity(Gravity.CENTER_VERTICAL); row.setPadding(dp(8), dp(8), dp(12), dp(8));
        row.setBackground(new android.graphics.drawable.RippleDrawable(ColorStateList.valueOf(0x3365E5CF), PartyUi.shape(a, 0xFF202A35, 16, false), null));
        ImageView cover = new ImageView(a); cover.setScaleType(ImageView.ScaleType.CENTER_CROP); cover.setImageDrawable(new PartyUi.Glyph("playlist"));
        cover.setBackground(PartyUi.shape(a, 0xFF344252, 12, false)); cover.setClipToOutline(true);
        row.addView(cover, new LinearLayout.LayoutParams(dp(56), dp(56)));
        LinearLayout labels = panelBody(a); labels.setPadding(dp(12), 0, 0, 0);
        TextView name = PartyUi.text(a, media.track.title, 16, PartyUi.INK); name.setTypeface(Typeface.DEFAULT_BOLD); name.setMaxLines(2); name.setEllipsize(android.text.TextUtils.TruncateAt.END); labels.addView(name);
        if (!media.track.artist.isEmpty()) { TextView artist = PartyUi.text(a, media.track.artist, 13, PartyUi.MUTED); artist.setSingleLine(true); artist.setEllipsize(android.text.TextUtils.TruncateAt.END); labels.addView(artist); }
        row.addView(labels, new LinearLayout.LayoutParams(0, -2, 1));
        if (media.uri.contains("://track/") && searchSimilar && currentSimilar) {
            TextView similar = PartyUi.action(a, "≈", false); similar.setContentDescription("Find numre som " + media.track.title);
            row.addView(similar, new LinearLayout.LayoutParams(dp(44), dp(44)));
            similar.setOnClickListener(v -> { if (validPanel(queue, generation, request)) showSimilar(media.uri); });
        }
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2); lp.bottomMargin = dp(8); rows.addView(row, lp);
        row.setOnClickListener(v -> { if (validPanel(queue, generation, request)) action.run(); });
        if (!media.track.artwork.isEmpty() && artIo != null) {
            artIo.execute(() -> {
                Bitmap image = fetchPartyBitmap(media.track.artwork);
                if (image != null && Math.max(image.getWidth(), image.getHeight()) > 160) {
                    float scale = 160f / Math.max(image.getWidth(), image.getHeight());
                    image = Bitmap.createScaledBitmap(image, Math.max(1, Math.round(image.getWidth() * scale)), Math.max(1, Math.round(image.getHeight() * scale)), true);
                }
                final Bitmap result = image;
                main.post(() -> { if (result != null && validPanel(queue, generation, request)) cover.setImageBitmap(result); });
            });
        }
    }
    private void showPlaylists() {
        Activity a = activeKioskActivity(); if (!showPlaylists || !playerControlsReady() || a == null || io == null) return;
        LinearLayout body = panelBody(a); ScrollView scroll = new ScrollView(a); scroll.setVerticalScrollBarEnabled(false);
        LinearLayout rows = panelBody(a); scroll.addView(rows); body.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
        TextView message = PartyUi.text(a, "Henter favoritplaylister…", 15, PartyUi.MUTED); rows.addView(message);
        openSheet(a, "Favoritplaylister", body, true);
        final long request = ++searchGeneration, generation = partyGeneration;
        final String queue = activeQueue(), base = maBase(), token = maToken;
        io.execute(() -> {
            java.util.List<PartyJukebox.Result> favorites = null;
            try {
                Object response = partyRequest(base, token, "music/playlists/library_items", new JSONObject().put("favorite", true).put("summary", false).put("limit", 200).put("offset", 0).put("order_by", "sort_name"));
                if (response instanceof JSONArray) favorites = PartyJukebox.playlists((JSONArray) response, base);
            } catch (Throwable ignored) {}
            final java.util.List<PartyJukebox.Result> items = favorites;
            main.post(() -> {
                if (!validPanel(queue, generation, request) || !showPlaylists) return;
                rows.removeAllViews();
                if (items == null || items.isEmpty()) {
                    message.setText(items == null ? "Playlister kunne ikke hentes fra MA." : "Markér dine begivenheds-playlister som favoritter i Music Assistant. De vises her næste gang du åbner panelet."); rows.addView(message); return;
                }
                for (PartyJukebox.Result item : items) addMediaRow(a, rows, item, request, queue, generation,
                        () -> { if (showPlaylists) chooseMedia(a, item, true, queue, generation); });
            });
        });
    }
    private void chooseMedia(Activity a, PartyJukebox.Result media, boolean playlist, String queue, long generation) {
        if (!playerControlsReady() || generation != partyGeneration || !queue.equals(activeQueue())) return;
        if (selectionDialog != null) selectionDialog.dismiss();
        LinearLayout body = panelBody(a);
        TextView title = PartyUi.text(a, media.track.title, 20, PartyUi.INK); title.setTypeface(Typeface.DEFAULT_BOLD); body.addView(title);
        if (playlist) {
            panelHeading(body, "PLAYLISTE");
            addPanelAction(body, "Start playliste · erstat køen", false, () -> {
                if (!showPlaylists || generation != partyGeneration || !queue.equals(activeQueue())) return;
                try { sendPlayerCommand(new PartyPlayerControls.Request("player_queues/play_media", new JSONObject().put("queue_id", queue).put("media", media.uri).put("option", "replace")), -1); }
                catch (Exception error) { reportPlayerCommandError(); }
                if (selectionDialog != null) selectionDialog.dismiss(); dismissSearch();
            });
            addPanelAction(body, "Læg hele playlisten sidst i køen", false, () -> { if (showPlaylists) { placeTrack(media.uri, -1, queue, generation); if (selectionDialog != null) selectionDialog.dismiss(); } });
        } else {
            panelHeading(body, "PLACERING I KØEN");
            EditText position = new EditText(a); position.setTextColor(PartyUi.INK); position.setHintTextColor(PartyUi.MUTED); position.setSingleLine(true);
            position.setInputType(android.text.InputType.TYPE_CLASS_NUMBER); position.setHint("Tomt = sidst i køen");
            position.setPadding(dp(14), 0, dp(14), 0); position.setBackground(PartyUi.shape(a, 0xFF222C38, 16, true));
            int saved = context.getSharedPreferences(PARTY_PREFS, Context.MODE_PRIVATE).getInt("add_position", -1);
            if (saved >= 0) position.setText(String.valueOf(saved));
            LinearLayout chips = new LinearLayout(a);
            String[] names = {"Nu", "Næste", "Nr. 3", "Sidst"}; int[] values = {0, 1, 3, -1};
            for (int i = 0; i < names.length; i++) {
                final int value = values[i]; TextView chip = PartyUi.action(a, names[i], saved == value); chip.setGravity(Gravity.CENTER); chip.setPadding(0, 0, 0, 0); chip.setTextSize(13);
                LinearLayout.LayoutParams cp = new LinearLayout.LayoutParams(0, dp(48), 1); cp.rightMargin = dp(4); chips.addView(chip, cp);
                chip.setOnClickListener(v -> { position.setText(value < 0 ? "" : String.valueOf(value)); for (int j = 0; j < chips.getChildCount(); j++) ((TextView)chips.getChildAt(j)).setTextColor(chips.getChildAt(j) == chip ? PartyUi.ACCENT : PartyUi.INK); });
            }
            body.addView(chips); LinearLayout.LayoutParams pp = new LinearLayout.LayoutParams(-1, dp(52)); pp.topMargin = dp(12); pp.bottomMargin = dp(12); body.addView(position, pp);
            TextView hint = PartyUi.text(a, "0 = afspil nu · 1 = næste · 3 = tredje nummer fra nu", 13, PartyUi.MUTED); body.addView(hint);
            panelHeading(body, "");
            addPanelAction(body, "Tilføj nummer", true, () -> {
                if (!allowSearch || generation != partyGeneration || !queue.equals(activeQueue())) return;
                int number = -1; try { if (!position.getText().toString().trim().isEmpty()) number = Integer.parseInt(position.getText().toString().trim()); } catch (Exception error) { position.setError("Vælg 0–100 eller tomt for sidst"); return; }
                if (number < -1 || number > 100) { position.setError("Vælg 0–100 eller tomt for sidst"); return; }
                context.getSharedPreferences(PARTY_PREFS, Context.MODE_PRIVATE).edit().putInt("add_position", number).apply();
                placeTrack(media.uri, number, queue, generation); if (selectionDialog != null) selectionDialog.dismiss();
            });
        }
        ScrollView choiceScroll = new ScrollView(a); choiceScroll.setVerticalScrollBarEnabled(false); choiceScroll.addView(body);
        LinearLayout choiceBody = panelBody(a); choiceBody.addView(choiceScroll, new LinearLayout.LayoutParams(-1, 0, 1));
        selectionDialog = PartyUi.sheet(a, playlist ? "Vælg stemning" : "Tilføj til jukebox", choiceBody, false);
        if (selectionDialog.getWindow() != null) selectionDialog.getWindow().setLayout(Math.min(dp(520), a.getResources().getDisplayMetrics().widthPixels - dp(24)), Math.min(dp(560), a.getResources().getDisplayMetrics().heightPixels - dp(64)));
        final Dialog opened = selectionDialog;
        opened.setOnDismissListener(d -> { if (selectionDialog == opened) selectionDialog = null; }); opened.show();
    }
    private void placeTrack(String uri, int position, String queue, long generation) {
        if (!playerControlsReady() || generation != partyGeneration || !queue.equals(activeQueue()) || io == null) return;
        if (position <= 0) { try { sendPlayerCommand(PartyJukebox.enqueue(queue, uri, position == 0), -1); } catch (Exception error) { reportPlayerCommandError(); } return; }
        final String base = maBase(), token = maToken;
        playerCommandPending = true; updatePlayerControls();
        io.execute(() -> {
            String message = "Nummeret kunne ikke tilføjes."; boolean ok = false, added = false;
            try {
                Object resolved = partyRequest(base, token, "music/item_by_uri", new JSONObject().put("uri", uri));
                if (!(resolved instanceof JSONObject) || ((JSONObject)resolved).optString("uri").isEmpty()) throw new IllegalStateException();
                final String canonicalUri = ((JSONObject)resolved).getString("uri");
                Object raw = partyRequest(base, token, "player_queues/get", new JSONObject().put("queue_id", queue));
                if (!(raw instanceof JSONObject) || !queue.equals(((JSONObject)raw).optString("queue_id"))) throw new IllegalStateException();
                JSONObject before = (JSONObject)raw;
                if (before.optBoolean("shuffle_enabled")) { message = "Slå shuffle fra i MA for at vælge en præcis køplacering."; throw new IllegalStateException(); }
                int offset = PartyPlacement.tailOffset(before);
                Object oldTail = partyRequest(base, token, "player_queues/items", new JSONObject().put("queue_id", queue).put("offset", offset).put("limit", 32));
                if (!(oldTail instanceof JSONArray) || generation != partyGeneration || !queue.equals(activeQueue())) throw new IllegalStateException();
                PartyPlayerControls.Request add = PartyJukebox.enqueue(queue, uri, false);
                added = PartyPlayerControls.accepted(partyRequest(base, token, add.command, add.args)); if (!added) throw new IllegalStateException();
                raw = partyRequest(base, token, "player_queues/get", new JSONObject().put("queue_id", queue));
                Object tail = partyRequest(base, token, "player_queues/items", new JSONObject().put("queue_id", queue).put("offset", offset).put("limit", 32));
                if (!(raw instanceof JSONObject) || !(tail instanceof JSONArray) || generation != partyGeneration || !queue.equals(activeQueue())) throw new IllegalStateException();
                PartyPlayerControls.Request move = PartyPlacement.move(before, (JSONArray)oldTail, (JSONObject)raw, (JSONArray)tail, offset, position, canonicalUri);
                if (move == null) throw new IllegalStateException();
                ok = move.command.isEmpty() || PartyPlayerControls.accepted(partyRequest(base, token, move.command, move.args));
                if (ok) message = "Nummeret er tilføjet på plads " + Math.min(position, Math.max(1, ((JSONObject)raw).optInt("items") - 1 - ((JSONObject)raw).optInt("current_index"))) + " fra nu.";
            } catch (Throwable ignored) { if (added) message = "Nummeret er tilføjet sidst; køen ændrede sig, eller placeringen er allerede bufferet. Det er ikke flyttet."; }
            final boolean success = ok; final String status = message;
            main.post(() -> { playerCommandPending = false; if (host != null) { host.status(status, !success); android.widget.Toast.makeText(context, status, android.widget.Toast.LENGTH_LONG).show(); pollMedia(); partyLastPoll = 0; pollPartyQueue(); updatePlayerControls(); } });
        });
    }
    private void resetTrackLyrics() {
        partyTrackMedia = null; lyricsTrack = ""; lyricsContent = ""; lyricsGeneration++; lyricsLastPoll = 0;
        lyrics = PartyLyrics.parse("", ""); if (lyricsView != null) lyricsView.setLyrics(lyrics);
    }
    private void applyTrackLyrics() {
        String identity = partyTrackMedia == null ? "" : partyTrackMedia.optString("uri", partyTrackMedia.optString("provider") + ":" + partyTrackMedia.optString("item_id"));
        if (!identity.equals(lyricsTrack)) { lyricsTrack = identity; lyricsGeneration++; lyricsLastPoll = 0; lyrics = PartyLyrics.parse("", ""); lyricsContent = ""; }
        JSONObject metadata = partyTrackMedia == null ? null : partyTrackMedia.optJSONObject("metadata");
        String content = metadata == null ? "" : metadata.optString("lrc_lyrics", "") + "\u0000" + metadata.optString("lyrics", "");
        if (!content.equals(lyricsContent)) { lyricsContent = content; PartyLyrics available = PartyLyrics.fromMedia(partyTrackMedia); if (!available.lines.isEmpty()) lyrics = available; }
        if (lyricsView != null) lyricsView.setLyrics(lyrics);
    }
    private void pollPartyLyrics() {
        if (!partyFullscreen || !PartySignal.lyrics(partyEffect) || lyricsPending || io == null || partyTrackMedia == null || !lyrics.lines.isEmpty()) return;
        long now = SystemClock.elapsedRealtime(); if (now - lyricsLastPoll < 30000) return; lyricsLastPoll = now;
        final String id = partyTrackMedia.optString("item_id", ""), provider = partyTrackMedia.optString("provider", "");
        if (id.isEmpty() || provider.isEmpty()) return;
        final String base = maBase(), token = maToken; final long generation = lyricsGeneration, queueGeneration = partyGeneration;
        final JSONObject queuedTrack = partyTrackMedia;
        lyricsPending = true;
        io.execute(() -> {
            PartyLyrics value = null;
            JSONObject fullTrack = queuedTrack;
            try {
                Object media = partyRequest(base, token, "music/tracks/get", new JSONObject().put("item_id", id).put("provider_instance_id_or_domain", provider));
                if (media instanceof JSONObject && ((JSONObject)media).has("item_id")) fullTrack = (JSONObject)media;
                value = PartyLyrics.fromMedia(fullTrack);
            } catch (Throwable ignored) {}
            if (value == null || value.lines.isEmpty()) {
                try {
                    // Same on-demand lookup as MA's own Now Playing UI: queue metadata
                    // and tracks/get may have no stored lyrics even when the provider does.
                    value = PartyLyrics.fromLookup(partyRequest(base, token, "metadata/get_track_lyrics",
                            new JSONObject().put("track", fullTrack), 15000));
                } catch (Throwable ignored) {}
            }
            final PartyLyrics found = value;
            main.post(() -> { lyricsPending = false; if (host == null || generation != lyricsGeneration || queueGeneration != partyGeneration) return;
                if (found != null && !found.lines.isEmpty()) { lyrics = found; if (lyricsView != null) lyricsView.setLyrics(lyrics); }
            });
        });
    }
    private void changeEq(boolean restore) {
        if (!showEqControls || !playerControlsReady() || eqPending || io == null) return;
        final String queue = activeQueue(); final long generation = partyGeneration;
        final String base = maBaseUrl.trim().replaceFirst("^ws:", "http:").replaceFirst("^wss:", "https:").replaceAll("/+$", "");
        final String token = maToken;
        final SharedPreferences backups = context.getSharedPreferences("party_eq_original", Context.MODE_PRIVATE);
        eqPending = true;
        io.execute(() -> {
            String status = "EQ kræver MA DSP på Sonos i en Universal-gruppe eller en enkelt Sonos-højttaler.";
            boolean error = true;
            try {
                Object raw = partyRequest(base, token, "players/get", new JSONObject().put("player_id", queue));
                if (!(raw instanceof JSONObject) || !queue.equals(((JSONObject) raw).optString("player_id"))) throw new IllegalStateException();
                JSONObject player = (JSONObject) raw;
                Map<String, JSONObject> members = new HashMap<>(); JSONArray ids = player.optJSONArray("group_members");
                if (ids != null && ids.length() <= 32) for (int i = 0; i < ids.length(); i++) {
                    String id = ids.optString(i, "");
                    Object member = partyRequest(base, token, "players/get", new JSONObject().put("player_id", id));
                    if (member instanceof JSONObject && id.equals(((JSONObject) member).optString("player_id"))) members.put(id, (JSONObject) member);
                }
                java.util.List<String> targets = PartyEq.targets(player, members);
                int success = 0;
                for (String id : targets) {
                    if (generation != partyGeneration || !queue.equals(activeQueue())) break;
                    String key = base + "|" + id;
                    JSONObject config;
                    if (restore) {
                        String saved = backups.getString(key, ""); if (saved.isEmpty()) continue;
                        config = new JSONObject(saved);
                    } else {
                        if (!backups.contains(key)) {
                            Object original = partyRequest(base, token, "config/players/dsp/get", new JSONObject().put("player_id", id));
                            if (!(original instanceof JSONObject) || !((JSONObject) original).has("enabled") || !((JSONObject) original).has("filters")) throw new IllegalStateException();
                            if (!backups.edit().putString(key, original.toString()).commit()) throw new IllegalStateException();
                        }
                        config = PartyEq.punch();
                    }
                    if (generation != partyGeneration || !queue.equals(activeQueue())) break;
                    Object saved = partyRequest(base, token, "config/players/dsp/save", new JSONObject().put("player_id", id).put("config", config));
                    if (!(saved instanceof JSONObject) || !((JSONObject) saved).has("enabled") || !((JSONObject) saved).has("filters") ||
                            ((JSONObject) saved).optBoolean("enabled") != config.optBoolean("enabled")) throw new IllegalStateException();
                    success++;
                    if (restore) backups.edit().remove(key).commit();
                }
                if (!targets.isEmpty()) {
                    status = success == 0 ? (restore ? "Ingen gemt EQ at gendanne for denne gruppe." : "EQ blev ikke ændret.") :
                            (restore ? "Oprindelig EQ gendannet på " : "Party Punch aktiveret på ") + success + " Sonos-højttaler(e).";
                    error = false;
                }
            } catch (Throwable ignored) { status = "EQ kunne ikke ændres fuldt. MA kræver et admin-token; brug Gendan oprindelig EQ efter en delvis ændring."; }
            final String message = status; final boolean failed = error;
            main.post(() -> { eqPending = false; if (host != null) host.status(message, failed); });
        });
    }

    private void pollPlayerVolume() {
        if (!partyFullscreen || !showVolume || playerVolumePending || playerCommandPending || io == null) return;
        long now = SystemClock.elapsedRealtime();
        if (now - playerVolumeLastPoll < 2000) return;
        playerVolumeLastPoll = now; readKioskMusicAssistantConfig();
        final String queue = activeQueue(), entity = nowPlayingEntity;
        if (queue.isEmpty() || maBaseUrl.isEmpty() || maToken.isEmpty()) {
            partyGuestStatus = queue.isEmpty() ? "Gæste-QR: venter på den valgte afspiller" : "Gæste-QR: MA-adresse eller token mangler"; updateParty(); return;
        }
        final long generation = partyGeneration;
        final long revision = playerVolumeRevision;
        final String base = maBaseUrl.trim().replaceFirst("^ws:", "http:").replaceFirst("^wss:", "https:").replaceAll("/+$", "");
        final String token = maToken;
        playerVolumePending = true;
        io.execute(() -> {
            int level = -1;
            try {
                Object result = partyRequest(base, token, "players/get", new JSONObject().put("player_id", queue));
                if (result instanceof JSONObject && queue.equals(((JSONObject) result).optString("player_id", "")))
                    level = PartyPlayerControls.volume((JSONObject) result);
            } catch (Throwable ignored) {}
            final int value = level;
            main.post(() -> {
                playerVolumePending = false;
                if (host == null || !partyFullscreen || generation != partyGeneration || revision != playerVolumeRevision || !entity.equals(nowPlayingEntity) || !queue.equals(activeQueue())) return;
                playerVolume = value; playerVolumeLastSuccess = value < 0 ? 0 : SystemClock.elapsedRealtime();
                updatePlayerControls();
            });
        });
    }
    private void removePartyView() {
        if (partyRoot != null && partyRoot.getParent() instanceof ViewGroup) ((ViewGroup) partyRoot.getParent()).removeView(partyRoot);
        partyRoot = null; partyView = null; partyActivity = null; lyricsView = null; main.removeCallbacks(lyricTick);
        volumeSlider = null; volumeLabel = null; playbackButton = null; stopButton = null; volumeMinus = null; volumePlus = null; volumeDragging = false; volumeDragQueue = "";
    }
    private void removeStaleViews(Activity activity) {
        if (activity == null) return;
        View content = activity.findViewById(android.R.id.content);
        if (content instanceof ViewGroup) {
            ViewGroup root = (ViewGroup) content;
            for (int i = root.getChildCount() - 1; i >= 0; i--) if ("party-mode:view".equals(root.getChildAt(i).getTag())) root.removeViewAt(i);
        }
    }
    private void registerLifecycle() {
        if (!(context.getApplicationContext() instanceof Application)) return;
        application = (Application) context.getApplicationContext();
        lifecycle = new Application.ActivityLifecycleCallbacks() {
            @Override public void onActivityCreated(Activity a, Bundle b) {}
            @Override public void onActivityStarted(Activity a) {}
            @Override public void onActivityResumed(Activity a) { currentActivity = a; if (partyFullscreen) ensurePartyView(); }
            @Override public void onActivityPaused(Activity a) {
                if (currentActivity == a) currentActivity = null;
                if (partyFullscreen && partyActivity == a && !a.isChangingConfigurations() && SystemClock.elapsedRealtime() >= foregroundUntil) { activation.hide(); closePresentation(); }
            }
            @Override public void onActivityStopped(Activity a) {}
            @Override public void onActivitySaveInstanceState(Activity a, Bundle b) {}
            @Override public void onActivityDestroyed(Activity a) { if (partyActivity == a) removePartyView(); }
        };
        application.registerActivityLifecycleCallbacks(lifecycle);
    }
    private Activity activeKioskActivity() {
        Activity a = currentActivity;
        if (a != null && !a.isFinishing() && !a.isDestroyed()) return a;
        return findResumedActivity();
    }
    private void readKioskMusicAssistantConfig() {
        SharedPreferences prefs = context.getSharedPreferences("FlutterSharedPreferences", Context.MODE_PRIVATE);
        maBaseUrl = prefs.getString("flutter.ks.sendspin.ma_url", ""); maToken = prefs.getString("flutter.ks.sendspin.ma_token", "");
    }
    private void setPartyEffect(String effect) {
        partyEffect = PartySignal.effect(effect);
        context.getSharedPreferences(PARTY_PREFS, Context.MODE_PRIVATE).edit().putString("effect", partyEffect).apply();
        publishPartyState();
        if (partyFullscreen) { removePartyView(); ensurePartyView(); publishPresentation(); pollPartyLyrics(); }
    }
    private void setPartyGuests(boolean follow) {
        partyGuestsFollow = follow;
        context.getSharedPreferences(PARTY_PREFS, Context.MODE_PRIVATE).edit().putString("guests_follow", String.valueOf(follow)).apply();
        clearPartyGuests(); partyGuestLastPoll = 0; publishPartyState(); updateParty();
        if (follow && partyFullscreen) pollPartyGuests();
    }
    private void setPartyQueue(boolean visible) {
        partyQueueVisible = visible;
        context.getSharedPreferences(PARTY_PREFS, Context.MODE_PRIVATE).edit().putString("queue_visible", String.valueOf(visible)).apply();
        if (partyView != null) partyView.setPresentation(partyEffect, partyQueueVisible);
    }
    private void updateParty() {
        if (!partyFullscreen || partyView == null) return;
        updatePlayerControls();
        partyView.setGuests(partyGuestsFollow ? partyQr : null, partyGuestText, partyGuestsFollow ? partyGuestStatus : "");
        if (partyGuestsFollow && !partyGuestStatus.isEmpty() && !partyGuestStatus.equals(reportedGuestStatus)) {
            reportedGuestStatus = partyGuestStatus; host.status(partyGuestStatus, false);
        }
        if (partyModel == null || SystemClock.elapsedRealtime() - partyLastSuccess > 8000) {
            java.util.List<PartyQueueModel.Track> fallback = new java.util.ArrayList<>();
            String title = attr(mediaAttributes, "media_title", "");
            if (!title.isEmpty()) fallback.add(new PartyQueueModel.Track(mediaIdentity, title, attr(mediaAttributes, "media_artist", ""), attr(mediaAttributes, "entity_picture", ""), true));
            PartyQueueModel model = new PartyQueueModel(fallback, estimatedMediaPosition(), numberAttr(mediaAttributes, "media_duration", 0), mediaState);
            partyView.setQueue(model, new HashMap<>(partyArtwork), "playing".equalsIgnoreCase(mediaState)); fetchPartyArtwork(model);
        } else partyView.setQueue(partyModel, new HashMap<>(partyArtwork), "playing".equalsIgnoreCase(mediaState));
        if (nowPlayingEntity.isEmpty()) partyView.setMessage("Vælg højttaler i Party-pluginet");
        else if (maBaseUrl.isEmpty() || maToken.isEmpty()) partyView.setMessage("Tilslut Music Assistant i Kiosk");
        else if (attr(mediaAttributes, "active_queue", "").isEmpty()) partyView.setMessage("Venter på MA-kø fra den valgte højttaler");
    }
    private String resolveHaUrl(String path) {
        if (path == null || path.isEmpty()) return null;
        if (path.startsWith("http://") || path.startsWith("https://")) return path;
        if (haBaseUrl.isEmpty()) return null;
        return haBaseUrl.replaceAll("/+$", "") + (path.startsWith("/") ? path : "/" + path);
    }
    private static String setting(Map<String, Object> settings, String key, String fallback) {
        Object value = settings.get(key); return value == null ? fallback : String.valueOf(value).trim();
    }
    private static int intSetting(Map<String, Object> settings, String key, int fallback, int min, int max) {
        Object value = settings.get(key);
        return value instanceof Number ? Math.max(min, Math.min(max, ((Number) value).intValue())) : fallback;
    }

    private void registerPartyAudioReceiver() {
        partyAudioReceiver = new BroadcastReceiver() {
            @Override public void onReceive(Context ignored, Intent intent) {
                if (!partyFullscreen || partyView == null || "off".equals(partyEffect)) return;
                long age = SystemClock.elapsedRealtime() - intent.getLongExtra("at", 0);
                if (age < 0 || age > 1000) return;
                if (lyricsView != null) lyricsView.acceptAudio(intent.getFloatArrayExtra("bands"));
                partyView.acceptAudio(intent.getFloatArrayExtra("bands"), intent.getFloatArrayExtra("waveform"),
                        intent.getIntExtra("fps", 20), intent.getBooleanExtra("demo", false));
            }
        };
        IntentFilter filter = new IntentFilter("me.jxl.kiosk.plugins.PARTY_AUDIO_FRAME");
        if (Build.VERSION.SDK_INT >= 33) context.registerReceiver(partyAudioReceiver, filter, Context.RECEIVER_NOT_EXPORTED);
        else context.registerReceiver(partyAudioReceiver, filter);
    }

    private void showPartyMenu(View anchor) {
        Activity a = activeKioskActivity(); if (a == null || !menuVisible()) return;
        LinearLayout body = panelBody(a), rows = panelBody(a); ScrollView scroll = new ScrollView(a);
        scroll.setVerticalScrollBarEnabled(false); scroll.addView(rows); body.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
        if (menuCategories.contains("visuals")) {
            panelHeading(rows, "VISUALISERING");
            String[] ids = {"off", "spectrum", "mirror", "radial", "wave", "particles", "tunnel", "lyrics", "discolyrics"};
            String[] names = {"Ingen visualisering", "Neon Spectrum", "Mirror Spectrum", "Radial Pulse", "Waveform", "Star Particles", "Neon Tunnel", "Lyrics · syng med", "Disco Lyrics · neon og pulser"};
            for (int i = 0; i < ids.length; i++) {
                final String effect = ids[i]; addPanelAction(rows, names[i], effect.equals(partyEffect), () -> { setPartyEffect(effect); showPartyMenu(anchor); });
            }
        }
        if (menuCategories.contains("music")) {
            panelHeading(rows, "MUSIK OG FORBINDELSE");
            if (allowSearch && searchAi) addPanelAction(rows, "AI DJ · åbn", false, this::showDj);
            addPanelAction(rows, "AI DJ · opsæt adresse", false, this::configureDj);
        }
        if (menuCategories.contains("screen")) {
            panelHeading(rows, "SKÆRM");
            addPanelAction(rows, "Hele køen", partyQueueVisible, () -> { setPartyQueue(!partyQueueVisible); showPartyMenu(anchor); });
            addPanelAction(rows, "Vis volumen", showVolume, () -> { setPlayerControlsVisible(true, !showVolume); showPartyMenu(anchor); });
            addPanelAction(rows, "Volumen · −/+ knapper", "Buttons".equals(volumeStyle), () -> { volumeStyle = "Buttons"; context.getSharedPreferences(PARTY_PREFS, Context.MODE_PRIVATE).edit().putString("volume_style", volumeStyle).apply(); setPlayerControlsVisible(true, true); showPartyMenu(anchor); });
            addPanelAction(rows, "Volumen · slider", "Slider".equals(volumeStyle), () -> { volumeStyle = "Slider"; context.getSharedPreferences(PARTY_PREFS, Context.MODE_PRIVATE).edit().putString("volume_style", volumeStyle).apply(); setPlayerControlsVisible(true, true); showPartyMenu(anchor); });
            addPanelAction(rows, "Vis afspilningsknapper", showPlayback, () -> { setPlayerControlsVisible(false, !showPlayback); showPartyMenu(anchor); });
        }
        if (menuCategories.contains("guests")) {
            panelHeading(rows, "GÆSTER");
            addPanelAction(rows, "Vis gæste-QR", partyGuestsFollow, () -> { setPartyGuests(!partyGuestsFollow); showPartyMenu(anchor); });
            addPanelAction(rows, "Aktivér gæsteadgang i MA", false, () -> changePartyGuestAccess(true));
            addPanelAction(rows, "Deaktivér gæsteadgang i MA", false, () -> changePartyGuestAccess(false));
            addPanelAction(rows, "Party Guest · opsæt adresse", false, this::configureGuest);
            addPanelAction(rows, "QR · Music Assistant", "Music Assistant".equals(guestPage), () -> { setGuestPage("Music Assistant"); showPartyMenu(anchor); });
            addPanelAction(rows, "QR · vores Party-gæsteside", "Party guest page".equals(guestPage), () -> { setGuestPage("Party guest page"); showPartyMenu(anchor); });
        }
        if (showEqControls && menuCategories.contains("sound")) {
            panelHeading(rows, "LYD");
            addPanelAction(rows, "Party Punch", false, () -> changeEq(false));
            addPanelAction(rows, "Gendan oprindelig EQ", false, () -> changeEq(true));
        }
        if (menuCategories.contains("diagnostics")) {
            panelHeading(rows, "GRAFIK");
            rows.addView(PartyUi.text(a, (partyView != null && partyView.hardwareCanvas() ? "Hardware-accelereret Canvas" : "Software-Canvas / endnu ikke målt") +
            " · " + fps + " FPS" + (settingFpsEconomy ? " · Eco" : "") + "\nEco kan vælges i pluginets backend.", 12, PartyUi.MUTED));
        }
        openSheet(a, "Party-indstillinger", body, false);
    }
    private void setGuestPage(String value) {
        if (!("Music Assistant".equals(value) || "Party guest page".equals(value))) return;
        guestPage = value;
        context.getSharedPreferences(PARTY_PREFS, Context.MODE_PRIVATE).edit().putString("guest_page", value).apply();
        clearPartyGuests(); partyGuestLastPoll = 0; publishPartyState(); updateParty(); pollPartyGuests();
    }
    private void setMenuCategory(String key, boolean visible) {
        if (!java.util.Arrays.asList(menuKeys).contains(key)) return;
        if (visible) menuCategories.add(key); else menuCategories.remove(key);
        context.getSharedPreferences(PARTY_PREFS, Context.MODE_PRIVATE).edit().putBoolean("menu_" + key, visible).apply();
        dismissSearch(); removePartyView(); updatePresentation(); publishPartyState();
    }
    private void clearPartyGuests() {
        final long generation = ++partyGuestGeneration;
        partyGuestUrl = ""; partyQr = null; partyGuestLastSuccess = 0;
        partyGuestStatus = "";
        Runnable clear = () -> {
            if (generation == partyGuestGeneration && partyView != null) partyView.setGuests(null, partyGuestText, "");
        };
        if (Looper.myLooper() == Looper.getMainLooper()) clear.run();
        else main.post(clear);
    }

    private void applyGuestAccessState(String queue, Boolean state) {
        guestAccessQueue = queue; guestAccessState = state;
        if (state == null && reportedGuestAccess != null) {
            try { host.removeSwitch("guest_access"); reportedGuestAccess = null; }
            catch (Throwable error) { host.log("Guest access status unavailable: " + error.getMessage()); }
        }
        publishPartyState();
    }

    private void pollGuestAccessState() {
        if (host == null || context == null || io == null) return;
        final String queue = attr(mediaAttributes, "active_queue", "");
        if (!queue.equals(guestAccessQueue)) { guestAccessRevision++; applyGuestAccessState(queue, null); guestStateLastPoll = 0; }
        if (guestStatePending || partyGuestChangePending) return;
        long now = SystemClock.elapsedRealtime();
        if (guestStateLastPoll != 0 && now - guestStateLastPoll < 15000) return;
        guestStateLastPoll = now;
        readKioskMusicAssistantConfig();
        if (queue.isEmpty() || maBaseUrl.isEmpty() || maToken.isEmpty()) { applyGuestAccessState(queue, null); return; }
        final String base = maBaseUrl.trim().replaceFirst("^ws:", "http:").replaceFirst("^wss:", "https:").replaceAll("/+$", "");
        final String token = maToken;
        final long revision = guestAccessRevision;
        guestStatePending = true;
        io.execute(() -> {
            Boolean state = null;
            try {
                Object response = partyRequest(base, token, "config/providers", new JSONObject().put("provider_domain", "party").put("include_values", true));
                state = PartyGuestConfig.guestAccess(response instanceof JSONArray ? (JSONArray) response : null, queue);
            } catch (Throwable ignored) {}
            final Boolean verified = state;
            main.post(() -> {
                guestStatePending = false;
                if (host == null || revision != guestAccessRevision || partyGuestChangePending || !queue.equals(attr(mediaAttributes, "active_queue", ""))) return;
                applyGuestAccessState(queue, verified);
            });
        });
    }

    private void changePartyGuestAccess(boolean enabled) {
        if (partyGuestChangePending || io == null || context == null) return;
        readKioskMusicAssistantConfig();
        final String queue = attr(mediaAttributes, "active_queue", "");
        if (queue.isEmpty() || maBaseUrl.isEmpty() || maToken.isEmpty()) {
            host.status("Vælg MA-højttalergruppe og tilslut Music Assistant først.", true); return;
        }
        final String base = maBaseUrl.trim().replaceFirst("^ws:", "http:").replaceFirst("^wss:", "https:").replaceAll("/+$", "");
        final String token = maToken;
        final long generation = partyGuestGeneration;
        guestAccessRevision++;
        partyGuestChangePending = true;
        partyGuestStatus = "Opdaterer gæsteadgang…";
        updateParty();
        io.execute(() -> {
            boolean changed = false;
            String message = "Kunne ikke ændre gæsteadgang. MA-tokenet skal have adgang til Party-indstillinger.";
            try {
                JSONObject filter = new JSONObject().put("provider_domain", "party").put("include_values", true);
                Object response = partyRequest(base, token, "config/providers", filter);
                if (!(response instanceof JSONArray)) throw new java.io.IOException("Party settings unavailable");
                String instance = PartyGuestConfig.matchingInstance(response instanceof JSONArray ? (JSONArray) response : null, queue);
                if (instance.isEmpty()) {
                    message = "Vælg den samme eksplicitte højttalergruppe som Party Player i Music Assistant først.";
                } else if (generation == partyGuestGeneration && queue.equals(attr(mediaAttributes, "active_queue", ""))) {
                    JSONObject args = new JSONObject().put("provider_domain", "party").put("instance_id", instance)
                            .put("values", new JSONObject().put("enable_guest_access", enabled));
                    Object saved = partyRequest(base, token, "config/providers/save", args);
                    if (saved instanceof JSONObject && instance.equals(((JSONObject) saved).optString("instance_id", ""))) {
                        Object verified = partyRequest(base, token, "config/providers", filter);
                        changed = Boolean.valueOf(enabled).equals(PartyGuestConfig.guestAccess(
                                verified instanceof JSONArray ? (JSONArray) verified : null, queue));
                    }
                }
            } catch (Throwable ignored) {}
            final boolean success = changed;
            final String error = message;
            main.post(() -> {
                partyGuestChangePending = false;
                if (host == null) return;
                if (!queue.equals(attr(mediaAttributes, "active_queue", ""))) { pollGuestAccessState(); return; }
                guestStateLastPoll = 0;
                if (success) {
                    applyGuestAccessState(queue, enabled);
                    clearPartyGuests(); partyGuestLastPoll = 0;
                    if (enabled) {
                        partyGuestsFollow = true;
                        context.getSharedPreferences(PARTY_PREFS, Context.MODE_PRIVATE).edit().putString("guests_follow", "true").apply();
                    }
                    host.status(enabled ? "MA-gæsteadgang aktiveret." : "MA-gæsteadgang deaktiveret.", false);
                    pollPartyGuests();
                } else { partyGuestStatus = error; host.status(error, true); }
                publishPartyState(); pollGuestAccessState(); updateParty();
            });
        });
    }

    private void pollPartyGuests() {
        if (!partyFullscreen || context == null) return;
        if (!partyFullscreen || !partyGuestsFollow || io == null || context == null) return;
        long now = SystemClock.elapsedRealtime();
        if (partyGuestLastSuccess > 0 && now - partyGuestLastSuccess > 12000) {
            partyQr = null; partyGuestUrl = "";
            partyGuestStatus = "Gæsteadgang kunne ikke bekræftes";
            updateParty();
        }
        if (partyGuestPending || now - partyGuestLastPoll < 5000) return;
        partyGuestLastPoll = now;
        readKioskMusicAssistantConfig();
        final String queue = attr(mediaAttributes, "active_queue", "");
        if (queue.isEmpty() || ("Music Assistant".equals(guestPage) && (maBaseUrl.isEmpty() || maToken.isEmpty()))) {
            partyGuestStatus = queue.isEmpty() ? "Gæste-QR: venter på den valgte afspiller" : "Gæste-QR: MA-adresse eller token mangler"; updateParty(); return;
        }
        final String base = maBaseUrl.trim().replaceFirst("^ws:", "http:").replaceFirst("^wss:", "https:").replaceAll("/+$", "");
        final String token = maToken;
        final long generation = partyGuestGeneration;
        final String destination = guestPage;
        final String configuredGuest = guestConnection();
        final boolean useLibrary = allowSearch && searchLibrary, useSimilar = allowSearch && searchSimilar, useAi = allowSearch && searchAi, useCurrent = allowSearch && currentSimilar;
        final String previousUrl = partyGuestUrl;
        final Bitmap previousQr = partyQr;
        partyGuestPending = true;
        io.execute(() -> {
            String url = "", message = "Aktivér Party-plugin og gæsteadgang i Music Assistant";
            String caption = "Scan og tilføj musik til køen";
            Bitmap qr = null;
            try {
                if ("Party guest page".equals(destination)) {
                    JSONObject modes = new JSONObject().put("library", useLibrary).put("similar", useSimilar).put("ai", useAi).put("current_similar", useCurrent);
                    JSONObject result = companionRequest(configuredGuest, "Party Guest", "/api/guest-link", new JSONObject().put("queue_id", queue).put("modes", modes));
                    url = PartyGuestLink.custom(result.optString("path", ""), configuredGuest);
                    qr = url.equals(previousUrl) && previousQr != null ? previousQr : partyQrBitmap(url);
                    caption = "Scan og find musik til festen";
                    message = url.isEmpty() || qr == null ? "Gæste-QR: kontrollér Party Guest og dens kø-id" : "";
                } else {
                Object player = partyRequest(base, token, "party/player", new JSONObject());
                if (PartyGuestLink.matches(queue, player)) {
                    Object link = partyRequest(base, token, "party/url", new JSONObject());
                    url = link instanceof String ? PartyGuestLink.validated((String) link, base) : "";
                    if (url.isEmpty()) message = "Gæste-QR: aktivér Guest access i Music Assistant";
                    if (!url.isEmpty()) {
                        try {
                            Object config = partyRequest(base, token, "party/config", new JSONObject());
                            if (config instanceof JSONObject) {
                                String value = ((JSONObject) config).optString("qr_text", "");
                                if (!value.isEmpty() && !"null".equals(value)) caption = value.substring(0, Math.min(120, value.length()));
                            }
                        } catch (Throwable ignored) {}
                        qr = url.equals(previousUrl) && previousQr != null ? previousQr : partyQrBitmap(url);
                        message = qr == null ? "Gæste-QR kunne ikke dannes" : "";
                    }
                } else if (player instanceof String && !((String) player).isEmpty()) {
                    message = "Vælg samme højttalergruppe som Party Player i Music Assistant";
                }
                }
            } catch (Throwable ignored) { message = "Party guest page".equals(destination) ? "Gæste-QR: kontrollér Party Guest-adresse, token og samme kø-id" : "Gæste-QR: MA-forbindelsen kunne ikke bekræftes"; }
            final String join = url, status = message, text = caption;
            final Bitmap symbol = qr;
            main.post(() -> {
                partyGuestPending = false;
                if (host == null || !partyFullscreen || !partyGuestsFollow || generation != partyGuestGeneration ||
                        !destination.equals(guestPage) || !queue.equals(attr(mediaAttributes, "active_queue", ""))) return;
                partyGuestUrl = join; partyQr = symbol; partyGuestStatus = status; partyGuestText = text;
                partyGuestLastSuccess = SystemClock.elapsedRealtime();
                updateParty();
            });
        });
    }

    private Bitmap partyQrBitmap(String url) {
        try {
            QrCode qr = QrCode.encodeText(url, QrCode.Ecc.MEDIUM);
            int scale = 6, side = (qr.size + 8) * scale;
            int[] pixels = new int[side * side];
            for (int y = 0; y < side; y++) for (int x = 0; x < side; x++)
                pixels[y * side + x] = qr.getModule(x / scale - 4, y / scale - 4) ? Color.BLACK : Color.WHITE;
            return Bitmap.createBitmap(pixels, side, side, Bitmap.Config.ARGB_8888);
        } catch (Throwable ignored) { return null; }
    }

    private void pollPartyQueue() {
        if (partyView == null || partyPollPending || io == null || context == null) return;
        long now = SystemClock.elapsedRealtime();
        if (now - partyLastPoll < 2000) return;
        partyLastPoll = now;
        readKioskMusicAssistantConfig();
        // HA's MA entity exposes the active queue, including grouped playback.
        // Never substitute the kiosk Sendspin player or an unrelated active queue.
        final String queueId = attr(mediaAttributes, "active_queue", "").trim();
        if (queueId.isEmpty() || maBaseUrl.trim().isEmpty() || maToken.trim().isEmpty()) return;
        if (!queueId.equals(partyTarget)) {
            partyTarget = queueId; partyModel = null; partyLastSuccess = 0; partyGeneration++;
        }
        final long generation = partyGeneration;
        final String entity = nowPlayingEntity;
        final String base = maBaseUrl.trim().replaceFirst("^ws:", "http:").replaceFirst("^wss:", "https:").replaceAll("/+$", "");
        final String token = maToken;
        partyPollPending = true;
        final int before = tracksBefore, after = tracksAfter; final String mediaAtRequest = mediaIdentity;
        io.execute(() -> {
            PartyQueueModel model = null; JSONObject media = null;
            try {
                JSONObject args = new JSONObject(); args.put("queue_id", queueId);
                Object result = partyRequest(base, token, "player_queues/get", args);
                if (result instanceof JSONObject && queueId.equals(((JSONObject) result).optString("queue_id", ""))) {
                    JSONObject queue = (JSONObject) result;
                    JSONObject current = queue.optJSONObject("current_item"); media = current == null ? null : current.optJSONObject("media_item");
                    JSONArray items = null;
                    try {
                        JSONObject itemArgs = new JSONObject();
                        itemArgs.put("queue_id", queueId); itemArgs.put("offset", PartyQueueModel.offset(queue, before)); itemArgs.put("limit", PartyQueueModel.limit(queue, before, after));
                        Object response = partyRequest(base, token, "player_queues/items", itemArgs);
                        if (response instanceof JSONArray) items = (JSONArray) response;
                    } catch (Throwable ignored) {}
                    model = PartyQueueModel.parse(queue, items, base, before, after);
                }
            } catch (Throwable ignored) {}
            final PartyQueueModel snapshot = model; final JSONObject trackMedia = media;
            main.post(() -> {
                partyPollPending = false;
                if (host == null || generation != partyGeneration || !mediaAtRequest.equals(mediaIdentity) || !entity.equals(nowPlayingEntity) ||
                        !queueId.equals(attr(mediaAttributes, "active_queue", ""))) return;
                if (snapshot != null) {
                    partyTrackMedia = trackMedia; applyTrackLyrics();
                    partyModel = snapshot; partyLastSuccess = SystemClock.elapsedRealtime();
                    fetchPartyArtwork(snapshot);
                }
                updateParty();
            });
        });
    }

    private Object partyRequest(String base, String token, String command, JSONObject args) throws Exception {
        return partyRequest(base, token, command, args, 3500);
    }
    private Object partyRequest(String base, String token, String command, JSONObject args, int readTimeout) throws Exception {
        URL url = new URL(base + "/api");
        if (!("http".equals(url.getProtocol()) || "https".equals(url.getProtocol())) || url.getUserInfo() != null) return null;
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        connection.setInstanceFollowRedirects(false);
        connection.setConnectTimeout(2500); connection.setReadTimeout(readTimeout);
        connection.setRequestMethod("POST"); connection.setDoOutput(true); connection.setUseCaches(false);
        connection.setRequestProperty("Authorization", "Bearer " + token);
        connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
        JSONObject request = new JSONObject(); request.put("message_id", "party-mode");
        request.put("command", command); request.put("args", args);
        byte[] body = request.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8);
        connection.setFixedLengthStreamingMode(body.length);
        try {
            try (java.io.OutputStream output = connection.getOutputStream()) { output.write(body); }
            if (connection.getResponseCode() != 200) return null;
            try (InputStream stream = connection.getInputStream()) {
                java.io.ByteArrayOutputStream bytes = new java.io.ByteArrayOutputStream();
                byte[] chunk = new byte[4096]; int count;
                while ((count = stream.read(chunk)) >= 0) {
                    if (bytes.size() + count > 512 * 1024) throw new java.io.IOException("Queue response too large");
                    bytes.write(chunk, 0, count);
                }
                Object response = new JSONTokener(bytes.toString("UTF-8")).nextValue();
                return response instanceof JSONObject && ((JSONObject) response).has("result")
                        ? ((JSONObject) response).opt("result") : response;
            }
        } finally { connection.disconnect(); }
    }

    private void fetchPartyArtwork(PartyQueueModel model) {
        if (artIo == null) return;
        for (PartyQueueModel.Track track : model.tracks) {
            String path = track.artwork;
            if (path.isEmpty() || partyArtwork.containsKey(path) || !partyArtworkPending.add(path)) continue;
            final String resolved = resolveHaUrl(path);
            final long generation = partyGeneration;
            artIo.execute(() -> {
                Bitmap cover = resolved == null ? null : fetchPartyBitmap(resolved);
                main.post(() -> {
                    partyArtworkPending.remove(path);
                    if (host == null || generation != partyGeneration || cover == null) return;
                    if (partyArtwork.size() >= 30) partyArtwork.clear();
                    partyArtwork.put(path, cover);
                    updateParty();
                });
            });
        }
    }

    private Bitmap fetchPartyBitmap(String source) {
        HttpURLConnection connection = null;
        try {
            URL url = new URL(source);
            if (!("http".equals(url.getProtocol()) || "https".equals(url.getProtocol()))) return null;
            connection = (HttpURLConnection) url.openConnection();
            connection.setConnectTimeout(2500); connection.setReadTimeout(3500);
            try (InputStream stream = connection.getInputStream()) {
                java.io.ByteArrayOutputStream bytes = new java.io.ByteArrayOutputStream();
                byte[] chunk = new byte[4096]; int count;
                while ((count = stream.read(chunk)) >= 0) {
                    if (bytes.size() + count > 4 * 1024 * 1024) return null;
                    bytes.write(chunk, 0, count);
                }
                byte[] data = bytes.toByteArray();
                BitmapFactory.Options bounds = new BitmapFactory.Options();
                bounds.inJustDecodeBounds = true;
                BitmapFactory.decodeByteArray(data, 0, data.length, bounds);
                BitmapFactory.Options decode = new BitmapFactory.Options();
                decode.inSampleSize = 1;
                while (Math.max(bounds.outWidth, bounds.outHeight) / decode.inSampleSize > 512) decode.inSampleSize *= 2;
                return BitmapFactory.decodeByteArray(data, 0, data.length, decode);
            }
        } catch (Throwable ignored) { return null; }
        finally { if (connection != null) connection.disconnect(); }
    }

    private Activity findResumedActivity() {
        try {
            Class<?> threadClass = Class.forName("android.app.ActivityThread");
            Method currentThread = threadClass.getDeclaredMethod("currentActivityThread");
            currentThread.setAccessible(true);
            Object thread = currentThread.invoke(null);
            if (thread == null) return null;

            Field activitiesField = threadClass.getDeclaredField("mActivities");
            activitiesField.setAccessible(true);
            Object activitiesObject = activitiesField.get(thread);
            if (!(activitiesObject instanceof Map)) return null;

            Activity fallback = null;
            for (Object record : ((Map<?, ?>) activitiesObject).values()) {
                if (record == null) continue;
                Class<?> recordClass = record.getClass();

                Field activityField = recordClass.getDeclaredField("activity");
                activityField.setAccessible(true);
                Object activityValue = activityField.get(record);
                if (!(activityValue instanceof Activity)) continue;
                Activity activity = (Activity) activityValue;
                if (!activity.getPackageName().equals(context.getPackageName()) ||
                        activity.isFinishing() ||
                        (Build.VERSION.SDK_INT >= 17 && activity.isDestroyed())) {
                    continue;
                }

                if (activity.hasWindowFocus()) return activity;

                boolean paused = false;
                boolean stopped = false;
                try {
                    Field pausedField = recordClass.getDeclaredField("paused");
                    pausedField.setAccessible(true);
                    paused = pausedField.getBoolean(record);
                } catch (Throwable ignored) {}
                try {
                    Field stoppedField = recordClass.getDeclaredField("stopped");
                    stoppedField.setAccessible(true);
                    stopped = stoppedField.getBoolean(record);
                } catch (Throwable ignored) {}

                if (!paused && !stopped) fallback = activity;
            }
            return fallback;
        } catch (Throwable ignored) {
            return null;
        }
    }

    private static Context applicationContext(PluginHost host) {
        try {
            Class<?> activityThread = Class.forName("android.app.ActivityThread");
            Method currentApplication = activityThread.getDeclaredMethod("currentApplication");
            currentApplication.setAccessible(true);
            Object value = currentApplication.invoke(null);
            if (value instanceof Application) return ((Application) value).getApplicationContext();
            if (value instanceof Context) return ((Context) value).getApplicationContext();
        } catch (Throwable ignored) {}

        Object current = host;
        for (int depth = 0; current != null && depth < 5; depth++) {
            Class<?> type = current.getClass();
            for (Class<?> c = type; c != null; c = c.getSuperclass()) {
                try {
                    for (Field field : c.getDeclaredFields()) {
                        field.setAccessible(true);
                        Object value = field.get(current);
                        if (value instanceof Context) return ((Context) value).getApplicationContext();
                    }
                } catch (Throwable ignored) {}
            }

            Object enclosing = null;
            for (Class<?> c = type; c != null && enclosing == null; c = c.getSuperclass()) {
                try {
                    for (Field field : c.getDeclaredFields()) {
                        if (!field.getName().startsWith("this$")) continue;
                        field.setAccessible(true);
                        Object value = field.get(current);
                        if (value != null && value.getClass().getName().startsWith("me.jxl.")) {
                            enclosing = value;
                            break;
                        }
                    }
                } catch (Throwable ignored) {}
            }
            current = enclosing;
        }
        return null;
    }

    private static String attr(Map<?, ?> attributes, String key, String fallback) {
        Object value = attributes == null ? null : attributes.get(key);
        if (value == null) return fallback;
        String text = String.valueOf(value);
        return "null".equals(text) ? fallback : text;
    }

    private static double numberAttr(Map<?, ?> attributes, String key, double fallback) {
        Object value = attributes == null ? null : attributes.get(key);
        if (value instanceof Number) return ((Number) value).doubleValue();
        if (value != null) {
            try { return Double.parseDouble(String.valueOf(value)); }
            catch (Throwable ignored) {}
        }
        return fallback;
    }

    private int dp(int value) {
        return Math.round(value * context.getResources().getDisplayMetrics().density);
    }
}
