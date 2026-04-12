import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState, useMemo } from 'react';
import { getDevice, getDeviceHistory, deleteDevice, executeCommand, setDeviceState, restartDeviceProtocol } from '@/lib/api';
import { useStore } from '@/lib/store';
import { Button, Card, CardContent, CardHeader, CardTitle, Badge, Slider, Switch, Input, Textarea, Select, Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui';
import { cn, safe } from '@/lib/utils';

export function DeviceDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const deviceStates = useStore((s) => s.deviceStates);
  const liveState = deviceStates[id!];
  const allRecentEvents = useStore((s) => s.recentEvents);
  const recentEvents = useMemo(() => allRecentEvents.filter((e) => e.device_id === id), [allRecentEvents, id]);

  const { data: device, isLoading } = useQuery({ queryKey: ['device', id], queryFn: () => getDevice(id!), refetchInterval: 5000 });
  const { data: history = [] } = useQuery({ queryKey: ['device-history', id], queryFn: () => getDeviceHistory(id!, 50), refetchInterval: 10000 });

  const [rawState, setRawState] = useState('');
  const [activeTab, setActiveTab] = useState('control');

  const cmdMutation = useMutation({
    mutationFn: ({ cmd, params }: { cmd: string; params?: Record<string, any> }) => executeCommand(id!, cmd, params || {}),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['device', id] }),
  });

  const stateMutation = useMutation({
    mutationFn: (state: Record<string, any>) => setDeviceState(id!, state),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['device', id] }),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteDevice(id!),
    onSuccess: () => navigate('/devices'),
  });

  const restartMutation = useMutation({
    mutationFn: () => restartDeviceProtocol(id!),
  });

  if (isLoading || !device) {
    return <div className="text-center py-12 text-muted-foreground">Завантаження...</div>;
  }

  const state = liveState || device.state || {};
  const stateVal = safe(state.state);
  const isOn = stateVal === 'ON' || stateVal === 'on';

  const config = device.protocol_config || {};
  const fn = config.friendly_name || device.name.toLowerCase().replace(/[^a-z0-9]+/g, '_');

  const getConnectionInfo = () => {
    const p = device.protocol;
    const rows: { label: string; value: string; mono?: boolean }[] = [];
    rows.push({ label: 'Протокол', value: p });
    if (config.manufacturer) rows.push({ label: 'Виробник', value: config.manufacturer });
    if (config.model_id) rows.push({ label: 'Модель', value: config.model_id });

    if (p === 'zigbee2mqtt') {
      rows.push({ label: 'Friendly Name', value: fn, mono: true });
      if (config.ieee_address) rows.push({ label: 'IEEE адреса', value: config.ieee_address, mono: true });
      rows.push({ label: 'MQTT брокер', value: 'mosquitto:1883' });
      rows.push({ label: 'Топік стану', value: `zigbee2mqtt/${fn}`, mono: true });
      rows.push({ label: 'Топік команд', value: `zigbee2mqtt/${fn}/set`, mono: true });
      rows.push({ label: 'Топік запиту', value: `zigbee2mqtt/${fn}/get`, mono: true });
      rows.push({ label: 'Виявлення', value: 'zigbee2mqtt/bridge/devices', mono: true });
    } else if (p === 'mqtt') {
      const scheme = config.topic_scheme || 'generic';
      const dn = config.device_name || fn;
      rows.push({ label: 'Схема', value: scheme });
      rows.push({ label: 'MQTT брокер', value: 'mosquitto:1883' });
      if (scheme === 'tasmota') {
        rows.push({ label: 'Стан', value: `stat/${dn}/POWER`, mono: true });
        rows.push({ label: 'Команди', value: `cmnd/${dn}/POWER`, mono: true });
        rows.push({ label: 'Телеметрія', value: `tele/${dn}/STATE`, mono: true });
      } else if (scheme === 'shelly') {
        rows.push({ label: 'Стан', value: `shellies/${dn}/relay/0`, mono: true });
        rows.push({ label: 'Команди', value: `shellies/${dn}/relay/0/command`, mono: true });
      } else {
        const bt = config.base_topic || `sds/${device.id}`;
        rows.push({ label: 'Стан', value: bt, mono: true });
        rows.push({ label: 'Команди', value: `${bt}/set`, mono: true });
      }
    } else if (p === 'http_hue') {
      rows.push({ label: 'API хост', value: 'http://<SDS_IP>:7000' });
      rows.push({ label: 'Токен', value: 'sds-test-token', mono: true });
      rows.push({ label: 'Список ламп', value: 'GET /api/<token>/lights', mono: true });
      rows.push({ label: 'Змінити стан', value: 'PUT /api/<token>/lights/<id>/state', mono: true });
    } else if (p === 'http_lifx') {
      rows.push({ label: 'API хост', value: 'http://<SDS_IP>:7000' });
      rows.push({ label: 'Device ID', value: device.id, mono: true });
      rows.push({ label: 'Список', value: 'GET /v1/lights', mono: true });
      rows.push({ label: 'Змінити стан', value: `PUT /v1/lights/${device.id}/state`, mono: true });
    } else if (p === 'http') {
      rows.push({ label: 'API хост', value: 'http://<SDS_IP>:7000' });
      rows.push({ label: 'Стан', value: `GET /devices/${device.id}/state`, mono: true });
      rows.push({ label: 'Команда', value: `POST /devices/${device.id}/command`, mono: true });
    } else if (p === 'miio') {
      rows.push({ label: 'UDP порт', value: '54321' });
      rows.push({ label: 'Токен', value: config.token || 'не задано', mono: true });
      rows.push({ label: 'Шифрування', value: 'AES-128-CBC' });
      if (device.type === 'vacuum') {
        rows.push({ label: 'Команди', value: 'get_status, app_start, app_pause, app_charge', mono: true });
      } else {
        rows.push({ label: 'Команди', value: 'get_prop, set_power, set_bright, set_rgb', mono: true });
      }
    } else if (p === 'ha_websocket') {
      rows.push({ label: 'WebSocket', value: 'ws://<SDS_IP>:8123', mono: true });
      rows.push({ label: 'Токен', value: 'test_token_for_selena', mono: true });
      rows.push({ label: 'Entity ID', value: `${device.type}.${fn}`, mono: true });
      rows.push({ label: 'Сервіси', value: 'call_service, get_states, subscribe_events' });
    }
    return rows;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold">{device.name}</h1>
          <div className="flex items-center gap-2 mt-1">
            <Badge>{device.protocol}</Badge>
            <Badge variant={device.is_online ? 'default' : 'destructive'}>{device.is_online ? 'Онлайн' : 'Офлайн'}</Badge>
            {device.room && <span className="text-sm text-muted-foreground">{device.room}</span>}
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => restartMutation.mutate()}>Перезапустити протокол</Button>
          <Button variant="destructive" size="sm" onClick={() => { if (confirm('Видалити цей пристрій?')) deleteMutation.mutate(); }}>Видалити</Button>
        </div>
      </div>

      {/* Параметри підключення */}
      <Card className="border-blue-200 dark:border-blue-900 bg-blue-50/50 dark:bg-blue-950/20">
        <CardContent className="p-4">
          <h3 className="font-semibold text-sm mb-3">Параметри підключення для Selena</h3>
          <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-xs">
            {getConnectionInfo().map((row, i) => (
              <React.Fragment key={i}>
                <span className="text-muted-foreground whitespace-nowrap">{row.label}:</span>
                {row.mono ? (
                  <code className="bg-background px-1.5 py-0.5 rounded border font-mono text-[11px] break-all">{row.value}</code>
                ) : (
                  <span>{row.value}</span>
                )}
              </React.Fragment>
            ))}
          </div>
        </CardContent>
      </Card>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="control">Керування</TabsTrigger>
          <TabsTrigger value="state">Стан</TabsTrigger>
          <TabsTrigger value="protocol">Протокол</TabsTrigger>
          <TabsTrigger value="history">Історія</TabsTrigger>
        </TabsList>

        {/* Панель керування */}
        <TabsContent value="control">
          <Card>
            <CardHeader><CardTitle>Панель керування</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              {device.type === 'light' && (
                <>
                  <div className="flex items-center gap-4">
                    <span className="text-sm font-medium w-24">Живлення</span>
                    <Switch checked={isOn} onCheckedChange={() => cmdMutation.mutate({ cmd: 'toggle' })} />
                    <span className="text-sm">{stateVal}</span>
                  </div>
                  {device.capabilities.includes('brightness') && (
                    <div className="flex items-center gap-4">
                      <span className="text-sm font-medium w-24">Яскравість</span>
                      <Slider
                        value={state.brightness || 0}
                        min={0}
                        max={254}
                        onChange={(v) => cmdMutation.mutate({ cmd: 'set_brightness', params: { brightness: v } })}
                        className="flex-1"
                      />
                      <span className="text-sm w-12">{Math.round(((state.brightness || 0) / 254) * 100)}%</span>
                    </div>
                  )}
                  {device.capabilities.includes('color_temp') && (
                    <div className="flex items-center gap-4">
                      <span className="text-sm font-medium w-24">Температура</span>
                      <Slider
                        value={state.color_temp || 300}
                        min={153}
                        max={500}
                        onChange={(v) => cmdMutation.mutate({ cmd: 'set_color_temp', params: { color_temp: v } })}
                        className="flex-1"
                      />
                      <span className="text-sm w-12">{state.color_temp || 300}K</span>
                    </div>
                  )}
                  {device.capabilities.includes('color') && (
                    <div className="flex items-center gap-4">
                      <span className="text-sm font-medium w-24">Колір</span>
                      <input
                        type="color"
                        value={`#${((state.color?.r || 255) << 16 | (state.color?.g || 255) << 8 | (state.color?.b || 255)).toString(16).padStart(6, '0')}`}
                        onChange={(e) => {
                          const hex = e.target.value.slice(1);
                          const r = parseInt(hex.slice(0, 2), 16);
                          const g = parseInt(hex.slice(2, 4), 16);
                          const b = parseInt(hex.slice(4, 6), 16);
                          cmdMutation.mutate({ cmd: 'set_color', params: { color: { r, g, b } } });
                        }}
                        className="w-12 h-10 rounded border cursor-pointer"
                      />
                    </div>
                  )}
                </>
              )}

              {device.type === 'switch' && (
                <div className="flex items-center gap-4">
                  <span className="text-sm font-medium w-24">Живлення</span>
                  <Switch checked={isOn} onCheckedChange={() => cmdMutation.mutate({ cmd: 'toggle' })} />
                  <span className="text-sm">{state.state}</span>
                  {state.power_consumption !== undefined && (
                    <span className="text-sm text-muted-foreground ml-4">{safe(state.power_consumption)} Вт</span>
                  )}
                </div>
              )}

              {device.type === 'climate' && (
                <>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="text-center p-4 bg-muted rounded-lg">
                      <div className="text-3xl font-bold">{safe(state.current_temperature)}°</div>
                      <div className="text-sm text-muted-foreground">Поточна</div>
                    </div>
                    <div className="text-center p-4 bg-primary/10 rounded-lg">
                      <div className="text-3xl font-bold">{safe(state.target_temperature)}°</div>
                      <div className="text-sm text-muted-foreground">Цільова</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="text-sm font-medium w-28">Цільова темп.</span>
                    <Slider
                      value={state.target_temperature || 22}
                      min={5}
                      max={35}
                      step={0.5}
                      onChange={(v) => stateMutation.mutate({ target_temperature: v })}
                      className="flex-1"
                    />
                    <span className="text-sm w-12">{safe(state.target_temperature)}°</span>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="text-sm font-medium w-28">Режим HVAC</span>
                    <Select
                      value={state.hvac_mode || 'off'}
                      onValueChange={(v) => cmdMutation.mutate({ cmd: 'set_hvac_mode', params: { hvac_mode: v } })}
                      options={[
                        { value: 'off', label: 'Вимк.' },
                        { value: 'heat', label: 'Нагрів' },
                        { value: 'cool', label: 'Охолодження' },
                        { value: 'auto', label: 'Авто' },
                        { value: 'fan_only', label: 'Вентилятор' },
                      ]}
                    />
                  </div>
                </>
              )}

              {device.type === 'sensor' && (
                <div className="space-y-3">
                  <p className="text-sm text-muted-foreground">Датчики працюють тільки на читання. Кнопки нижче імітують події:</p>
                  {state.occupancy !== undefined && (
                    <div className="flex gap-2">
                      <Button size="sm" onClick={() => stateMutation.mutate({ occupancy: true })}>Виявити рух</Button>
                      <Button size="sm" variant="outline" onClick={() => stateMutation.mutate({ occupancy: false })}>Очистити рух</Button>
                    </div>
                  )}
                  {state.contact !== undefined && (
                    <div className="flex gap-2">
                      <Button size="sm" onClick={() => stateMutation.mutate({ contact: false })}>Відкрити двері</Button>
                      <Button size="sm" variant="outline" onClick={() => stateMutation.mutate({ contact: true })}>Закрити двері</Button>
                    </div>
                  )}
                  {state.temperature !== undefined && (
                    <div className="flex items-center gap-4">
                      <span className="text-sm w-24">Температура</span>
                      <Slider value={state.temperature} min={-20} max={50} step={0.1} onChange={(v) => stateMutation.mutate({ temperature: v })} className="flex-1" />
                      <span className="text-sm w-12">{safe(state.temperature)}°</span>
                    </div>
                  )}
                  {state.humidity !== undefined && (
                    <div className="flex items-center gap-4">
                      <span className="text-sm w-24">Вологість</span>
                      <Slider value={state.humidity} min={0} max={100} onChange={(v) => stateMutation.mutate({ humidity: v })} className="flex-1" />
                      <span className="text-sm w-12">{safe(state.humidity)}%</span>
                    </div>
                  )}
                  {state.smoke !== undefined && (
                    <div className="flex gap-2">
                      <Button size="sm" variant="destructive" onClick={() => stateMutation.mutate({ smoke: true })}>Виявити дим</Button>
                      <Button size="sm" variant="outline" onClick={() => stateMutation.mutate({ smoke: false })}>Очистити дим</Button>
                    </div>
                  )}
                  {state.water_leak !== undefined && (
                    <div className="flex gap-2">
                      <Button size="sm" variant="destructive" onClick={() => stateMutation.mutate({ water_leak: true })}>Виявити протікання</Button>
                      <Button size="sm" variant="outline" onClick={() => stateMutation.mutate({ water_leak: false })}>Очистити</Button>
                    </div>
                  )}
                </div>
              )}

              {device.type === 'vacuum' && (
                <>
                  <div className="flex items-center gap-4 flex-wrap">
                    <Badge variant={stateVal === 'cleaning' ? 'default' : 'secondary'}>{stateVal}</Badge>
                    <span className="text-sm">Батарея: {safe(state.battery)}%</span>
                    <span className="text-sm">Потужність: {safe(state.fan_speed)}</span>
                  </div>
                  <div className="flex gap-2 flex-wrap">
                    <Button size="sm" onClick={() => cmdMutation.mutate({ cmd: 'start' })}>Старт</Button>
                    <Button size="sm" variant="outline" onClick={() => cmdMutation.mutate({ cmd: 'pause' })}>Па��за</Button>
                    <Button size="sm" variant="outline" onClick={() => cmdMutation.mutate({ cmd: 'return_to_base' })}>На базу</Button>
                    <Button size="sm" variant="ghost" onClick={() => cmdMutation.mutate({ cmd: 'locate' })}>Знайти</Button>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="text-sm font-medium w-24">Потужність</span>
                    <Select
                      value={state.fan_speed || 'standard'}
                      onValueChange={(v) => cmdMutation.mutate({ cmd: 'set_fan_speed', params: { fan_speed: v } })}
                      options={[
                        { value: 'quiet', label: 'Тихий' },
                        { value: 'standard', label: 'Стандарт' },
                        { value: 'turbo', label: 'Турбо' },
                        { value: 'max', label: 'Макс' },
                      ]}
                    />
                  </div>
                </>
              )}

              {device.type === 'lock' && (
                <div className="flex gap-3">
                  <Button size="lg" onClick={() => cmdMutation.mutate({ cmd: 'lock' })} className={state.state === 'locked' ? 'bg-green-600' : ''}>
                    Замкнути
                  </Button>
                  <Button size="lg" variant="destructive" onClick={() => cmdMutation.mutate({ cmd: 'unlock' })}>
                    Відімкнути
                  </Button>
                </div>
              )}

              {device.type === 'cover' && (
                <>
                  <div className="flex gap-2">
                    <Button size="sm" onClick={() => cmdMutation.mutate({ cmd: 'open_cover' })}>Відкрити</Button>
                    <Button size="sm" variant="outline" onClick={() => cmdMutation.mutate({ cmd: 'stop_cover' })}>Стоп</Button>
                    <Button size="sm" onClick={() => cmdMutation.mutate({ cmd: 'close_cover' })}>Закрити</Button>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="text-sm font-medium w-20">Позиція</span>
                    <Slider value={state.position || 0} min={0} max={100} onChange={(v) => cmdMutation.mutate({ cmd: 'set_position', params: { position: v } })} className="flex-1" />
                    <span className="text-sm w-12">{state.position || 0}%</span>
                  </div>
                </>
              )}

              {device.type === 'media_player' && (
                <>
                  <div className="flex gap-2">
                    <Button size="sm" onClick={() => cmdMutation.mutate({ cmd: 'play' })}>Грати</Button>
                    <Button size="sm" variant="outline" onClick={() => cmdMutation.mutate({ cmd: 'pause' })}>Пауза</Button>
                    <Button size="sm" variant="outline" onClick={() => cmdMutation.mutate({ cmd: 'stop' })}>Стоп</Button>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="text-sm font-medium w-20">Гучність</span>
                    <Slider value={(state.volume_level || 0) * 100} min={0} max={100} onChange={(v) => cmdMutation.mutate({ cmd: 'set_volume', params: { volume_level: v / 100 } })} className="flex-1" />
                    <span className="text-sm w-12">{Math.round((state.volume_level || 0) * 100)}%</span>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Інспектор стану */}
        <TabsContent value="state">
          <Card>
            <CardHeader><CardTitle>Інспектор стану</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <pre className="p-4 bg-muted rounded-md text-xs overflow-auto">{JSON.stringify(state, null, 2)}</pre>
              <div>
                <p className="text-sm font-medium mb-2">Редактор стану (JSON)</p>
                <Textarea
                  value={rawState || JSON.stringify(state, null, 2)}
                  onChange={(e) => setRawState(e.target.value)}
                  rows={8}
                  className="font-mono text-xs"
                />
                <Button
                  size="sm"
                  className="mt-2"
                  onClick={() => {
                    try {
                      const parsed = JSON.parse(rawState);
                      stateMutation.mutate(parsed);
                    } catch {}
                  }}
                >
                  Застосувати стан
                </Button>
              </div>

              <div>
                <p className="text-sm font-medium mb-2">Конфігурація протоколу</p>
                <pre className="p-4 bg-muted rounded-md text-xs overflow-auto">{JSON.stringify(device.protocol_config, null, 2)}</pre>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Інспектор протоколу */}
        <TabsContent value="protocol">
          <Card>
            <CardHeader><CardTitle>Інспектор протоколу</CardTitle></CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-[500px] overflow-y-auto">
                {recentEvents.length === 0 && (
                  <p className="text-sm text-muted-foreground">Поки немає подій протоколу. Взаємодійте з пристроєм, щоб побачити повідомлення.</p>
                )}
                {recentEvents.map((event) => (
                  <div key={event.id} className={cn(
                    'p-2 rounded text-xs border-l-2',
                    event.direction === 'received' ? 'border-l-green-500 bg-green-50 dark:bg-green-950/20' : 'border-l-blue-500 bg-blue-50 dark:bg-blue-950/20'
                  )}>
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{event.direction === 'received' ? '\u2193 ВХІД' : '\u2191 ВИХІД'}</span>
                      <Badge variant="outline" className="text-[10px]">{safe(event.protocol)}</Badge>
                      <span className="text-muted-foreground ml-auto">{safe(event.timestamp) ? new Date(event.timestamp).toLocaleTimeString() : ''}</span>
                    </div>
                    {event.topic && <div className="mt-1 font-mono text-muted-foreground">{safe(event.topic)}</div>}
                    <div className="mt-1 font-mono break-all">{safe(event.payload)}</div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Історія */}
        <TabsContent value="history">
          <Card>
            <CardHeader><CardTitle>Історія змін стану</CardTitle></CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-[500px] overflow-y-auto">
                {history.map((h: any) => (
                  <div key={h.id} className="text-xs p-2 border-b">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{safe(h.event_type)}</span>
                      <span className="text-muted-foreground ml-auto">{safe(h.timestamp) ? new Date(h.timestamp).toLocaleString() : ''}</span>
                    </div>
                    <div className="mt-1 font-mono text-muted-foreground truncate">{safe(h.payload)}</div>
                  </div>
                ))}
                {history.length === 0 && <p className="text-sm text-muted-foreground">Поки немає історії</p>}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
