/**
 * AI Analysis Panel - DeepSeek-powered insights with Chat + AI Ranking
 * Features: quick prompts, free chat, AI intelligent ranking
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  RobotOutlined, SendOutlined, ThunderboltOutlined,
  RiseOutlined, WarningOutlined, BulbOutlined,
} from '@ant-design/icons';
import { RankingItem } from '../store/rankingStore';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

interface AIRankingItem {
  code: string;
  name: string;
  ai_rank: number;
  reason: string;
  risk: string;
  advice: string;
}

interface Props {
  code?: string;
  rankings: RankingItem[];
  compact?: boolean;
  onAIRanking?: (rankings: AIRankingItem[]) => void;
}

const QUICK_PROMPTS = [
  { icon: <RiseOutlined />, label: '推荐买入', prompt: '基于当前数据，推荐3只最值得买入的股票，说明每只的买入理由和主要风险。' },
  { icon: <WarningOutlined />, label: '风险警示', prompt: '检查Top20中哪些股票存在较高风险？请列出并说明风险点。' },
  { icon: <ThunderboltOutlined />, label: '今日最强', prompt: '今天表现最强劲的股票有哪些？分析其强势能否持续。' },
  { icon: <BulbOutlined />, label: '深度对比', prompt: '对比Top5股票，分析各自的优缺点，给出综合推荐排名。' },
];

const AIAnalysis: React.FC<Props> = ({ code, rankings, compact, onAIRanking }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || loading) return;

    const userMsg: ChatMessage = {
      role: 'user',
      content: text.trim(),
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMsg]);
    setInputValue('');
    setLoading(true);

    try {
      const history = messages.map(m => ({ role: m.role, content: m.content }));
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text.trim(), history, mode: 'analyst' }),
      });

      if (res.ok) {
        const data = await res.json();
        const aiMsg: ChatMessage = {
          role: 'assistant',
          content: data.reply || 'AI暂未返回内容',
          timestamp: new Date().toISOString(),
        };
        setMessages(prev => [...prev, aiMsg]);
      } else {
        const data = await res.json();
        if (!data.enabled) setError('AI未启用 (需设置DEEPSEEK_API_KEY)');
        else setError('AI回复失败');
      }
    } catch {
      setError('AI服务连接失败');
    } finally {
      setLoading(false);
    }
  }, [messages, loading]);

  // Refresh AI ranking
  const fetchAIRanking = useCallback(async () => {
    try {
      const res = await fetch('/api/ai/rank', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        if (data.rankings?.length && onAIRanking) {
          onAIRanking(data.rankings);
        }
      }
    } catch {
      // silent
    }
  }, [onAIRanking]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(inputValue);
    }
  };

  // Compact mode = right panel
  if (compact) {
    return (
      <>
        {/* === Header === */}
        <div className="panel-header">
          <span><RobotOutlined /> AI CHAT</span>
          <div style={{ display: 'flex', gap: 6 }}>
            <span
              style={{ cursor: 'pointer', fontSize: 11, color: 'var(--accent)' }}
              onClick={fetchAIRanking}
              title="AI重新排名"
            >
              🤖 AI排名
            </span>
          </div>
        </div>

        {/* === 错误 === */}
        {error && (
          <div style={{ padding: '2px 8px', flexShrink: 0, fontSize: 11, color: 'var(--warning)', textAlign: 'center' }}>
            {error}
          </div>
        )}

        {/* === 快捷按钮 === */}
        <div style={{ padding: '4px 8px', display: 'flex', flexWrap: 'wrap', gap: 3, flexShrink: 0 }}>
          {QUICK_PROMPTS.map((qp, i) => (
            <button
              key={i}
              className="quick-prompt-btn"
              onClick={() => sendMessage(qp.prompt)}
              disabled={loading}
            >
              {qp.icon} {qp.label}
            </button>
          ))}
        </div>

        {/* === 聊天区 === */}
        <div style={{ flex: 1, overflow: 'auto', padding: '4px 8px' }}>
          {messages.length === 0 && (
            <div style={{ textAlign: 'center', padding: 20, color: 'var(--text-muted)', fontSize: 11 }}>
              <RobotOutlined style={{ fontSize: 22, display: 'block', margin: '0 auto 8px' }} />
              💬 问AI任何股票问题
            </div>
          )}
          {messages.map((msg, i) => (
            <div key={i} className={`chat-bubble ${msg.role === 'user' ? 'chat-user' : 'chat-ai'}`}>
              <div className="chat-bubble-role">{msg.role === 'user' ? '👤' : '🤖'}</div>
              <div className="chat-bubble-text">{msg.content}</div>
              <div className="chat-bubble-time">{new Date(msg.timestamp).toLocaleTimeString()}</div>
            </div>
          ))}
          {loading && (
            <div className="chat-bubble chat-ai">
              <div className="chat-bubble-role">🤖</div>
              <div className="chat-bubble-text"><span className="pulse">分析中...</span></div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {/* === 输入框 === */}
        <div style={{ padding: '8px', borderTop: '1px solid var(--border)', flexShrink: 0 }}>
          <div style={{ display: 'flex', gap: 6 }}>
            <textarea
              ref={inputRef}
              value={inputValue}
              onChange={e => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入问题..."
              disabled={loading}
              rows={2}
              style={{
                flex: 1, resize: 'none', background: 'var(--bg-card)',
                border: '1px solid var(--border)', borderRadius: 6,
                color: 'var(--text-primary)', padding: '6px 10px',
                fontSize: 12, fontFamily: 'var(--font-sans)', outline: 'none',
              }}
            />
            <button
              onClick={() => sendMessage(inputValue)}
              disabled={loading || !inputValue.trim()}
              style={{
                background: loading ? 'var(--bg-card)' : 'var(--accent)',
                border: 'none', borderRadius: 6, color: '#fff',
                padding: '0 14px', cursor: loading ? 'not-allowed' : 'pointer',
                fontSize: 16, display: 'flex', alignItems: 'center',
              }}
            >
              <SendOutlined />
            </button>
          </div>
        </div>
      </>
    );
  }

  // Full mode = center tab
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '8px 16px', borderBottom: '1px solid var(--border)', flexShrink: 0,
      }}>
        <h3 style={{ color: 'var(--accent)', fontSize: 14, margin: 0 }}>
          <RobotOutlined /> AI 智能分析引擎
        </h3>
        <div style={{ display: 'flex', gap: 10 }}>
          <span
            style={{ cursor: 'pointer', color: 'var(--accent)', fontSize: 12, fontWeight: 600 }}
            onClick={fetchAIRanking}
          >
            🤖 AI重新排名
          </span>
        </div>
      </div>

      {error && (
        <div style={{ padding: '4px 16px', flexShrink: 0 }}>
          <div style={{ color: 'var(--warning)', fontSize: 12, textAlign: 'center' }}>
            {error}
            {error.includes('未启用') && (
              <><br /><small>前往 platform.deepseek.com 获取免费API Key</small></>
            )}
          </div>
        </div>
      )}

      {/* Quick prompts */}
      <div style={{
        padding: '8px 16px', display: 'flex', gap: 8, flexShrink: 0,
        borderBottom: '1px solid var(--border)', flexWrap: 'wrap',
      }}>
        {QUICK_PROMPTS.map((qp, i) => (
          <button
            key={i}
            className="quick-prompt-btn"
            onClick={() => sendMessage(qp.prompt)}
            disabled={loading}
            title={qp.prompt}
          >
            {qp.icon} {qp.label}
          </button>
        ))}
      </div>

      {/* Chat messages */}
      <div style={{ flex: 1, overflow: 'auto', padding: '12px 16px' }}>
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
            <RobotOutlined style={{ fontSize: 40, display: 'block', margin: '0 auto 12px' }} />
            <div style={{ fontSize: 13 }}>点击上方快捷按钮或输入问题，获取AI投资建议</div>
            <div style={{ fontSize: 11, marginTop: 8, color: 'var(--text-muted)' }}>
              示例："推荐3只短线股" / "茅台怎么样？" / "哪些股票风险最大？"
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`chat-bubble ${msg.role === 'user' ? 'chat-user' : 'chat-ai'}`}
            style={{ maxWidth: msg.role === 'user' ? '60%' : '85%' }}
          >
            <div className="chat-bubble-role">
              {msg.role === 'user' ? '👤 你' : '🤖 AI分析师'}
            </div>
            <div className="chat-bubble-text">{msg.content}</div>
            <div className="chat-bubble-time">
              {new Date(msg.timestamp).toLocaleTimeString()}
            </div>
          </div>
        ))}
        {loading && (
          <div className="chat-bubble chat-ai" style={{ maxWidth: '85%' }}>
            <div className="chat-bubble-role">🤖 AI分析师</div>
            <div className="chat-bubble-text">
              <span className="pulse">正在分析中...</span>
            </div>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      {/* Input */}
      <div style={{
        padding: '10px 16px', borderTop: '1px solid var(--border)', flexShrink: 0,
      }}>
        <div style={{ display: 'flex', gap: 8 }}>
          <textarea
            ref={inputRef}
            value={inputValue}
            onChange={e => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入你的问题，如：推荐3只值得买入的股票..."
            disabled={loading}
            rows={2}
            style={{
              flex: 1,
              resize: 'none',
              background: 'var(--bg-card)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              color: 'var(--text-primary)',
              padding: '8px 12px',
              fontSize: 13,
              fontFamily: 'var(--font-sans)',
              outline: 'none',
            }}
          />
          <button
            onClick={() => sendMessage(inputValue)}
            disabled={loading || !inputValue.trim()}
            style={{
              background: loading ? 'var(--bg-card)' : 'var(--accent)',
              border: 'none',
              borderRadius: 8,
              color: '#fff',
              padding: '0 20px',
              cursor: loading ? 'not-allowed' : 'pointer',
              fontSize: 18,
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              transition: 'all 0.15s',
            }}
          >
            <SendOutlined />
          </button>
        </div>
        <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4, textAlign: 'right' }}>
          Enter 发送 · Shift+Enter 换行
        </div>
      </div>
    </div>
  );
};

export default AIAnalysis;
