"""
AgroSmart — Backend FastAPI
===========================
Responsabilidades:
  1. Expor endpoints REST para o app mobile consultar dados dos sensores e clima
  2. Fazer bridge entre HTTP (app) e MQTT (ESP32) para controle da bomba
  3. Buscar previsão de chuva na API OpenWeatherMap e decidir se deve irrigar

Pré-requisitos:
  pip install fastapi uvicorn httpx paho-mqtt python-dotenv

Variáveis de ambiente (.env):
  OPENWEATHER_API_KEY=sua_chave_aqui   (gratuita em openweathermap.org)
  MQTT_BROKER=broker.hivemq.com
  MQTT_PORT=1883
  CITY=São Paulo                       (cidade para previsão de chuva)
"""

import os
import json
import asyncio
import threading
from datetime import datetime
from typing import Optional

import httpx
import paho.mqtt.client as mqtt_client
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# ── Carrega variáveis de ambiente ──────────────────────────────────────────────
load_dotenv()

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "INSIRA_SUA_CHAVE_AQUI")
MQTT_BROKER         = os.getenv("MQTT_BROKER", "broker.hivemq.com")
MQTT_PORT           = int(os.getenv("MQTT_PORT", 1883))
CITY                = os.getenv("CITY", "São Paulo")

# ── Tópicos MQTT (devem coincidir com o firmware do ESP32) ─────────────────────
TOPIC_SOLO   = "agrosmart/telemetria/solo"
TOPIC_TEMP   = "agrosmart/telemetria/temperatura"
TOPIC_CMD    = "agrosmart/comando/bomba"
TOPIC_STATUS = "agrosmart/status/bomba"

# ── Estado em memória (substitui banco de dados para fins acadêmicos) ──────────
state: dict = {
    "umidade_solo": None,      # % (0-100) — lido do higrômetro simulado
    "temperatura":  None,      # °C — lido do DHT22
    "status_bomba": "DESCONHECIDO",
    "vai_chover":   None,      # True / False — dado da API clima
    "ultima_atualizacao": None,
    "mqtt_conectado": False,
}

# ── Cliente MQTT (roda em thread separada para não bloquear o servidor) ────────
_mqtt = mqtt_client.Client(client_id="AgroSmart-Backend", clean_session=True)

def _on_connect(client, userdata, flags, rc):
    """Callback disparado quando a conexão com o broker é estabelecida."""
    if rc == 0:
        state["mqtt_conectado"] = True
        # Assina todos os tópicos de telemetria e status
        client.subscribe(TOPIC_SOLO)
        client.subscribe(TOPIC_TEMP)
        client.subscribe(TOPIC_STATUS)
        print(f"[MQTT] Conectado ao broker {MQTT_BROKER} e inscrito nos tópicos.")
    else:
        print(f"[MQTT] Falha na conexão. Código: {rc}")

def _on_message(client, userdata, msg):
    """Callback disparado quando uma mensagem MQTT é recebida."""
    payload = msg.payload.decode("utf-8").strip()
    topic   = msg.topic
    state["ultima_atualizacao"] = datetime.now().isoformat()

    if topic == TOPIC_SOLO:
        try:
            state["umidade_solo"] = float(payload)
            print(f"[MQTT] Umidade do solo atualizada: {payload}%")
        except ValueError:
            print(f"[MQTT] Payload inválido para solo: {payload}")

    elif topic == TOPIC_TEMP:
        try:
            state["temperatura"] = float(payload)
            print(f"[MQTT] Temperatura atualizada: {payload}°C")
        except ValueError:
            print(f"[MQTT] Payload inválido para temperatura: {payload}")

    elif topic == TOPIC_STATUS:
        state["status_bomba"] = payload
        print(f"[MQTT] Status da bomba: {payload}")

def _on_disconnect(client, userdata, rc):
    """Callback de desconexão — registra no estado."""
    state["mqtt_conectado"] = False
    print(f"[MQTT] Desconectado do broker. Código: {rc}")

def _start_mqtt_loop():
    """Inicia o cliente MQTT em thread de background."""
    _mqtt.on_connect    = _on_connect
    _mqtt.on_message    = _on_message
    _mqtt.on_disconnect = _on_disconnect
    try:
        _mqtt.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        _mqtt.loop_forever()   # Bloqueia a thread — ok pois está em background
    except Exception as e:
        print(f"[MQTT] Erro ao conectar: {e}")

# ── FastAPI App ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AgroSmart API",
    description="Backend IoT para o sistema de irrigação inteligente AgroSmart",
    version="1.0.0",
)

# Permite requisições do app mobile (qualquer origem para fins acadêmicos)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Inicializa o loop MQTT em background ao subir o servidor."""
    thread = threading.Thread(target=_start_mqtt_loop, daemon=True)
    thread.start()
    print("[API] Servidor iniciado. Loop MQTT rodando em background.")

# ── Modelos Pydantic ───────────────────────────────────────────────────────────
class ComandoBomba(BaseModel):
    comando: str  # "LIGAR" ou "DESLIGAR"

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/", tags=["Root"])
def root():
    """Health-check básico."""
    return {"projeto": "AgroSmart", "status": "online", "versao": "1.0.0"}


@app.get("/telemetria", tags=["Sensores"])
def get_telemetria():
    """
    Retorna os últimos dados recebidos dos sensores do ESP32 via MQTT.
    Inclui umidade do solo, temperatura do ar e status da bomba.
    """
    return {
        "umidade_solo":       state["umidade_solo"],
        "temperatura":        state["temperatura"],
        "status_bomba":       state["status_bomba"],
        "mqtt_conectado":     state["mqtt_conectado"],
        "ultima_atualizacao": state["ultima_atualizacao"],
    }


@app.get("/clima", tags=["Clima"])
async def get_clima():
    """
    Consulta a API OpenWeatherMap e retorna previsão de chuva para as
    próximas 24h na cidade configurada (variável CITY no .env).
    Armazena internamente se vai chover para uso na lógica preditiva.
    """
    if OPENWEATHER_API_KEY == "INSIRA_SUA_CHAVE_AQUI":
        # Modo demo: retorna dados simulados para desenvolvimento
        dados_simulados = {
            "cidade": CITY,
            "temperatura_atual": 24.5,
            "descricao": "céu limpo (simulado)",
            "vai_chover_24h": False,
            "probabilidade_chuva": 0.10,
            "fonte": "SIMULADO — configure OPENWEATHER_API_KEY no .env",
        }
        state["vai_chover"] = dados_simulados["vai_chover_24h"]
        return dados_simulados

    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {
        "q":     CITY,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
        "lang":  "pt_br",
        "cnt":   8,  # 8 intervalos de 3h = 24h
    }

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=502,
                detail=f"Erro ao consultar OpenWeatherMap: {e.response.status_code}"
            )
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Falha de rede: {str(e)}")

    data = resp.json()

    # Analisa se algum dos próximos intervalos prevê chuva
    previsoes = data.get("list", [])
    max_prob_chuva = max(
        (p.get("pop", 0) for p in previsoes), default=0
    )
    vai_chover = max_prob_chuva >= 0.4  # Limiar: 40% de probabilidade

    state["vai_chover"] = vai_chover

    return {
        "cidade": data["city"]["name"],
        "temperatura_atual": previsoes[0]["main"]["temp"] if previsoes else None,
        "descricao": previsoes[0]["weather"][0]["description"] if previsoes else None,
        "vai_chover_24h": vai_chover,
        "probabilidade_chuva": round(max_prob_chuva, 2),
        "fonte": "OpenWeatherMap",
    }


@app.post("/bomba", tags=["Controle"])
def controlar_bomba(body: ComandoBomba):
    """
    Envia um comando LIGAR ou DESLIGAR para a bomba via MQTT.
    O ESP32 recebe o comando e aciona o relé (LED azul na simulação).
    """
    comando = body.comando.upper()

    if comando not in ("LIGAR", "DESLIGAR"):
        raise HTTPException(
            status_code=400,
            detail="Comando inválido. Use 'LIGAR' ou 'DESLIGAR'."
        )

    if not state["mqtt_conectado"]:
        raise HTTPException(
            status_code=503,
            detail="Backend desconectado do broker MQTT. Verifique a conexão."
        )

    result = _mqtt.publish(TOPIC_CMD, comando, qos=1)

    if result.rc != mqtt_client.MQTT_ERR_SUCCESS:
        raise HTTPException(
            status_code=500,
            detail=f"Falha ao publicar no broker MQTT. Código: {result.rc}"
        )

    print(f"[API] Comando '{comando}' enviado para o tópico '{TOPIC_CMD}'")
    return {"mensagem": f"Comando '{comando}' enviado com sucesso.", "topico": TOPIC_CMD}


@app.get("/decisao", tags=["Lógica Preditiva"])
async def get_decisao():
    """
    Lógica preditiva principal do AgroSmart:
    Cruza dados do solo com previsão climática para decidir se deve irrigar.

    Regras:
      - Solo seco (< 30%) E sem chuva prevista → IRRIGAR
      - Solo seco (< 30%) E chuva prevista       → AGUARDAR
      - Solo úmido (>= 30%)                      → SOLO ADEQUADO
    """
    solo      = state["umidade_solo"]
    vai_chover = state["vai_chover"]

    # Se os dados ainda não chegaram, consulta o clima agora
    if vai_chover is None:
        try:
            await get_clima()
            vai_chover = state["vai_chover"]
        except Exception:
            vai_chover = None

    # Determina a decisão
    if solo is None:
        decisao = "AGUARDANDO_DADOS"
        motivo  = "Nenhuma leitura recebida do sensor de solo ainda."
        acao    = None
    elif solo < 30:
        if vai_chover:
            decisao = "AGUARDAR"
            motivo  = f"Solo seco ({solo:.0f}%), mas chuva prevista. Economizando água."
            acao    = "DESLIGAR"
        else:
            decisao = "IRRIGAR"
            motivo  = f"Solo seco ({solo:.0f}%) e sem chuva prevista. Ativando irrigação."
            acao    = "LIGAR"
    else:
        decisao = "SOLO_ADEQUADO"
        motivo  = f"Umidade do solo em {solo:.0f}% — dentro do nível ideal."
        acao    = "DESLIGAR"

    return {
        "decisao":         decisao,
        "motivo":          motivo,
        "umidade_solo":    solo,
        "vai_chover_24h":  vai_chover,
        "acao_sugerida":   acao,
    }
