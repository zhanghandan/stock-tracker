"""
短信验证码发送 (阿里云短信服务)
"""
import os
import random
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from loguru import logger

CST = ZoneInfo("Asia/Shanghai")

# 阿里云短信配置
ALIYUN_ACCESS_KEY = os.getenv("ALIYUN_ACCESS_KEY_ID", "")
ALIYUN_ACCESS_SECRET = os.getenv("ALIYUN_ACCESS_KEY_SECRET", "")
SMS_SIGN_NAME = os.getenv("SMS_SIGN_NAME", "股票追踪")
SMS_TEMPLATE_CODE = os.getenv("SMS_TEMPLATE_CODE", "SMS_123456789")

# 开发模式：如果没有配置短信服务，验证码打印到日志
DEV_MODE = not (ALIYUN_ACCESS_KEY and ALIYUN_ACCESS_SECRET)


def generate_code() -> str:
    """生成6位数字验证码"""
    return f"{random.randint(100000, 999999)}"


async def send_sms(phone: str, code: str) -> bool:
    """
    发送短信验证码
    优先使用阿里云短信，未配置则打印到日志（开发模式）
    """
    if DEV_MODE:
        logger.warning(f"[DEV MODE] 验证码已生成但未发送短信: 手机={phone}, 验证码={code}")
        logger.info(f"📱 登录验证码: {code} (手机: {phone})")
        return True

    try:
        from alibabacloud_dysmsapi20170525.client import Client as DysmsapiClient
        from alibabacloud_dysmsapi20170525 import models as dysmsapi_models
        from alibabacloud_tea_openapi import models as open_api_models

        config = open_api_models.Config(
            access_key_id=ALIYUN_ACCESS_KEY,
            access_key_secret=ALIYUN_ACCESS_SECRET,
        )
        config.endpoint = "dysmsapi.aliyuncs.com"
        client = DysmsapiClient(config)

        request = dysmsapi_models.SendSmsRequest(
            phone_numbers=phone,
            sign_name=SMS_SIGN_NAME,
            template_code=SMS_TEMPLATE_CODE,
            template_param=json.dumps({"code": code}),
        )

        response = client.send_sms(request)
        if response.body.code == "OK":
            logger.info(f"短信发送成功: {phone}")
            return True
        else:
            logger.error(f"短信发送失败: {response.body.message}")
            return False

    except ImportError:
        logger.warning(f"[DEV MODE] 阿里云短信SDK未安装，验证码={code} (手机={phone})")
        return True
    except Exception as e:
        logger.error(f"短信发送异常: {e}")
        # 失败时也记录验证码（用户可能需要手动输入）
        logger.info(f"📱 验证码: {code} (手机: {phone})")
        return True  # 开发模式允许继续


async def save_code_to_db(phone: str, code: str) -> bool:
    """保存验证码到数据库"""
    from sqlalchemy import text
    from backend.database import async_session

    expires_at = (datetime.now(CST) + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")

    async with async_session() as session:
        await session.execute(
            text("""
                INSERT INTO verification_codes (phone, code, expires_at, used, created_at)
                VALUES (:phone, :code, :expires_at, 0, datetime('now'))
            """),
            {"phone": phone, "code": code, "expires_at": expires_at}
        )
        await session.commit()

    return True


async def verify_code(phone: str, code: str) -> bool:
    """验证验证码是否正确且未过期"""
    from sqlalchemy import text
    from backend.database import async_session

    now = datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")

    async with async_session() as session:
        result = await session.execute(
            text("""
                SELECT id FROM verification_codes
                WHERE phone = :phone AND code = :code
                  AND used = 0 AND expires_at > :now
                ORDER BY created_at DESC LIMIT 1
            """),
            {"phone": phone, "code": code, "now": now}
        )
        row = result.fetchone()

        if row:
            # 标记为已使用
            await session.execute(
                text("UPDATE verification_codes SET used = 1 WHERE id = :id"),
                {"id": row[0]}
            )
            await session.commit()
            return True

    return False
