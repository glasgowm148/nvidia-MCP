"""Build a private, per-device APK and client; never connect to a TV."""

import argparse
import os
import secrets
import subprocess
import zipfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("android-jar", "build-tools", "r8-jar", "java-home", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    source = Path(__file__).resolve().parent
    root = args.output.expanduser().resolve()
    checkout = source.parents[1]
    if root == checkout or checkout in root.parents:
        parser.error("Use a private output directory outside this checkout")
    os.umask(0o077)
    root.mkdir(parents=True, exist_ok=True)
    root.chmod(0o700)
    assets, classes, client = root / "assets", root / "classes", root / "client"
    for path in (assets, classes, client):
        path.mkdir(exist_ok=True)
    token, key, password = assets / "handoff-token", root / "signing.p12", root / "signing-password"
    # Refuse to silently rotate an installed device's signing identity.
    if key.exists() != password.exists():
        raise ValueError("Incomplete signing identity; restore its matching key/password first")
    if not token.exists():
        token.write_text(secrets.token_hex(32))
    if len(token.read_text()) != 64:
        raise ValueError("Expected a 64-character installation token")
    java, tools = args.java_home / "bin", args.build_tools

    def run(*command):
        # Tool failure output may contain private paths; keep it out of routine logs.
        subprocess.run([str(value) for value in command], check=True, capture_output=True)

    def compile_java(path, destination):
        run(
            java / "javac",
            "--release",
            "8",
            "-classpath",
            args.android_jar,
            "-d",
            destination,
            path,
        )
        run(
            java / "java",
            "-cp",
            args.r8_jar,
            "com.android.tools.r8.D8",
            "--min-api",
            "26",
            "--lib",
            args.android_jar,
            "--output",
            destination,
            *sorted(destination.rglob("*.class")),
        )

    compile_java(source / "src/org/kodimanager/profileswitch/ArmReceiver.java", classes)
    run(
        tools / "aapt2",
        "link",
        "-I",
        args.android_jar,
        "--manifest",
        source / "AndroidManifest.xml",
        "-A",
        assets,
        "-o",
        root / "unsigned.apk",
    )
    with zipfile.ZipFile(root / "unsigned.apk", "a") as archive:
        archive.write(classes / "classes.dex", "classes.dex")
    run(tools / "zipalign", "-f", "4", root / "unsigned.apk", root / "aligned.apk")
    if not key.exists():
        password.write_text(secrets.token_urlsafe(32))
        run(
            java / "keytool",
            "-genkeypair",
            "-keystore",
            key,
            "-storepass:file",
            password,
            "-alias",
            "profile-switch",
            "-keyalg",
            "RSA",
            "-keysize",
            "2048",
            "-validity",
            "3650",
            "-dname",
            "CN=Local Kodi Profile Switch",
        )
    signer = tools / "lib/apksigner.jar"
    run(
        java / "java",
        "-jar",
        signer,
        "sign",
        "--ks",
        key,
        "--ks-pass",
        "file:" + str(password),
        "--out",
        root / "kodi-profile-switch.apk",
        root / "aligned.apk",
    )
    run(java / "java", "-jar", signer, "verify", root / "kodi-profile-switch.apk")
    compile_java(source / "kodi/profile_restart/KodiProfileLauncher.java", client)
    print("Private APK signature verified; client classes.dex built. TV unchanged.")


if __name__ == "__main__":
    main()
