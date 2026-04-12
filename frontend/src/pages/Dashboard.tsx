import { useQuery } from '@tanstack/react-query';
import { getDevices, getHealth } from '@/lib/api';
import { useStore } from '@/lib/store';
import { DeviceCard } from '@/components/DeviceCard';
import { Badge, Input, Select, Card, CardContent } from '@/components/ui';
import { useState, useMemo } from 'react';
import { safe } from '@/lib/utils';
import type { Device } from '@/types';

export function Dashboard() {
  const { data: devices = [], isLoading } = useQuery({ queryKey: ['devices'], queryFn: getDevices, refetchInterval: 10000 });
  const { data: health } = useQuery({ queryKey: ['health'], queryFn: getHealth, refetchInterval: 5000 });
  const recentEvents = useStore((s) => s.recentEvents);

  const [search, setSearch] = useState('');
  const [filterRoom, setFilterRoom] = useState('');
  const [filterType, setFilterType] = useState('');
  const [filterProtocol, setFilterProtocol] = useState('');

  const rooms = useMemo(() => [...new Set(devices.map((d) => d.room).filter(Boolean))], [devices]);
  const types = useMemo(() => [...new Set(devices.map((d) => d.type))], [devices]);
  const protocols = useMemo(() => [...new Set(devices.map((d) => d.protocol))], [devices]);

  const filtered = useMemo(() => {
    return devices.filter((d: Device) => {
      if (search && !d.name.toLowerCase().includes(search.toLowerCase())) return false;
      if (filterRoom && d.room !== filterRoom) return false;
      if (filterType && d.type !== filterType) return false;
      if (filterProtocol && d.protocol !== filterProtocol) return false;
      return true;
    });
  }, [devices, search, filterRoom, filterType, filterProtocol]);

  return (
    <div className="space-y-6">
      {health && (
        <div className="flex items-center gap-2 flex-wrap">
          {Object.entries(health.protocols).map(([name, proto]) => (
            <Badge
              key={name}
              variant={proto.status === 'connected' ? 'default' : proto.status === 'error' ? 'destructive' : 'secondary'}
            >
              {name}: {proto.status === 'connected' ? 'під\u2019єднано' : proto.status === 'error' ? 'помилка' : proto.status}
            </Badge>
          ))}
        </div>
      )}

      <div className="flex flex-wrap gap-3">
        <Input
          placeholder="Пошук пристроїв..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-64"
        />
        <Select
          value={filterRoom}
          onValueChange={setFilterRoom}
          options={rooms.map((r) => ({ value: r, label: r }))}
          placeholder="Усі кімнати"
          className="w-40"
        />
        <Select
          value={filterType}
          onValueChange={setFilterType}
          options={types.map((t) => ({ value: t, label: t }))}
          placeholder="Усі типи"
          className="w-40"
        />
        <Select
          value={filterProtocol}
          onValueChange={setFilterProtocol}
          options={protocols.map((p) => ({ value: p, label: p }))}
          placeholder="Усі протоколи"
          className="w-40"
        />
      </div>

      <div className="flex gap-6">
        <div className="flex-1">
          {isLoading ? (
            <div className="text-center py-12 text-muted-foreground">Завантаження пристроїв...</div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              {devices.length === 0 ? 'Поки немає пристроїв. Натисніть "Додати пристрій" щоб створити.' : 'Немає пристроїв за фільтрами.'}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {filtered.map((device: Device) => (
                <DeviceCard key={device.id} device={device} />
              ))}
            </div>
          )}
        </div>

        <div className="hidden xl:block w-80 shrink-0">
          <Card>
            <CardContent className="p-4">
              <h3 className="font-semibold text-sm mb-3">Останні події</h3>
              <div className="space-y-2 max-h-[600px] overflow-y-auto">
                {recentEvents.slice(0, 30).map((event) => (
                  <div key={event.id} className="text-xs border-b pb-2 last:border-0">
                    <div className="flex items-center gap-1">
                      <span className={event.direction === 'received' ? 'text-green-600' : 'text-blue-600'}>
                        {event.direction === 'received' ? '\u2193' : '\u2191'}
                      </span>
                      <span className="font-medium truncate">{safe(event.device_name || event.protocol)}</span>
                      <span className="text-muted-foreground ml-auto">
                        {safe(event.timestamp) ? new Date(event.timestamp).toLocaleTimeString() : ''}
                      </span>
                    </div>
                    {event.topic && (
                      <div className="text-muted-foreground truncate">{safe(event.topic)}</div>
                    )}
                    <div className="text-muted-foreground truncate">{safe(event.payload)?.slice(0, 80)}</div>
                  </div>
                ))}
                {recentEvents.length === 0 && (
                  <p className="text-muted-foreground text-xs">Поки немає подій</p>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
