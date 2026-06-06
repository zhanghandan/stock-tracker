/**
 * 登录页 - 手机号 + 验证码
 */
import React, { useState } from 'react';
import { Input, Button, message } from 'antd';
import { PhoneOutlined, SafetyOutlined } from '@ant-design/icons';
import { useAuthStore } from '../store/authStore';

const LoginPage: React.FC = () => {
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [sending, setSending] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const [loading, setLoading] = useState(false);
  const setAuth = useAuthStore((s) => s.setAuth);

  const handleSendCode = async () => {
    if (!/^1[3-9]\d{9}$/.test(phone)) {
      message.error('请输入正确的手机号');
      return;
    }
    setSending(true);
    try {
      const res = await fetch(`/api/auth/send-code?phone=${phone}`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        message.success('验证码已发送');
        // 开发模式：自动填入验证码
        if (data.code) {
          setCode(data.code);
          message.info(`验证码: ${data.code}`);
        }
        setCountdown(60);
        const timer = setInterval(() => {
          setCountdown((prev) => {
            if (prev <= 1) { clearInterval(timer); return 0; }
            return prev - 1;
          });
        }, 1000);
      } else {
        message.error(data.message || '发送失败');
      }
    } catch {
      message.error('网络错误');
    } finally {
      setSending(false);
    }
  };

  const handleLogin = async () => {
    if (!phone || !code) {
      message.error('请输入手机号和验证码');
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`/api/auth/login?phone=${phone}&code=${code}`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        setAuth(data.user, data.token);
        message.success('登录成功');
      } else {
        message.error(data.detail || '登录失败');
      }
    } catch {
      message.error('网络错误');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        {/* Logo */}
        <div className="login-logo">
          <div className="login-icon">📈</div>
          <h2>A股实时追踪</h2>
          <p>AI驱动的高价值股智能分析</p>
        </div>

        {/* Phone Input */}
        <div className="login-input-group">
          <Input
            size="large"
            prefix={<PhoneOutlined />}
            placeholder="请输入手机号"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            maxLength={11}
            type="tel"
          />
        </div>

        {/* Code Input */}
        <div className="login-input-group code-row">
          <Input
            size="large"
            prefix={<SafetyOutlined />}
            placeholder="请输入验证码"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            maxLength={6}
            style={{ flex: 1 }}
          />
          <Button
            size="large"
            type="primary"
            ghost
            onClick={handleSendCode}
            loading={sending}
            disabled={countdown > 0}
            style={{ minWidth: 110 }}
          >
            {countdown > 0 ? `${countdown}s` : '获取验证码'}
          </Button>
        </div>

        {/* Login Button */}
        <Button
          type="primary"
          size="large"
          block
          onClick={handleLogin}
          loading={loading}
          className="login-btn"
        >
          登录
        </Button>

        <div className="login-footer">
          登录即表示同意服务条款和隐私政策
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
