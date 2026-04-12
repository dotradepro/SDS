import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { getDevices } from '@/lib/api';
import { DeviceCard } from '@/components/DeviceCard';
import { Button, Input, Select } from '@/components/ui';
import { useState, useMemo } from 'react';
import type { Device } from '@/types';

export function DevicesList() {
  const { data: devices = [], isLoading } = useQuery({ queryKey: ['devices'], queryFn: getDevices, refetchInterval: 10000 });
  const [search, setSearch] = useState('');
  const [filterRoom, setFilterRoom] = useState('');
  const [filterType, setFilterType] = useState('');

  const rooms = useMemo(() => [...new Set(devices.map((d: Device) => d.room).filter(Boolean))], [devices]);
  const types = useMemo(() => [...new Set(devices.map((d: Device) => d.type))], [devices]);

  const filtered = useMemo(() => {
    return devices.filter((d: Device) => {
      if (search && !d.name.toLowerCase().includes(search.toLowerCase())) return false;
      if (filterRoom && d.room !== filterRoom) return false;
      if (filterType && d.type !== filterType) return false;
      return true;
    });
  }, [devices, search, filterRoom, filterType]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Усі при��трої ({devices.length})</h1>
        <Link to="/devices/new">
          <Button>+ Додати пристрій</Button>
        </Link>
      </div>

      <div className="flex flex-wrap gap-3">
        <Input placeholder="Пошук..." value={search} onChange={(e) => setSearch(e.target.value)} className="w-64" />
        <Select value={filterRoom} onValueChange={setFilterRoom} options={rooms.map((r) => ({ value: r, label: r }))} placeholder="Усі кімнати" className="w-40" />
        <Select value={filterType} onValueChange={setFilterType} options={types.map((t) => ({ value: t, label: t }))} placeholder="Усі типи" className="w-40" />
      </div>

      {isLoading ? (
        <div className="text-center py-12 text-muted-foreground">Завантаження...</div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filtered.map((device: Device) => (
            <DeviceCard key={device.id} device={device} />
          ))}
        </div>
      )}
    </div>
  );
}
