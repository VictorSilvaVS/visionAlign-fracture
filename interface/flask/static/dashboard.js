// c:\Users\Sonu\Desktop\projetos github\323\visionAlign\interface\flask\static\dashboard.js
console.log("dashboard.js loaded for dynamic values only");

// Função para buscar dados de /api/basic_stats
async function fetchBasicApiStats() {
    try {
        const response = await fetch('/api/basic_stats');
        if (!response.ok) {
            console.error(`Erro ao buscar /api/basic_stats: ${response.status}`);
            return null;
        }
        // /api/basic_stats retorna JSON diretamente, sem criptografia
        return await response.json();
    } catch (error) {
        console.error('Erro em fetchBasicApiStats:', error);
        return null;
    }
}

// Função para buscar dados de /api/alerts_history (para a lista de resultados de classificação)
async function fetchApiAlertsHistory(limit = 5) {
    try {
        const response = await fetch(`/api/alerts_history?limit=${limit}`);
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ message: `Erro HTTP ${response.status}` }));
            throw new Error(errorData.message || `Falha ao buscar histórico de alertas: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error("Erro em fetchApiAlertsHistory:", error);
        throw error; // Re-lança para ser tratado
    }
}
// Função para buscar dados de /api/detection_history (para a lista de resultados)
async function fetchApiDetectionHistory(period = 'hour') {
    try {
        const response = await fetch(`/api/detection_history?period=${period}`);
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ message: `Erro HTTP ${response.status}` }));
            throw new Error(errorData.message || `Falha ao buscar histórico: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error("Erro em fetchApiDetectionHistory:", error);
        throw error; // Re-lança para ser tratado
    }
}

// Função para atualizar os KPIs e Status
function updateKpisAndStatus(statsData) {
    const systemStatusIndicator = document.getElementById('system-status-indicator');
    const systemStatusText = document.getElementById('system-status-text');
    const kpiAccuracy = document.getElementById('kpi-accuracy-value');
    const kpiSpeed = document.getElementById('kpi-speed-value');
    const kpiCount = document.getElementById('kpi-count-value');

    if (statsData) {
        if (systemStatusIndicator && systemStatusText) {
            // Usa o 'status' de /api/basic_stats
            const isOnline = statsData.status === 'Operacional';
            systemStatusIndicator.className = `status-indicator ${isOnline ? 'status-online' : 'status-offline'}`;
            systemStatusText.textContent = statsData.status || 'Offline';
        }
        // Agora ai_accuracy_percent e fps estão em /api/basic_stats
        if (kpiAccuracy) {
            kpiAccuracy.textContent = statsData.ai_accuracy_percent !== undefined
                ? `${parseFloat(statsData.ai_accuracy_percent).toFixed(1)}%`
                : 'N/A';
        }
        if (kpiSpeed) {
            // "Velocidade" é representada pelo FPS
            kpiSpeed.textContent = statsData.fps !== undefined
                ? `${parseFloat(statsData.fps).toFixed(1)} FPS`
                : 'N/A';
        }
        // total_detected está em /api/basic_stats
        if (kpiCount) kpiCount.textContent = (statsData.total_detected !== undefined ? statsData.total_detected : 'N/A');
    } else {
        // Fallback se não houver dados
        if (systemStatusIndicator && systemStatusText) {
            systemStatusIndicator.className = 'status-indicator status-offline';
            systemStatusText.textContent = 'Offline';
        }
        if (kpiAccuracy) kpiAccuracy.textContent = 'N/A';
        if (kpiSpeed) kpiSpeed.textContent = 'N/A';
        if (kpiCount) kpiCount.textContent = 'N/A';
    }
}

// Função para atualizar os badges de contagem
function updateCountBadges(statsData) {
    const countNormal = document.getElementById('count-normal-value');
    const countFallen = document.getElementById('count-fallen-value');
    const countInverted = document.getElementById('count-inverted-value');

    if (statsData) {
        // Usar os valores de statsData se existirem, senão '0'
        if (countNormal) countNormal.textContent = (statsData.lata_normal !== undefined ? statsData.lata_normal : '0');
        if (countFallen) countFallen.textContent = (statsData.lata_tombada !== undefined ? statsData.lata_tombada : '0');
        if (countInverted) countInverted.textContent = (statsData.lata_invertida !== undefined ? statsData.lata_invertida : '0');
    } else {
        if (countNormal) countNormal.textContent = '0';
        if (countFallen) countFallen.textContent = '0';
        if (countInverted) countInverted.textContent = '0';
    }
}

// Função para popular a lista de resultados da classificação COM BASE NOS ALERTAS DO DB
function populateAlertsResultsList(alertsApiResponse) {
    const listElement = document.getElementById('detection-results-list-items');
    if (!listElement) {
        console.warn("Elemento 'detection-results-list-items' para alertas não encontrado.");
        return;
    }

    listElement.innerHTML = ''; // Limpa conteúdo antigo

    const alerts = alertsApiResponse?.alerts;

    if (!alerts || alerts.length === 0) {
        listElement.innerHTML = '<p class="text-sm text-gray-500 text-center py-4">Nenhum alerta recente para exibir.</p>';
        return;
    }

    alerts.forEach(alert => {
        const itemDiv = document.createElement('div');
        itemDiv.className = 'border-b pb-4';

        // O tipo do alerta (e.g., "Lata Invertida", "Lata Tombada") vem diretamente da API
        let typeText = alert.type || "Tipo Desconhecido";
        let primaryAnomalyTypeClass = "bg-gray-100 text-gray-800"; // Default
        let statusIndicatorClass = "status-warning"; // Default
        let confidencePercent = 0; // Default confidence

        const details = alert.details || "";

        // Determinar a classe de estilo com base no tipo do alerta
        if (typeText.toLowerCase().includes("invertida")) {
            primaryAnomalyTypeClass = "bg-red-100 text-red-800";
            statusIndicatorClass = "status-offline"; // Vermelho para invertida
        } else if (typeText.toLowerCase().includes("tombada")) {
            primaryAnomalyTypeClass = "bg-yellow-100 text-yellow-800";
            statusIndicatorClass = "status-warning"; // Amarelo para tombada
        } else if (typeText.toLowerCase().includes("normal")) {
            primaryAnomalyTypeClass = "bg-green-100 text-green-800";
            statusIndicatorClass = "status-online"; // Verde para normal
        } else {
            // Mantém o default para tipos desconhecidos ou outros
        }

        // Extrair confiança dos detalhes
        // A string de detalhes do servidor é como "Algum texto (Confiança: 91.6%)"
        const confidenceMatch = details.match(/\(Confiança:\s*(\d+\.?\d*)%\)/i);
        if (confidenceMatch && confidenceMatch[1]) {
            confidencePercent = parseFloat(confidenceMatch[1]);
        } else {
            console.warn(`[populateAlertsResultsList] Não foi possível extrair confiança dos detalhes: "${details}". Usando 50% como fallback.`);
            confidencePercent = 50; // Ou algum outro valor padrão
        }

        const formattedConfidence = parseFloat(confidencePercent.toFixed(1));
        const lataId = alert.lata_id || 'N/A';

        let formattedTimestamp = alert.timestamp; // Vem como ISO string
        try {
            // Tenta formatar para HH:MM:SS
            const dateObj = new Date(alert.timestamp);
            if (!isNaN(dateObj)) {
                 formattedTimestamp = `${String(dateObj.getHours()).padStart(2, '0')}:${String(dateObj.getMinutes()).padStart(2, '0')}:${String(dateObj.getSeconds()).padStart(2, '0')}`;
            }
        } catch (e) {
            console.warn("Erro ao formatar timestamp do alerta para HH:MM:SS:", alert.timestamp, e);
        }

        // Monta o HTML para o item da lista, seguindo seu layout
        itemDiv.innerHTML = `
            <div class="flex justify-between items-start">
                <div>
                    <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${primaryAnomalyTypeClass}">
                        <span class="status-indicator ${statusIndicatorClass} mr-1.5"></span>
                        ${typeText}
                    </span>
                    <p class="mt-1 text-sm font-medium">Lata #${lataId}</p>
                </div>
                <span class="text-xs text-gray-500">${formattedTimestamp}</span>
            </div>
            <div class="mt-2">
                <p class="text-xs text-gray-500">Confiança:</p>
                <div class="confidence-bar mt-1">
                    <div class="confidence-fill" style="width: ${formattedConfidence}%"></div>
                </div>
                <p class="text-xs text-right text-gray-500 mt-1">${formattedConfidence}%</p>
            </div>
        `;
        listElement.appendChild(itemDiv);
    });
}


// Função principal para atualizar o dashboard
async function updateDashboardValues() {
    console.log("Updating dashboard values...");
    try {
        const statsData = await fetchBasicApiStats(); // Alterado aqui
        const alertsApiResponse = await fetchApiAlertsHistory(5); // Pega os últimos 5 alertas para o dashboard

        if (statsData) {
            updateKpisAndStatus(statsData);
            updateCountBadges(statsData);
        }

        if (alertsApiResponse) {
            populateAlertsResultsList(alertsApiResponse);
        } else {
            // Limpa a lista se não houver dados ou erro
            populateAlertsResultsList({ alerts: [] }); // Passa um objeto com uma lista vazia de alertas
        }

    } catch (error) {
        console.error("Erro ao atualizar valores do dashboard:", error);
        // Poderia exibir uma mensagem de erro global no dashboard
        const statusMessageElement = document.getElementById('dashboard-status-message'); // Crie este elemento se desejar
        if (statusMessageElement) {
            statusMessageElement.textContent = `Erro ao carregar dados: ${error.message}`;
            statusMessageElement.className = 'text-red-500 text-center py-2';
        }
        // Garante que os valores sejam zerados ou mostrem N/A em caso de erro
        updateKpisAndStatus(null);
        updateCountBadges(null);
        populateAlertsResultsList({ alerts: [] });
    }
}

// Inicializa o dashboard quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => {
    // Verifica se estamos na página do dashboard antes de executar
    // Usar o ID do container principal do conteúdo do dashboard
    if (document.getElementById('dashboard-content')) {
        console.log("Initializing Dashboard Page for dynamic values...");
        updateDashboardValues(); // Carga inicial
        setInterval(updateDashboardValues, 5000); // Atualiza a cada 5 segundos (ajuste conforme necessário)
    }
});