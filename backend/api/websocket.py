"""
WebSocket连接管理与实时推送
"""
import asyncio
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger

from backend.config import WS_PING_INTERVAL, WS_MAX_CONNECTIONS

CST = ZoneInfo("Asia/Shanghai")


class WSConnectionManager:
    """WebSocket连接管理器"""

    def __init__(self):
        self._connections: dict[str, WebSocket] = {}
        self._subscriptions: dict[str, set[str]] = {}  # client_id -> {codes}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, client_id: str):
        """接受新连接"""
        await websocket.accept()

        # 限制最大连接数
        if len(self._connections) >= WS_MAX_CONNECTIONS:
            await websocket.close(code=1013, reason="连接数已达上限")
            logger.warning(f"拒绝新连接 {client_id}: 已达上限")
            return False

        async with self._lock:
            self._connections[client_id] = websocket
            self._subscriptions[client_id] = set()

        logger.info(f"WebSocket连接: {client_id} (总连接数: {len(self._connections)})")
        return True

    async def disconnect(self, client_id: str):
        """断开连接"""
        async with self._lock:
            self._connections.pop(client_id, None)
            self._subscriptions.pop(client_id, None)

        logger.info(f"WebSocket断开: {client_id} (剩余: {len(self._connections)})")

    async def subscribe(self, client_id: str, codes: list[str]):
        """订阅指定股票"""
        async with self._lock:
            if client_id in self._subscriptions:
                self._subscriptions[client_id].update(codes)

    async def unsubscribe(self, client_id: str, codes: list[str]):
        """取消订阅"""
        async with self._lock:
            if client_id in self._subscriptions:
                self._subscriptions[client_id].difference_update(codes)

    def get_subscribed_clients(self, code: str) -> list[str]:
        """获取订阅了某只股票的所有客户端"""
        clients = []
        for cid, codes in self._subscriptions.items():
            if code in codes:
                clients.append(cid)
        return clients

    async def send_to_client(self, client_id: str, message: dict):
        """发送消息给指定客户端"""
        ws = self._connections.get(client_id)
        if ws:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.debug(f"发送消息失败 {client_id}: {e}")
                await self.disconnect(client_id)

    async def broadcast(self, message: dict):
        """广播消息给所有连接客户端"""
        disconnected = []
        for client_id, ws in self._connections.items():
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(client_id)

        for cid in disconnected:
            await self.disconnect(cid)

    async def broadcast_ranking(self, rankings: list[dict]):
        """广播排名快照"""
        msg = {
            "type": "ranking_snapshot",
            "timestamp": datetime.now(CST).isoformat(),
            "data": rankings,
        }
        await self.broadcast(msg)

    async def broadcast_market_status(self, status: str):
        """广播市场状态变更"""
        msg = {
            "type": "market_status",
            "timestamp": datetime.now(CST).isoformat(),
            "status": status,
        }
        await self.broadcast(msg)

    async def send_alert(self, level: str, message: str, code: str = ""):
        """发送告警"""
        alert_msg = {
            "type": "alert",
            "timestamp": datetime.now(CST).isoformat(),
            "level": level,
            "message": message,
            "code": code,
        }
        # 广播给所有客户端
        await self.broadcast(alert_msg)
        logger.info(f"告警: [{level}] {message}")

    async def send_stock_update(self, code: str, data: dict):
        """发送个股更新给订阅者"""
        clients = self.get_subscribed_clients(code)
        msg = {
            "type": "stock_update",
            "timestamp": datetime.now(CST).isoformat(),
            "code": code,
            "data": data,
        }
        for cid in clients:
            await self.send_to_client(cid, msg)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


# 全局WebSocket管理器实例
ws_manager = WSConnectionManager()


# FastAPI WebSocket端点处理函数
async def ws_endpoint(websocket: WebSocket):
    """WebSocket连接处理"""
    client_id = f"client_{id(websocket)}_{len(ws_manager._connections)}"

    connected = await ws_manager.connect(websocket, client_id)
    if not connected:
        return

    try:
        # 发送欢迎消息
        await websocket.send_json({
            "type": "connected",
            "timestamp": datetime.now(CST).isoformat(),
            "client_id": client_id,
            "message": "已连接到A股实时追踪系统",
        })

        # 发送最新排名（如果有的话）
        from backend.scoring.engine import get_top_rankings
        rankings = await get_top_rankings(limit=50)
        if rankings:
            await websocket.send_json({
                "type": "ranking_snapshot",
                "timestamp": datetime.now(CST).isoformat(),
                "data": rankings,
            })

        # 处理客户端消息
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=WS_PING_INTERVAL
                )

                msg_type = data.get("type", "")

                if msg_type == "subscribe":
                    codes = data.get("codes", [])
                    await ws_manager.subscribe(client_id, codes)
                    await websocket.send_json({
                        "type": "subscribed",
                        "codes": list(ws_manager._subscriptions.get(client_id, set())),
                    })

                elif msg_type == "unsubscribe":
                    codes = data.get("codes", [])
                    await ws_manager.unsubscribe(client_id, codes)

                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong"})

                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"未知消息类型: {msg_type}",
                    })

            except asyncio.TimeoutError:
                # 发送心跳
                try:
                    await websocket.send_json({"type": "pong"})
                except Exception:
                    break

    except WebSocketDisconnect:
        logger.debug(f"客户端断开: {client_id}")
    except Exception as e:
        logger.error(f"WebSocket异常 {client_id}: {e}")
    finally:
        await ws_manager.disconnect(client_id)
