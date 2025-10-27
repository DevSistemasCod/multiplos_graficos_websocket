// @ts-nocheck
// ======== Configurações iniciais ========

// Objeto que armazena os gráficos de cada ESP32, identificados por ID
const dispositivos = {};

// Lista com combinações de tipos de gráficos a serem usados
const tiposGraficoPorOrdem = [
  ['bar', 'bar'],
  ['doughnut', 'doughnut'],
  ['polarArea', 'polarArea'],
  ['line', 'line'],
  ['pie', 'pie'],
];

// Container principal onde os gráficos serão adicionados dinamicamente
const container = document.getElementById('graficosContainer');

// ======== Cria gráficos para cada dispositivo ========
function criarGraficosParaDispositivo(id, tipoUltra, tipoEncoder) {
  // Evita recriar gráficos já existentes
  if (dispositivos[id]) return;

  // Cria um container visual para o dispositivo
  const dispositivoContainer = document.createElement('div');
  dispositivoContainer.classList.add('dispositivo');

  // Adiciona um título com o ID do ESP32
  const titulo = document.createElement('h3');
  titulo.textContent = `ESP32 - ${id}`;
  dispositivoContainer.appendChild(titulo);

  // Cria dois elementos <canvas> para os gráficos
  const canvasUltra = document.createElement('canvas');
  const canvasEncoder = document.createElement('canvas');
  dispositivoContainer.appendChild(canvasUltra);
  dispositivoContainer.appendChild(canvasEncoder);

  // Adiciona o container ao HTML principal
  container.appendChild(dispositivoContainer);

  // === Cria gráfico do sensor ultrassônico ===
  const graficoUltra = new Chart(canvasUltra.getContext('2d'), {
    type: tipoUltra,
    data: {
      labels: [],
      datasets: [
        { label: 'Quantidade de Peças', data: [], backgroundColor: [] },
      ],
    },
    options: {
      plugins: {
        legend: { labels: { font: { size: 16 }, color: '#697b6dff' } },
      },
      scales: {
        x: { ticks: { font: { size: 14 }, color: '#697b6dff' } },
        y: {
          ticks: { font: { size: 14 }, color: '#697b6dff' },
          beginAtZero: true,
        },
      },
    },
  });

  // === Cria gráfico do encoder ===
  const graficoEncoder = new Chart(canvasEncoder.getContext('2d'), {
    type: tipoEncoder,
    data: {
      labels: ['Contagem'],
      datasets: [{ label: 'Encoder', data: [0], backgroundColor: ['#0077ff'] }],
    },
    options: {
      plugins: {
        legend: { labels: { font: { size: 16 }, color: '#697b6dff' } },
      },
      scales: {
        x: { ticks: { font: { size: 14 }, color: '#697b6dff' } },
        y: {
          ticks: { font: { size: 14 }, color: '#697b6dff' },
          beginAtZero: true,
        },
      },
    },
  });

  // Guarda ambos os gráficos no objeto global de dispositivos
  dispositivos[id] = { ultrassonico: graficoUltra, encoder: graficoEncoder };
}

// ======== Garante que existam gráficos para o dispositivo atual ========
function inicializarGraficosDoDispositivo(id) {
  if (!dispositivos[id]) {
    console.log(`Novo dispositivo detectado: ${id}`);

    //Object.keys() pega todas as chaves (ou propriedades)
    // de um objeto e devolve uma lista (array) com elas.

    // neste caso Pega todas as chaves do objeto dispositivos (os ESPs detectados)
    //  Conta quantos existem e guarda em  qtdDispositivos.
    const qtdDispositivos = Object.keys(dispositivos).length;

    // Escolhe o tipo de gráfico conforme a ordem de chegada
    const [tipoUltra, tipoEncoder] =
      tiposGraficoPorOrdem[
        //Garante que o índice nunca ultrapasse o tamanho da lista de tipos de gráfico.
        Math.min(qtdDispositivos, tiposGraficoPorOrdem.length - 1)
      ];

    criarGraficosParaDispositivo(id, tipoUltra, tipoEncoder);
  }
}

// ======== Atualiza o gráfico do sensor ultrassônico ========
function atualizarGraficoUltrassonico(graficoUltra, dados) {
  const tipo = dados.tipo;
  const quantidade = dados.quantidade;

  // Verifica se esse tipo de peça já existe no gráfico
  const indice = graficoUltra.data.labels.indexOf(tipo);

  if (indice === -1) {
    // Novo tipo adiciona ao gráfico
    graficoUltra.data.labels.push(tipo);
    graficoUltra.data.datasets[0].data.push(quantidade);
    graficoUltra.data.datasets[0].backgroundColor.push(corPorTipo(tipo));
  } else {
    // Tipo existente → atualiza a quantidade
    graficoUltra.data.datasets[0].data[indice] = quantidade;
  }

  graficoUltra.update();
}

// ======== Atualiza o gráfico do encoder ========
function atualizarGraficoEncoder(graficoEncoder, dados) {
  const contagem = dados.contagem;
  graficoEncoder.data.datasets[0].data[0] = contagem;
  graficoEncoder.update();
}

// ======== Função auxiliar: define cor conforme o tipo ========
function corPorTipo(tipo) {
  switch (tipo) {
    case 'Grande':
      return '#fcff32ff';
    case 'Media':
      return '#34e758ff';
    case 'Pequena':
      return '#ba66f5ff';
    default:
      return '#999999';
  }
}

// ======== Processa os dados recebidos via WebSocket ========
function processamentoMensagem(dados) {
  const id = dados.id || 'desconhecido';

  // Garante que o dispositivo tenha gráficos criados
  inicializarGraficosDoDispositivo(id);

  // Pega os gráficos existentes
  const graficoUltra = dispositivos[id].ultrassonico;
  const graficoEncoder = dispositivos[id].encoder;

  // Decide o que atualizar com base nos dados recebidos
  if ('tipo' in dados && 'quantidade' in dados) {
    atualizarGraficoUltrassonico(graficoUltra, dados);
  } else if ('contagem' in dados) {
    atualizarGraficoEncoder(graficoEncoder, dados);
  } else {
    console.log(`Dados desconhecidos recebidos de ${id}:`, dados);
  }
}

// ======== Conecta WebSocket para cada ESP32 ========
function conectarWebSocket(ip) {
  const socket = new WebSocket(`ws://${ip}:8080`);
  console.log(`Conectando ao ESP32: ${ip}`);

  // Ao receber mensagem do ESP32
  socket.onmessage = (event) => {
    try {
      const dados = JSON.parse(event.data);
      processamentoMensagem(dados);
    } catch (erro) {
      console.error('Erro ao processar mensagem:', erro);
    }
  };

  // Caso a conexão caia, tenta reconectar automaticamente
  socket.onclose = () => {
    console.warn(`Conexão perdida com ${ip}. Tentando reconectar em 2s...`);
    setTimeout(() => conectarWebSocket(ip), 2000);
  };

  // Caso ocorra erro de rede
  socket.onerror = (erro) => {
    console.error(`Erro na conexão com ${ip}:`, erro);
    socket.close();
  };
}

// ======== Inicia tudo quando a página for carregada ========
document.addEventListener('DOMContentLoaded', () => {
  console.log('Página carregada. Iniciando conexões com os ESP32...');

  // Lista de IPs dos dispositivos ESP32
  const listaIPs = ['10.110.22.14', '10.110.22.5', '10.110.22.7'];

  // Cria uma conexão WebSocket para cada IP
  listaIPs.forEach((ip) => conectarWebSocket(ip));
});
