import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getProtocols, restartProtocol } from '@/lib/api';
import { Button, Card, CardContent, CardHeader, CardTitle, Badge } from '@/components/ui';
import type { ProtocolStatus } from '@/types';

const STATUS_COLORS: Record<string, 'default' | 'secondary' | 'destructive'> = {
  connected: 'default',
  disconnected: 'destructive',
  stopped: 'secondary',
  error: 'destructive',
  disabled: 'secondary',
};

const STATUS_UA: Record<string, string> = {
  connected: 'під\u2019єднано',
  disconnected: 'від\u2019єднано',
  stopped: 'зупинено',
  error: 'помилка',
  disabled: 'вимкнено',
};

export function Protocols() {
  const queryClient = useQueryClient();
  const { data: protocols = [], isLoading } = useQuery({
    queryKey: ['protocols'],
    queryFn: getProtocols,
    refetchInterval: 5000,
  });

  const restartMutation = useMutation({
    mutationFn: (name: string) => restartProtocol(name),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['protocols'] }),
  });

  if (isLoading) return <div className="text-center py-12 text-muted-foreground">Завантаження...</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Статус протоколів</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {protocols.map((proto: ProtocolStatus) => (
          <Card key={proto.name}>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg">{proto.name}</CardTitle>
                <Badge variant={STATUS_COLORS[proto.status] || 'secondary'}>{STATUS_UA[proto.status] || proto.status}</Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {proto.message && (
                <p className="text-xs text-muted-foreground">{proto.message}</p>
              )}

              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="p-2 bg-muted rounded">
                  <div className="text-lg font-bold">{proto.stats.messages_sent}</div>
                  <div className="text-[10px] text-muted-foreground">Надіслано</div>
                </div>
                <div className="p-2 bg-muted rounded">
                  <div className="text-lg font-bold">{proto.stats.messages_received}</div>
                  <div className="text-[10px] text-muted-foreground">Отримано</div>
                </div>
                <div className="p-2 bg-muted rounded">
                  <div className="text-lg font-bold text-destructive">{proto.stats.errors}</div>
                  <div className="text-[10px] text-muted-foreground">Помилки</div>
                </div>
              </div>

              <Button
                size="sm"
                variant="outline"
                className="w-full"
                onClick={() => restartMutation.mutate(proto.name)}
                disabled={restartMutation.isPending}
              >
                Перезапустити
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
