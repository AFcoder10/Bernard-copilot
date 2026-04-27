import os
import subprocess
import shutil
import sys

def build():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    venv_python = os.path.join(project_dir, ".venv", "Scripts", "python.exe")
    pyinstaller_exe = os.path.join(project_dir, ".venv", "Scripts", "pyinstaller.exe")
    spec_file = os.path.join(project_dir, "Bernard.spec")

    print(f"--- Bernard EXE Builder ---")
    print(f"Project Dir: {project_dir}")

    # 1. Clean up old builds
    print("\n[1/3] Cleaning old build/dist folders...")
    for folder in ["build", "dist"]:
        path = os.path.join(project_dir, folder)
        if os.path.exists(path):
            try:
                shutil.rmtree(path)
                print(f"  Removed {folder}/")
            except Exception as e:
                print(f"  Error removing {folder}: {e}")

    # 2. Run PyInstaller
    print("\n[2/3] Running PyInstaller (this will take several minutes)...")
    if not os.path.exists(pyinstaller_exe):
        print(f"Error: PyInstaller not found at {pyinstaller_exe}")
        return

    try:
        # Use subprocess.run to capture real-time output if possible, or just let it stream
        process = subprocess.Popen(
            [pyinstaller_exe, spec_file, "--noconfirm", "--clean"],
            cwd=project_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        for line in process.stdout:
            print(line, end="")

        process.wait()

        if process.returncode == 0:
            print("\n[3/3] Build Successful!")
            print(f"Executable location: {os.path.join(project_dir, 'dist', 'Bernard', 'Bernard.exe')}")
        else:
            print(f"\n[!] Build Failed with exit code {process.returncode}")

    except Exception as e:
        print(f"\n[!] An error occurred during the build: {e}")

if __name__ == "__main__":
    build()
