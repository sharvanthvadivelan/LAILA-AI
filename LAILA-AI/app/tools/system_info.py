import platform, sys, shutil, subprocess
import psutil
from app.core.config import VERSION


def system_info():
    gpu = "Not detected"
    binary = shutil.which("nvidia-smi")
    if binary:
        try:
            result = subprocess.run(
                [binary, "--query-gpu=name,memory.total", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if result.returncode == 0:
                gpu = result.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass
    ram = psutil.virtual_memory()
    return {
        "os": platform.platform(),
        "cpu": platform.processor() or platform.machine(),
        "cpu_threads": psutil.cpu_count(),
        "ram_gb": round(ram.total / 2**30, 1),
        "available_ram_gb": round(ram.available / 2**30, 1),
        "gpu": gpu,
        "python": sys.version.split()[0],
        "app_version": VERSION,
    }
