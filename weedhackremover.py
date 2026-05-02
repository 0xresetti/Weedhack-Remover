import os
import re
import sys
import json
import shutil
import struct
import hashlib
import subprocess
import glob
import winreg
import zipfile
import ctypes

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


KNOWN_MALICIOUS_HASHES = {
    # Weedhack v3
    "c40868122888c12b30d4e436ca7ac60af5eef098e1b2f7105aa1b681bfd8bef4",
    "abc2a974fe8059c2f840b9fc2118aab6924a916fe60c5bd5d547b2fda72affbd",
    "3689795a003faf4991e3ef11631c06269cd14c49bfffbc4013bbf0a5f429210c",
    "6cb8d2c7347da8efa6dff068b46f26892360dee34aa11e78e5b3d49dc0ee2d3a",
    "118ed4b24ae6c0dcc20d4228ebcdef9271beb80f91b4c7b28d61c735a8f2b514",
}

KNOWN_MALICIOUS_ETH_ADDR = "0x1280a841Fbc1F883365d3C83122260E0b2995B74"

KNOWN_MALICIOUS_UUIDS = set()

GREEK_UNICODE_RANGE = re.compile(r"[Ͱ-Ͽ]")


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def kill_javaw_processes():
    print()
    print("=" * 60)
    print("WARNING: PROCESS TERMINATION")
    print("=" * 60)
    print()
    print("  Weedhack runs using javaw.exe (headless Java).")
    print("  To ensure the malware is fully stopped, ALL javaw.exe")
    print("  processes will be killed.")
    print()
    print("  This WILL terminate:")
    print("    - Any running Minecraft instances")
    print("    - Any other Java GUI applications")
    print("    - Any background Java processes")
    print()
    print("  Save any work in Java applications before proceeding.")
    print()
    confirm = input("  Type 'KILL' to terminate all javaw.exe processes: ").strip().upper()
    if confirm != "KILL":
        print("  [-] Skipped killing javaw.exe processes.")
        print("      (Malware may still be running in memory!)")
        return False

    try:
        result = subprocess.run(
            ["taskkill", "/F", "/IM", "javaw.exe"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print("  [+] Killed all javaw.exe processes.")
        elif result.returncode == 128:
            print("  [-] No javaw.exe processes were running.")
        else:
            print(f"  [!] taskkill returned code {result.returncode}: {result.stderr.strip()}")
    except Exception as e:
        print(f"  [!] Could not kill javaw.exe: {e}")

    return True


# ---------------------------------------------------------------------------
# Old variant cleanup (Weedhack v1/v2/v3 persistence)
# ---------------------------------------------------------------------------

def remove_scheduled_task():
    try:
        result = subprocess.run(
            ["schtasks", "/Delete", "/TN", "JavaSecurityUpdater", "/F"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print("[+] Removed scheduled task: JavaSecurityUpdater")
        else:
            print("[-] Scheduled task 'JavaSecurityUpdater' not found (OK)")
    except Exception:
        print("[-] Could not query scheduled tasks")


def remove_persistence_folder():
    folder = os.path.join(os.environ["APPDATA"], "Microsoft", "SecurityUpdates")
    if os.path.exists(folder):
        shutil.rmtree(folder, ignore_errors=True)
        print(f"[+] Removed folder: {folder}")
    else:
        print("[-] SecurityUpdates folder not found (OK)")


def remove_defender_exclusion():
    if not is_admin():
        print("[-] Skipping Defender exclusion removal (requires admin)")
        return
    try:
        cmd = "Remove-MpPreference -ExclusionPath 'C:\\Users'"
        subprocess.run(["powershell", "-Command", cmd], capture_output=True)
        print("[+] Removed Defender exclusion for C:\\Users")
    except Exception:
        print("[-] Could not remove Defender exclusion")


def clean_registry():
    try:
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS
        )

        bad_values = []
        i = 0
        while True:
            try:
                name, data, _ = winreg.EnumValue(key, i)
                if "SecurityUpdates" in str(data) or "JavaSecurityUpdater" in name:
                    bad_values.append(name)
                i += 1
            except OSError:
                break

        for name in bad_values:
            winreg.DeleteValue(key, name)
            print(f"[+] Removed registry value: {name}")

        winreg.CloseKey(key)

        if not bad_values:
            print("[-] No malicious registry entries found (OK)")
    except Exception:
        print("[-] Could not check registry")


def clean_temp_files():
    temp = os.environ.get("TEMP", "")
    found = False
    if temp:
        for f in glob.glob(os.path.join(temp, "lib*.tmp")):
            try:
                os.remove(f)
                print(f"[+] Removed temp file: {f}")
                found = True
            except Exception:
                pass
    if not found:
        print("[-] No suspicious temp files found (OK)")


# ---------------------------------------------------------------------------
# New variant detection (Weedhack v4+ / Ethereum RPC C2)
# ---------------------------------------------------------------------------

def get_minecraft_mod_dirs():
    user = os.path.expanduser("~")
    appdata = os.environ.get("APPDATA", "")
    localappdata = os.environ.get("LOCALAPPDATA", "")

    candidates = [
        os.path.join(appdata, ".minecraft", "mods"),
        os.path.join(appdata, ".lunarclient", "offline", "multiver", "mods"),
        os.path.join(appdata, ".feather", "mods"),
        os.path.join(appdata, "com.modrinth.theseus", "profiles"),
        os.path.join(appdata, "PrismLauncher", "instances"),
        os.path.join(appdata, "MultiMC", "instances"),
        os.path.join(appdata, "ATLauncher", "instances"),
        os.path.join(appdata, "gdlauncher_next", "instances"),
        os.path.join(localappdata, "Packages"),
        os.path.join(user, "curseforge", "minecraft", "Instances"),
        os.path.join(user, "Downloads"),
    ]

    dirs = []
    for c in candidates:
        if os.path.isdir(c):
            dirs.append(c)

    return dirs


def find_jar_files(directories):
    jars = []
    for d in directories:
        for root, _, files in os.walk(d):
            for f in files:
                if f.lower().endswith(".jar"):
                    jars.append(os.path.join(root, f))
    return jars


def has_greek_unicode(text):
    return bool(GREEK_UNICODE_RANGE.search(text))


def read_utf8_from_constant_pool(data, offset):
    if offset + 2 > len(data):
        return None
    length = struct.unpack(">H", data[offset : offset + 2])[0]
    offset += 2
    if offset + length > len(data):
        return None
    try:
        return data[offset : offset + length].decode("utf-8", errors="replace")
    except Exception:
        return None


def extract_strings_from_class(class_bytes):
    strings = []
    if len(class_bytes) < 10 or class_bytes[:4] != b"\xCA\xFE\xBA\xBE":
        return strings

    try:
        cp_count = struct.unpack(">H", class_bytes[8:10])[0]
        offset = 10
        utf8_offsets = []

        i = 1
        while i < cp_count and offset < len(class_bytes):
            tag = class_bytes[offset]
            offset += 1

            if tag == 1:  # CONSTANT_Utf8
                if offset + 2 > len(class_bytes):
                    break
                str_len = struct.unpack(">H", class_bytes[offset : offset + 2])[0]
                if offset + 2 + str_len > len(class_bytes):
                    break
                utf8_offsets.append(offset)
                offset += 2 + str_len
            elif tag in (7, 8, 16, 19, 20):  # 2-byte refs
                if offset + 2 > len(class_bytes):
                    break
                offset += 2
            elif tag in (3, 4, 9, 10, 11, 12, 17, 18):  # 4-byte
                if offset + 4 > len(class_bytes):
                    break
                offset += 4
            elif tag in (5, 6):  # 8-byte (long/double), takes 2 pool slots
                if offset + 8 > len(class_bytes):
                    break
                offset += 8
                i += 1
            elif tag == 15:  # MethodHandle
                if offset + 3 > len(class_bytes):
                    break
                offset += 3
            else:
                break
            i += 1

        for off in utf8_offsets:
            s = read_utf8_from_constant_pool(class_bytes, off)
            if s:
                strings.append(s)
    except Exception:
        pass

    return strings


def analyze_jar(jar_path):
    reasons = []
    confidence = 0

    try:
        zf = zipfile.ZipFile(jar_path, "r")
    except Exception:
        return None

    with zf:
        # Check fabric.mod.json
        fabric_meta = None
        if "fabric.mod.json" in zf.namelist():
            try:
                fabric_meta = json.loads(zf.read("fabric.mod.json"))
            except Exception:
                pass

        if fabric_meta:
            entrypoints = []
            ep_section = fabric_meta.get("entrypoints", {})
            for ep_list in ep_section.values():
                if isinstance(ep_list, list):
                    entrypoints.extend(ep_list)
                elif isinstance(ep_list, str):
                    entrypoints.append(ep_list)

            for ep in entrypoints:
                if has_greek_unicode(ep):
                    reasons.append(
                        f"fabric.mod.json has greek unicode entrypoint: {ep}"
                    )
                    confidence += 50

        # Check fabric.api.json (weedhack v3 buyer tracking)
        if "fabric.api.json" in zf.namelist():
            try:
                api_content = zf.read("fabric.api.json").decode("utf-8", errors="replace")
                if "api_version" in api_content.lower():
                    reasons.append("fabric.api.json with api_version (buyer tracking)")
                    confidence += 40
            except Exception:
                pass

        # Analyze .class files
        greek_packages = set()
        has_custom_classloader = False
        has_weedhack_method = False
        has_eth_addr = False
        has_known_uuid = False
        has_session_theft = False
        has_rsa_sig = False
        has_invokedynamic_xor = False
        hash_matches = []
        dummy_class_count = 0

        for name in zf.namelist():
            if not name.endswith(".class"):
                continue

            try:
                class_bytes = zf.read(name)
            except Exception:
                continue

            # SHA256 hash check
            h = hashlib.sha256(class_bytes).hexdigest()
            if h in KNOWN_MALICIOUS_HASHES:
                hash_matches.append(name)

            # Check for known strings in constant pool
            strings = extract_strings_from_class(class_bytes)

            for s in strings:
                if KNOWN_MALICIOUS_ETH_ADDR in s:
                    has_eth_addr = True
                if s in KNOWN_MALICIOUS_UUIDS:
                    has_known_uuid = True
                if s == "initializeWeedhack":
                    has_weedhack_method = True
                if s == "SHA256withRSA":
                    has_rsa_sig = True
                if s in ("method_1674", "method_1676", "method_44717"):
                    has_session_theft = True

            # Check for custom ClassLoader via constant pool strings
            if (any("ClassLoader" in s for s in strings)
                    and any("defineClass" in s for s in strings)):
                has_custom_classloader = True

            # Check package for greek unicode
            class_path = name.replace("\\", "/").replace(".class", "")
            if has_greek_unicode(class_path):
                pkg = "/".join(class_path.split("/")[:-1])
                if pkg:
                    greek_packages.add(pkg)

            # Check for XOR-based string decryption (invokedynamic obfuscation)
            if b"\xFF\xFF" in class_bytes and b"CallSite" in class_bytes:
                has_invokedynamic_xor = True

            # Detect dummy/padding classes (return 0 only)
            if len(class_bytes) < 500 and strings and len(strings) < 5:
                non_java_strings = [
                    s for s in strings
                    if not s.startswith("java/")
                    and not s.startswith("(")
                    and s not in ("Code", "<init>", "()V", "this", "()I", "SourceFile")
                    and not s.endswith(".java")
                    and len(s) > 1
                ]
                if len(non_java_strings) == 0:
                    dummy_class_count += 1

        if hash_matches:
            reasons.append(f"SHA256 hash match on: {', '.join(hash_matches)}")
            confidence += 80

        if has_weedhack_method:
            reasons.append("Contains 'initializeWeedhack' method signature")
            confidence += 60

        if has_eth_addr:
            reasons.append(f"Contains known malicious Ethereum address")
            confidence += 50

        if has_known_uuid:
            reasons.append("Contains known weedhack operator UUID")
            confidence += 50

        # NOTE: add new UUIDs to KNOWN_MALICIOUS_UUIDS as they are discovered
        # in payloads distributed to real victims

        if has_session_theft:
            reasons.append("References MC session token methods (credential theft)")
            confidence += 30

        if has_rsa_sig:
            reasons.append("Uses SHA256withRSA signature verification (C2 auth)")
            confidence += 20

        if has_custom_classloader:
            reasons.append("Contains custom ClassLoader (in-memory payload execution)")
            confidence += 20

        if has_invokedynamic_xor:
            reasons.append("Uses invokedynamic + XOR string obfuscation")
            confidence += 15

        if greek_packages:
            reasons.append(
                f"Greek unicode package names: {', '.join(sorted(greek_packages))}"
            )
            confidence += 25

        if dummy_class_count >= 5:
            reasons.append(f"{dummy_class_count} dummy padding classes detected")
            confidence += 10

    if confidence >= 25:
        return {"path": jar_path, "confidence": confidence, "reasons": reasons}

    return None


def scan_mod_directories():
    print()
    print("=" * 60)
    print("SCANNING FOR INFECTED MINECRAFT MODS")
    print("=" * 60)
    print()

    mod_dirs = get_minecraft_mod_dirs()

    if not mod_dirs:
        print("[-] No Minecraft mod directories found.")
        return []

    print(f"[*] Scanning {len(mod_dirs)} directories...")
    for d in mod_dirs:
        print(f"    {d}")
    print()

    jars = find_jar_files(mod_dirs)
    print(f"[*] Found {len(jars)} JAR files to analyze...")
    print()

    detections = []
    scanned = 0
    for jar in jars:
        scanned += 1
        if scanned % 50 == 0:
            print(f"    ...scanned {scanned}/{len(jars)} JARs...")

        result = analyze_jar(jar)
        if result:
            detections.append(result)

    print(f"[*] Scan complete. {scanned} JARs scanned, {len(detections)} suspicious.")
    return detections


def report_and_remove_detections(detections):
    if not detections:
        print("[-] No infected mods detected.")
        return

    detections.sort(key=lambda d: d["confidence"], reverse=True)

    print()
    print("!" * 60)
    print("INFECTED MODS DETECTED")
    print("!" * 60)

    for i, det in enumerate(detections, 1):
        verdict = "CONFIRMED" if det["confidence"] >= 80 else (
            "HIGH" if det["confidence"] >= 50 else "SUSPICIOUS"
        )
        print()
        print(f"  [{i}] {verdict} (confidence: {det['confidence']})")
        print(f"      File: {det['path']}")
        print(f"      Indicators:")
        for r in det["reasons"]:
            print(f"        - {r}")

    print()
    print("-" * 60)
    confirm = input(
        "  Delete ALL detected malicious JARs? (type 'DELETE' to confirm): "
    ).strip().upper()

    if confirm != "DELETE":
        print()
        print("  [-] Skipped deletion. Files left in place.")
        print("      You should manually inspect and remove these files!")
        return

    print()
    for det in detections:
        try:
            os.remove(det["path"])
            print(f"  [+] Deleted: {det['path']}")
        except Exception as e:
            print(f"  [!] Could not delete {det['path']}: {e}")


# ---------------------------------------------------------------------------
# Launcher account invalidation
# ---------------------------------------------------------------------------

def invalidate_launcher_accounts():
    print()
    print("=" * 60)
    print("WARNING: MINECRAFT LAUNCHER ACCOUNT TOKEN REMOVAL")
    print("=" * 60)
    print()
    print("  Weedhack steals your Minecraft session token. Even after")
    print("  changing your password, the STOLEN TOKEN may still be")
    print("  valid until it expires or is invalidated.")
    print()
    print("  This step will DELETE your launcher account files, which")
    print("  forces a fresh login next time you open your launcher.")
    print()
    print("  WHAT THIS MEANS FOR YOU:")
    print("    - You will be LOGGED OUT of all Minecraft launchers")
    print("    - You will need to RE-ENTER your username and password")
    print("    - You will need to re-authenticate with Microsoft/Mojang")
    print("    - Any saved launcher settings (NOT worlds/mods) may reset")
    print("    - Your Minecraft worlds, resource packs, and mods are")
    print("      NOT affected - only login tokens are removed")
    print()
    print("  THIS IS ANNOYING BUT RECOMMENDED. If you skip this step,")
    print("  the attacker may still have a working session token.")
    print()

    appdata = os.environ.get("APPDATA", "")
    localappdata = os.environ.get("LOCALAPPDATA", "")

    account_files = [
        os.path.join(appdata, ".minecraft", "launcher_accounts.json"),
        os.path.join(appdata, ".minecraft", "launcher_accounts_microsoft_store.json"),
        os.path.join(appdata, ".minecraft", "launcher_profiles.json"),
        os.path.join(appdata, ".lunarclient", "settings", "game", "accounts.json"),
        os.path.join(appdata, ".feather", "accounts.json"),
        os.path.join(localappdata, "Packages", "Microsoft.4297127D64EC6_8wekyb3d8bbwe",
                     "LocalCache", "Local", "launcher_accounts.json"),
    ]

    existing = [f for f in account_files if os.path.isfile(f)]

    if not existing:
        print("  [-] No launcher account files found.")
        return

    print(f"  Found {len(existing)} launcher account file(s):")
    for f in existing:
        print(f"    {f}")
    print()

    confirm = input(
        "  Type 'INVALIDATE' to delete these files and force re-login: "
    ).strip().upper()

    if confirm != "INVALIDATE":
        print()
        print("  [-] Skipped account invalidation.")
        print("      MAKE SURE you change your Microsoft/Mojang password!")
        return

    print()
    for f in existing:
        try:
            os.remove(f)
            print(f"  [+] Deleted: {f}")
        except Exception as e:
            print(f"  [!] Could not delete {f}: {e}")

    print()
    print("  [+] Launcher tokens invalidated. You will need to log in")
    print("      again next time you launch Minecraft.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print()
    print("=" * 60)
    print("  WEEDHACK MALWARE REMOVAL TOOL")
    print("  github.com/0xresetti/Weedhack-Remover")
    print("=" * 60)
    print()
    print("  This tool removes known Weedhack malware variants")
    print("  including old (v1-v3) and new (v4+) versions.")
    print()

    if is_admin():
        print("  [*] Running as Administrator")
    else:
        print("  [!] Running without admin - some features limited")
        print("      (Right-click > Run as Administrator for full cleanup)")
    print()
    input("  Press Enter to begin...")

    # Step 1: Kill javaw.exe
    kill_javaw_processes()

    # Step 2: Old variant cleanup
    print()
    print("=" * 60)
    print("REMOVING OLD VARIANT PERSISTENCE (v1-v3)")
    print("=" * 60)
    print()

    remove_scheduled_task()
    remove_persistence_folder()
    remove_defender_exclusion()
    clean_registry()
    clean_temp_files()

    # Step 3: Scan for infected mods
    detections = scan_mod_directories()
    report_and_remove_detections(detections)

    # Step 4: Invalidate launcher accounts
    invalidate_launcher_accounts()

    # Step 5: Summary
    print()
    print("=" * 60)
    print("  REMOVAL COMPLETE")
    print("=" * 60)
    print()
    print("  IMPORTANT - YOU MUST ALSO DO THE FOLLOWING:")
    print()
    print("  1. CHANGE YOUR MICROSOFT/MOJANG PASSWORD IMMEDIATELY")
    print("     (This invalidates any stolen session tokens)")
    print()
    print("  2. CHANGE YOUR DISCORD PASSWORD")
    print("     (This resets your Discord token)")
    print()
    print("  3. CHECK AND CLEAR SAVED BROWSER PASSWORDS")
    print("     (Weedhack second-stage payloads may steal browser data)")
    print()
    print("  4. CHECK CRYPTOCURRENCY WALLETS")
    print("     (Weedhack uses Ethereum-based C2 infrastructure and")
    print("      may target crypto wallets)")
    print()
    print("  5. DELETE THE ORIGINAL INFECTED MOD FILE")
    print("     (If you downloaded the mod somewhere, delete it from")
    print("      your Downloads folder or wherever you saved it)")
    print()
    print("  6. REBOOT YOUR COMPUTER")
    print("     (Ensures no malware remains in memory)")
    print()
    print("=" * 60)
    print()
    input("  Press Enter to exit...")


if __name__ == "__main__":
    main()
