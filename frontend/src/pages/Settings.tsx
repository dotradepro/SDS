import { useNavigate } from 'react-router-dom';
import { useStore } from '@/lib/store';
import { Button, Card, CardContent, CardHeader, CardTitle, Input, Label, Switch } from '@/components/ui';

export function Settings() {
  const navigate = useNavigate();
  const { theme, toggleTheme } = useStore();

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

      <Card>
        <CardHeader><CardTitle>MQTT брокер</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label>Хост</Label>
            <Input value="mosquitto" disabled className="mt-1" />
          </div>
          <div>
            <Label>Порт (plain)</Label>
            <Input value="1883" disabled className="mt-1" />
          </div>
          <div>
            <Label>Порт (TLS)</Label>
            <Input value="8883" disabled className="mt-1" />
          </div>
          <div>
            <Label>Порт (WebSocket)</Label>
            <Input value="9001" disabled className="mt-1" />
          </div>
          <p className="text-xs text-muted-foreground">Налаштування MQTT брокера задаються через docker-compose.yml</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Home Assistant WS API</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label>Порт</Label>
            <Input value="8123" disabled className="mt-1" />
          </div>
          <div>
            <Label>Токен</Label>
            <Input value="test_token_for_selena" disabled className="mt-1 font-mono text-xs" />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Керування даними</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-3">
            <Button variant="outline">Експорт конфігурації</Button>
            <Button variant="outline" onClick={() => navigate('/import')}>Імпорт з зовнішньої системи</Button>
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
