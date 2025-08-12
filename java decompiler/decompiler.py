import subprocess
import os

jar_file = "../CraftBukkit/craftbukkit-1.20.1.jar"

cfr_jar = "cfr-0.152.jar"

output_dir = "../CraftBukkit/CraftBukkit-1.20.1"

os.makedirs(output_dir, exist_ok=True)

cmd = [
    "java", "-jar", cfr_jar,
    jar_file,
    "--outputdir", output_dir
]

print("Décompilation en cours...")
subprocess.run(cmd, check=True)
print(f"✅ Décompilation terminée. Les fichiers .java sont dans '{output_dir}'")
