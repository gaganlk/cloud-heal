"""
Redis-backed WebSocket manager with resilient reconnect handling.
Uses exponential backoff for Redis connectivity to prevent log spam.
"""
import asyncio
import json
import logging
import os
from typing import Dict, Optional

import redis.asyncio as aioredis
from fastapi import WebSocket

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
WS_BROADCAST_CHANNEL = "ws:broadcast"
WS_CLIENT_CHANNEL_PREFIX = "ws:client:"


class RedisWebSocketManager:
    """
    Multi-worker WebSocket manager using Redis pub/sub.
    Includes robust error handling and exponential backoff for Redis connectivity.
    """

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self._redis: Optional[aioredis.Redis] = None
        self._pubsub = None
        self._listener_task: Optional[asyncio.Task] = None
        self._local_mode = False
        self._is_running = False

    async def startup(self):
        """Initialize Redis connection and start the background listener."""
        self._is_running = True
        await self._init_redis_with_backoff()

    async def _init_redis_with_backoff(self):
        """Attempts to connect to Redis with exponential backoff."""
        delay = 1.0
        max_delay = 60.0
        
        while self._is_running:
            try:
                self._redis = aioredis.from_url(
                    REDIS_URL, 
                    decode_responses=True,
                    socket_connect_timeout=2.0,
                    socket_keepalive=True
                )
                await self._redis.ping()
                
                self._pubsub = self._redis.pubsub()
                await self._pubsub.subscribe(WS_BROADCAST_CHANNEL)
                
                # Re-subscribe existing clients if any (e.g. on reconnect)
                for client_id in self.active_connections:
                    await self._pubsub.subscribe(f"{WS_CLIENT_CHANNEL_PREFIX}{client_id}")

                self._listener_task = asyncio.create_task(self._listen_and_forward())
                self._local_mode = False
                logger.info(f"WebSocket manager connected to Redis: {REDIS_URL}")
                break
            except Exception as e:
                self._local_mode = True
                logger.warning(f"Redis connection failed ({e}). Retrying in {delay}s...")
                await asyncio.sleep(delay)
                delay = min(delay * 2, max_delay)

    async def shutdown(self):
        """Graceful shutdown of connections and tasks."""
        self._is_running = False
        if self._listener_task:
            self._listener_task.cancel()
        
        if self._pubsub:
            try:
                await self._pubsub.unsubscribe()
            except: pass
            
        if self._redis:
            await self._redis.aclose()
        logger.info("WebSocket manager shutdown complete.")

    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        
        if not self._local_mode and self._pubsub:
            try:
                personal_channel = f"{WS_CLIENT_CHANNEL_PREFIX}{client_id}"
                await self._pubsub.subscribe(personal_channel)
            except Exception as e:
                logger.error(f"Failed to subscribe to personal channel for {client_id}: {e}")
                
        logger.info(f"WS Connected: {client_id} (mode={'Local' if self._local_mode else 'Redis'})")

    async def disconnect(self, websocket: WebSocket, client_id: str):
        """Remove connection and cleanup channels."""
        self.active_connections.pop(client_id, None)
        if not self._local_mode and self._pubsub:
            try:
                personal_channel = f"{WS_CLIENT_CHANNEL_PREFIX}{client_id}"
                await self._pubsub.unsubscribe(personal_channel)
            except: pass
        logger.info(f"WS Disconnected: {client_id}")

    async def broadcast(self, message: dict):
        """Push message to all workers via Redis, or local clients if in fallback mode."""
        if self._local_mode or not self._redis:
            await self._local_broadcast(message)
        else:
            try:
                await self._redis.publish(WS_BROADCAST_CHANNEL, json.dumps(message))
            except Exception as e:
                logger.error(f"Redis publish failed: {e}")
                await self._local_broadcast(message)

    async def _local_broadcast(self, message: dict):
        """Fallback: send directly to connections in this process."""
        dead = []
        for cid, ws in list(self.active_connections.items()):
            try:
                await ws.send_json(message)
            except:
                dead.append(cid)
        for cid in dead:
            self.active_connections.pop(cid, None)

    async def send_to_client(self, client_id: str, message: dict):
        """Direct message to a specific client via Redis."""
        if not self._local_mode and self._redis:
            try:
                channel = f"{WS_CLIENT_CHANNEL_PREFIX}{client_id}"
                await self._redis.publish(channel, json.dumps(message))
                return
            except: pass
            
        # Fallback to local
        ws = self.active_connections.get(client_id)
        if ws:
            try:
                await ws.send_json(message)
            except:
                self.active_connections.pop(client_id, None)

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Directly send a message to a specific WebSocket connection."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.debug(f"Failed to send personal message: {e}")


    async def _listen_and_forward(self):
        """Background task forwarding Redis messages to local WebSockets."""
        try:
            async for message in self._pubsub.listen():
                if not self._is_running: break
                if message["type"] != "message": continue

                channel = message["channel"]
                try:
                    data = json.loads(message["data"])
                except: continue

                if channel == WS_BROADCAST_CHANNEL:
                    await self._local_broadcast(data)
                elif channel.startswith(WS_CLIENT_CHANNEL_PREFIX):
                    client_id = channel[len(WS_CLIENT_CHANNEL_PREFIX):]
                    ws = self.active_connections.get(client_id)
                    if ws:
                        try:
                            await ws.send_json(data)
                        except:
                            self.active_connections.pop(client_id, None)
        except aioredis.ConnectionError:
            logger.warning("Redis connection lost. Initiating reconnect...")
            asyncio.create_task(self._init_redis_with_backoff())
        except Exception as e:
            if self._is_running:
                logger.error(f"WS Listener error: {e}")
                await asyncio.sleep(5)
                asyncio.create_task(self._init_redis_with_backoff())

# Singleton instance
manager = RedisWebSocketManager()
