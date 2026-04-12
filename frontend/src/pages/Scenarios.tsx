import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getScenarios, createScenario, deleteScenario, startScenario, stopScenario } from '@/lib/api';
import { Button, Card, CardContent, CardHeader, CardTitle, Badge, Input, Textarea } from '@/components/ui';
import { useState } from 'react';
import type { Scenario } from '@/types';

export function Scenarios() {
  const queryClient = useQueryClient();
  const { data: scenarios = [], isLoading } = useQuery({ queryKey: ['scenarios'], queryFn: getScenarios, refetchInterval: 5000 });
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [newStepsJson, setNewStepsJson] = useState('[]');

  const createMutation = useMutation({
    mutationFn: () => createScenario({
      name: newName,
      description: newDesc,
      triggers: [{ type: 'manual' }],
      steps: JSON.parse(newStepsJson),
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scenarios'] });
      setShowCreate(false);
      setNewName('');
      setNewDesc('');
      setNewStepsJson('[]');
    },
  });

  const startMut = useMutation({
    mutationFn: startScenario,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['scenarios'] }),
  });

  const stopMut = useMutation({
    mutationFn: stopScenario,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['scenarios'] }),
  });

  const deleteMut = useMutation({
    mutationFn: deleteScenario,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['scenarios'] }),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Сценарії</h1>
        <Button onClick={() => setShowCreate(!showCreate)}>{showCreate ? 'Скасувати' : 'Створити сценарій'}</Button>
      </div>

      {showCreate && (
        <Card>
          <CardHeader><CardTitle>Новий сценарій</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-sm font-medium">Назва</label>
              <Input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Назва сценарію" className="mt-1" />
            </div>
            <div>
              <label className="text-sm font-medium">Опис</label>
              <Input value={newDesc} onChange={(e) => setNewDesc(e.target.value)} placeholder="Опис" className="mt-1" />
            </div>
            <div>
              <label className="text-sm font-medium">Кроки (JSON)</label>
              <Textarea
                value={newStepsJson}
                onChange={(e) => setNewStepsJson(e.target.value)}
                rows={6}
                className="mt-1 font-mono text-xs"
                placeholder='[{"delay_seconds": 0, "device_id": "...", "action": "set_state", "state": {"state": "ON"}}]'
              />
            </div>
            <Button onClick={() => createMutation.mutate()} disabled={!newName || createMutation.isPending}>
              {createMutation.isPending ? 'Створення...' : 'Створити'}
            </Button>
          </CardContent>
        </Card>
      )}

      {isLoading ? (
        <div className="text-center py-12 text-muted-foreground">Завантаження...</div>
      ) : scenarios.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">Поки немає сценаріїв.</div>
      ) : (
        <div className="grid gap-4">
          {scenarios.map((scenario: Scenario) => (
            <Card key={scenario.id}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold">{scenario.name}</h3>
                    <p className="text-sm text-muted-foreground">{scenario.description}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <Badge variant={scenario.is_active ? 'default' : 'secondary'}>
                        {scenario.is_active ? 'Працює' : 'Зупинено'}
                      </Badge>
                      <span className="text-xs text-muted-foreground">{scenario.steps.length} кроків</span>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    {scenario.is_active ? (
                      <Button size="sm" variant="outline" onClick={() => stopMut.mutate(scenario.id)}>Зупинити</Button>
                    ) : (
                      <Button size="sm" onClick={() => startMut.mutate(scenario.id)}>Запустити</Button>
                    )}
                    <Button size="sm" variant="destructive" onClick={() => { if (confirm('Видалити?')) deleteMut.mutate(scenario.id); }}>Видалити</Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
