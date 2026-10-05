import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.file.Files
import java.util.zip.ZipInputStream
import java.util.zip.ZipOutputStream
import java.util.zip.ZipEntry
import me.jxl.kiosk_satellite.plugins.PluginPackage
import me.jxl.kiosk_satellite.plugins.PluginManifest
import org.json.JSONObject

/** Validate the real release ZIP with Kiosk's pinned installer, without running plugin code. */
fun main(args: Array<String>) {
    val archive = File(args[0])
    val manifest = File(args[1]).readText()
    val root = Files.createTempDirectory("party-install-").toFile()
    try {
        val destination = File(root, "valid")
        val installed = PluginPackage.extract(archive.readBytes(), destination)
        PluginPackage.verifyManifest(installed, manifest)
        check(installed.id == "party-mode")
        verifyUpgradeSettings(installed, PluginManifest(JSONObject(File(args[2]).readText())))
        val license = File(destination, "LICENSE").readText()
        check("Project Nayuki" in license && "Permission is hereby granted" in license) {
            "Bundled QR library license is missing from the accepted LICENSE file"
        }
        val expectedHash = File(archive.path + ".sha256").readText().trim().split(' ').first()
        check(PluginPackage.sha256(archive.readBytes()) == expectedHash)

        // Reproduce the original installation failure using the same installer.
        val bad = ByteArrayOutputStream()
        ZipOutputStream(bad).use { output ->
            ZipInputStream(archive.inputStream()).use { input ->
                while (true) {
                    val entry = input.nextEntry ?: break
                    output.putNextEntry(ZipEntry(entry.name))
                    input.copyTo(output)
                    output.closeEntry()
                }
            }
            output.putNextEntry(ZipEntry("THIRD_PARTY_NOTICES.md"))
            output.write("Not an allowed root package entry".toByteArray())
            output.closeEntry()
        }
        val failure = runCatching { PluginPackage.extract(bad.toByteArray(), File(root, "invalid")) }.exceptionOrNull()
        check(failure?.message == "Unexpected or duplicate ZIP entry: THIRD_PARTY_NOTICES.md") {
            "The installer no longer reproduces the reported package failure"
        }
        check(!File(root, "invalid").exists())
        println("Kiosk installer accepted the release ZIP; manifest, checksum and QR license verified")
    } finally {
        root.deleteRecursively()
    }
}

/** Match PluginBridge.install: retain only declared keys, then validate saved values. */
private fun verifyUpgradeSettings(current: PluginManifest, previous: PluginManifest) {
    val retained = (0 until current.settings.length()).map {
        current.settings.getJSONObject(it).getString("key")
    }.toSet()
    fun upgrade(values: JSONObject): Map<String, Any> {
        val overrides = JSONObject()
        for (key in retained) if (values.has(key)) overrides.put(key, values.get(key))
        return current.config(overrides)
    }
    val saved = JSONObject(previous.config(JSONObject()))
    val baseline = upgrade(saved)
    check(baseline["screenControls"] == "All controls")
    check(current.config(JSONObject())["screenControls"] == "Menu only")
    for (i in 0 until previous.settings.length()) {
        val setting = previous.settings.getJSONObject(i)
        val key = setting.getString("key")
        if (setting.getString("type") != "select") continue
        val options = setting.getJSONArray("options")
        for (j in 0 until options.length()) {
            val value = options.getString(j)
            val migrated = upgrade(JSONObject(saved.toString()).put(key, value))
            if (key in retained) check(migrated[key] == value) { "Upgrade lost $key=$value" }
        }
    }
    // Prove this catches the exact 0.1.5 failure before plugin.configure can run.
    val broken = JSONObject(current.json.toString())
    val settings = broken.getJSONArray("settings")
    for (i in 0 until settings.length()) {
        val setting = settings.getJSONObject(i)
        if (setting.getString("key") == "screenControls") {
            val options = setting.getJSONArray("options")
            for (j in options.length() - 1 downTo 0) if (options.getString(j) == "All controls") options.remove(j)
        }
    }
    val failure = runCatching { PluginManifest(broken).config(JSONObject().put("screenControls", "All controls")) }.exceptionOrNull()
    check(failure?.message == "Unknown selection option")
    println("Saved 0.1.3 settings and every old selection option accepted during upgrade")
}
