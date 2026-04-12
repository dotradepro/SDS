import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useStore } from '@/lib/store';
import { getHealth } from '@/lib/api';
import { Button, Card, CardContent, CardHeader, CardTitle, Input, Label, Switch, Badge } from '@/components/ui';

export function Settings() {
  const navigate = useNavigate();
  const { theme, toggleTheme } = useStore();
  const { data: health } = useQuery({ queryKey: ['health'], queryFn: getHealth, refetchInterval: 10000 });

  const host = typeof window !== 'undefined' ? window.location.hostname : 'localhost';

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold">Налаштування</h1>

      <Card>
        <CardHeader><CardTitle>Зовнішній вигляд</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <Label>Темна тема</Label>
              <p className="text-sm text-muted-foreground">Перемикання темної/світлої теми</p>
            </div>
            <Switch checked={theme === 'dark'} onCheckedChange={toggleTheme} />
          </div>
        </CardContent>
      </Card>

      {/* Connection info for Selena */}
      <Card className="border-blue-200 dark:border-blue-900 bg-blue-50/50 dark:bg-blue-950/20">
        <CardHeader>
          <CardTitle>Параметри підключення для Selena</CardTitle>
          <p className="text-sm text-muted-foreground">Використовуйте ці адреси для імпорту пристроїв у Selena</p>
        </CardHeader>
        <CardContent className="space-y-5">
          {/* HA WebSocket */}
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Label className="font-semibold">Home Assistant</Label>
              {health?.protocols?.ha_websocket && (
                <Badge variant={health.protocols.ha_websocket.status === 'connected' ? 'default' : 'destructive'}>
                  {health.protocols.ha_websocket.status === 'connected' ? 'активний' : 'помилка'}
                </Badge>
              )}
            </div>
            <div className="grid grid-cols-[100px_1fr] gap-2 text-sm">
              <span className="text-muted-foreground">WebSocket:</span>
              <code className="bg-background px-2 py-1 rounded border font-mono text-xs select-all">ws://{host}:8123</code>
              <span className="text-muted-foreground">Токен:</span>
              <code className="bg-background px-2 py-1 rounded border font-mono text-xs select-all">будь-який (приймається автоматично)</code>
            </div>
            <p className="text-xs text-muted-foreground">Selena підключається як до Home Assistant. Будь-який access_token буде прийнято. В��ддає get_states з усіма пристроями.</p>
          </div>

          <div className="border-t" />

          {/* Philips Hue */}
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Label className="font-semibold">Philips Hue Bridge</Label>
              <Badge variant="default">активний</Badge>
            </div>
            <div className="grid grid-cols-[100px_1fr] gap-2 text-sm">
              <span className="text-muted-foreground">API URL:</span>
              <code className="bg-background px-2 py-1 rounded border font-mono text-xs select-all">http://{host}:7000/api</code>
              <span className="text-muted-foreground">Реєстрація:</span>
              <code className="bg-background px-2 py-1 rounded border font-mono text-xs select-all">POST /api {'\u2192'} отримати username</code>
              <span className="text-muted-foreground">Лампи:</span>
              <code className="bg-background px-2 py-1 rounded border font-mono text-xs select-all">GET /api/&lt;token&gt;/lights</code>
            </div>
            <p className="text-xs text-muted-foreground">Будь-який токен приймається. POST /api створює нового "користувача" і повертає токен.</p>
          </div>

          <div className="border-t" />

          {/* LIFX */}
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Label className="font-semibold">LIFX API</Label>
              <Badge variant="default">активний</Badge>
            </div>
            <div className="grid grid-cols-[100px_1fr] gap-2 text-sm">
              <span className="text-muted-foreground">API URL:</span>
              <code className="bg-background px-2 py-1 rounded border font-mono text-xs select-all">http://{host}:7000/v1/lights</code>
            </div>
          </div>

          <div className="border-t" />

          {/* MQTT */}
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Label className="font-semibold">MQTT / Zigbee2MQTT</Label>
              {health?.protocols?.mqtt && (
                <Badge variant={health.protocols.mqtt.status === 'connected' ? 'default' : 'destructive'}>
                  {health.protocols.mqtt.status === 'connected' ? 'активний' : 'помилка'}
                </Badge>
              )}
            </div>
            <div className="grid grid-cols-[100px_1fr] gap-2 text-sm">
              <span className="text-muted-foreground">Plain:</span>
              <code className="bg-background px-2 py-1 rounded border font-mono text-xs select-all">{host}:1883</code>
              <span className="text-muted-foreground">TLS:</span>
              <code className="bg-background px-2 py-1 rounded border font-mono text-xs select-all">{host}:8883</code>
              <span className="text-muted-foreground">WebSocket:</span>
              <code className="bg-background px-2 py-1 rounded border font-mono text-xs select-all">{host}:9001</code>
              <span className="text-muted-foreground">Discovery:</span>
              <code className="bg-background px-2 py-1 rounded border font-mono text-xs select-all">zigbee2mqtt/bridge/devices</code>
            </div>
            <p className="text-xs text-muted-foreground">Анонімний доступ. Selena підписується на zigbee2mqtt/bridge/devices для виявлення пристроїв.</p>
          </div>

          <div className="border-t" />

          {/* miio */}
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Label className="font-semibold">Xiaomi miio</Label>
              {health?.protocols?.miio && (
                <Badge variant={health.protocols.miio.status === 'connected' ? 'default' : 'destructive'}>
                  {health.protocols.miio.status === 'connected' ? 'активний' : 'помилка'}
                </Badge>
              )}
            </div>
            <div className="grid grid-cols-[100px_1fr] gap-2 text-sm">
              <span className="text-muted-foreground">UDP порт:</span>
              <code className="bg-background px-2 py-1 rounded border font-mono text-xs select-all">{host}:54321</code>
              <span className="text-muted-foreground">Шифрування:</span>
              <span>AES-128-CBC (токен задається при створенні пристрою)</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Protocol status */}
      {health && (
        <Card>
          <CardHeader><CardTitle>Статус протоколів</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {Object.entries(health.protocols).map(([name, proto]) => (
                <div key={name} className="flex items-center gap-2 text-sm">
                  <div className={`w-2 h-2 rounded-full ${proto.status === 'connected' ? 'bg-green-500' : 'bg-red-500'}`} />
                  <span>{name}</span>
                  <span className="text-muted-foreground text-xs ml-auto">{proto.stats.messages_sent + proto.stats.messages_received} msg</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle>Керування даними</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-3 flex-wrap">
            <Button variant="outline" onClick={() => navigate('/import')}>Імпорт з зовнішньої системи</Button>
            <Button variant="outline">Е��спорт конфігурації</Button>
          </div>
          <Button variant="destructive" onClick={() => {
            if (confirm('Скинути всі пристрої? Це видалить усі пристрої та їх історію.')) {
              // TODO: implement reset all
            }
          }}>
            Скинути всі пристрої
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
