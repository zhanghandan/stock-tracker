/**
 * 告警通知组件
 */
import React, { useEffect } from 'react';
import { notification, List, Badge, Button, Popover, Space, Empty } from 'antd';
import { BellOutlined } from '@ant-design/icons';
import { useAlertStore } from '../store/alertStore';

const AlertNotification: React.FC = () => {
  const alerts = useAlertStore((s) => s.alerts);
  const clearAlerts = useAlertStore((s) => s.clearAlerts);

  // 实时告警弹窗
  useEffect(() => {
    if (alerts.length === 0) return;
    const latest = alerts[0];

    // 只弹Top3的告警
    // 实际可配置
    if (latest.level === 'info' || latest.level === 'warning') {
      // 用浏览器通知（如果授权）
      if (Notification.permission === 'granted') {
        new Notification('A股追踪提醒', {
          body: latest.message,
          icon: '/favicon.svg',
        });
      }
    }
  }, [alerts.length > 0 ? alerts[0]?.id : null]);

  // 请求通知权限
  useEffect(() => {
    if (Notification.permission === 'default') {
      Notification.requestPermission();
    }
  }, []);

  const levelColor: Record<string, string> = {
    info: '#1890ff',
    warning: '#faad14',
    critical: '#ff4d4f',
  };

  const popoverContent = (
    <div style={{ width: 'min(360px, 85vw)', maxHeight: 400, overflow: 'auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span style={{ fontWeight: 'bold' }}>告警消息</span>
        <Button size="small" onClick={clearAlerts}>清空</Button>
      </div>
      {alerts.length === 0 ? (
        <Empty description="暂无告警" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <List
          size="small"
          dataSource={alerts.slice(0, 20)}
          renderItem={(item) => (
            <List.Item style={{ borderBottom: '1px solid #f0f0f0', padding: '6px 0' }}>
              <div style={{ width: '100%' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Badge color={levelColor[item.level]} />
                  <span style={{ fontSize: 12, color: '#999' }}>
                    {new Date(item.timestamp).toLocaleTimeString()}
                  </span>
                  {item.code && (
                    <span style={{ fontSize: 11, background: '#f0f0f0', padding: '0 4px', borderRadius: 2 }}>
                      {item.code}
                    </span>
                  )}
                </div>
                <div style={{ fontSize: 13, marginTop: 2 }}>{item.message}</div>
              </div>
            </List.Item>
          )}
        />
      )}
    </div>
  );

  return (
    <Popover content={popoverContent} trigger="click" placement="bottomRight">
      <Badge count={alerts.length} size="small" offset={[-5, 5]}>
        <BellOutlined style={{ color: '#fff', fontSize: 18, cursor: 'pointer' }} />
      </Badge>
    </Popover>
  );
};

export default AlertNotification;
