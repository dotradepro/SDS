import { Routes, Route } from 'react-router-dom';
import { Layout } from '@/components/Layout';
import { useWebSocket } from '@/hooks/useWebSocket';
import { Dashboard } from '@/pages/Dashboard';
import { DevicesList } from '@/pages/DevicesList';
import { DeviceNew } from '@/pages/DeviceNew';
import { DeviceDetail } from '@/pages/DeviceDetail';
import { Events } from '@/pages/Events';
import { Scenarios } from '@/pages/Scenarios';
import { Protocols } from '@/pages/Protocols';
import { Settings } from '@/pages/Settings';

export default function App() {
  useWebSocket();

  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/devices" element={<DevicesList />} />
        <Route path="/devices/new" element={<DeviceNew />} />
        <Route path="/devices/:id" element={<DeviceDetail />} />
        <Route path="/events" element={<Events />} />
        <Route path="/scenarios" element={<Scenarios />} />
        <Route path="/protocols" element={<Protocols />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </Layout>
  );
}
