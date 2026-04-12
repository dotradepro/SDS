import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Card, CardContent, Badge, Switch, Slider } from './ui';
import { executeCommand } from '@/lib/api';
import { useStore } from '@/lib/store';
import type { Device } from '@/types';
import { cn, safe } from '@/lib/utils';

const DEVICE_ICONS: Record<string, string> = {
  light: '\uD83D\uDCA1',
  switch: '\uD83D\uDD0C',
  climate: '\uD83C\uDF21',
  sensor: '\uD83D\uDCE1',
  media_player: '\uD83C\uDFB5',
  lock: '\uD83D\uDD12',
  cover: '\uD83E\uDE9F',
  camera: '\uD83D\uDCF7',
  vacuum: '\uD83E\uDDF9',
  speaker: '\uD83D\uDD0A',
};

const PROTOCOL_COLORS: Record<string, string> = {
  zigbee2mqtt: 'bg-yellow-500/20 text-yellow-700 dark:text-yellow-400',
  mqtt: 'bg-green-500/20 text-green-700 dark:text-green-400',
  http_hue: 'bg-blue-500/20 text-blue-700 dark:text-blue-400',
  http_lifx: 'bg-purple-500/20 text-purple-700 dark:text-purple-400',
  http: 'bg-sky-500/20 text-sky-700 dark:text-sky-400',
  miio: 'bg-orange-500/20 text-orange-700 dark:text-orange-400',
  ha_websocket: 'bg-cyan-500/20 text-cyan-700 dark:text-cyan-400',
  tuya: 'bg-red-500/20 text-red-700 dark:text-red-400',
};

export function DeviceCard({ device }: { device: Device }) {
  const queryClient = useQueryClient();
  const liveState = useStore((s) => s.deviceStates[device.id]);
  const state = liveState || device.state || {};

  const toggleMutation = useMutation({
    mutationFn: () => executeCommand(device.id, 'toggle'),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['devices'] }),
  });

  const brightnessMutation = useMutation({
    mutationFn: (brightness: number) => executeCommand(device.id, 'set_brightness', { brightness }),
  });

  const stateVal = safe(state.state);
  const isOn = stateVal === 'ON' || stateVal === 'on' || stateVal === 'playing' || stateVal === 'cleaning' || stateVal === 'unlocked' || stateVal === 'open';
  const hasToggle = ['light', 'switch', 'media_player', 'speaker'].includes(device.type);
  const hasBrightness = device.type === 'light' && device.capabilities?.includes('brightness');

  return (
    <Link to={`/devices/${device.id}`}>
      <Card className={cn(
        'hover:shadow-md transition-shadow cursor-pointer relative overflow-hidden',
        !device.is_online && 'opacity-60'
      )}>
        <div className={cn(
          'absolute top-3 right-3 w-2.5 h-2.5 rounded-full',
          device.is_online ? 'bg-green-500' : 'bg-gray-400'
        )} />

        <CardContent className="p-4">
          <div className="flex items-start gap-3">
            <div className="text-3xl">{DEVICE_ICONS[device.type] || '\uD83D\uDCE6'}</div>

            <div className="flex-1 min-w-0">
              <h3 className="font-semibold text-sm truncate">{safe(device.name)}</h3>
              {device.room && (
                <p className="text-xs text-muted-foreground truncate">{safe(device.room)}</p>
              )}

              <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                <Badge className={cn('text-[10px] px-1.5 py-0', PROTOCOL_COLORS[device.protocol] || '')}>
                  {safe(device.protocol)}
                </Badge>
                <Badge variant={isOn ? 'default' : 'secondary'} className="text-[10px] px-1.5 py-0">
                  {stateVal || '\u043D\u0435\u0432\u0456\u0434\u043E\u043C\u043E'}
                </Badge>
              </div>
              {/* Ключовий параметр */}
              {device.protocol_config?.friendly_name && (
                <div className="mt-1 text-[10px] text-muted-foreground font-mono truncate">
                  {device.protocol === 'zigbee2mqtt' ? `z2m/${device.protocol_config.friendly_name}` :
                   device.protocol === 'ha_websocket' ? `${device.type}.${device.protocol_config.friendly_name}` :
                   device.protocol_config.friendly_name}
                </div>
              )}

              <div className="mt-2 text-xs text-muted-foreground space-y-0.5">
                {device.type === 'light' && typeof state.brightness === 'number' && (
                  <div>Яскравість: {Math.round((state.brightness / 254) * 100)}%</div>
                )}
                {device.type === 'climate' && typeof state.current_temperature === 'number' && (
                  <div>{state.current_temperature}° / ціль {safe(state.target_temperature)}°</div>
                )}
                {device.type === 'sensor' && typeof state.temperature === 'number' && (
                  <div>{state.temperature}° / {safe(state.humidity)}% вологість</div>
                )}
                {device.type === 'sensor' && state.occupancy !== undefined && (
                  <div>Рух: {state.occupancy ? 'Виявлено' : 'Немає'}</div>
                )}
                {device.type === 'vacuum' && state.battery !== undefined && (
                  <div>Батарея: {safe(state.battery)}%</div>
                )}
              </div>
            </div>
          </div>

          {hasToggle && (
            <div className="mt-3 flex items-center gap-2" onClick={(e) => e.preventDefault()}>
              <Switch
                checked={isOn}
                onCheckedChange={() => toggleMutation.mutate()}
              />
              {hasBrightness && isOn && (
                <Slider
                  value={Number(state.brightness) || 0}
                  min={0}
                  max={254}
                  onChange={(v) => brightnessMutation.mutate(v)}
                  className="flex-1"
                />
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </Link>
  );
}
