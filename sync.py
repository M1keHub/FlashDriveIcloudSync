import os
import json
import shutil
import subprocess
from pathlib import Path

def load_config(config_path="config.json"):
    with open(config_path, "r") as f:
        config = json.load(f)
    
    flash_drive_path = Path(config["flash_drive_path"]).expanduser()
    backup_directories = [Path(d).expanduser() for d in config["backup_directories"]]
    
    return flash_drive_path, backup_directories

def get_relative_files(root_path):
    files = {}
    for path in root_path.rglob("*"):
        if path.is_file():
            # Skip system files like .DS_Store
            if path.name == ".DS_Store":
                continue
            relative_path = path.relative_to(root_path)
            files[str(relative_path)] = path
    return files

def evict_from_icloud(file_path):
    """Forces unload of local files to iCloud."""
    try:
        # brctl evict is the command to remove local copy of iCloud file
        subprocess.run(["brctl", "evict", str(file_path)], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error evicting {file_path}: {e}")
    except FileNotFoundError:
        print("brctl command not found. iCloud eviction skipped.")

def get_disk_info(path):
    if not path.exists():
        return None
    usage = shutil.disk_usage(path)
    total_gb = usage.total / (1024**3)
    free_gb = usage.free / (1024**3)
    used_gb = usage.used / (1024**3)
    percent_free = (usage.free / usage.total) * 100
    return {
        "total": total_gb,
        "used": used_gb,
        "free": free_gb,
        "percent_free": percent_free
    }

def main():
    try:
        flash_root, backup_dirs = load_config()
    except Exception as e:
        print(f"Error loading config: {e}")
        return

    if not flash_root.exists():
        print(f"Flash drive not found at {flash_root}")
        return

    for local_dir in backup_dirs:
        if not local_dir.exists():
            print(f"Local directory {local_dir} does not exist. Skipping.")
            continue

        print(f"\n--- Syncing {local_dir} ---")
        
        # Determine target path on flash drive
        # Requirements: ~/Documents/test1 -> /Volumes/UsbFlash/test1
        # We assume the user wants the folder name on the flash drive root.
        target_dir = flash_root / local_dir.name
        if not target_dir.exists():
            print(f"Target directory {target_dir} does not exist. Creating it.")
            target_dir.mkdir(parents=True, exist_ok=True)

        local_files = get_relative_files(local_dir)
        flash_files = get_relative_files(target_dir)

        # 6. New files on local drive
        new_local = set(local_files.keys()) - set(flash_files.keys())
        if new_local:
            print(f"\nNew files on local drive ({len(new_local)}):")
            for f in sorted(new_local):
                print(f"  {f}")
            if input("Copy these files to flash drive? (y/n): ").lower() == 'y':
                for f in new_local:
                    src = local_files[f]
                    dst = target_dir / f
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    print(f"  Copied {f}")

        # 7. New files on flash drive
        new_flash = set(flash_files.keys()) - set(local_files.keys())
        if new_flash:
            print(f"\nNew files on flash drive ({len(new_flash)}):")
            for f in sorted(new_flash):
                print(f"  {f}")
            if input("Copy these files to local drive? (y/n): ").lower() == 'y':
                for f in new_flash:
                    src = flash_files[f]
                    dst = local_dir / f
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    print(f"  Copied {f}")

        # 8. Match existing files
        common = set(local_files.keys()) & set(flash_files.keys())
        if common:
            if input("\nMatch existing files for size differences? (y/n): ").lower() == 'y':
                mismatches = []
                for f in common:
                    local_size = local_files[f].stat().st_size
                    flash_size = flash_files[f].stat().st_size
                    if local_size != flash_size:
                        mismatches.append((f, local_size, flash_size))
                
                if mismatches:
                    print("Size mismatches found (no fix offered):")
                    for f, l_sz, f_sz in mismatches:
                        print(f"  {f}: Local={l_sz} bytes, Flash={f_sz} bytes")
                else:
                    print("All existing files match in size.")

        # 9. Force unload local files to iCloud
        if input("\nEvict local files from disk (keep in iCloud)? (y/n): ").lower() == 'y':
            for f in local_files.values():
                evict_from_icloud(f)
            print("Eviction process requested via brctl.")

    # 10. Final info
    info = get_disk_info(flash_root)
    if info:
        print("\n--- Flash Drive Storage Info ---")
        print(f"Total size:     {info['total']:.2f} GB")
        print(f"Available:      {info['free']:.2f} GB ({info['percent_free']:.1f}%)")
        print(f"Used:           {info['used']:.2f} GB")

if __name__ == "__main__":
    main()
