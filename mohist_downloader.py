import requests
import zipfile
import io
import re
import os
import glob
import concurrent.futures
from tqdm import tqdm

RED = '\033[91m'
RESET = '\033[0m'
mx_works = min(128, (os.cpu_count() or 4) * 5)


def sanity_check_version(version_str):
    pattern = r'^\d+\.\d+\.[\d\.]+$'
    return bool(re.match(pattern, version_str))


def prompt_force_accept(version, detected_version):
    prompt = (f"{RED}WARNING: Detected Forge version '{detected_version}' "
              f"does NOT match your target.\nForce accept and patch version {version}? (y/N): {RESET}")
    answer = input(prompt).strip().lower()
    return answer == 'y'


def prompt_force_accept_unknown(version):
    prompt = (f"{RED}WARNING: Cannot detect Forge version for version {version}.\n"
              f"Force accept and patch anyway? (y/N): {RESET}")
    answer = input(prompt).strip().lower()
    return answer == 'y'


def prompt_download_unpatched(version):
    prompt = (f"{RED}No matching version found or forge version mismatch.\n"
              f"Do you want to download the latest Mohist version {version} anyway? (y/N): {RESET}")
    answer = input(prompt).strip().lower()
    return answer == 'y'


def find_and_patch_forge_version_in_jar(jar_bytes, target_version):
    jar_in = io.BytesIO(jar_bytes)
    jar_out = io.BytesIO()
    with zipfile.ZipFile(jar_in, 'r') as zin, zipfile.ZipFile(jar_out, 'w') as zout:
        patched = False
        for item in zin.infolist():
            content = zin.read(item.filename)
            if item.filename.endswith(('.json', '.properties', '.toml', '.txt')):
                try:
                    text = content.decode('utf-8')
                    new_text = re.sub(
                        r'((forgeVersion|forge)[\"\':= ]+)"?[\d\.]+"?',
                        lambda m: m.group(1) + f'"{target_version}"',
                        text,
                        flags=re.IGNORECASE
                    )
                    if new_text != text:
                        patched = True
                        content = new_text.encode('utf-8')
                except Exception:
                    pass
            zout.writestr(item, content)
    return jar_out.getvalue(), patched


def extract_forge_version_from_jar(jar_bytes):
    version_patterns = [
        r'forgeVersion[\"\':= ]+([\d\.]+)',       # typical
        r'forge[\"\':= ]+\"?([\d\.]+)\"?',        # generic forge key
        r'forge-([\d\.]+)',                       # sometimes hyphenated
        r'ForgeVersion[\"\':= ]+([\d\.]+)',       # capitalized variant
    ]

    try:
        with zipfile.ZipFile(io.BytesIO(jar_bytes)) as jar:
            candidate_files = [f for f in jar.namelist() if f.lower().endswith(('.json', '.properties', '.toml', '.txt', '.xml', '.mf'))]

            for file_name in candidate_files:
                try:
                    content = jar.read(file_name).decode('utf-8', errors='ignore')
                except Exception:
                    continue

                for pattern in version_patterns:
                    m = re.search(pattern, content, re.IGNORECASE)
                    if m:
                        ver = m.group(1)
                        if sanity_check_version(ver):
                            return ver
                        else:
                            return None

            # As a last resort
            if 'META-INF/MANIFEST.MF' in jar.namelist():
                manifest = jar.read('META-INF/MANIFEST.MF').decode('utf-8', errors='ignore')
                for line in manifest.splitlines():
                    if 'Implementation-Version:' in line or 'Implementation-Version' in line:
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            ver = parts[1].strip()
                            if sanity_check_version(ver):
                                return ver
                            else:
                                return None
    except Exception:
        return None

    return None


def fetch_and_check_version(version, minecraft_version):
    url = f"https://mohistmc.com/builds-raw/Mohist-{minecraft_version}/Mohist-{minecraft_version}-{version}.jar"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code != 200:
            return (version, None, None)
        jar_bytes = response.content
        forge_version = extract_forge_version_from_jar(jar_bytes)
        return (version, forge_version, jar_bytes)
    except Exception:
        return (version, None, None)


def cleanup_jars_folder(keep_files):
    folder = "patched_jars"
    files = glob.glob(os.path.join(folder, "*.jar"))
    keep_paths = {os.path.abspath(f) for f in keep_files}
    for f in files:
        f_path = os.path.abspath(f)
        if f_path not in keep_paths and not f_path.endswith("-error.jar"):
            try:
                os.remove(f)
            except Exception:
                pass




def main(minecraft_version, target_forge_version, start_version=0, max_workers=mx_works):
    print("Number of current workers : " + str(max_workers))
    os.makedirs("patched_jars", exist_ok=True)

    available_versions = None
    try:
        url = f"https://mohistmc.com/builds-raw/Mohist-{minecraft_version}/"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            matches = re.findall(rf'Mohist-{re.escape(minecraft_version)}-(\d+)\.jar', resp.text)
            available_versions = sorted(set(int(m) for m in matches if int(m) >= start_version))
    except Exception:
        pass

    # Fallback brute force range if none found
    if not available_versions:
        available_versions = list(range(start_version, start_version + 100))

    last_downloaded_version = None
    last_detected_forge_version = None
    last_jar_bytes = None

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_and_check_version, v, minecraft_version): v for v in available_versions}
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="Scanning versions"):
            version, forge_version, jar_bytes = future.result()
            if jar_bytes is not None:
                # keep the highest version found
                if last_downloaded_version is None or version > last_downloaded_version:
                    last_downloaded_version = version
                    last_detected_forge_version = forge_version
                    last_jar_bytes = jar_bytes

    if last_downloaded_version is None:
        print("No Mohist versions found in range.")
        return

    print(f"\nLast downloaded version: {last_downloaded_version}")

    forge_version_valid = last_detected_forge_version is not None and sanity_check_version(last_detected_forge_version)

    if last_detected_forge_version == target_forge_version and forge_version_valid:
        print(f"Forge version matches target: {last_detected_forge_version}")
        filename = f"patched_jars/Mohist-{minecraft_version}-{last_detected_forge_version}-{last_downloaded_version}.jar"
        with open(filename, "wb") as f:
            f.write(last_jar_bytes)
        cleanup_jars_folder(filename)
        print(f"Saved jar as {filename}")
        return

    # If forge version invalid (no dot or fails sanity check) -> save as error file and exit
    if not forge_version_valid and last_jar_bytes is not None:
        filename = f"patched_jars/Mohist-{minecraft_version}-{last_detected_forge_version or 'unknown'}-{last_downloaded_version}-error.jar"
        with open(filename, "wb") as f:
            f.write(last_jar_bytes)
        print(f"{RED}Forge version invalid or missing proper format - saved error jar as {filename}.{RESET}")
        print(f"{RED}This file will be ignored in future runs.{RESET}")
        return

    # Otherwise, ask to patch or download unpatched last version anyway
    if last_detected_forge_version is None:
        accept_patch = prompt_force_accept_unknown(last_downloaded_version)
    else:
        accept_patch = prompt_force_accept(last_downloaded_version, last_detected_forge_version)

    if accept_patch:
        patched_bytes, patched = find_and_patch_forge_version_in_jar(last_jar_bytes, target_forge_version)

        patched_filename = f"patched_jars/Mohist-{minecraft_version}-{target_forge_version}-{last_downloaded_version}-patched.jar" if patched else f"patched_jars/Mohist-{minecraft_version}-{target_forge_version}-{last_downloaded_version}-forced.jar"
        with open(patched_filename, "wb") as f:
            f.write(patched_bytes)

        unpatched_filename = f"patched_jars/Mohist-{minecraft_version}-{last_detected_forge_version or 'unknown'}-{last_downloaded_version}-unpatched.jar"
        with open(unpatched_filename, "wb") as f:
            f.write(last_jar_bytes)

        cleanup_jars_folder([patched_filename, unpatched_filename])
        print(f"{RED}⚠️ WARNING: Patched jar saved as {patched_filename}. Use at your own risk! ⚠️{RESET}")
        print(f"Unpatched jar saved as {unpatched_filename}")
        return

    accept_unpatched = prompt_download_unpatched(last_downloaded_version)
    if accept_unpatched:
        filename = f"patched_jars/Mohist-{minecraft_version}-{last_detected_forge_version or 'unknown'}-{last_downloaded_version}-unpatched.jar"
        with open(filename, "wb") as f:
            f.write(last_jar_bytes)
        cleanup_jars_folder([filename])
        print(f"Unpatched jar saved as {filename}")
    else:
        print("No jar saved.")


if __name__ == "__main__":
    print(r"""            __  __   ____   _    _  _____   _____  _______          
           |  \/  | / __ \ | |  | ||_   _| / ____||__   __|         
           | \  / || |  | || |__| |  | |  | (___     | |            
           | |\/| || |  | ||  __  |  | |   \___ \    | |            
           | |  | || |__| || |  | | _| |_  ____) |   | |            
  _____    |_|  |_| \____/ |_|  |_||_____||_____/    |_|            
 |  __ \                        | |                  | |            
 | |  | |  ___ __      __ _ __  | |  ___    __ _   __| |  ___  _ __ 
 | |  | | / _ \\ \ /\ / /| '_ \ | | / _ \  / _` | / _` | / _ \| '__|
 | |__| || (_) |\ V  V / | | | || || (_) || (_| || (_| ||  __/| |   
 |_____/  \___/  \_/\_/  |_| |_||_| \___/  \__,_| \__,_| \___||_|   
                                                                    
                                                                    """)
    mc_ver = input              ("Enter Minecraft version (e.g. 1.18.2)                 : ").strip()
    forge_ver = input           ("Enter desired Forge version (e.g. 40.2.4)             : ").strip()
    start_ver_input = input     ("Enter minimal Mohist version to start from (default 0): ").strip()
    set_max_worker_input = input("Enter maximal number of worker threads (default 128)  : ").strip()
    set_max_worker = int(set_max_worker_input) if set_max_worker_input else 128
    mx_works = min(set_max_worker, (os.cpu_count() or 4) * 5)
    start_ver = int(start_ver_input) if start_ver_input.isdigit() else 0
    main(mc_ver, forge_ver, start_ver)
