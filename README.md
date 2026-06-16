# 🌱 AgroSmart — Irrigação Inteligente: Simulação IoT e Lógica Preditiva


---

## 📋 Sobre o Projeto

O **AgroSmart** é um sistema de irrigação automatizada focado em eficiência hídrica. Em vez de ligar a água por timer cego, o sistema decide **quando e quanto irrigar** com base em dados físicos (sensores) e dados web (previsão climática) em tempo real.

Nesta versão, foi desenvolvido um **Gêmeo Digital (Simulação)** na plataforma Wokwi, provando a viabilidade do software, da lógica preditiva e da comunicação em nuvem sem custos iniciais de hardware.

---

## 🗂️ Estrutura do Repositório

```
AgroSmart/
├── src/
│   └── main.cpp          # Firmware do ESP32 (C++) — lógica IoT + MQTT
├── backend/
│   ├── main.py           # API FastAPI — bridge HTTP↔MQTT + consulta clima
│   ├── requirements.txt  # Dependências Python
│   └── .env.example      # Modelo de variáveis de ambiente (copiar para .env)
├── mobile-app/
│   └── index.html        # App mobile web — painel de controle MQTT
├── .gitignore
├── diagram.json          # Circuito Wokwi (ESP32 + DHT22 + Potenciômetro + LED)
├── platformio.ini        # Configuração PlatformIO
├── wokwi.toml            # Configuração da simulação Wokwi
└── README.md
```

---

## 🏗️ Arquitetura do Sistema

```
┌─────────────────┐      MQTT (Pub) a cada 2s     ┌──────────────────┐
│  ESP32 (Wokwi)  │ ──────────────────────────►   │                  │
│                 │   agrosmart/telemetria/solo     │  HiveMQ Public   │
│  • DHT22        │   agrosmart/telemetria/temp     │  Broker          │
│  • Potenciômetro│ ◄─────────────────────────── │  broker.hivemq   │
│  • LED (Bomba)  │      MQTT (Sub) comandos        │  .com:1883       │
└─────────────────┘   agrosmart/comando/bomba       └────────┬─────────┘
                                                             │ MQTT (Sub/Pub)
                                                    ┌────────▼─────────┐
                                                    │  Backend FastAPI  │
                                                    │  Python           │
                                                    │                   │
                                                    │  GET  /           │
                                                    │  GET  /telemetria │
                                                    │  GET  /clima ─────┼──► OpenWeatherMap
                                                    │  GET  /decisao    │
                                                    │  POST /bomba      │
                                                    └────────┬─────────┘
                                                             │ HTTP REST
                                                    ┌────────▼─────────┐
                                                    │  App Mobile Web   │
                                                    │  HTML5/CSS3/JS    │
                                                    │                   │
                                                    │  • Gauges sensores│
                                                    │  • Previsão clima │
                                                    │  • Decisão prediti│
                                                    │  • Controle bomba │
                                                    │  • Modo Auto/Manual│
                                                    └──────────────────┘
```

---

## 🔧 Tópicos MQTT

| Tópico | Direção | Payload | Descrição |
|---|---|---|---|
| `agrosmart/telemetria/solo` | ESP32 → Broker | `"42"` (%) | Umidade do solo — potenciômetro mapeado 0–100% |
| `agrosmart/telemetria/temperatura` | ESP32 → Broker | `"24.5"` (°C) | Temperatura lida pelo DHT22 |
| `agrosmart/comando/bomba` | App/Backend → ESP32 | `"LIGAR"` / `"DESLIGAR"` | Controle remoto da bomba |
| `agrosmart/status/bomba` | ESP32 → Broker | `"BOMBA_LIGADA"` / `"BOMBA_DESLIGADA"` | Confirmação do estado do relé |

> O ESP32 publica telemetria a cada **2 segundos**. O app mobile consome os dados via backend a cada **2 segundos**.

---

## 🚀 Como Executar

### 1. Simulação Wokwi (ESP32)

1. Acesse o projeto diretamente: **https://wokwi.com/projects/466022879727959041**
2. Clique em ▶ para iniciar — o ESP32 conecta automaticamente ao broker HiveMQ
3. Ajuste o **potenciômetro** para simular a umidade do solo (0–100%)
4. Monitore o **Serial Monitor** para ver os logs de telemetria e conexão MQTT

### 2. Backend FastAPI

```bash
cd backend

# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis de ambiente
cp .env.example .env
# Edite o .env — sem a chave OpenWeather o backend roda em modo demo

# Subir o servidor
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Documentação interativa dos endpoints: **http://localhost:8000/docs**

### 3. App Mobile

Abra `mobile-app/index.html` no navegador do celular ou computador.

1. No campo de endereço, coloque `http://localhost:8000`
2. Clique em **Conectar**
3. Os dados atualizam automaticamente a cada 2 segundos

> **Testando no celular:** use o IP local da sua máquina (ex: `http://192.168.1.x:8000`) em vez de `localhost`.

### 4. Monitorar via HiveMQ (opcional)

Acesse [broker.hivemq.com](https://broker.hivemq.com) → **Connect** → assine o tópico `agrosmart/#` para ver todas as mensagens em tempo real.

---

## 🧠 Lógica Preditiva

O backend cruza os dados do sensor de solo com a previsão climática antes de decidir:

```
Solo < 30%  E  sem chuva prevista  →  IRRIGAR   (aciona bomba)
Solo < 30%  E  chuva prevista      →  AGUARDAR  (economiza água)
Solo >= 30%                        →  SOLO ADEQUADO
```

No **Modo Automático** do app, o sistema executa o comando sugerido sem intervenção manual.

---

## 📱 Funcionalidades do App Mobile

- **Gauges em tempo real** — umidade do solo e temperatura com cores de alerta (verde/amarelo/vermelho)
- **Previsão climática** — probabilidade de chuva nas próximas 24h via OpenWeatherMap
- **Decisão preditiva** — card visual com resultado IRRIGAR / AGUARDAR / SOLO ADEQUADO
- **Controle manual da bomba** — botões LIGAR/DESLIGAR publicam direto no broker via backend
- **Modo Automático** — liga/desliga a bomba automaticamente pela lógica preditiva (sem repetir comandos desnecessários)
- **Log de eventos** — registro em tempo real de todas as ações e comunicações

---

## 🌐 Endpoints da API

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/` | Health-check — confirma que o servidor está online |
| `GET` | `/telemetria` | Últimas leituras dos sensores recebidas via MQTT |
| `GET` | `/clima` | Previsão de chuva 24h (cache de 10min por padrão) |
| `GET` | `/decisao` | Decisão preditiva cruzando solo + clima |
| `POST` | `/bomba` | Envia `{"comando": "LIGAR"}` ou `{"comando": "DESLIGAR"}` |

---

## 🛠️ Tecnologias Utilizadas

| Camada | Tecnologia |
|---|---|
| Microcontrolador | ESP32 (simulado no Wokwi) |
| Firmware | C++ / Arduino Framework (PlatformIO) |
| Protocolo IoT | MQTT — broker público HiveMQ |
| Backend | Python 3 / FastAPI / Paho-MQTT / HTTPX |
| API Climática | OpenWeatherMap (plano gratuito) |
| App Mobile | HTML5 / CSS3 / JavaScript puro |
| Simulação | Wokwi Online Simulator |

---

## 📦 Dependências do Firmware (PlatformIO)

```ini
knolleary/PubSubClient              — Cliente MQTT para ESP32
beegee-tokyo/DHT sensor library for ESPx — Driver do sensor DHT22
```

## 📦 Dependências do Backend (Python)

```
fastapi       — Framework da API REST
uvicorn       — Servidor ASGI
httpx         — Requisições HTTP assíncronas (OpenWeatherMap)
paho-mqtt     — Cliente MQTT em background
python-dotenv — Leitura do arquivo .env
```