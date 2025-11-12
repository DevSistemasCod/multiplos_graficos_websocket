import network
import uasyncio as asyncio
import ujson
from machine import Pin, time_pulse_us
from time import sleep
from webSocket import websocket_handshake, Websocket
from utime import localtime


SSID = "MinhaRede"
PASSWORD = "iot@2025"
ESP_ID = "ESP32_A01"  # Identificador da ESP32

TRIG_PIN = 33
ECHO_PIN = 32
DISTANCIA_LIMITE = 10
SOM_VELOCIDADE_CM_POR_US = 0.0343
TIPOS_PECA = ["Grande", "Media", "Pequena"]

PIN_CLK = 25        # Pino do sinal CLK do encoder
PIN_DT = 26         # Pino do sinal de direção (DT)
PIN_SW = 27         # Pino do botão do encoder
POSICAO_ALVO = 10   # Posição-alvo usada para contagem


def conectar_wifi(nome_rede, senha_rede):
    conexao_wifi = network.WLAN(network.STA_IF)
    conexao_wifi.active(True)

    if not conexao_wifi.isconnected():
        print("Conectando à rede Wi-Fi...")
        conexao_wifi.connect(nome_rede, senha_rede)  # Tenta se conectar
        while not conexao_wifi.isconnected():
            print(".", end="")
            sleep(0.5)

    print("\nConectado ao Wi-Fi! IP:", conexao_wifi.ifconfig()[0])
    return conexao_wifi.ifconfig()[0]  # Retorna o endereço IP do ESP32


def medir_distancia(pino_trigger, pino_echo):
    pino_trigger.off()
    sleep(0.002)
    pino_trigger.on()
    sleep(0.00001)  # Pulso de 10 microssegundos para disparar o sensor
    pino_trigger.off()

    duracao = time_pulse_us(pino_echo, 1, 30000)  # Mede o tempo de ida e volta do pulso

    if duracao < 0:
        return -1  # Caso ocorra erro na leitura

    return (duracao * SOM_VELOCIDADE_CM_POR_US) / 2  # Calcula distância em cm


def criar_objetos_ultrassonico(vetor_contadores):
    tempo = localtime()
    data_str = "{:02d}/{:02d}/{:04d}".format(tempo[2], tempo[1], tempo[0])
    hora_str = "{:02d}:{:02d}:{:02d}".format(tempo[3], tempo[4], tempo[5])
    lista = []

    # Percorre cada contador do vetor e cria um objeto JSON correspondente
    for i in range(len(vetor_contadores)):
        # vetor_contadores[i] retorna o valor de contagem correspondente à peça do índice i
        quantidade = vetor_contadores[i]
        tipo_peca = TIPOS_PECA[i]  # Associa o tipo de peça (Grande, Média ou Pequena)

        objeto = {
            "id": ESP_ID,
            "sensor": "ultrassonico",
            "tipo": tipo_peca,
            "quantidade": int(quantidade),
            "data": data_str,
            "hora": hora_str
        }
        lista.append(objeto)

    return lista  # Retorna a lista com os objetos JSON


def criar_payload_encoder(contagem):
    tempo = localtime()
    data_str = "{:02d}/{:02d}/{:04d}".format(tempo[2], tempo[1], tempo[0])
    hora_str = "{:02d}:{:02d}:{:02d}".format(tempo[3], tempo[4], tempo[5])

    return {
        "id": ESP_ID,
        "sensor": "encoder",
        "contagem": contagem,
        "data": data_str,
        "hora": hora_str
    }


async def tarefa_ultrassonico(conexao_ws):
    pino_trigger = Pin(TRIG_PIN, Pin.OUT)
    pino_echo = Pin(ECHO_PIN, Pin.IN)

    vetor_contadores = [0, 0, 0]  # Contadores de peças grandes, médias e pequenas
    estado_anterior = False       # Indica se o objeto estava próximo anteriormente

    while True:
        try:
            distancia_cm = medir_distancia(pino_trigger, pino_echo)

            if distancia_cm > 0:
                # Quando algo está dentro do limite e antes não estava
                if distancia_cm <= DISTANCIA_LIMITE and not estado_anterior:
                    estado_anterior = True

                    # Atualiza os contadores
                    vetor_contadores[0] = vetor_contadores[0] + 1
                    vetor_contadores[1] = vetor_contadores[1] + 2
                    vetor_contadores[2] = vetor_contadores[2] + 3

                    lista = criar_objetos_ultrassonico(vetor_contadores)

                    for objeto in lista:
                        # percorre a lista e envia os dados via WebSocket
                        print("Ultrassonico Enviando:", objeto)
                        await conexao_ws.send(ujson.dumps(objeto))

                # Quando o objeto sai da área de detecção
                elif distancia_cm > DISTANCIA_LIMITE:
                    estado_anterior = False

            await asyncio.sleep(0.2)

        except Exception as e:
            print("Erro na tarefa do ultrassonico:", e)
            await asyncio.sleep(1)


async def tarefa_encoder(conexao_ws):
    clk = Pin(PIN_CLK, Pin.IN, Pin.PULL_UP)
    direcao = Pin(PIN_DT, Pin.IN, Pin.PULL_UP)
    botao = Pin(PIN_SW, Pin.IN, Pin.PULL_UP)

    posicao = 0
    contagem = 0
    estado_alvo_anterior = False
    clk_anterior = clk.value()

    while True:
        try:
            clk_atual = clk.value()

            # Detecta mudança no sinal do encoder
            if clk_atual != clk_anterior:
                if direcao.value() != clk_atual:
                    posicao = posicao + 1
                else:
                    posicao = posicao - 1

                print("Posição atual:", posicao)

                # Quando a posição atinge o alvo, conta mais uma rotação
                if posicao == POSICAO_ALVO and not estado_alvo_anterior:
                    contagem = contagem + 1
                    estado_alvo_anterior = True

                    payload = criar_payload_encoder(contagem)
                    print("Encoder Enviando:", payload)
                    await conexao_ws.send(ujson.dumps(payload))

                elif posicao != POSICAO_ALVO:
                    estado_alvo_anterior = False

            clk_anterior = clk_atual
            await asyncio.sleep(0.001)

        except Exception as e:
            print("Erro na tarefa do encoder:", e)
            await asyncio.sleep(1)


async def atender_cliente(conexao_entrada, conexao_saida):
    if not await websocket_handshake(conexao_entrada, conexao_saida):
        print("Falha no handshake com cliente WebSocket")
        return

    conexao_ws = Websocket(conexao_entrada, conexao_saida)
    print("Cliente WebSocket conectado!")

    try:
        # asyncio.gather executa várias tarefas assíncronas ao mesmo tempo
        # aqui ele roda as duas tarefas (ultrassônico e encoder) de forma paralela, sem travar o programa
        await asyncio.gather(
            tarefa_ultrassonico(conexao_ws),
            tarefa_encoder(conexao_ws)
        )

    except Exception as erro:
        print("Erro na conexão WS:", erro)
    finally:
        conexao_ws.close()
        print("Conexão WebSocket encerrada")


async def main():
    ip_esp = conectar_wifi(SSID, PASSWORD)
    print("Servidor rodando... IP:", ip_esp)

    # cria um servidor assíncrono que fica escutando na porta 8080
    # toda vez que um cliente se conecta, a função atender_cliente é chamada para tratá-lo
    server = await asyncio.start_server(atender_cliente, "0.0.0.0", 8080)

    print("Aguardando clientes WebSocket...")

    while True:
        await asyncio.sleep(1)  # Mantém o servidor ativo


asyncio.run(main())
