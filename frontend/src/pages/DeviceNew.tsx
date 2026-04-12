import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createDevice, getTemplates } from '@/lib/api';
import { Button, Card, CardContent, CardHeader, CardTitle, Input, Label, Select, Badge } from '@/components/ui';
import type { DeviceType, DeviceCreate } from '@/types';

const DEVICE_TYPES: { value: DeviceType; label: string; icon: string; desc: string }[] = [
  { value: 'light', label: 'Лампа', icon: '\uD83D\uDCA1', desc: 'RGB, діммер, стрічка' },
  { value: 'switch', label: 'Розетка / Вимикач', icon: '\uD83D\uDD0C', desc: 'Реле, smart plug' },
  { value: 'climate', label: 'Термостат', icon: '\uD83C\uDF21', desc: 'Клімат-контроль' },
  { value: 'sensor', label: 'Датчик', icon: '\uD83D\uDCE1', desc: 'Рух, двері, температура' },
  { value: 'vacuum', label: 'Пилосос', icon: '\uD83E\uDDF9', desc: 'Roborock, Xiaomi' },
  { value: 'media_player', label: 'Медіаплеєр', icon: '\uD83C\uDFB5', desc: 'Колонка, ТВ' },
  { value: 'lock', label: 'Замок', icon: '\uD83D\uDD12', desc: 'Smart lock' },
  { value: 'cover', label: 'Штори / Жалюзі', icon: '\uD83E\uDE9F', desc: 'Рулонні, вертикальні' },
  { value: 'camera', label: 'Камера', icon: '\uD83D\uDCF7', desc: 'IP камера' },
  { value: 'speaker', label: 'Колонка', icon: '\uD83D\uDD0A', desc: 'Голосовий асистент' },
];

const SENSOR_SUBTYPES = [
  { value: 'temperature_humidity', label: 'Температура / Вологість' },
  { value: 'motion', label: 'Рух (PIR)' },
  { value: 'door_window', label: 'Двері / Вікно' },
  { value: 'smoke', label: 'Дим' },
  { value: 'water_leak', label: 'Протікання води' },
  { value: 'illuminance', label: 'Освітленість' },
];

const PROTOCOL_INFO: Record<string, { label: string; desc: string; port: string; how: string }> = {
  zigbee2mqtt: {
    label: 'Zigbee2MQTT',
    desc: 'Zigbee пристрої через Z2M шлюз',
    port: 'MQTT 1883',
    how: 'Selena підписується на zigbee2mqtt/bridge/devices для виявлення, відправляє команди в zigbee2mqtt/<friendly_name>/set',
  },
  mqtt: {
    label: 'MQTT (Tasmota/Shelly/Generic)',
    desc: 'Будь-які MQTT пристрої',
    port: 'MQTT 1883',
    how: 'Selena підписується на топіки стану і відправляє команди в командні топіки',
  },
  http_hue: {
    label: 'Philips Hue API',
    desc: 'Емуляція Hue Bridge',
    port: 'HTTP 7000',
    how: 'Selena звертається до GET/PUT /api/<token>/lights/<id>/state',
  },
  http_lifx: {
    label: 'LIFX HTTP API',
    desc: 'Емуляція LIFX Cloud API',
    port: 'HTTP 7000',
    how: 'Selena звертається до GET/PUT /v1/lights/<id>/state',
  },
  http: {
    label: 'Generic HTTP REST',
    desc: 'Довільний HTTP REST пристрій',
    port: 'HTTP 7000',
    how: 'Selena звертається до GET /devices/<id>/state, POST /devices/<id>/command',
  },
  miio: {
    label: 'Xiaomi miio',
    desc: 'Xiaomi LAN протокол (UDP)',
    port: 'UDP 54321',
    how: 'Selena відправляє зашифровані UDP пакети з командами (get_prop, set_power, app_start...)',
  },
  ha_websocket: {
    label: 'Home Assistant WS API',
    desc: 'WebSocket API в стилі HA',
    port: 'WS 8123',
    how: 'Selena підключається через ws://<host>:8123, автентифікується токеном, підписується на state_changed',
  },
};

const MQTT_SCHEMES = [
  { value: 'tasmota', label: 'Tasmota', desc: 'cmnd/<name>/POWER, stat/<name>/POWER' },
  { value: 'shelly', label: 'Shelly', desc: 'shellies/<name>/relay/0/command' },
  { value: 'generic', label: 'Generic', desc: '<base_topic>, <base_topic>/set' },
];

export function DeviceNew() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: templates = {} } = useQuery({ queryKey: ['templates'], queryFn: getTemplates });

  const [step, setStep] = useState(1);
  const [deviceType, setDeviceType] = useState<DeviceType>('light');
  const [sensorSubtype, setSensorSubtype] = useState('temperature_humidity');
  const [protocol, setProtocol] = useState('');
  const [mqttScheme, setMqttScheme] = useState('tasmota');
  const [name, setName] = useState('');
  const [room, setRoom] = useState('');
  const [friendlyName, setFriendlyName] = useState('');
  const [manufacturer, setManufacturer] = useState('');
  const [modelId, setModelId] = useState('');
  const [token, setToken] = useState('ffffffffffffffffffffffffffffffff');
  const [baseTopic, setBaseTopic] = useState('');

  const template = templates[deviceType];
  const supportedProtocols = template?.supported_protocols || [];
  const protoInfo = PROTOCOL_INFO[protocol] || {};

  const autoFriendlyName = friendlyName || name.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');

  // Генерація топіків для прев'ю
  const getTopicsPreview = () => {
    const fn = autoFriendlyName || 'device_name';
    if (protocol === 'zigbee2mqtt') {
      return [
        { label: 'Стан (retained)', topic: `zigbee2mqtt/${fn}` },
        { label: 'Команди', topic: `zigbee2mqtt/${fn}/set` },
        { label: 'Запит стану', topic: `zigbee2mqtt/${fn}/get` },
        { label: 'Виявлення', topic: 'zigbee2mqtt/bridge/devices' },
      ];
    }
    if (protocol === 'mqtt') {
      const dn = autoFriendlyName || 'device';
      if (mqttScheme === 'tasmota') return [
        { label: 'Стан', topic: `stat/${dn}/POWER` },
        { label: 'Телеметрія', topic: `tele/${dn}/STATE` },
        { label: 'Команди', topic: `cmnd/${dn}/POWER` },
      ];
      if (mqttScheme === 'shelly') return [
        { label: 'Стан', topic: `shellies/${dn}/relay/0` },
        { label: 'Команди', topic: `shellies/${dn}/relay/0/command` },
      ];
      const bt = baseTopic || `sds/${dn}`;
      return [
        { label: 'Стан (retained)', topic: bt },
        { label: 'Команди', topic: `${bt}/set` },
      ];
    }
    if (protocol === 'http_hue') return [
      { label: 'Список ламп', topic: 'GET /api/<token>/lights' },
      { label: 'Стан лампи', topic: 'GET /api/<token>/lights/<id>' },
      { label: 'Змінити стан', topic: 'PUT /api/<token>/lights/<id>/state' },
    ];
    if (protocol === 'http_lifx') return [
      { label: 'Список', topic: 'GET /v1/lights' },
      { label: 'Змінити стан', topic: 'PUT /v1/lights/<id>/state' },
      { label: 'Перемкнути', topic: 'POST /v1/lights/<id>/toggle' },
    ];
    if (protocol === 'http') return [
      { label: 'Стан', topic: `GET /devices/<id>/state` },
      { label: 'Команда', topic: `POST /devices/<id>/command` },
    ];
    if (protocol === 'miio') return [
      { label: 'Протокол', topic: 'UDP 54321, AES-128-CBC' },
      { label: 'Hello', topic: 'Handshake packet (32 bytes)' },
      { label: 'Команди', topic: 'get_prop, set_power, set_bright...' },
    ];
    if (protocol === 'ha_websocket') return [
      { label: 'Підключення', topic: 'ws://<host>:8123' },
      { label: 'Токен', topic: 'test_token_for_selena' },
      { label: 'Entity ID', topic: `${deviceType}.${autoFriendlyName || 'device'}` },
    ];
    return [];
  };

  const mutation = useMutation({
    mutationFn: (data: DeviceCreate) => createDevice(data),
    onSuccess: (device) => {
      queryClient.invalidateQueries({ queryKey: ['devices'] });
      navigate(`/devices/${device.id}`);
    },
  });

  const handleCreate = () => {
    const fn = autoFriendlyName;
    let defaultState = { ...(template?.default_state || {}) };
    if (deviceType === 'sensor' && template?.subtypes?.[sensorSubtype]) {
      defaultState = { ...template.subtypes[sensorSubtype].default_state };
    }

    const protocolConfig: Record<string, any> = {
      friendly_name: fn,
      manufacturer: manufacturer || 'SDS Simulator',
      model_id: modelId || 'SDS_Virtual',
    };

    if (protocol === 'mqtt') {
      protocolConfig.topic_scheme = mqttScheme;
      protocolConfig.device_name = fn;
      if (mqttScheme === 'generic' && baseTopic) {
        protocolConfig.base_topic = baseTopic;
      }
    }
    if (protocol === 'miio') protocolConfig.token = token;

    let caps = template?.capabilities || [];
    if (deviceType === 'sensor' && template?.subtypes?.[sensorSubtype]) {
      caps = template.subtypes[sensorSubtype].capabilities;
    }

    mutation.mutate({
      name, type: deviceType,
      protocol: protocol || supportedProtocols[0] || 'mqtt',
      protocol_config: protocolConfig,
      state: defaultState, capabilities: caps,
      room, icon: template?.icon || '',
      auto_report_interval: 60,
    });
  };

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Додати новий пристрій</h1>

      {/* Степпер */}
      <div className="flex items-center gap-2 mb-6">
        {['Тип', 'Протокол', 'Параметри', 'Створити'].map((label, i) => (
          <div key={i} className="flex items-center gap-2">
            <button
              onClick={() => i + 1 < step && setStep(i + 1)}
              className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-colors ${
                i + 1 <= step ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'
              }`}
            >
              {i + 1}
            </button>
            <span className={`text-xs hidden sm:inline ${i + 1 <= step ? 'text-foreground' : 'text-muted-foreground'}`}>{label}</span>
            {i < 3 && <div className="w-6 h-0.5 bg-muted" />}
          </div>
        ))}
      </div>

      {/* Крок 1: Тип */}
      {step === 1 && (
        <Card>
          <CardHeader><CardTitle>1. Оберіть тип пристрою</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {DEVICE_TYPES.map((dt) => (
                <button
                  key={dt.value}
                  onClick={() => { setDeviceType(dt.value); setProtocol(''); }}
                  className={`p-4 rounded-lg border text-center transition-colors ${
                    deviceType === dt.value ? 'border-primary bg-primary/10 ring-2 ring-primary' : 'border-border hover:bg-accent'
                  }`}
                >
                  <div className="text-2xl">{dt.icon}</div>
                  <div className="text-sm font-medium mt-1">{dt.label}</div>
                  <div className="text-[10px] text-muted-foreground">{dt.desc}</div>
                </button>
              ))}
            </div>
            {deviceType === 'sensor' && (
              <div className="mt-4">
                <Label>Підтип датчика</Label>
                <Select value={sensorSubtype} onValueChange={setSensorSubtype} options={SENSOR_SUBTYPES} className="mt-1" />
              </div>
            )}
            <Button className="mt-6 w-full" onClick={() => setStep(2)}>Далі</Button>
          </CardContent>
        </Card>
      )}

      {/* Крок 2: Протокол */}
      {step === 2 && (
        <Card>
          <CardHeader><CardTitle>2. Оберіть протокол підключення</CardTitle></CardHeader>
          <CardContent>
            <div className="space-y-3">
              {supportedProtocols.map((p: string) => {
                const info = PROTOCOL_INFO[p] || { label: p, desc: '', port: '', how: '' };
                return (
                  <button
                    key={p}
                    onClick={() => setProtocol(p)}
                    className={`w-full p-4 rounded-lg border text-left transition-colors ${
                      protocol === p ? 'border-primary bg-primary/10 ring-2 ring-primary' : 'border-border hover:bg-accent'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-semibold">{info.label}</span>
                      <Badge variant="outline" className="text-[10px]">{info.port}</Badge>
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">{info.desc}</div>
                    <div className="text-xs text-blue-600 dark:text-blue-400 mt-1">{info.how}</div>
                  </button>
                );
              })}
            </div>
            <div className="flex gap-3 mt-6">
              <Button variant="outline" onClick={() => setStep(1)}>Назад</Button>
              <Button className="flex-1" onClick={() => setStep(3)} disabled={!protocol}>Далі</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Крок 3: Параметри */}
      {step === 3 && (
        <Card>
          <CardHeader><CardTitle>3. Параметри пристрою</CardTitle></CardHeader>
          <CardContent className="space-y-5">
            {/* Основні */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Назва пристрою *</Label>
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Лампа у вітальні" className="mt-1" />
              </div>
              <div>
                <Label>Кімната</Label>
                <Input value={room} onChange={(e) => setRoom(e.target.value)} placeholder="Вітальня" className="mt-1" />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Виробник</Label>
                <Input value={manufacturer} onChange={(e) => setManufacturer(e.target.value)} placeholder="IKEA, Aqara, TuYa..." className="mt-1" />
              </div>
              <div>
                <Label>Модель</Label>
                <Input value={modelId} onChange={(e) => setModelId(e.target.value)} placeholder="LED1545G12" className="mt-1" />
              </div>
            </div>

            {/* Параметри протоколу */}
            <div className="border rounded-lg p-4 bg-muted/30">
              <h4 className="font-semibold text-sm mb-3 flex items-center gap-2">
                Параметри протоколу: <Badge>{protoInfo.label || protocol}</Badge>
              </h4>

              {/* Z2M */}
              {protocol === 'zigbee2mqtt' && (
                <div className="space-y-3">
                  <div>
                    <Label>Friendly Name <span className="text-muted-foreground font-normal">(ідентифікатор в Z2M)</span></Label>
                    <Input value={friendlyName} onChange={(e) => setFriendlyName(e.target.value)}
                      placeholder={autoFriendlyName || 'living_room_light'} className="mt-1 font-mono text-sm" />
                    <p className="text-[11px] text-muted-foreground mt-1">Це ім'я буде в MQTT топіках: zigbee2mqtt/<span className="font-semibold">{autoFriendlyName || '...'}</span>/set</p>
                  </div>
                </div>
              )}

              {/* MQTT */}
              {protocol === 'mqtt' && (
                <div className="space-y-3">
                  <div>
                    <Label>Схема топіків</Label>
                    <div className="grid grid-cols-3 gap-2 mt-1">
                      {MQTT_SCHEMES.map((s) => (
                        <button key={s.value} onClick={() => setMqttScheme(s.value)}
                          className={`p-2 rounded border text-left text-xs ${mqttScheme === s.value ? 'border-primary bg-primary/10' : 'border-border'}`}>
                          <div className="font-semibold">{s.label}</div>
                          <div className="text-muted-foreground text-[10px] mt-0.5">{s.desc}</div>
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <Label>Ім'я пристрою <span className="text-muted-foreground font-normal">(для топіків)</span></Label>
                    <Input value={friendlyName} onChange={(e) => setFriendlyName(e.target.value)}
                      placeholder={autoFriendlyName || 'kitchen_plug'} className="mt-1 font-mono text-sm" />
                  </div>
                  {mqttScheme === 'generic' && (
                    <div>
                      <Label>Базовий топік</Label>
                      <Input value={baseTopic} onChange={(e) => setBaseTopic(e.target.value)}
                        placeholder={`sensors/${autoFriendlyName || 'device'}`} className="mt-1 font-mono text-sm" />
                    </div>
                  )}
                </div>
              )}

              {/* Hue / LIFX */}
              {(protocol === 'http_hue' || protocol === 'http_lifx') && (
                <div className="space-y-2">
                  <p className="text-xs text-muted-foreground">HTTP пристрій автоматично отримає ID. Додаткових параметрів не потрібно.</p>
                  <p className="text-xs">Хост API: <code className="bg-muted px-1 rounded">http://&lt;SDS_IP&gt;:7000</code></p>
                </div>
              )}

              {/* Generic HTTP */}
              {protocol === 'http' && (
                <div className="space-y-2">
                  <p className="text-xs text-muted-foreground">Ендпоінти створяться автоматично по ID пристрою.</p>
                </div>
              )}

              {/* miio */}
              {protocol === 'miio' && (
                <div className="space-y-3">
                  <div>
                    <Label>Токен пристрою <span className="text-muted-foreground font-normal">(32 hex символи, 16 байт)</span></Label>
                    <Input value={token} onChange={(e) => setToken(e.target.value)}
                      placeholder="ffffffffffffffffffffffffffffffff" className="mt-1 font-mono text-sm" />
                    <p className="text-[11px] text-muted-foreground mt-1">Використовується для AES-128-CBC шифрування. В реальному пристрої отримується через Mi Home app.</p>
                  </div>
                  <p className="text-xs">UDP порт: <code className="bg-muted px-1 rounded">54321</code></p>
                </div>
              )}

              {/* HA WebSocket */}
              {protocol === 'ha_websocket' && (
                <div className="space-y-3">
                  <div>
                    <Label>Friendly Name <span className="text-muted-foreground font-normal">(для entity_id)</span></Label>
                    <Input value={friendlyName} onChange={(e) => setFriendlyName(e.target.value)}
                      placeholder={autoFriendlyName || 'device_name'} className="mt-1 font-mono text-sm" />
                    <p className="text-[11px] text-muted-foreground mt-1">
                      Entity ID: <code className="bg-muted px-1 rounded">{deviceType}.{autoFriendlyName || '...'}</code>
                    </p>
                  </div>
                  <div className="text-xs space-y-1">
                    <p>WebSocket: <code className="bg-muted px-1 rounded">ws://&lt;SDS_IP&gt;:8123</code></p>
                    <p>Токен: <code className="bg-muted px-1 rounded">test_token_for_selena</code></p>
                  </div>
                </div>
              )}
            </div>

            {/* Прев'ю топіків/ендпоінтів */}
            {name && (
              <div className="border rounded-lg p-4 bg-blue-50 dark:bg-blue-950/20">
                <h4 className="font-semibold text-sm mb-2">Як Selena буде взаємодіяти з цим пристроєм:</h4>
                <div className="space-y-1.5">
                  {getTopicsPreview().map((t, i) => (
                    <div key={i} className="flex items-baseline gap-2 text-xs">
                      <span className="text-muted-foreground w-28 shrink-0">{t.label}:</span>
                      <code className="bg-background px-1.5 py-0.5 rounded border font-mono text-[11px] break-all">{t.topic}</code>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="flex gap-3">
              <Button variant="outline" onClick={() => setStep(2)}>Назад</Button>
              <Button className="flex-1" onClick={() => setStep(4)} disabled={!name}>Далі: Перегляд</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Крок 4: Перегляд */}
      {step === 4 && (
        <Card>
          <CardHeader><CardTitle>4. Перевірте та створіть</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              <div className="text-muted-foreground">Назва:</div><div className="font-medium">{name}</div>
              <div className="text-muted-foreground">Тип:</div><div className="font-medium">{DEVICE_TYPES.find(d => d.value === deviceType)?.label}</div>
              <div className="text-muted-foreground">Протокол:</div><div className="font-medium">{protoInfo.label || protocol}</div>
              <div className="text-muted-foreground">Кімната:</div><div className="font-medium">{room || '—'}</div>
              <div className="text-muted-foreground">Виробник:</div><div className="font-medium">{manufacturer || 'SDS Simulator'}</div>
              <div className="text-muted-foreground">Модель:</div><div className="font-medium">{modelId || 'SDS_Virtual'}</div>
              {protocol === 'miio' && (<><div className="text-muted-foreground">Токен:</div><div className="font-mono text-xs break-all">{token}</div></>)}
            </div>

            <div className="border rounded-lg p-3 bg-muted/30">
              <h4 className="text-xs font-semibold mb-2">Параметри підключення для Selena:</h4>
              <div className="space-y-1">
                {getTopicsPreview().map((t, i) => (
                  <div key={i} className="flex items-baseline gap-2 text-xs">
                    <span className="text-muted-foreground w-28 shrink-0">{t.label}:</span>
                    <code className="font-mono text-[11px]">{t.topic}</code>
                  </div>
                ))}
              </div>
            </div>

            <div className="p-3 bg-muted rounded-md">
              <div className="text-xs font-medium mb-1">Початковий стан:</div>
              <pre className="text-[11px] overflow-auto">{JSON.stringify(
                deviceType === 'sensor' && template?.subtypes?.[sensorSubtype]
                  ? template.subtypes[sensorSubtype].default_state
                  : template?.default_state || {},
                null, 2
              )}</pre>
            </div>

            <div className="flex gap-3">
              <Button variant="outline" onClick={() => setStep(3)}>Назад</Button>
              <Button className="flex-1" onClick={handleCreate} disabled={mutation.isPending}>
                {mutation.isPending ? 'Створення...' : 'Створити пристрій'}
              </Button>
            </div>
            {mutation.isError && (
              <p className="text-destructive text-sm">{(mutation.error as Error).message}</p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
