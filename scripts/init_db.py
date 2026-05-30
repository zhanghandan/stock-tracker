"""
初始化数据库 - 创建所有表
"""
import sys
import asyncio
from pathlib import Path

# 将项目根目录加入Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database import init_db


async def main():
    print("Creating database tables...")
    await init_db()
    print("OK - Database tables created successfully!")


if __name__ == "__main__":
    asyncio.run(main())
