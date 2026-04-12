import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getImportSources, connectImportSource, executeImport } from '@/lib/api';
import { Button, Card, CardContent, CardHeader, CardTitle, Input, Label, Badge } from '@/components/ui';
import { safe } from '@/lib/utils';
import type { ImportSource, DiscoveredDevice, ImportConnectResponse } from '@/types';

const SOURCE_ICONS: Record<string, string> = {
  home_assistant: '\uD83C\uDFE0',
  philips_hue: '\uD83D\uDCA1',
  ikea: '\uD83E\uDEAA',
  mqtt: '\uD83D\uDD0C',
  tuya: '\u2601\uFE0F',
  smartthings: '\uD83D\uDCF1',
};

const DEVICE_ICONS: Record<string, string> = {
  light: '\uD83D\uDCA1', switch: '\uD83D\uDD0C', climate: '\uD83C\uDF21', sensor: '\uD83D\uDCE1',
  media_player: '\uD83C\uDFB5', lock: '\uD83D\uDD12', cover: '\uD83E\uDE9F', camera: '\uD83D\uDCF7',
  vacuum: '\uD83E\uDDF9', speaker: '\uD83D\uDD0A',
};

const AUTH_MESSAGES: Record<string, { connecting: string; searching: string; found: string }> = {
  home_assistant: {
    connecting: 'Підключення до Home Assistant...',
    searching: 'Отримання списку пристроїв та кімнат...',
    found: 'Підключено до Home Assistant!',
  },
  philips_hue: {
    connecting: 'Пошук Hue Bridge в мережі...',
    searching: 'Зчитування конфігурації ламп та груп...',
    found: 'Hue Bridge знайдено!',
  },
  ikea_tradfri: {
    connecting: 'Генерація PSK ключа...',
    searching: 'Отримання списку IKEA пристроїв...',
    found: 'IKEA Gateway підключено!',
  },
  mqtt_broker: {
    connecting: 'Підключення до MQTT брокера...',
    searching: 'Сканування активних топіків...',
    found: 'Брокер підключено, топіки знайдено!',
  },
  tuya: {
    connecting: 'Авторизація через Tuya Cloud...',
    searching: 'Отримання списку пристроїв з хмари...',
    found: 'Tuya Cloud підключено!',
  },
  smartthings: {
    connecting: 'Авторизація через Samsung Account...',
    searching: 'Завантаження пристроїв SmartThings...',
    found: 'SmartThings підключено!',
  },
};

export function Import() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: sources = [] } = useQuery({ queryKey: ['import-sources'], queryFn: getImportSources });

  const [step, setStep] = useState(1);
  const [selectedSource, setSelectedSource] = useState<ImportSource | null>(null);
  const [authData, setAuthData] = useState<Record<string, string>>({});
  const [connectResult, setConnectResult] = useState<ImportConnectResponse | null>(null);
  const [selectedDevices, setSelectedDevices] = useState<Set<string>>(new Set());
  const [connectPhase, setConnectPhase] = useState<'idle' | 'connecting' | 'searching' | 'found'>('idle');

  const localSources = sources.filter((s: ImportSource) => s.category === 'local');
  const cloudSources = sources.filter((s: ImportSource) => s.category === 'cloud');

  const connectMutation = useMutation({
    mutationFn: () => connectImportSource(selectedSource!.id, authData),
    onMutate: () => setConnectPhase('connecting'),
    onSuccess: (result) => {
      setConnectResult(result);
      setSelectedDevices(new Set(result.discovered_devices.map((d) => d.temp_id)));
      setConnectPhase('found');
      setTimeout(() => setStep(3), 800);
    },
    onError: () => setConnectPhase('idle'),
  });

  // Simulate progressive connection messages
  const startConnect = () => {
    setConnectPhase('connecting');
    setTimeout(() => setConnectPhase('searching'), 1200);
    connectMutation.mutate();
  };

  const executeMutation = useMutation({
    mutationFn: () => executeImport(connectResult!.session_id, Array.from(selectedDevices)),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['devices'] });
      setStep(5); // success
    },
  });

  const toggleDevice = (tempId: string) => {
    setSelectedDevices((prev) => {
      const next = new Set(prev);
      if (next.has(tempId)) next.delete(tempId);
      else next.add(tempId);
      return next;
    });
  };

  const toggleAll = () => {
    if (!connectResult) return;
    const all = connectResult.discovered_devices.map((d) => d.temp_id);
    if (selectedDevices.size === all.length) {
      setSelectedDevices(new Set());
    } else {
      setSelectedDevices(new Set(all));
    }
  };

  // Group discovered devices by room
  const devicesByRoom = useMemo(() => {
    if (!connectResult) return {};
    const groups: Record<string, DiscoveredDevice[]> = {};
    for (const d of connectResult.discovered_devices) {
      const room = d.room || 'Без кімнати';
      if (!groups[room]) groups[room] = [];
      groups[room].push(d);
    }
    return groups;
  }, [connectResult]);

  const msgs = selectedSource ? AUTH_MESSAGES[selectedSource.id] || AUTH_MESSAGES.home_assistant : AUTH_MESSAGES.home_assistant;

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Імпорт пристроїв</h1>

      {/* Степпер */}
      <div className="flex items-center gap-2 mb-6">
        {['Система', 'Підключення', 'Пристрої', 'Імпорт'].map((label, i) => (
          <div key={i} className="flex items-center gap-2">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-colors ${
              i + 1 <= step ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'
            }`}>
              {i + 1 < step ? '\u2713' : i + 1}
            </div>
            <span className={`text-xs hidden sm:inline ${i + 1 <= step ? 'text-foreground' : 'text-muted-foreground'}`}>{label}</span>
            {i < 3 && <div className="w-6 h-0.5 bg-muted" />}
          </div>
        ))}
      </div>

      {/* Крок 1: Вибір системи */}
      {step === 1 && (
        <div className="space-y-6">
          <Card>
            <CardHeader><CardTitle>Локальні системи</CardTitle></CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {localSources.map((src: ImportSource) => (
                  <button
                    key={src.id}
                    onClick={() => {
                      setSelectedSource(src);
                      const defaults: Record<string, string> = {};
                      src.auth_fields.forEach((f) => { if (f.default_value) defaults[f.name] = f.default_value; });
                      setAuthData(defaults);
                      setStep(2);
                    }}
                    className="p-4 rounded-lg border text-left hover:bg-accent hover:border-primary transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-2xl">{SOURCE_ICONS[src.icon] || '\uD83D\uDD0C'}</span>
                      <div className="flex-1">
                        <div className="font-semibold">{safe(src.name)}</div>
                        <div className="text-xs text-muted-foreground">{safe(src.description)}</div>
                        <div className="text-xs text-blue-600 dark:text-blue-400 mt-1">{safe(src.what_imports)}</div>
                      </div>
                      <Badge variant="outline" className="text-[10px] shrink-0">{safe(src.auth_type)}</Badge>
                    </div>
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Хмарні системи</CardTitle></CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {cloudSources.map((src: ImportSource) => (
                  <button
                    key={src.id}
                    onClick={() => {
                      setSelectedSource(src);
                      setAuthData({});
                      setStep(2);
                    }}
                    className="p-4 rounded-lg border text-left hover:bg-accent hover:border-primary transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-2xl">{SOURCE_ICONS[src.icon] || '\u2601\uFE0F'}</span>
                      <div className="flex-1">
                        <div className="font-semibold">{safe(src.name)}</div>
                        <div className="text-xs text-muted-foreground">{safe(src.description)}</div>
                        <div className="text-xs text-blue-600 dark:text-blue-400 mt-1">{safe(src.what_imports)}</div>
                      </div>
                      <Badge variant="outline" className="text-[10px] shrink-0">{safe(src.auth_type)}</Badge>
                    </div>
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Крок 2: Підключення */}
      {step === 2 && selectedSource && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <span className="text-2xl">{SOURCE_ICONS[selectedSource.icon] || ''}</span>
              Підключення до {selectedSource.name}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Auth fields for credential-based sources */}
            {selectedSource.auth_fields.length > 0 && (
              <div className="space-y-3">
                {selectedSource.auth_fields.map((field) => (
                  <div key={field.name}>
                    <Label>{safe(field.label)} {field.required && <span className="text-destructive">*</span>}</Label>
                    <Input
                      type={field.type === 'password' ? 'password' : 'text'}
                      value={authData[field.name] || ''}
                      onChange={(e) => setAuthData({ ...authData, [field.name]: e.target.value })}
                      placeholder={field.placeholder}
                      className="mt-1"
                    />
                  </div>
                ))}
              </div>
            )}

            {/* Hue: button press simulation */}
            {selectedSource.auth_type === 'button_press' && connectPhase === 'idle' && (
              <div className="text-center py-8">
                <div className="w-24 h-24 mx-auto rounded-full border-4 border-primary flex items-center justify-center mb-4 animate-pulse">
                  <span className="text-4xl">\uD83D\uDCA1</span>
                </div>
                <p className="text-sm text-muted-foreground">Натисніть кнопку на мосту Hue Bridge,</p>
                <p className="text-sm text-muted-foreground">потім натисніть "Підключити" нижче</p>
              </div>
            )}

            {/* IKEA: PSK generation */}
            {selectedSource.auth_type === 'psk' && connectPhase === 'idle' && (
              <div className="text-center py-6">
                <p className="text-sm text-muted-foreground mb-2">PSK ключ буде згенеровано автоматично</p>
                <p className="text-xs text-muted-foreground">Переконайтесь, що IKEA Gateway увімкнено та в одній мережі</p>
              </div>
            )}

            {/* Tuya: QR code simulation */}
            {selectedSource.id === 'tuya' && connectPhase === 'idle' && (
              <div className="text-center py-6">
                <div className="w-48 h-48 mx-auto border-2 border-dashed rounded-lg flex items-center justify-center mb-4 bg-muted/30">
                  <div className="text-center">
                    <div className="text-4xl mb-2">QR</div>
                    <p className="text-xs text-muted-foreground">Скануйте QR-код<br />в додатку Tuya Smart</p>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground">Або натисніть "Підключити" для імітації</p>
              </div>
            )}

            {/* SmartThings: OAuth redirect */}
            {selectedSource.id === 'smartthings' && connectPhase === 'idle' && (
              <div className="text-center py-6">
                <p className="text-sm mb-4">Авторизація через Samsung Account</p>
                <div className="p-4 bg-muted rounded-lg inline-block">
                  <p className="text-xs text-muted-foreground">Ви будете перенаправлені на</p>
                  <p className="text-sm font-mono">account.samsung.com</p>
                </div>
              </div>
            )}

            {/* Connection progress */}
            {connectPhase !== 'idle' && (
              <div className="text-center py-6 space-y-3">
                {connectPhase === 'connecting' && (
                  <>
                    <div className="w-8 h-8 mx-auto border-2 border-primary border-t-transparent rounded-full animate-spin" />
                    <p className="text-sm">{msgs.connecting}</p>
                  </>
                )}
                {connectPhase === 'searching' && (
                  <>
                    <div className="w-8 h-8 mx-auto border-2 border-primary border-t-transparent rounded-full animate-spin" />
                    <p className="text-sm">{msgs.searching}</p>
                  </>
                )}
                {connectPhase === 'found' && (
                  <>
                    <div className="w-12 h-12 mx-auto rounded-full bg-green-100 dark:bg-green-900 flex items-center justify-center">
                      <span className="text-green-600 text-xl">\u2713</span>
                    </div>
                    <p className="text-sm font-medium text-green-600">{msgs.found}</p>
                    {connectResult && (
                      <p className="text-xs text-muted-foreground">
                        Знайдено {connectResult.discovered_devices.length} пристроїв
                      </p>
                    )}
                  </>
                )}
              </div>
            )}

            <div className="flex gap-3">
              <Button variant="outline" onClick={() => { setStep(1); setConnectPhase('idle'); }}>Назад</Button>
              {connectPhase === 'idle' && (
                <Button className="flex-1" onClick={startConnect} disabled={connectMutation.isPending}>
                  Підключити
                </Button>
              )}
            </div>
            {connectMutation.isError && (
              <p className="text-destructive text-sm">{(connectMutation.error as Error).message}</p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Крок 3: Перегляд знайдених пристроїв */}
      {step === 3 && connectResult && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Знайдені пристрої</CardTitle>
              <Badge>{selectedDevices.size} з {connectResult.discovered_devices.length} обрано</Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* System info */}
            <div className="p-3 bg-muted/50 rounded-lg text-xs grid grid-cols-2 sm:grid-cols-4 gap-2">
              {Object.entries(connectResult.system_info).map(([k, v]) => (
                <div key={k}>
                  <span className="text-muted-foreground">{safe(k)}: </span>
                  <span className="font-medium">{safe(v)}</span>
                </div>
              ))}
            </div>

            {/* Select all */}
            <div className="flex items-center gap-2">
              <button
                onClick={toggleAll}
                className="h-4 w-4 rounded border border-primary flex items-center justify-center text-[10px]"
              >
                {selectedDevices.size === connectResult.discovered_devices.length ? '\u2713' : ''}
              </button>
              <span className="text-sm cursor-pointer" onClick={toggleAll}>
                {selectedDevices.size === connectResult.discovered_devices.length ? 'Зняти всі' : 'Обрати всі'}
              </span>
            </div>

            {/* Devices grouped by room */}
            <div className="space-y-4 max-h-[400px] overflow-y-auto">
              {Object.entries(devicesByRoom).map(([room, devices]) => (
                <div key={room}>
                  <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">{safe(room)}</h4>
                  <div className="space-y-1">
                    {devices.map((dev) => (
                      <div
                        key={dev.temp_id}
                        onClick={() => toggleDevice(dev.temp_id)}
                        className={`flex items-center gap-3 p-2 rounded-lg cursor-pointer transition-colors ${
                          selectedDevices.has(dev.temp_id) ? 'bg-primary/10 border border-primary/30' : 'bg-muted/30 hover:bg-muted/60'
                        }`}
                      >
                        <button className="h-4 w-4 rounded border border-primary flex items-center justify-center text-[10px] shrink-0">
                          {selectedDevices.has(dev.temp_id) ? '\u2713' : ''}
                        </button>
                        <span className="text-lg">{DEVICE_ICONS[dev.type] || '\uD83D\uDCE6'}</span>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium truncate">{safe(dev.name)}</div>
                          <div className="text-[10px] text-muted-foreground">
                            {safe(dev.manufacturer)} {safe(dev.model)} | {safe(dev.protocol)}
                          </div>
                        </div>
                        <Badge variant="outline" className="text-[10px] shrink-0">{safe(dev.type)}</Badge>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            <div className="flex gap-3">
              <Button variant="outline" onClick={() => setStep(2)}>Назад</Button>
              <Button className="flex-1" onClick={() => setStep(4)} disabled={selectedDevices.size === 0}>
                Далі: Імпорт {selectedDevices.size} пристроїв
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Крок 4: Підтвердження та імпорт */}
      {step === 4 && connectResult && (
        <Card>
          <CardHeader><CardTitle>Імпорт пристроїв</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="p-4 bg-muted/30 rounded-lg">
              <div className="text-sm">
                <strong>Джерело:</strong> {selectedSource?.name}
              </div>
              <div className="text-sm mt-1">
                <strong>Пристроїв для імпорту:</strong> {selectedDevices.size}
              </div>
              <div className="text-sm mt-1">
                <strong>Кімнати:</strong> {Object.keys(devicesByRoom).join(', ')}
              </div>
            </div>

            <div className="text-xs text-muted-foreground">
              Кожен пристрій буде створений у SDS з правильними протоколами та конфігурацією.
              Після імпорту Selena зможе виявити та керувати ними.
            </div>

            {executeMutation.isPending && (
              <div className="text-center py-4">
                <div className="w-8 h-8 mx-auto border-2 border-primary border-t-transparent rounded-full animate-spin mb-2" />
                <p className="text-sm">Створення пристроїв...</p>
              </div>
            )}

            <div className="flex gap-3">
              <Button variant="outline" onClick={() => setStep(3)} disabled={executeMutation.isPending}>Назад</Button>
              <Button className="flex-1" onClick={() => executeMutation.mutate()} disabled={executeMutation.isPending}>
                {executeMutation.isPending ? 'Імпортування...' : `Імпортувати ${selectedDevices.size} пристроїв`}
              </Button>
            </div>
            {executeMutation.isError && (
              <p className="text-destructive text-sm">{(executeMutation.error as Error).message}</p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Крок 5: Успіх */}
      {step === 5 && (
        <Card>
          <CardContent className="py-12 text-center space-y-4">
            <div className="w-16 h-16 mx-auto rounded-full bg-green-100 dark:bg-green-900 flex items-center justify-center">
              <span className="text-green-600 text-3xl">\u2713</span>
            </div>
            <h2 className="text-xl font-bold">Імпорт завершено!</h2>
            <p className="text-muted-foreground">
              Створено {selectedDevices.size} пристроїв з {selectedSource?.name}.
              <br />Вони вже доступні через відповідні протоколи.
            </p>
            <div className="flex gap-3 justify-center pt-4">
              <Button variant="outline" onClick={() => { setStep(1); setConnectResult(null); setConnectPhase('idle'); }}>
                Імпортувати ще
              </Button>
              <Button onClick={() => navigate('/')}>
                Перейти до пристроїв
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
