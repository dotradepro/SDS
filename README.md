# SDS — Smart Device Simulator

[![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.12-green?logo=python)](https://python.org)
[![React](https://img.shields.io/badge/React-18-blue?logo=react)](https://react.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support%20Project-FF5E5B?logo=ko-fi&logoColor=white)](https://ko-fi.com/dotradepro)

Локальний симулятор розумних пристроїв для тестування голосового асистента **Selena**. Імітує реальні пристрої на рівні протоколу — Selena не знає, що це симулятор.

## Можливості

- **7 протоколів** — MQTT, Zigbee2MQTT, HTTP (Hue/LIFX), Home Assistant WS API, Xiaomi miio, mDNS
- **10 типів пристроїв** — лампи, розетки, термостати, датчики, пилососи, замки, штори, камери, медіаплеєри, колонки
- **Кросс-протокольний експорт** — кожен інтерфейс (HA, Hue, Z2M, LIFX) віддає **ВСІ** пристрої SDS, незалежно від протоколу створення
- **Імітація міграції** — імпорт пристроїв з Home Assistant, Philips Hue, IKEA TRÅDFRI, MQTT, Tuya, SmartThings з реалістичними пресетами (50+ пристроїв)
- **Авторизація** — будь-який токен приймається (HA WS, Hue, LIFX) — імітація успішного OAuth2/API key
- **Актуальні версії протоколів** — HA 2025.12.1, Hue API 1.65.0, Z2M 1.42.0
- **Веб-інтерфейс** (українською) — створення, керування, моніторинг протоколів в реальному часі
- **Docker** — запуск одною командою, працює локально без хмари

## Архітектура

```
┌──────────────────────────────────────────────────────────────────┐
│                        Docker Network                            │
│                                                                  │
│  ┌────────────┐    REST/WS    ┌───────────────────────────────┐  │
│  │  Frontend   │◄────────────►│        SDS Backend             │  │
│  │  React:80   │              │        FastAPI:7000            │  │
│  └────────────┘               │                               │  │
│                                │  ┌─────────────────────────┐ │  │
│                                │  │    Protocol Engine        │ │  │
│                                │  │  MQTT │ HTTP │ WS │ mDNS │ │  │
│                                │  │  miio │ Z2M  │ LIFX      │ │  │
│                                │  └─────────────────────────┘ │  │
│                                └───────────────────────────────┘  │
│                                                                   │
│  ┌────────────┐                                                   │
│  │ Mosquitto   │  MQTT 1883 │ TLS 8883 │ WS 9001                 │
│  └────────────┘                                                   │
│                                                                   │
│  ┌────────────┐                                                   │
│  │  Selena     │◄── підключається як до HA / Hue / Z2M            │
│  └────────────┘    і бачить ВСІ пристрої через будь-який протокол │
└──────────────────────────────────────────────────────────────────┘
```

## Швидкий старт

```bash
git clone https://github.com/dotradepro/SDS.git
cd SDS
bash scripts/gen_certs.sh
docker compose up --build -d
```

Веб-інтерфейс: **http://localhost**

## Як це працює для Selena

SDS емулює кілька smart home систем одночасно. Selena підключається до SDS як до **справжньої** системи і бачить всі пристрої:

| Selena робить | SDS відповідає як | Що отримує |
|---------------|-------------------|------------|
| `ws://SDS:8123` + будь-який токен | Home Assistant 2025.12.1 | Всі пристрої як HA entities |
| `GET /api/<token>/lights` | Hue Bridge API 1.65.0 | Всі пристрої як Hue lights |
| `POST /api` (реєстрація) | Hue Bridge (link button) | username + clientkey |
| `GET /v1/lights` | LIFX Cloud API | Всі пристрої з rooms |
| `sub zigbee2mqtt/bridge/devices` | Z2M Bridge 1.42.0 | Всі пристрої з exposes |
| `sub zigbee2mqtt/bridge/info` | Z2M Bridge info | Версія, coordinator, конфіг |
| UDP `:54321` hello + команди | Xiaomi miio | Відповіді get_status, set_power |

**Авторизація:** SDS приймає **будь-який** токен/пароль — імітація успішного підключення.

## Протоколи

| Протокол | Порт | Версія | Опис |
|----------|------|--------|------|
| **MQTT** | 1883 / 8883 (TLS) / 9001 (WS) | Mosquitto 2.0 | Tasmota, Shelly, Generic топіки |
| **Zigbee2MQTT** | через MQTT 1883 | 1.42.0 | Повна емуляція bridge + groups + bridge/info |
| **HTTP Hue** | 7000 | API 1.65.0 | Philips Hue Bridge (`POST /api`, `/api/<token>/lights`) |
| **HTTP LIFX** | 7000 | v1 | LIFX API (`/v1/lights`) |
| **HTTP Generic** | 7000 | — | REST API (`/devices/<id>/state`) |
| **Home Assistant WS** | 8123 | 2025.12.1 | WebSocket API (auth, get_states, call_service, subscribe) |
| **Xiaomi miio** | UDP 54321 | miio v1 | AES-128-CBC, hello/get_status/set_power/app_start |
| **mDNS/DNS-SD** | multicast | — | Виявлення пристроїв (zeroconf) |

## Типи пристроїв

| Тип | Протоколи | Можливості |
|-----|-----------|------------|
| **Лампа** (light) | Z2M, MQTT, Hue, LIFX, miio | brightness, color_temp, RGB |
| **Розетка** (switch) | Z2M, MQTT (Tasmota/Shelly) | ON/OFF, power monitoring |
| **Термостат** (climate) | Z2M, MQTT, HTTP | temperature, HVAC mode, fan |
| **Датчик** (sensor) | Z2M, MQTT | temp, motion, door, smoke, leak, illuminance |
| **Пилосос** (vacuum) | miio, MQTT | start, pause, return, fan speed, battery |
| **Замок** (lock) | Z2M, HA WS, HTTP | lock, unlock, battery |
| **Штори** (cover) | Z2M, MQTT | position, tilt, open/close |
| **Камера** (camera) | HTTP | snapshot, motion detection |
| **Медіаплеєр** (media_player) | HTTP, HA WS | play, pause, volume, source |
| **Колонка** (speaker) | HTTP, HA WS | volume, DND |

## Імпорт з зовнішніх систем

SDS може масово створювати пристрої з реалістичними пресетами, імітуючи міграцію з інших систем:

### Локальні системи

| Система | Авторизація | Що імпортується | Кількість |
|---------|-------------|-----------------|-----------|
| **Home Assistant** | OAuth2 + URL сервера | Пристрої, кімнати, автоматизації | 14 пристроїв |
| **Philips Hue** | Натиснути кнопку на Bridge | Лампи, групи, сцени | 9 пристроїв |
| **IKEA TRÅDFRI** | PSK авто-генерація | Лампи, групи, жалюзі | 7 пристроїв |
| **MQTT Broker** | host + логін + пароль | Топіки як пристрої | 6 пристроїв |

### Хмарні системи

| Система | Авторизація | Що імпортується | Кількість |
|---------|-------------|-----------------|-----------|
| **Tuya / SmartLife** | OAuth2 через QR | Пристрої, кімнати, DP коди | 9 пристроїв |
| **Samsung SmartThings** | OAuth2 samsung.com | Пристрої, кімнати | 7 пристроїв |

### API імпорту

```
GET  /api/v1/import/sources           — список 6 доступних систем
POST /api/v1/import/connect           — імітація підключення (повертає знайдені пристрої)
POST /api/v1/import/execute           — створити обрані пристрої в SDS
```

## API

Базовий URL: `http://localhost:7000/api/v1`

### Пристрої

```
GET    /devices                    — список всіх пристроїв
POST   /devices                    — створити пристрій
GET    /devices/{id}               — отримати пристрій
PUT    /devices/{id}               — оновити конфігурацію
DELETE /devices/{id}               — видалити пристрій
GET    /devices/{id}/state         — поточний стан
POST   /devices/{id}/state         — встановити стан
POST   /devices/{id}/command       — виконати команду
GET    /devices/{id}/history       — історія змін
POST   /devices/{id}/restart       — перезапустити протокол
```

### Шаблони

```
GET    /templates                  — шаблони всіх типів пристроїв
GET    /templates/{type}           — шаблон конкретного типу
```

### Сценарії

```
GET    /scenarios                  — список сценаріїв
POST   /scenarios                  — створити
PUT    /scenarios/{id}             — оновити
DELETE /scenarios/{id}             — видалити
POST   /scenarios/{id}/start       — запустити
POST   /scenarios/{id}/stop        — зупинити
```

### Z2M Групи

```
GET    /groups                     — список Z2M груп
POST   /groups                     — створити групу
DELETE /groups/{id}                — видалити групу
POST   /groups/{id}/members        — додати пристрій до групи
DELETE /groups/{id}/members/{did}  — видалити з групи
```

### Імпорт

```
GET    /import/sources             — список систем для імпорту
POST   /import/connect             — підключитися (імітація)
POST   /import/execute             — імпортувати обрані пристрої
```

### Утиліти

```
GET    /health                     — статус всіх протоколів
GET    /protocols                  — список протоколів з статистикою
POST   /protocols/{name}/restart   — перезапустити протокол
```

### WebSocket (реальний час)

```
ws://localhost:7000/ws
```

Повідомлення: `state_changed`, `protocol_event`, `device_added`, `device_removed`, `protocol_status`.

### Емуляція зовнішніх API

```
# Philips Hue Bridge API
POST   /api                          — реєстрація (повертає username + clientkey)
GET    /api/<token>/lights           — список всіх пристроїв як Hue лампи
GET    /api/<token>/lights/<id>      — стан лампи
PUT    /api/<token>/lights/<id>/state — змінити стан
GET    /api/<token>/config           — конфігурація Bridge

# LIFX API
GET    /v1/lights                    — список всіх пристроїв
PUT    /v1/lights/<id>/state         — змінити стан
POST   /v1/lights/<id>/toggle        — перемкнути

# Generic REST
GET    /devices/<id>/state           — стан пристрою
POST   /devices/<id>/command         — виконати команду
```

## Приклади використання

### Zigbee2MQTT — увімкнути лампу

```bash
# Selena відправляє команду
mosquitto_pub -h SDS_IP -t 'zigbee2mqtt/living_room_light/set' \
  -m '{"state":"ON","brightness":127}'

# Selena читає стан (retained)
mosquitto_sub -h SDS_IP -t 'zigbee2mqtt/living_room_light' -C 1

# Selena виявляє всі пристрої
mosquitto_sub -h SDS_IP -t 'zigbee2mqtt/bridge/devices' -C 1

# Selena читає інфо бриджа (версія Z2M, coordinator)
mosquitto_sub -h SDS_IP -t 'zigbee2mqtt/bridge/info' -C 1
```

### Philips Hue — підключення + керування

```bash
# 1. Реєстрація (імітація натискання кнопки на Bridge)
curl -X POST http://SDS_IP:7000/api \
  -d '{"devicetype":"selena#rpi","generateclientkey":true}'
# Відповідь: [{"success":{"username":"abc...","clientkey":"DEF..."}}]

# 2. Список ламп (будь-який токен працює)
curl http://SDS_IP:7000/api/abc123/lights

# 3. Увімкнути лампу
curl -X PUT http://SDS_IP:7000/api/abc123/lights/1/state \
  -d '{"on":true,"bri":200}'

# 4. Конфігурація Bridge
curl http://SDS_IP:7000/api/abc123/config
```

### Home Assistant WebSocket — підключення

```python
import websockets, json, asyncio

async def main():
    async with websockets.connect("ws://SDS_IP:8123") as ws:
        # auth_required (HA 2025.12.1)
        print(await ws.recv())

        # Будь-який токен приймається
        await ws.send(json.dumps({
            "type": "auth",
            "access_token": "будь_який_токен"
        }))
        print(await ws.recv())  # auth_ok

        # Отримати ВСІ пристрої SDS як HA entities
        await ws.send(json.dumps({"id": 1, "type": "get_states"}))
        states = json.loads(await ws.recv())
        # Результат: light.*, switch.*, sensor.*, climate.*, vacuum.* ...

        # Підписка на зміни стану
        await ws.send(json.dumps({
            "id": 2,
            "type": "subscribe_events",
            "event_type": "state_changed"
        }))

        # Виклик сервісу
        await ws.send(json.dumps({
            "id": 3,
            "type": "call_service",
            "domain": "light",
            "service": "turn_on",
            "target": {"entity_id": "light.living_room_ceiling"},
            "service_data": {"brightness": 200}
        }))

asyncio.run(main())
```

### Xiaomi miio — UDP протокол

```python
import socket, struct, hashlib, json
from Crypto.Cipher import AES

token = bytes.fromhex("ffffffffffffffffffffffffffffffff")
key, iv = hashlib.md5(token).digest(), hashlib.md5(hashlib.md5(token).digest() + token).digest()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(3)

# Hello
sock.sendto(bytes.fromhex("21310020" + "ff" * 28), ("SDS_IP", 54321))
sock.recvfrom(4096)  # hello response

# Команди: get_status, app_start, set_power, set_bright, set_rgb
```

### MQTT Tasmota / Shelly

```bash
# Tasmota: увімкнути розетку
mosquitto_pub -h SDS_IP -t 'cmnd/kitchen_plug/POWER' -m 'ON'
mosquitto_sub -h SDS_IP -t 'stat/kitchen_plug/POWER' -C 1  # → ON

# Shelly: увімкнути реле
mosquitto_pub -h SDS_IP -t 'shellies/shelly_balcony/relay/0/command' -m 'on'
mosquitto_sub -h SDS_IP -t 'shellies/shelly_balcony/relay/0' -C 1  # → on
```

## Структура проекту

```
sds/
├── main.py                          # FastAPI entry point
├── config.yaml                      # Конфігурація протоколів
├── docker-compose.yml               # Docker оркестрація
├── Dockerfile                       # Backend контейнер
├── mosquitto.conf                   # MQTT брокер (3 listeners)
├── requirements.txt                 # Python залежності
├── scripts/
│   └── gen_certs.sh                 # Генерація TLS сертифікатів
├── core/
│   ├── database.py                  # SQLite + SQLAlchemy async
│   ├── device_manager.py            # Реєстр пристроїв, CRUD, стан
│   ├── event_bus.py                 # Асинхронна шина подій
│   ├── state_machine.py             # Переходи станів пристроїв
│   └── scheduler.py                 # Сценарії автоматизації
├── protocols/
│   ├── base.py                      # Базовий клас протоколу
│   ├── mqtt_handler.py              # MQTT (Tasmota, Shelly, Generic)
│   ├── zigbee2mqtt_handler.py       # Z2M bridge + groups + bridge/info
│   ├── http_handler.py              # Hue Bridge API + LIFX + Generic
│   ├── websocket_ha_handler.py      # Home Assistant WS API 2025.12.1
│   ├── miio_handler.py              # Xiaomi miio (UDP, AES-128-CBC)
│   └── mdns_handler.py              # mDNS/DNS-SD (zeroconf)
├── api/
│   ├── devices.py                   # CRUD ендпоінти пристроїв
│   ├── events.py                    # Лог подій
│   ├── scenarios.py                 # Сценарії автоматизації
│   ├── imports.py                   # Імпорт з зовнішніх систем
│   └── websocket.py                 # WS для UI (реальний час)
├── models/
│   ├── device.py                    # Pydantic моделі + 10 шаблонів
│   ├── event.py                     # Модель події
│   ├── scenario.py                  # Модель сценарію
│   ├── import_source.py             # Моделі імпорту (6 систем)
│   └── import_presets.py            # 50+ реалістичних пресетів
└── frontend/
    ├── Dockerfile                   # Frontend (node build → nginx)
    ├── nginx.conf                   # Проксі API + WS
    ├── package.json
    └── src/
        ├── App.tsx                  # Роутінг (9 сторінок)
        ├── components/              # Layout, DeviceCard, UI
        ├── pages/
        │   ├── Dashboard.tsx        # Панель з фільтрами + live events
        │   ├── DeviceNew.tsx        # 4-кроковий візард створення
        │   ├── DeviceDetail.tsx     # Керування + стан + протокол
        │   ├── DevicesList.tsx      # Список з пошуком
        │   ├── Events.tsx           # Журнал подій (live/DB)
        │   ├── Scenarios.tsx        # Сценарії автоматизації
        │   ├── Protocols.tsx        # Статус протоколів
        │   ├── Import.tsx           # Імпорт з 6 систем (4 кроки)
        │   └── Settings.tsx         # Параметри підключення
        ├── hooks/useWebSocket.ts    # Realtime оновлення
        ├── lib/                     # API клієнт, Zustand store
        └── types/                   # TypeScript типи
```

## Конфігурація

### config.yaml

```yaml
mqtt:
  broker_host: mosquitto
  broker_port: 1883

ha_websocket:
  enabled: true
  port: 8123
  token: any              # будь-який токен приймається

miio:
  enabled: true
  port: 54321

zigbee2mqtt:
  bridge_prefix: zigbee2mqtt

mdns:
  enabled: true
```

### Порти

| Порт | Сервіс | Протокол |
|------|--------|----------|
| **80** | Веб-інтерфейс | HTTP (nginx) |
| **7000** | Backend API + Hue/LIFX | HTTP (FastAPI) |
| **1883** | MQTT (plain) | MQTT |
| **8883** | MQTT (TLS, self-signed) | MQTT over TLS |
| **9001** | MQTT (WebSocket) | MQTT over WS |
| **8123** | Home Assistant WS API | WebSocket |
| **54321/udp** | Xiaomi miio | UDP + AES |
| **5683/udp** | CoAP | UDP |

## Розробка

```bash
# Backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 7000 --reload

# Frontend
cd frontend && npm install && npm run dev
```

## Підтримати проект

Якщо SDS корисний для вас — підтримайте розробку:

[![Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/dotradepro)

## Ліцензія

[MIT](LICENSE)
