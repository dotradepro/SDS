import { Link, useLocation } from 'react-router-dom';
import { useStore } from '@/lib/store';
import { cn } from '@/lib/utils';
import { Badge } from './ui';

const navItems = [
  { path: '/', label: '\u041F\u0430\u043D\u0435\u043B\u044C' },
  { path: '/devices', label: '\u041F\u0440\u0438\u0441\u0442\u0440\u043E\u0457' },
  { path: '/events', label: '\u041F\u043E\u0434\u0456\u0457' },
  { path: '/scenarios', label: '\u0421\u0446\u0435\u043D\u0430\u0440\u0456\u0457' },
  { path: '/protocols', label: '\u041F\u0440\u043E\u0442\u043E\u043A\u043E\u043B\u0438' },
  { path: '/import', label: '\u0406\u043C\u043F\u043E\u0440\u0442' },
  { path: '/settings', label: '\u041D\u0430\u043B\u0430\u0448\u0442\u0443\u0432\u0430\u043D\u043D\u044F' },
];

export function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const { wsConnected, theme, toggleTheme } = useStore();

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="flex h-14 items-center px-4 gap-4">
          <Link to="/" className="flex items-center gap-2 font-bold text-lg">
            <span className="bg-primary text-primary-foreground rounded px-2 py-0.5 text-sm">SDS</span>
            <span className="hidden sm:inline">Симулятор пристроїв</span>
          </Link>

          <nav className="flex items-center gap-1 ml-6">
            {navItems.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                className={cn(
                  'px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
                  location.pathname === item.path
                    ? 'bg-accent text-accent-foreground'
                    : 'text-muted-foreground hover:text-foreground hover:bg-accent/50'
                )}
              >
                {item.label}
              </Link>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-3">
            <Badge variant={wsConnected ? 'default' : 'destructive'}>
              {wsConnected ? 'WS з\u2019\u0454\u0434\u043D\u0430\u043D\u043E' : 'WS \u0432\u0456\u0434\u2019\u0454\u0434\u043D\u0430\u043D\u043E'}
            </Badge>

            <button
              onClick={toggleTheme}
              className="h-9 w-9 rounded-md border flex items-center justify-center hover:bg-accent"
              title="Змінити тему"
            >
              {theme === 'dark' ? '\u2600' : '\u263E'}
            </button>

            <Link
              to="/devices/new"
              className="inline-flex items-center justify-center rounded-md bg-primary text-primary-foreground px-4 py-2 text-sm font-medium hover:bg-primary/90"
            >
              + Додати пристрій
            </Link>
          </div>
        </div>
      </header>

      <main className="p-4 max-w-[1600px] mx-auto">
        {children}
      </main>
    </div>
  );
}
