import { useEffect, useRef, useCallback } from 'react';
import { useStore } from '@/lib/store';
import type { WSMessage } from '@/types';

function safeString(v: unknown): string {
  if (v === null || v === undefined) return '';
  if (typeof v === 'string') return v;
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number>();
  const { setWsConnected, addEvent, updateDeviceState } = useStore();

  const connect = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

    ws.onopen = () => {
      setWsConnected(true);
      ws.send(JSON.stringify({ type: 'get_all_states' }));
    };

    ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data);

        if (msg.type === 'state_changed' && msg.device_id && msg.new_state) {
          updateDeviceState(msg.device_id, msg.new_state);
        }

        if (msg.type === 'protocol_event' || msg.type === 'state_changed') {
          addEvent({
            id: Date.now() + Math.random(),
            device_id: msg.device_id || null,
            device_name: safeString(msg.device_name),
            protocol: safeString(msg.protocol),
            direction: safeString(msg.direction),
            event_type: safeString(msg.type),
            topic: safeString(msg.topic),
            payload: safeString(msg.payload || msg.new_state),
            timestamp: safeString(msg.timestamp) || new Date().toISOString(),
          });
        }

        if (msg.type === 'all_states' && Array.isArray(msg.devices)) {
          for (const device of msg.devices) {
            if (device?.id && device?.state) {
              updateDeviceState(device.id, device.state);
            }
          }
        }
      } catch (err) {
        console.error('WS message error:', err);
      }
    };

    ws.onclose = () => {
      setWsConnected(false);
      reconnectTimeoutRef.current = window.setTimeout(connect, 3000);
    };

    ws.onerror = () => ws.close();
    wsRef.current = ws;
  }, [setWsConnected, addEvent, updateDeviceState]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimeoutRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return wsRef;
}
