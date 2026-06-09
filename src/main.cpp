#include <WiFi.h>
#include <PubSubClient.h>
#include "DHTesp.h"

// ==========================================
// CONFIGURAÇÕES DO PROJETO E REDE
// ==========================================
const char* SSID_REDE = "Wokwi-GUEST"; 
const char* SENHA_REDE = "";

// Utilizamos o HiveMQ como broker público para simplificar o ambiente de testes
const char* BROKER_MQTT = "broker.hivemq.com"; 
const int PORTA_MQTT = 1883;

// ==========================================
// MAPEAMENTO DE HARDWARE (PINAGEM)
// ==========================================
const int PINO_SENSOR_CLIMA = 15; // DHT22 (Temperatura/Umidade do Ar)
const int PINO_SENSOR_SOLO = 34;  // Potenciômetro simulando o Higrômetro
const int PINO_BOMBA_AGUA = 2;    // LED Azul atuando como a bomba

// ==========================================
// ARQUITETURA DOS TÓPICOS MQTT
// ==========================================
// Estrutura semântica para facilitar a integração com o app mobile
const char* TOPICO_LEITURA_SOLO = "agrosmart/telemetria/solo";
const char* TOPICO_LEITURA_TEMP = "agrosmart/telemetria/temperatura";
const char* TOPICO_COMANDO_BOMBA = "agrosmart/comando/bomba";
const char* TOPICO_STATUS_BOMBA = "agrosmart/status/bomba";

// ==========================================
// INSTÂNCIAS GLOBAIS
// ==========================================
WiFiClient clienteWiFi;
PubSubClient mqtt(clienteWiFi);
DHTesp sensorClima;

// Controle de concorrência de tempo (Evita o uso do delay() no loop principal)
unsigned long ultimoEnvio = 0;
const unsigned long INTERVALO_ENVIO_MS = 5000; 

// ==========================================
// FUNÇÕES DE INFRAESTRUTURA
// ==========================================

void conectarWiFi() {
  Serial.printf("\n[REDE] Iniciando conexão com a rede: %s\n", SSID_REDE);
  WiFi.begin(SSID_REDE, SENHA_REDE);
  
  // Loop de espera ativa com feedback visual no terminal
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n[REDE] Wi-Fi conectado com sucesso! IP obtido.");
}

void reconectarMQTT() {
  // Garante a resiliência do sistema: fica em loop até o broker responder
  while (!mqtt.connected()) {
    Serial.print("[MQTT] Tentando estabelecer conexão com o broker...");
    
    // Gera um ID dinâmico para evitar conflitos de sessão no broker público
    String idCliente = "AgroSmart-Node-" + String(random(0xffff), HEX);
    
    if (mqtt.connect(idCliente.c_str())) {
      Serial.println(" SUCESSO!");
      
      // Assim que conecta, registra o interesse (subscribe) nos comandos
      mqtt.subscribe(TOPICO_COMANDO_BOMBA);
      Serial.println("[MQTT] Escutando comandos no tópico da bomba.");
    } else {
      Serial.print(" FALHA. Código: ");
      Serial.print(mqtt.state());
      Serial.println(" -> Nova tentativa em 5 segundos.");
      delay(5000);
    }
  }
}

// ==========================================
// LÓGICA DE NEGÓCIO E CONTROLE
// ==========================================

// Callback acionado sempre que um comando chega do celular via MQTT
void processarComandoRecebido(char* topico, byte* payload, unsigned int tamanho) {
  // Transforma o array de bytes em uma String legível
  String comando = "";
  for (unsigned int i = 0; i < tamanho; i++) {
    comando += (char)payload[i];
  }
  
  Serial.printf("[MQTT-RECV] Tópico: %s | Comando recebido: %s\n", topico, comando.c_str());

  // Roteamento do comando
  if (String(topico) == TOPICO_COMANDO_BOMBA) {
    if (comando == "LIGAR") {
      digitalWrite(PINO_BOMBA_AGUA, HIGH);
      mqtt.publish(TOPICO_STATUS_BOMBA, "BOMBA_LIGADA");
      Serial.println("[SISTEMA] ATUADOR: Bomba ativada remotamente.");
    } 
    else if (comando == "DESLIGAR") {
      digitalWrite(PINO_BOMBA_AGUA, LOW);
      mqtt.publish(TOPICO_STATUS_BOMBA, "BOMBA_DESLIGADA");
      Serial.println("[SISTEMA] ATUADOR: Bomba desativada remotamente.");
    }
    else {
      Serial.println("[SISTEMA] AVISO: Comando não reconhecido.");
    }
  }
}

// ==========================================
// CICLO DE VIDA DO MICROCONTROLADOR
// ==========================================

void setup() {
  Serial.begin(115200);
  Serial.println("\n=================================");
  Serial.println("  INICIANDO SISTEMA AGROSMART   ");
  Serial.println("=================================");

  // Setup de atuadores físicos
  pinMode(PINO_BOMBA_AGUA, OUTPUT);
  digitalWrite(PINO_BOMBA_AGUA, LOW); // Medida de segurança: inicializa desligado
  
  // Setup de sensores
  sensorClima.setup(PINO_SENSOR_CLIMA, DHTesp::DHT22);
  
  // Inicialização das camadas de rede
  conectarWiFi();
  mqtt.setServer(BROKER_MQTT, PORTA_MQTT);
  mqtt.setCallback(processarComandoRecebido);
}

void loop() {
  // Camada de persistência de conexão
  if (!mqtt.connected()) {
    reconectarMQTT();
  }
  mqtt.loop(); // Processa pacotes de entrada/saída (Heartbeat)

  // Temporizador não-bloqueante para aquisição de dados
  unsigned long tempoAtual = millis();
  if (tempoAtual - ultimoEnvio >= INTERVALO_ENVIO_MS) {
    ultimoEnvio = tempoAtual;

    // 1. Aquisição de Dados Ambientais
    TempAndHumidity dadosClima = sensorClima.getTempAndHumidity();
    String tempStr = String(dadosClima.temperature, 1);
    
    // 2. Aquisição de Dados de Solo (Simulado)
    // O conversor Analógico-Digital do ESP32 lê de 0 a 4095. Convertendo para % (0-100)
    int leituraCrua = analogRead(PINO_SENSOR_SOLO);
    int umidadeSoloPercentual = map(leituraCrua, 0, 4095, 0, 100);
    String soloStr = String(umidadeSoloPercentual);

    // 3. Transmissão para Nuvem (Publish)
    mqtt.publish(TOPICO_LEITURA_TEMP, tempStr.c_str());
    mqtt.publish(TOPICO_LEITURA_SOLO, soloStr.c_str());

    // 4. Log local para monitoramento
    Serial.printf("[TELEMETRIA] Temp do Ar: %s°C | Umidade do Solo: %s%%\n", tempStr.c_str(), soloStr.c_str());
  }
}