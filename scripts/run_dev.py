"""
一键启动开发环境
启动后端 FastAPI 服务器和前端 Vite 开发服务器
"""
import sys
import subprocess
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).parent.parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"


def print_banner():
    print("""
╔══════════════════════════════════════════════════════════════╗
║              A股高价值股实时追踪系统                           ║
║              Stock Value Tracker v1.0.0                       ║
╚══════════════════════════════════════════════════════════════╝
    """)


def check_dependencies():
    """检查依赖是否安装"""
    print("📋 检查依赖...")

    # 检查Python包
    try:
        import akshare
        print(f"  ✅ akshare {akshare.__version__}")
    except ImportError:
        print("  ❌ akshare 未安装，请运行: pip install -r requirements.txt")
        return False

    try:
        import fastapi
        print(f"  ✅ fastapi")
    except ImportError:
        print("  ❌ fastapi 未安装")
        return False

    # 检查Node
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        print(f"  ✅ Node.js {result.stdout.strip()}")
    except FileNotFoundError:
        print("  ⚠️  Node.js 未安装（后端仍可运行，前端需要Node.js）")

    # 检查前端node_modules
    if not (FRONTEND_DIR / "node_modules").exists():
        print("\n⚠️  前端依赖未安装，请运行:")
        print(f"    cd {FRONTEND_DIR}")
        print("    npm install")
        print()

    return True


def init_database():
    """初始化数据库"""
    print("\n📦 初始化数据库...")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "init_db.py")],
        capture_output=True, text=True,
        cwd=str(ROOT),
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        return False
    return True


def seed_database():
    """导入股票列表"""
    print("🌱 导入A股股票列表...")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "seed_stocks.py")],
        capture_output=True, text=True,
        cwd=str(ROOT),
    )
    print(result.stdout)
    if result.returncode != 0:
        # 种子失败不阻塞启动
        print("⚠️  种子导入有警告，系统仍可运行")


def main():
    print_banner()

    if not check_dependencies():
        print("\n❌ 依赖检查未通过，请先安装所需依赖")
        sys.exit(1)

    # 初始化数据库
    if not init_database():
        print("❌ 数据库初始化失败")
        sys.exit(1)

    # 导入股票列表
    seed_database()

    # 启动后端
    print("\n" + "=" * 60)
    print("🚀 启动后端服务器 (FastAPI + uvicorn)")
    print("   API文档: http://localhost:8000/api/docs")
    print("   WebSocket: ws://localhost:8000/ws/live")
    print("=" * 60)

    backend_process = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "backend.main:app",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--reload",
        ],
        cwd=str(ROOT),
    )

    # 启动前端
    print("\n" + "=" * 60)
    print("🎨 启动前端开发服务器 (Vite + React)")
    print("   仪表盘: http://localhost:5173")
    print("=" * 60)

    frontend_process = None
    if (FRONTEND_DIR / "node_modules").exists():
        frontend_process = subprocess.Popen(
            ["npm", "run", "dev", "--", "--port", "5173"],
            cwd=str(FRONTEND_DIR),
            shell=True,
        )
    else:
        print("⚠️  前端依赖未安装，仅启动后端")
        print("   安装前端: cd frontend && npm install")
        print("   然后运行: npm run dev")

    print("\n" + "=" * 60)
    print("✅ 系统启动完成！")
    print("   后端API: http://localhost:8000/api/docs")
    print("   仪表盘:  http://localhost:5173 (需安装前端依赖)")
    print("   按 Ctrl+C 停止所有服务")
    print("=" * 60 + "\n")

    # 自动打开浏览器
    try:
        time.sleep(2)
        webbrowser.open("http://localhost:5173")
    except Exception:
        pass

    try:
        backend_process.wait()
    except KeyboardInterrupt:
        print("\n🛑 正在停止服务...")
        backend_process.terminate()
        if frontend_process:
            frontend_process.terminate()
        print("👋 系统已停止")


if __name__ == "__main__":
    main()
