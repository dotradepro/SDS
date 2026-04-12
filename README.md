# SDS — Smart Device Simulator

[![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.12-green?logo=python)](https://python.org)
[![React](https://img.shields.io/badge/React-18-blue?logo=react)](https://react.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support%20Project-FF5E5B?logo=ko-fi&logoColor=white)](https://ko-fi.com/dotradepro)

Локальний симулятор розумних пристроїв для тестування голосового асистента **Selena**. Імітує реальні пристрої на рівні протоколу — Selena не знає, що це симулятор.

## Можливості

- **7 протоколів** — MQTT, Zigbee2MQTT, HTTP (Hue/LIFX), Home Assistant WS API, Xiaomi miio, mDNS, CoAP
- **10 типів пристроїв** — лампи, розетки, термостати, датчики, пилососи, замки, штори, камери, медіаплеєри, колонки
- **Веб-інтерфейс** — створення пристроїв через візард, керування, моніторинг протоколів в реальному часі
- **Docker** — запуск одною командою, працює локально без хмари

## Архітектура

```
┌─────────────────────────────────────────────────────────────┐
│                      Docker Network                          │
│                                                              │
│  ┌────────────┐   REST/WS   ┌───────────────────────────┐   │
│  │  Frontend   │◄──────────►│       SDS Backend          │   │
│  │  React:80   │            │       FastAPI:7000         │   │
│  └────────────┘             │                            │   │
│                              │  MQTT │ HTTP │ CoAP │ WS  │   │
│                              │  mDNS │ miio │ Z2M        │   │
│                              └───────────────────────────┘   │
│                                                              │
│  ┌────────────┐         ┌────────────┐                       │
│  │ Mosquitto   │         │   Selena   │◄── бачить пристрої   │
│  │ MQTT:1883   │         │   Core     │    через протоколи   │
│  └────────────┘         └────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

## Швидкий старт

```bash
git clone https://github.com/your-org/sds.git
cd sds
bash scripts/gen_certs.sh    # TLS сертифікати для MQTT
docker compose up --build -d
```

Відкрийте **http://localhost** — веб-інтерфейс SDS.

## Протоколи

| Протокол | Порт | Опис |
|----------|------|------|
| **MQTT** | 1883 (plain), 8883 (TLS), 9001 (WS) | Tasmota, Shelly, Generic топіки |
| **Zigbee2MQTT** | через MQTT 1883 | Повна емуляція Z2M bridge + групи |
| **HTTP Hue** | 7000 | Philips Hue Bridge API (`/api/<token>/lights`) |
| **HTTP LIFX** | 7000 | LIFX API (`/v1/lights`) |
| **HTTP Generic** | 7000 | REST API (`/devices/<id>/state`) |
| **Home Assistant WS** | 8123 | WebSocket API (auth, subscribe, call_service) |
| **Xiaomi miio** | UDP 54321 | AES-128-CBC шифрований протокол |
| **mDNS/DNS-SD** | multicast | Виявлення пристроїв (zeroconf) |

## Типи пристроїв

| Тип | Протоколи | Можливості |
|-----|-----------|------------|
| **Лампа** (light) | Z2M, MQTT, Hue, LIFX, miio | brightness, color_temp, RGB |
| **Розетка** (switch) | Z2M, MQTT (Tasmota/Shelly) | ON/OFF, power monitoring |
| **Термостат** (climate) | Z2M, MQTT, HTTP | temperature, HVAC mode, fan |
| **Датчик** (sensor) | Z2M, MQTT, CoAP | temperature, motion, door, smoke, leak |
| **Пилосос** (vacuum) | miio, MQTT | start, pause, return, fan speed |
| **Замок** (lock) | Z2M, HA WS, HTTP | lock, unlock, battery |
| **Штори** (cover) | Z2M, MQTT | position, tilt, open/close |
| **Камера** (camera) | HTTP | snapshot, motion detection |
| **Медіаплеєр** (media_player) | HTTP, HA WS | play, pause, volume |
| **Колонка** (speaker) | HTTP, HA WS | volume, DND |

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
```

### Сценарії

```
GET    /scenarios                  — список сценаріїв
POST   /scenarios                  — створити
POST   /scenarios/{id}/start       — запустити
POST   /scenarios/{id}/stop        — зупинити
```

### Утиліти

```
GET    /health                     — статус всіх протоколів
GET    /protocols                  — список протоколів
GET    /groups                     — Z2M групи
POST   /groups                     — створити групу
```

### WebSocket (реальний час)

```
ws://localhost:7000/ws
```

Повідомлення: `state_changed`, `protocol_event`, `device_added`, `protocol_status`.

## Приклади використання

### Zigbee2MQTT — увімкнути лампу

```bash
# Selena відправляє команду
mosquitto_pub -h localhost -t 'zigbee2mqtt/living_room_light/set' \
  -m '{"state":"ON","brightness":127}'

# Selena читає стан (retained)
mosquitto_sub -h localhost -t 'zigbee2mqtt/living_room_light' -C 1

# Selena виявляє всі пристрої
mosquitto_sub -h localhost -t 'zigbee2mqtt/bridge/devices' -C 1
```

### Philips Hue API

```bash
# Список ламп
curl http://localhost:7000/api/sds-test-token/lights

# Увімкнути лампу з яскравістю
curl -X PUT http://localhost:7000/api/sds-test-token/lights/1/state \
  -d '{"on":true,"bri":200}'
```

### Home Assistant WebSocket

```python
import websockets, json, asyncio

async def main():
    async with websockets.connect("ws://localhost:8123") as ws:
        await ws.recv()  # auth_required
        await ws.send(json.dumps({
            "type": "auth",
            "access_token": "test_token_for_selena"
        }))
        await ws.recv()  # auth_ok

        # Отримати всі стани
        await ws.send(json.dumps({"id": 1, "type": "get_states"}))
        states = json.loads(await ws.recv())

        # Увімкнути пристрій
        await ws.send(json.dumps({
            "id": 2,
            "type": "call_service",
            "domain": "light",
            "service": "turn_on",
            "target": {"entity_id": "light.living_room"},
            "service_data": {"brightness": 200}
        }))

asyncio.run(main())
```

### Xiaomi miio (UDP)

```python
# Відправити hello-пакет
hello = bytes.fromhex("2131" + "0020" + "ff" * 28)
sock.sendto(hello, ("localhost", 54321))

# Команди: get_status, app_start, set_power, set_bright
```

## Структура проекту

```
sds/
├── main.py                          # FastAPI entry point
├── config.yaml                      # Конфігурація протоколів
├── docker-compose.yml               # Docker оркестрація
├── Dockerfile                       # Backend контейнер
├── mosquitto.conf                   # MQTT брокер конфігурація
├── requirements.txt                 # Python залежності
├── scripts/
│   └── gen_certs.sh                 # Генерація TLS сертифікатів
├── core/
│   ├── database.py                  # SQLite + SQLAlchemy
│   ├── device_manager.py            # Реєстр пристроїв, CRUD, стан
│   ├── event_bus.py                 # Асинхронна шина подій
│   ├── state_machine.py             # Переходи станів пристроїв
│   └── scheduler.py                 # Сценарії автоматизації
├── protocols/
│   ├── base.py                      # Базовий клас протоколу
│   ├── mqtt_handler.py              # MQTT (Tasmota, Shelly, Generic)
│   ├── zigbee2mqtt_handler.py       # Zigbee2MQTT з підтримкою груп
│   ├── http_handler.py              # HTTP (Hue, LIFX, Generic REST)
│   ├── websocket_ha_handler.py      # Home Assistant WS API
│   ├── miio_handler.py              # Xiaomi miio (UDP, AES)
│   └── mdns_handler.py              # mDNS/DNS-SD (zeroconf)
├── devices/                         # Логіка типів пристроїв
├── api/
│   ├── devices.py                   # CRUD ендпоінти
│   ├── events.py                    # Лог подій
│   ├── scenarios.py                 # Сценарії
│   └── websocket.py                 # WS для UI
├── models/
│   ├── device.py                    # Pydantic моделі + шаблони
│   ├── event.py                     # Модель події
│   └── scenario.py                  # Модель сценарію
└── frontend/
    ├── Dockerfile                   # Frontend контейнер (nginx)
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── App.tsx                  # Роутінг
        ├── components/              # UI компоненти
        ├── pages/                   # Сторінки (Dashboard, DeviceNew...)
        ├── hooks/                   # useWebSocket
        ├── lib/                     # API клієнт, store, utils
        └── types/                   # TypeScript типи
```

## Конфігурація

### config.yaml

```yaml
mqtt:
  broker_host: mosquitto
  broker_port: 1883

ha_websocket:
  port: 8123
  token: test_token_for_selena

miio:
  port: 54321

zigbee2mqtt:
  bridge_prefix: zigbee2mqtt
```

### Порти

| Порт | Сервіс |
|------|--------|
| 80 | Веб-інтерфейс |
| 7000 | Backend API + HTTP протоколи |
| 1883 | MQTT (plain) |
| 8883 | MQTT (TLS) |
| 9001 | MQTT (WebSocket) |
| 8123 | Home Assistant WS API |
| 54321/udp | Xiaomi miio |
| 5683/udp | CoAP |

## Розробка

```bash
# Запуск backend локально
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 7000 --reload

# Запуск frontend локально
cd frontend
npm install
npm run dev
```

## Підтримати проект

Якщо SDS корисний для вас — підтримайте розробку:

[![Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/dotradepro)

## Ліцензія

[MIT](LICENSE)
