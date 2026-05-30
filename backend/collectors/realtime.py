"""
实时行情采集器 - 直接调用新浪/腾讯API获取行情
绕过akshare的限制，直接使用httpx请求底层API
"""
import asyncio
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import pandas as pd
from sqlalchemy import text
from loguru import logger

from backend.database import async_session
from backend.utils.cache import realtime_cache

CST = ZoneInfo("Asia/Shanghai")

# 新浪实时行情API
SINA_API = "https://hq.sinajs.cn/list={symbols}"
# 腾讯实时行情API (备选)
TENCENT_API = "https://qt.gtimg.cn/q={symbols}"

# HTTP请求头
HEADERS = {
    "Referer": "https://finance.sina.com.cn",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


def _build_sina_symbols(codes: list[str]) -> str:
    """构建新浪股票代码格式: sh600519,sz000001"""
    symbols = []
    for code in codes:
        code = str(code).strip()
        if code.startswith("6") or code.startswith("9"):
            symbols.append(f"sh{code}")
        elif code.startswith(("0", "3")):
            symbols.append(f"sz{code}")
        elif code.startswith(("4", "8")):
            symbols.append(f"bj{code}")
        else:
            symbols.append(f"sz{code}")
    return ",".join(symbols)


def _parse_sina_response(text: str) -> list[dict]:
    """
    解析新浪实时行情响应
    格式: var hq_str_sh600519="名称,今开,昨收,现价,最高,最低,竞买价,竞卖价,成交量,成交额,..."
    """
    results = []
    # 正则匹配所有股票数据
    pattern = r'var hq_str_(\w+)="([^"]*)"'
    matches = re.findall(pattern, text)

    for symbol, data_str in matches:
        if not data_str:
            continue

        parts = data_str.split(",")
        if len(parts) < 30:
            continue

        # 从symbol提取code (sh600519 -> 600519)
        code = symbol[2:] if len(symbol) > 2 else symbol

        try:
            result = {
                "code": code,
                "name": parts[0],
                "open": _parse_float(parts[1]),        # 今开
                "prev_close": _parse_float(parts[2]),   # 昨收
                "latest_price": _parse_float(parts[3]), # 当前价
                "high": _parse_float(parts[4]),         # 最高
                "low": _parse_float(parts[5]),          # 最低
                "volume_hands": _parse_float(parts[8]), # 成交量(股)
                "turnover_yuan": _parse_float(parts[9]),# 成交额
                "date": parts[30] if len(parts) > 30 else "",  # 日期
                "time": parts[31] if len(parts) > 31 else "",  # 时间
            }

            # 计算涨跌
            if result["latest_price"] is not None and result["prev_close"] is not None and result["prev_close"] > 0:
                result["change_amount"] = round(result["latest_price"] - result["prev_close"], 3)
                result["change_pct"] = round((result["latest_price"] - result["prev_close"]) / result["prev_close"] * 100, 2)
            else:
                result["change_amount"] = None
                result["change_pct"] = None

            # 振幅
            if result["high"] is not None and result["low"] is not None and result["prev_close"] is not None and result["prev_close"] > 0:
                result["amplitude"] = round((result["high"] - result["low"]) / result["prev_close"] * 100, 2)
            else:
                result["amplitude"] = None

            results.append(result)
        except Exception as e:
            logger.debug(f"解析股票数据失败 {symbol}: {e}")
            continue

    return results


def _parse_float(val: str) -> float | None:
    """安全解析浮点数"""
    if val is None or val == "" or val == "-":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


async def fetch_realtime_batch(codes: list[str], batch_size: int = 500) -> list[dict]:
    """
    分批获取个股实时行情
    新浪API每次最多支持约800只股票
    """
    all_results = []
    chunks = [codes[i:i + batch_size] for i in range(0, len(codes), batch_size)]

    async with httpx.AsyncClient(timeout=15.0, headers=HEADERS) as client:
        for chunk in chunks:
            try:
                symbols = _build_sina_symbols(chunk)
                url = SINA_API.format(symbols=symbols)

                resp = await client.get(url)
                if resp.status_code == 200:
                    # 需要正确解码（新浪返回GBK编码）
                    text = resp.text
                    if "hq_str_" in text:
                        results = _parse_sina_response(text)
                        all_results.extend(results)
                        logger.debug(f"获取行情: {len(results)}/{len(chunk)} 只")
                    else:
                        logger.warning(f"新浪API返回异常数据: {text[:100]}")
                else:
                    logger.warning(f"新浪API HTTP错误: {resp.status_code}")

                # 批次间短暂休息
                await asyncio.sleep(0.3)

            except Exception as e:
                logger.warning(f"获取行情批次失败: {e}")
                continue

    return all_results


async def fetch_realtime_data() -> pd.DataFrame | None:
    """
    获取全A股实时行情
    策略:
    1. 先获取股票列表
    2. 分批查询新浪实时API
    3. 缓存成功结果
    """
    # 获取股票列表
    async with async_session() as session:
        result = await session.execute(
            text("SELECT code FROM stocks WHERE is_active = 1")
        )
        codes = [row[0] for row in result.fetchall()]

    if not codes:
        logger.warning("股票列表为空，尝试akshare获取")
        try:
            import akshare as ak
            df = await asyncio.to_thread(ak.stock_info_a_code_name)
            if df is not None:
                codes = [str(row["code"]) for _, row in df.iterrows()]
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return None

    logger.info(f"开始获取 {len(codes)} 只股票实时行情...")

    # 分批获取
    results = await fetch_realtime_batch(codes, batch_size=400)

    if results:
        df = pd.DataFrame(results)
        realtime_cache.set("realtime_df", df)
        logger.info(f"实时行情获取完成: {len(results)}/{len(codes)} 只")
        return df
    else:
        # 使用缓存
        cached = realtime_cache.get("realtime_df")
        if cached is not None:
            logger.warning("使用缓存的行情数据")
            return cached
        logger.error("无法获取实时行情数据")
        return None


async def save_realtime_to_db(df: pd.DataFrame | None):
    """将实时行情批量写入数据库"""
    if df is None or df.empty:
        logger.warning("实时行情数据为空，跳过写入")
        return

    now_str = datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")

    # 确保需要的列存在
    for col in ["volume_ratio", "turnover_rate", "pe_ttm", "pb",
                "total_mv", "float_mv", "change_60d", "change_ytd"]:
        if col not in df.columns:
            df[col] = None

    async with async_session() as session:
        rows_written = 0
        for _, row in df.iterrows():
            try:
                code = str(row.get("code", ""))
                if not code:
                    continue

                await session.execute(
                    text("""
                        INSERT OR REPLACE INTO stock_realtime (
                            code, name, latest_price, change_pct, change_amount,
                            volume_hands, turnover_yuan, amplitude, high, low,
                            open, prev_close, volume_ratio, turnover_rate,
                            pe_ttm, pb, total_mv, float_mv,
                            change_60d, change_ytd, updated_at
                        ) VALUES (
                            :code, :name, :latest_price, :change_pct, :change_amount,
                            :volume_hands, :turnover_yuan, :amplitude, :high, :low,
                            :open, :prev_close, :volume_ratio, :turnover_rate,
                            :pe_ttm, :pb, :total_mv, :float_mv,
                            :change_60d, :change_ytd, :updated_at
                        )
                    """),
                    {
                        "code": code,
                        "name": str(row.get("name", "")),
                        "latest_price": _sf(row.get("latest_price")),
                        "change_pct": _sf(row.get("change_pct")),
                        "change_amount": _sf(row.get("change_amount")),
                        "volume_hands": _sf(row.get("volume_hands")),
                        "turnover_yuan": _sf(row.get("turnover_yuan")),
                        "amplitude": _sf(row.get("amplitude")),
                        "high": _sf(row.get("high")),
                        "low": _sf(row.get("low")),
                        "open": _sf(row.get("open")),
                        "prev_close": _sf(row.get("prev_close")),
                        "volume_ratio": _sf(row.get("volume_ratio")),
                        "turnover_rate": _sf(row.get("turnover_rate")),
                        "pe_ttm": _sf(row.get("pe_ttm")),
                        "pb": _sf(row.get("pb")),
                        "total_mv": _sf(row.get("total_mv")),
                        "float_mv": _sf(row.get("float_mv")),
                        "change_60d": _sf(row.get("change_60d")),
                        "change_ytd": _sf(row.get("change_ytd")),
                        "updated_at": now_str,
                    }
                )
                rows_written += 1
            except Exception as e:
                logger.debug(f"写入行情失败 {code}: {e}")
                continue

        await session.commit()
        logger.info(f"实时行情写入完成: {rows_written} 条")


def _sf(val) -> float | None:
    """安全转换为float"""
    if val is None:
        return None
    try:
        f = float(val)
        return None if pd.isna(f) else f
    except (ValueError, TypeError):
        return None


async def get_candidate_codes(limit: int = 200) -> list[str]:
    """筛选候选股"""
    async with async_session() as session:
        result = await session.execute(
            text("""
                SELECT code FROM stock_realtime
                WHERE latest_price IS NOT NULL
                  AND latest_price > 2.0
                  AND name NOT LIKE '%ST%'
                  AND name NOT LIKE '%退%'
                ORDER BY ABS(COALESCE(change_pct, 0)) DESC
                LIMIT :limit
            """),
            {"limit": limit}
        )
        codes = [row[0] for row in result.fetchall()]
        return codes
