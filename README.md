# Mohist Downloader and Forge Version Patcher

This Python script downloads Mohist Minecraft server builds for a specified Minecraft version and target Forge version. It scans available Mohist versions, checks their embedded Forge versions, and optionally patches the Forge version in the JAR file if it doesn't match the target.

## Features

* Downloads the latest Mohist builds for a given Minecraft version starting from a minimum Mohist version.
* Extracts and validates the Forge version inside the downloaded JAR files.
* Automatically patches the Forge version inside the JAR if it differs from the target version.
* Supports multithreaded downloads for faster processing.
* Saves patched, unpatched, or error-marked JAR files in a dedicated folder.
* Interactive prompts for patching or downloading unpatched builds when versions don't match.

## Requirements

* Python 3.7+
* [requests](https://pypi.org/project/requests/)
* [tqdm](https://pypi.org/project/tqdm/)

Install required packages with:

```bash
pip install requests tqdm
```

## Usage

Run the script and provide the requested inputs:

```bash
python mohist.py
```

You will be prompted to enter:

* Minecraft version (e.g., `1.18.2`)
* Desired Forge version (e.g., `40.2.4`)
* Minimal Mohist version to start scanning from (default: `0`)
* Maximum number of worker threads to speed up scanning (default: `128`)

The script will scan available Mohist versions, download the latest matching version, patch the Forge version if needed, and save the output JARs in the `patched_jars` folder.

## Notes

* If the detected Forge version does not pass a basic sanity check, the script saves the file with an `-error.jar` suffix and ignores it in future runs.
* If no matching version is found, you can choose to download the latest unpatched Mohist build.
* Patched files are saved with a `-patched.jar` suffix and come with a warning to use at your own risk.

## License

This script is provided as-is without warranty. Use at your own risk.

---

If you want, I can customize it further with usage examples or advanced options!
