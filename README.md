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
│   └── .env.example      # Modelo de variáveis de ambiente
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
┌─────────────────┐        MQTT (Pub)         ┌──────────────────┐
│  ESP32 (Wokwi)  │ ────────────────────────► │                  │
│                 │   agrosmart/telemetria/*   │  HiveMQ Cloud /  │
│  • DHT22        │                           │  Mosquitto Broker │
│  • Higrômetro   │ ◄──────────────────────── │                  │
│  • LED (Bomba)  │       MQTT (Sub)          └────────┬─────────┘
└─────────────────┘   agrosmart/comando/bomba          │
                                                       │ MQTT (Sub/Pub)
                                              ┌────────▼─────────┐
                                              │  Backend FastAPI  │
                                              │  (Python)         │
                                              │  • GET /telemetria│
                                              │  • GET /clima     │ ◄── OpenWeatherMap
                                              │  • GET /decisao   │
                                              │  • POST /bomba    │
                                              └────────┬─────────┘
                                                       │ HTTP (REST)
                                              ┌────────▼─────────┐
                                              │  App Mobile Web   │
                                              │  (HTML/JS)        │
                                              │  • Painel sensores│
                                              │  • Controle bomba │
                                              │  • Modo auto/manual│
                                              └──────────────────┘
```

---

## 🔧 Tópicos MQTT

| Tópico | Direção | Payload | Descrição |
|---|---|---|---|
| `agrosmart/telemetria/solo` | ESP32 → Broker | `"42"` (%) | Umidade do solo simulada |
| `agrosmart/telemetria/temperatura` | ESP32 → Broker | `"24.5"` (°C) | Temperatura do DHT22 |
| `agrosmart/comando/bomba` | App/Backend → ESP32 | `"LIGAR"` / `"DESLIGAR"` | Controle remoto da bomba |
| `agrosmart/status/bomba` | ESP32 → Broker | `"BOMBA_LIGADA"` / `"BOMBA_DESLIGADA"` | Confirmação do estado |

---

## 🚀 Como Executar

### 1. Simulação Wokwi (ESP32)

1. Acesse [wokwi.com](https://wokwi.com) e importe o projeto (ou use o link da simulação no repositório)
2. Compile e execute — o ESP32 conecta automaticamente ao broker HiveMQ público
3. Ajuste o potenciômetro para simular a umidade do solo (0–100%)

### 2. Backend FastAPI

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edite o .env e insira sua chave da OpenWeatherMap (gratuita em openweathermap.org)
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Documentação interativa disponível em: **http://localhost:8000/docs**

### 3. App Mobile

Abra `mobile-app/index.html` no navegador do celular ou computador.

- Configure o endereço do backend (ex: `http://192.168.x.x:8000` na mesma rede Wi-Fi)
- Clique em **Conectar** — o app atualiza os dados a cada 5 segundos

> **Dica:** Para testar no celular, use o IP local da máquina em vez de `localhost`.

---

## 📱 Funcionalidades do App Mobile

- **Leituras em tempo real** — umidade do solo e temperatura com gauges coloridos
- **Previsão climática** — probabilidade de chuva nas próximas 24h via OpenWeatherMap
- **Decisão preditiva** — recomenda IRRIGAR, AGUARDAR ou informa solo adequado
- **Controle da bomba** — botões LIGAR/DESLIGAR enviam comandos via MQTT/backend
- **Modo Automático** — ativa a bomba automaticamente pela lógica preditiva
- **Log de eventos** — registro em tempo real de todas as ações

---

## 🧠 Lógica Preditiva

```
Solo < 30% E sem chuva prevista  →  IRRIGAR  (aciona bomba)
Solo < 30% E chuva prevista      →  AGUARDAR (economiza água)
Solo >= 30%                      →  SOLO ADEQUADO
```

---

## 🌐 Endpoints da API

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/` | Health-check |
| `GET` | `/telemetria` | Últimas leituras dos sensores |
| `GET` | `/clima` | Previsão de chuva (OpenWeatherMap) |
| `GET` | `/decisao` | Decisão preditiva |
| `POST` | `/bomba` | Envia comando `LIGAR`/`DESLIGAR` |

---

## 🛠️ Tecnologias Utilizadas

| Camada | Tecnologia |
|---|---|
| Microcontrolador | ESP32 (simulado no Wokwi) |
| Firmware | C++ / Arduino Framework (PlatformIO) |
| Protocolo IoT | MQTT (broker HiveMQ público) |
| Backend | Python / FastAPI / Paho-MQTT |
| API Climática | OpenWeatherMap (plano gratuito) |
| App Mobile | HTML5 / CSS3 / JavaScript puro |
| Simulação | Wokwi Online Simulator |

---

## 📦 Dependências do Firmware

```ini
knolleary/PubSubClient              — Cliente MQTT para Arduino
beegee-tokyo/DHT sensor library for ESPx — Driver do DHT22
```