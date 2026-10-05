import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.file.Files
import java.util.zip.ZipInputStream
import java.util.zip.ZipOutputStream
import java.util.zip.ZipEntry
import me.jxl.kiosk_satellite.plugins.PluginPackage

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
