/**
 * WebSocket连接管理
 */
import { WS_URL } from '../utils/constants';

export type WSMessageHandler = (data: any) => void;

class WSClient {
  private ws: WebSocket | null = null;
  private handlers: Map<string, Set<WSMessageHandler>> = new Map();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempt: number = 0;
  private maxReconnectDelay: number = 30000;
  private baseDelay: number = 1000;
  private intentionalClose: boolean = false;

  public onStatusChange?: (status: 'connected' | 'disconnected' | 'reconnecting') => void;

  connect() {
    this.intentionalClose = false;
    this._connect();
  }

  private _connect() {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    try {
      this.ws = new WebSocket(WS_URL);
    } catch (e) {
      console.error('WebSocket创建失败:', e);
      this._scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      console.log('WebSocket已连接');
      this.reconnectAttempt = 0;
      this.onStatusChange?.('connected');
    };

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        const type = msg.type;

        // 分发到对应的处理器
        if (this.handlers.has(type)) {
          this.handlers.get(type)!.forEach((handler) => handler(msg));
        }

        // 通用处理器
        if (this.handlers.has('*')) {
          this.handlers.get('*')!.forEach((handler) => handler(msg));
        }
      } catch (e) {
        console.error('WebSocket消息解析失败:', e);
      }
    };

    this.ws.onclose = (event) => {
      if (!this.intentionalClose) {
        console.log(`WebSocket断开 (code: ${event.code})，准备重连...`);
        this.onStatusChange?.('disconnected');
        this._scheduleReconnect();
      }
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket错误:', error);
    };
  }

  private _scheduleReconnect() {
    if (this.reconnectTimer) return;

    this.reconnectAttempt++;
    const delay = Math.min(
      this.baseDelay * Math.pow(2, this.reconnectAttempt - 1),
      this.maxReconnectDelay
    );

    console.log(`${delay / 1000}秒后尝试重连 (第${this.reconnectAttempt}次)`);
    this.onStatusChange?.('reconnecting');

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this._connect();
    }, delay);
  }

  disconnect() {
    this.intentionalClose = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.ws?.close();
    this.ws = null;
  }

  subscribe(codes: string[]) {
    this._send({ type: 'subscribe', codes });
  }

  unsubscribe(codes: string[]) {
    this._send({ type: 'unsubscribe', codes });
  }

  on(type: string, handler: WSMessageHandler) {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, new Set());
    }
    this.handlers.get(type)!.add(handler);

    return () => {
      this.handlers.get(type)?.delete(handler);
    };
  }

  private _send(data: any) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

// 单例
export const wsClient = new WSClient();
