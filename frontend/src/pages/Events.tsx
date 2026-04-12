import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { getEvents, clearEvents as clearEventsApi } from '@/lib/api';
import { useStore } from '@/lib/store';
import { Button, Input, Select, Badge, Card, CardContent } from '@/components/ui';
import { cn, safe } from '@/lib/utils';

const DIRECTION_COLORS: Record<string, string> = {
  received: 'text-green-600 dark:text-green-400',
  sent: 'text-blue-600 dark:text-blue-400',
  internal: 'text-yellow-600 dark:text-yellow-400',
};

export function Events() {
  const queryClient = useQueryClient();
  const { recentEvents, clearEvents: clearLocalEvents } = useStore();
  const [filterProtocol, setFilterProtocol] = useState('');
  const [filterDevice, setFilterDevice] = useState('');
  const [searchPayload, setSearchPayload] = useState('');
  const [showLive, setShowLive] = useState(true);

  const { data: dbEvents = [] } = useQuery({
    queryKey: ['events', filterProtocol, filterDevice],
    queryFn: () => getEvents({ protocol: filterProtocol || undefined, device_id: filterDevice || undefined, limit: 500 }),
    enabled: !showLive,
    refetchInterval: 5000,
  });

  const clearMutation = useMutation({
    mutationFn: clearEventsApi,
    onSuccess: () => {
      clearLocalEvents();
      queryClient.invalidateQueries({ queryKey: ['events'] });
    },
  });

  const events = showLive ? recentEvents : dbEvents;
  const filtered = events.filter((e) => {
    if (filterProtocol && e.protocol !== filterProtocol) return false;
    if (filterDevice && e.device_id !== filterDevice) return false;
    if (searchPayload && !e.payload?.toLowerCase().includes(searchPayload.toLowerCase()) && !e.topic?.toLowerCase().includes(searchPayload.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Журнал подій</h1>
        <div className="flex gap-2">
          <Button variant={showLive ? 'default' : 'outline'} size="sm" onClick={() => setShowLive(true)}>Живий</Button>
          <Button variant={!showLive ? 'default' : 'outline'} size="sm" onClick={() => setShowLive(false)}>З бази</Button>
          <Button variant="destructive" size="sm" onClick={() => clearMutation.mutate()}>Очистити</Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-3">
        <Input placeholder="Пошук у payload/topic..." value={searchPayload} onChange={(e) => setSearchPayload(e.target.value)} className="w-64" />
        <Select
          value={filterProtocol}
          onValueChange={setFilterProtocol}
          options={[
            { value: 'mqtt', label: 'MQTT' },
            { value: 'zigbee2mqtt', label: 'Zigbee2MQTT' },
            { value: 'http_hue', label: 'HTTP Hue' },
            { value: 'miio', label: 'miio' },
            { value: 'ha_websocket', label: 'HA WebSocket' },
          ]}
          placeholder="Усі протоколи"
          className="w-40"
        />
        <Input placeholder="ID пристрою..." value={filterDevice} onChange={(e) => setFilterDevice(e.target.value)} className="w-48" />
      </div>

      <Card>
        <CardContent className="p-0">
          <div className="max-h-[700px] overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-card border-b">
                <tr>
                  <th className="text-left p-2 w-24">Час</th>
                  <th className="text-left p-2 w-32">Пристрій</th>
                  <th className="text-left p-2 w-24">Протокол</th>
                  <th className="text-left p-2 w-8">Нап.</th>
                  <th className="text-left p-2 w-32">Тип</th>
                  <th className="text-left p-2">Топік / Payload</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((event) => (
                  <tr key={event.id} className="border-b hover:bg-accent/50">
                    <td className="p-2 text-muted-foreground whitespace-nowrap">{safe(event.timestamp) ? new Date(event.timestamp).toLocaleTimeString() : ''}</td>
                    <td className="p-2 truncate max-w-[130px]">{safe(event.device_name || event.device_id) || '-'}</td>
                    <td className="p-2"><Badge variant="outline" className="text-[10px]">{safe(event.protocol)}</Badge></td>
                    <td className="p-2">
                      <span className={cn('font-bold', DIRECTION_COLORS[event.direction] || '')}>
                        {event.direction === 'received' ? '\u2193' : event.direction === 'sent' ? '\u2191' : '\u2022'}
                      </span>
                    </td>
                    <td className="p-2 truncate max-w-[130px]">{safe(event.event_type)}</td>
                    <td className="p-2">
                      {event.topic && <div className="text-muted-foreground font-mono truncate">{safe(event.topic)}</div>}
                      <div className="font-mono truncate max-w-[500px]">{safe(event.payload)}</div>
                    </td>
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={6} className="p-8 text-center text-muted-foreground">Немає подій</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
