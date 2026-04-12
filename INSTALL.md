# Встановлення SDS

Покрокова інструкція з встановлення та запуску Smart Device Simulator.

## Системні вимоги

| Компонент | Мінімум | Рекомендовано |
|-----------|---------|---------------|
| ОС | Linux, macOS, Windows (WSL2) | Linux (Debian/Ubuntu) |
| Docker | 20.10+ | 24.0+ |
| Docker Compose | v2.0+ | v2.20+ |
| RAM | 2 GB | 4+ GB |
| Диск | 1 GB | 2+ GB |
| CPU | 1 core | 2+ cores |

> SDS працює на Raspberry Pi 4/5 (ARM64) та на x86_64.

## Крок 1: Встановлення Docker

### Ubuntu / Debian

```bash
# Оновити пакети
sudo apt update && sudo apt upgrade -y

# Встановити Docker
curl -fsSL https://get.docker.com | sh

# Додати користувача до групи docker
sudo usermod -aG docker $USER

# Перезайти в сесію (або перезавантажити)
newgrp docker

# Перевірити
docker --version
docker compose version
```

### macOS

Встановіть [Docker Desktop](https://www.docker.com/products/docker-desktop/).

### Windows

Встановіть [Docker Desktop з WSL2](https://docs.docker.com/desktop/install/windows-install/).

## Крок 2: Клонування репозиторію

```bash
git clone https://github.com/your-org/sds.git
cd sds
```

## Крок 3: Генерація TLS сертифікатів

Скрипт створює self-signed сертифікати для MQTT over TLS (порт 8883):

```bash
bash scripts/gen_certs.sh
```

Результат:
```
certs/
├── ca.crt        # Кореневий сертифікат CA
├── ca.key        # Ключ CA
├── server.crt    # Сертифікат сервера
└── server.key    # Ключ сервера
```

> Сертифікати створюються один раз. При повторному запуску скрипт пропустить генерацію, якщо файли вже існують.

## Крок 4: Запуск

```bash
docker compose up --build -d
```

Це запустить 3 контейнери:

| Контейнер | Опис | Порт |
|-----------|------|------|
| `sds-frontend` | Веб-інтерфейс (nginx) | **80** |
| `sds-backend` | FastAPI + протоколи | 7000, 8123, 54321 |
| `sds-mosquitto` | MQTT брокер | 1883, 8883, 9001 |

## Крок 5: Перевірка

```bash
# Статус контейнерів
docker compose ps

# Health check
curl http://localhost:7000/api/v1/health

# Відкрити веб-інтерфейс
open http://localhost    # macOS
xdg-open http://localhost  # Linux
```

Очікуваний результат health check:
```json
{
  "status": "ok",
  "protocols": {
    "mqtt": {"status": "connected"},
    "zigbee2mqtt": {"status": "connected"},
    "http": {"status": "connected"},
    "ha_websocket": {"status": "connected"},
    "miio": {"status": "connected"},
    "mdns": {"status": "connected"}
  }
}
```

## Конфігурація

### config.yaml

Основний файл конфігурації протоколів. Монтується в контейнер як read-only.

```yaml
mqtt:
  broker_host: mosquitto     # Ім'я сервісу в Docker
  broker_port: 1883          # Порт MQTT брокера

ha_websocket:
  enabled: true
  port: 8123                 # Порт WebSocket API
  token: test_token_for_selena  # Токен автентифікації

miio:
  enabled: true
  port: 54321                # UDP порт для Xiaomi пристроїв

zigbee2mqtt:
  bridge_prefix: zigbee2mqtt # Префікс MQTT топіків

mdns:
  enabled: true              # mDNS виявлення пристроїв
```

### mosquitto.conf

Конфігурація MQTT брокера з трьома listener'ами:

| Listener | Порт | Протокол |
|----------|------|----------|
| Plain | 1883 | MQTT (без шифрування) |
| TLS | 8883 | MQTT over TLS |
| WebSocket | 9001 | MQTT over WebSocket |

> Всі listener'и дозволяють анонімний доступ (тестове середовище).

### Змінні оточення

Можна перевизначити через `docker-compose.yml` → `environment`:

| Змінна | За замовчуванням | Опис |
|--------|------------------|------|
| `MQTT_BROKER` | `mosquitto` | Хост MQTT брокера |
| `MQTT_PORT` | `1883` | Порт MQTT |
| `DATABASE_URL` | `sqlite:////app/data/sds.db` | Шлях до бази даних |

## Оновлення

```bash
cd sds
git pull
docker compose up --build -d
```

> Дані пристроїв зберігаються у Docker volume `sds_data` і не втрачаються при оновленні.

## Зупинка та видалення

```bash
# Зупинити
docker compose down

# Зупинити і видалити дані (volumes)
docker compose down -v

# Видалити образи
docker compose down --rmi all
```

## Логи

```bash
# Всі контейнери
docker compose logs -f

# Тільки backend
docker compose logs -f sds-backend

# Тільки MQTT
docker compose logs -f mosquitto
```

## Вирішення проблем

### Порт 80 зайнятий

Змініть порт в `docker-compose.yml`:

```yaml
sds-frontend:
  ports:
    - "8080:80"    # змінити 80 на 8080
```

### MQTT не підключається

```bash
# Перевірити що Mosquitto працює
docker compose logs mosquitto

# Перевірити підключення
mosquitto_pub -h localhost -p 1883 -t 'test' -m 'hello'
mosquitto_sub -h localhost -p 1883 -t 'test' -C 1
```

### Backend не стартує

```bash
# Перевірити логи
docker compose logs sds-backend

# Перезапустити
docker compose restart sds-backend
```

### Сертифікати — помилка TLS

```bash
# Перегенерувати сертифікати
rm -f certs/*
bash scripts/gen_certs.sh
docker compose restart mosquitto
```

### mDNS не працює

mDNS потребує multicast в мережі. В Docker bridge network multicast обмежений. Для повної підтримки mDNS використовуйте `network_mode: host` для backend в `docker-compose.yml`.

### Скинути все

```bash
docker compose down -v
rm -f certs/*
bash scripts/gen_certs.sh
docker compose up --build -d
```
