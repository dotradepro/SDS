export interface Device {
  id: string;
  name: string;
  type: DeviceType;
  protocol: string;
  protocol_config: Record<string, any>;
  state: Record<string, any>;
  capabilities: string[];
  room: string;
  icon: string;
  created_at: string;
  updated_at: string;
  is_online: boolean;
  auto_report_interval: number;
}

export type DeviceType =
  | 'light'
  | 'switch'
  | 'climate'
  | 'sensor'
  | 'media_player'
  | 'lock'
  | 'cover'
  | 'camera'
  | 'vacuum'
  | 'speaker';

export interface DeviceCreate {
  name: string;
  type: DeviceType;
  protocol: string;
  protocol_config: Record<string, any>;
  state: Record<string, any>;
  capabilities: string[];
  room: string;
  icon: string;
  auto_report_interval: number;
}

export interface DeviceTemplate {
  default_state: Record<string, any>;
  capabilities: string[];
  icon: string;
  supported_protocols: string[];
  commands: string[];
  subtypes?: Record<string, { default_state: Record<string, any>; capabilities: string[] }>;
}

export interface Event {
  id: number;
  device_id: string | null;
  device_name: string;
  protocol: string;
  direction: string;
  event_type: string;
  topic: string;
  payload: string;
  timestamp: string;
}

export interface Scenario {
  id: string;
  name: string;
  description: string;
  is_active: boolean;
  triggers: ScenarioTrigger[];
  steps: ScenarioStep[];
  created_at: string;
  updated_at: string;
}

export interface ScenarioTrigger {
  type: string;
  interval_seconds?: number;
  cron?: string;
  delay_seconds?: number;
  device_id?: string;
  condition?: Record<string, any>;
}

export interface ScenarioStep {
  delay_seconds: number;
  device_id: string;
  action: string;
  state: Record<string, any>;
  params: Record<string, any>;
}

export interface ProtocolStatus {
  name: string;
  is_running: boolean;
  status: string;
  message: string;
  stats: {
    messages_sent: number;
    messages_received: number;
    errors: number;
  };
}

export interface Z2MGroup {
  id: number;
  friendly_name: string;
  members: { ieee_address: string; endpoint: number }[];
}

export interface WSMessage {
  type: string;
  [key: string]: any;
}
