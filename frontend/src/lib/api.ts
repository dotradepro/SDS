import type { Device, DeviceCreate, Event, Scenario, ProtocolStatus, DeviceTemplate, Z2MGroup } from '@/types';

const BASE = '/api/v1';

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

// Devices
export const getDevices = () => request<Device[]>('/devices');
export const getDevice = (id: string) => request<Device>(`/devices/${id}`);
export const createDevice = (data: DeviceCreate) =>
  request<Device>('/devices', { method: 'POST', body: JSON.stringify(data) });
export const updateDevice = (id: string, data: Partial<Device>) =>
  request<Device>(`/devices/${id}`, { method: 'PUT', body: JSON.stringify(data) });
export const deleteDevice = (id: string) =>
  request<void>(`/devices/${id}`, { method: 'DELETE' });
export const getDeviceState = (id: string) => request<Record<string, any>>(`/devices/${id}/state`);
export const setDeviceState = (id: string, state: Record<string, any>) =>
  request<Record<string, any>>(`/devices/${id}/state`, { method: 'POST', body: JSON.stringify({ state }) });
export const executeCommand = (id: string, command: string, params: Record<string, any> = {}) =>
  request<Record<string, any>>(`/devices/${id}/command`, { method: 'POST', body: JSON.stringify({ command, params }) });
export const getDeviceHistory = (id: string, limit = 100) =>
  request<Event[]>(`/devices/${id}/history?limit=${limit}`);
export const restartDeviceProtocol = (id: string) =>
  request<void>(`/devices/${id}/restart`, { method: 'POST' });

// Templates
export const getTemplates = () => request<Record<string, DeviceTemplate>>('/templates');
export const getTemplate = (type: string) => request<DeviceTemplate>(`/templates/${type}`);

// Events
export const getEvents = (params?: { device_id?: string; protocol?: string; limit?: number }) => {
  const q = new URLSearchParams();
  if (params?.device_id) q.set('device_id', params.device_id);
  if (params?.protocol) q.set('protocol', params.protocol);
  if (params?.limit) q.set('limit', String(params.limit));
  return request<Event[]>(`/events?${q}`);
};
export const clearEvents = () => request<void>('/events', { method: 'DELETE' });

// Scenarios
export const getScenarios = () => request<Scenario[]>('/scenarios');
export const createScenario = (data: Partial<Scenario>) =>
  request<Scenario>('/scenarios', { method: 'POST', body: JSON.stringify(data) });
export const updateScenario = (id: string, data: Partial<Scenario>) =>
  request<Scenario>(`/scenarios/${id}`, { method: 'PUT', body: JSON.stringify(data) });
export const deleteScenario = (id: string) =>
  request<void>(`/scenarios/${id}`, { method: 'DELETE' });
export const startScenario = (id: string) =>
  request<void>(`/scenarios/${id}/start`, { method: 'POST' });
export const stopScenario = (id: string) =>
  request<void>(`/scenarios/${id}/stop`, { method: 'POST' });

// Protocols
export const getHealth = () => request<{ status: string; protocols: Record<string, ProtocolStatus> }>('/health');
export const getProtocols = () => request<ProtocolStatus[]>('/protocols');
export const restartProtocol = (name: string) =>
  request<void>(`/protocols/${name}/restart`, { method: 'POST' });

// Z2M Groups
export const getGroups = () => request<Z2MGroup[]>('/groups');
export const createGroup = (friendly_name: string) =>
  request<Z2MGroup>('/groups', { method: 'POST', body: JSON.stringify({ friendly_name }) });
export const deleteGroup = (id: number) =>
  request<void>(`/groups/${id}`, { method: 'DELETE' });
export const addGroupMember = (groupId: number, deviceId: string) =>
  request<void>(`/groups/${groupId}/members`, { method: 'POST', body: JSON.stringify({ device_id: deviceId }) });
export const removeGroupMember = (groupId: number, deviceId: string) =>
  request<void>(`/groups/${groupId}/members/${deviceId}`, { method: 'DELETE' });
