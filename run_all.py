"""
SML AI Router — Run All
รัน 3 ส่วนพร้อมกัน:
1. ค้นหา AI API ฟรี (find_free_ai.py)
2. ทดสอบ API จริง (test_ai_apis.py)
3. เปิด Dashboard (dashboard.py)
"""

import subprocess
import sys
import os
import time
import signal

# Fix Windows encoding for emoji/Thai
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def main():
    print("🚀 SML AI Router — Starting All Services")
    print("=" * 50)

    procs = []

    # 1. Dashboard
    print("🖥️  Starting Dashboard...")
    p_dash = subprocess.Popen(
        [sys.executable, os.path.join(SCRIPT_DIR, "dashboard.py")],
        cwd=SCRIPT_DIR,
    )
    procs.append(("Dashboard", p_dash))
    time.sleep(1)

    # 2. Find free AI APIs
    print("🔍 Starting API Finder...")
    p_find = subprocess.Popen(
        [sys.executable, os.path.join(SCRIPT_DIR, "find_free_ai.py")],
        cwd=SCRIPT_DIR,
    )
    procs.append(("Finder", p_find))

    # 3. Wait a bit for finder to get initial data, then start tester
    print("⏳ รอ 30 วินาที ให้ finder หาข้อมูลก่อน แล้วเริ่มทดสอบ...")
    time.sleep(30)

    print("🧪 Starting API Tester...")
    p_test = subprocess.Popen(
        [sys.executable, os.path.join(SCRIPT_DIR, "test_ai_apis.py")],
        cwd=SCRIPT_DIR,
    )
    procs.append(("Tester", p_test))

    print()
    print("=" * 50)
    print("✅ ทุกอย่างทำงานแล้ว!")
    print("📍 Dashboard: http://127.0.0.1:8899")
    print("📋 Logs: free_ai_apis.log, test_results.log")
    print("📁 Data: free_ai_apis.json")
    print("⏹️  Ctrl+C เพื่อหยุดทั้งหมด")
    print("=" * 50)

    try:
        while True:
            # Check if any process died
            for name, proc in procs:
                if proc.poll() is not None:
                    print(f"⚠️ {name} หยุดทำงาน (exit code: {proc.returncode})")
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n🛑 หยุดทุก process...")
        for name, proc in procs:
            try:
                proc.terminate()
                proc.wait(timeout=5)
                print(f"  ✅ {name} หยุดแล้ว")
            except Exception:
                proc.kill()
                print(f"  ⚠️ {name} ถูก kill")
        print("👋 จบ! ขอบคุณครับลูกพี่!")


if __name__ == "__main__":
    main()
