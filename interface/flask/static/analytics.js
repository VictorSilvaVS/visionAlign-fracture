// Variáveis globais para instâncias dos gráficos e estado da página
let classificationChartInstance = null;
let trendChartInstance = null;
let eventHistoryCurrentPage = 1;
const ALERTS_PER_PAGE = 15;
let currentAlertFilters = {
    start_date: '',
    end_date: '',
    type: '',
    lata_id: ''
};
async function fetchAnalyticsChartData(period) {
    console.log(`[Analytics] Buscando dados de gráficos para o período: ${period}`);
    try {
        const response = await fetch(`/api/detection_history?period=${period}`);
        if (!response.ok) {
            console.error(`[Analytics] Erro ao buscar dados de gráficos (${response.status}): ${await response.text()}`);
            return null;
        }
        const data = await response.json();
        console.log("[Analytics] Dados de gráficos recebidos:", data);
        return data;
    } catch (error) {
        console.error('[Analytics] Erro na função fetchAnalyticsChartData:', error);
        return null;
    }
}

/**
 * @param {string} containerId - ID do div container do gráfico.
 * @param {string} canvasId - ID que será dado ao elemento canvas.
 * @param {string} placeholderId - ID do div placeholder a ser removido.
 * @returns {CanvasRenderingContext2D|null} O contexto 2D do canvas ou null se falhar.
 */
function setupChartCanvas(containerId, canvasId, placeholderId) {
    const container = document.getElementById(containerId);
    if (!container) {
        console.error(`[Analytics] Container do gráfico '${containerId}' não encontrado.`);
        return null;
    }
    console.log(`[Analytics] Container '${containerId}' encontrado.`);

    // Configurar container com altura fixa
    container.style.height = '350px';
    container.style.maxHeight = '350px';
    container.style.width = '100%';
    container.style.position = 'relative';
    container.style.overflow = 'hidden';

    const placeholder = document.getElementById(placeholderId);
    if (placeholder) {
        placeholder.remove();
        console.log(`[Analytics] Placeholder '${placeholderId}' removido.`);
    }

    let canvas = document.getElementById(canvasId);
    if (!canvas) {
        console.log(`[Analytics] Canvas '${canvasId}' não existe. Criando...`);
        canvas = document.createElement('canvas');
        canvas.id = canvasId;
        canvas.style.display = 'block';
        canvas.style.maxHeight = '350px';
        canvas.style.height = '350px';
        canvas.style.width = '100%';
        container.appendChild(canvas);
        console.log(`[Analytics] Canvas '${canvasId}' criado e adicionado ao container '${containerId}'.`);
    } else {
        console.log(`[Analytics] Canvas '${canvasId}' já existe.`);
        canvas.style.display = 'block';
        canvas.style.maxHeight = '350px';
        canvas.style.height = '350px';
    }
    
    console.log(`[Analytics] HTML do container '${containerId}' após manipulação do canvas:`, container.innerHTML);

    const ctx = canvas.getContext('2d');
    if (!ctx) {
        console.error(`[Analytics] ERRO: Falha ao obter contexto 2D para '${canvasId}'. O canvas é válido?`);
        return null;
    }
    console.log(`[Analytics] Contexto 2D para '${canvasId}' obtido com sucesso.`);
    return ctx;
}


/**
 * Renderiza ou atualiza o gráfico de distribuição de classificação.
 */
function renderClassificationChart(apiData) {
    console.log("[Analytics] Iniciando renderClassificationChart...");
    const ctx = setupChartCanvas('classificationChartContainer', 'classificationChartCanvas', 'classificationChartPlaceholder');
    if (!ctx) return;

    if (!apiData || !apiData.detection_types || !apiData.detection_types.data || !apiData.detection_types.labels) {
        console.error("[Analytics] Dados de 'detection_types' ausentes ou incompletos para o gráfico de classificação.");
        document.getElementById('classificationChartContainer').innerHTML = '<div class="w-full h-full flex items-center justify-center bg-gray-50 rounded"><p class="text-gray-500">Dados indisponíveis.</p></div>';
        return;
    }
    
    console.log("[Analytics] Dados para ClassificationChart:", JSON.stringify(apiData.detection_types));
    const chartData = {
        labels: apiData.detection_types.labels,
        datasets: [{
            label: 'Distribuição',
            data: apiData.detection_types.data,
            backgroundColor: ['rgba(75, 192, 192, 0.7)', 'rgba(255, 99, 132, 0.7)', 'rgba(255, 206, 86, 0.7)'],
            borderColor: ['rgba(75, 192, 192, 1)', 'rgba(255, 99, 132, 1)', 'rgba(255, 206, 86, 1)'],
            borderWidth: 1
        }]
    };

    if (classificationChartInstance) {
        console.log("[Analytics] Destruindo instância antiga do ClassificationChart.");
        classificationChartInstance.destroy();
    }
    
    try {
        classificationChartInstance = new Chart(ctx, {
            type: 'pie',
            data: chartData,
            options: { 
                responsive: true, 
                maintainAspectRatio: false, 
                animation: { duration: 750 },
                plugins: { legend: { position: 'top' } } 
            }
        });
        if (classificationChartInstance) {
            console.log("[Analytics] ClassificationChartInstance CRIADO com SUCESSO.");
        } else {
            console.error("[Analytics] ERRO: ClassificationChartInstance NÃO FOI CRIADO (new Chart retornou falsy).");
        }
    } catch (e) {
        console.error("[Analytics] ERRO ao criar ClassificationChartInstance:", e);
    }
}

/**
 * Renderiza ou atualiza o gráfico de tendência de rejeições.
 */
function renderTrendChart(apiData) {
    console.log("[Analytics] Iniciando renderTrendChart...");
    const ctx = setupChartCanvas('trendChartContainer', 'trendChartCanvas', 'trendChartPlaceholder');
    if (!ctx) return;

    if (!apiData || !apiData.detections_per_hour || !apiData.detections_per_hour.labels || !apiData.detections_per_hour.rejections) {
        console.error("[Analytics] Dados de 'detections_per_hour' ausentes ou incompletos para o gráfico de tendência.");
        document.getElementById('trendChartContainer').innerHTML = '<div class="w-full h-full flex items-center justify-center bg-gray-50 rounded"><p class="text-gray-500">Dados indisponíveis.</p></div>';
        return;
    }

    console.log("[Analytics] Dados para TrendChart:", JSON.stringify(apiData.detections_per_hour));
    const chartData = {
        labels: apiData.detections_per_hour.labels,
        datasets: [
            {
                label: 'Rejeições',
                data: apiData.detections_per_hour.rejections,
                borderColor: 'rgba(255, 99, 132, 1)',
                backgroundColor: 'rgba(255, 99, 132, 0.5)',
                type: 'bar',
                yAxisID: 'yRejections',
            },
            {
                label: 'Total Detecções',
                data: apiData.detections_per_hour.totals,
                borderColor: 'rgba(54, 162, 235, 1)',
                type: 'line',
                fill: false,
                yAxisID: 'yTotals',
            }
        ]
    };

    if (trendChartInstance) {
        console.log("[Analytics] Destruindo instância antiga do TrendChart.");
        trendChartInstance.destroy();
    }

    try {
        trendChartInstance = new Chart(ctx, {
            type: 'bar',
            data: chartData,
            options: {
                responsive: true, 
                maintainAspectRatio: false,
                animation: { duration: 750 },
                scales: {
                    yRejections: { type: 'linear', display: true, position: 'left', title: { display: true, text: 'Rejeições' } },
                    yTotals: { type: 'linear', display: true, position: 'right', title: { display: true, text: 'Total' }, grid: { drawOnChartArea: false } }
                },
                plugins: { legend: { position: 'top' } }
            }
        });
        if (trendChartInstance) {
            console.log("[Analytics] TrendChartInstance CRIADO com SUCESSO.");
        } else {
            console.error("[Analytics] ERRO: TrendChartInstance NÃO FOI CRIADO (new Chart retornou falsy).");
        }
    } catch (e) {
        console.error("[Analytics] ERRO ao criar TrendChartInstance:", e);
    }
}

/**
 * Atualiza os KPIs na página.
 */
function updateKpis(kpiData) {
    console.log("[Analytics] Atualizando KPIs com dados:", kpiData);
    if (!kpiData) {
        console.warn("[Analytics] Dados de KPI não fornecidos para atualização.");
        return;
    }
    // Usar as novas chaves da API
    document.getElementById('kpiTotalDetections').textContent = kpiData.total_detections_last_hour ?? '--';
    document.getElementById('kpiErrorRate').textContent = kpiData.error_rate_last_hour !== undefined ? `${parseFloat(kpiData.error_rate_last_hour).toFixed(1)}%` : '--%';
    const errorRateBar = document.getElementById('kpiErrorRateBar');
    if (errorRateBar) errorRateBar.style.width = kpiData.error_rate_last_hour !== undefined ? `${parseFloat(kpiData.error_rate_last_hour).toFixed(1)}%` : '0%';
    document.getElementById('kpiAvgTime').textContent = kpiData.avg_processing_time_ms_last_hour ?? '--';
    console.log("[Analytics] KPIs atualizados.");
}

/**
 * Atualiza as Informações do Modelo na página.
 */
function updateModelInfo(modelInfoData) {
    console.log("[Analytics] Atualizando Model Info com dados:", modelInfoData);
    if (!modelInfoData) {
        console.warn("[Analytics] Dados de Model Info não fornecidos para atualização.");
        document.getElementById('modelVersion').textContent = '--';
        document.getElementById('lastTrained').textContent = '--';
        document.getElementById('datasetSize').textContent = '--';
        return;
    }
    document.getElementById('modelVersion').textContent = modelInfoData.version || '--';
    document.getElementById('lastTrained').textContent = modelInfoData.last_trained || '--';
    document.getElementById('datasetSize').textContent = modelInfoData.dataset_size || '--';
    console.log("[Analytics] Model Info atualizado.");
}
/**
 * Busca o histórico de eventos da API.
 */
async function fetchAlertsHistory(filters, page, perPage) {
    console.log(`[Analytics] Buscando histórico de eventos: page=${page}, perPage=${perPage}, filters:`, filters);
    const params = new URLSearchParams({
        page: page,
        per_page: perPage,
        start_date: filters.start_date || '',
        end_date: filters.end_date || '',
        type: filters.type || '',
        lata_id: filters.lata_id || ''
    });

    try {
        const response = await fetch(`/api/alerts_history?${params.toString()}`);
        if (!response.ok) {
            console.error(`[Analytics] Erro ao buscar histórico de eventos (${response.status}): ${await response.text()}`);
            return null;
        }
        const data = await response.json();
        console.log("[Analytics] Histórico de eventos recebido:", data);
        return data;
    } catch (error) {
        console.error('[Analytics] Erro na função fetchAlertsHistory:', error);
        return null;
    }
}

/**
 * Popula a tabela de histórico de eventos.
 */
function populateEventHistoryTable(alerts) {
    const tableBody = document.getElementById('eventHistoryTableBody');
    if (!tableBody) {
        console.error("[Analytics] Elemento 'eventHistoryTableBody' não encontrado.");
        return;
    }
    console.log("[Analytics] eventHistoryTableBody encontrado. Limpando conteúdo...");
    tableBody.innerHTML = ''; 

    if (!alerts || alerts.length === 0) {
        console.log("[Analytics] Nenhum alerta para exibir na tabela.");
        tableBody.innerHTML = '<tr><td colspan="4" class="px-6 py-4 text-center text-sm text-gray-500">Nenhum evento encontrado.</td></tr>';
        return;
    }

    console.log(`[Analytics] Populando tabela de eventos com ${alerts.length} alertas.`);
    alerts.forEach(alert => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-700">${alert.timestamp || '--'}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-700">${alert.type || '--'}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-700">${alert.lata_id || '--'}</td>
            <td class="px-6 py-4 text-sm text-gray-700 break-all">${alert.details || '--'}</td>
        `;
        tableBody.appendChild(row);
    });
    console.log(`[Analytics] Tabela de eventos populada. Número de linhas adicionadas: ${tableBody.rows.length}`);
}

/**
 * Renderiza os controles de paginação.
 */
function renderPaginationControls(paginationData) {
    const paginationControls = document.getElementById('paginationControls');
    const paginationInfo = document.getElementById('paginationInfo');
    if (!paginationControls || !paginationInfo) {
        console.error("[Analytics] Elementos de paginação 'paginationControls' ou 'paginationInfo' não encontrados.");
        return;
    }
    console.log("[Analytics] Elementos de paginação encontrados.");

    console.log("[Analytics] Renderizando controles de paginação com:", JSON.stringify(paginationData));
    paginationControls.innerHTML = '';
    if (!paginationData || paginationData.total_pages <= 1) {
        paginationInfo.textContent = `Mostrando ${paginationData.total_items || 0} resultados.`;
        console.log("[Analytics] Paginação não necessária ou dados insuficientes.");
        return;
    }

    const { page, total_pages, total_items } = paginationData;
    paginationInfo.textContent = `Página ${page} de ${total_pages} (${total_items} resultados).`;

    const prevButton = document.createElement('button');
    prevButton.innerHTML = '<i class="fas fa-chevron-left"></i>';
    prevButton.className = "px-3 py-1 border rounded-md text-sm hover:bg-gray-100 disabled:opacity-50";
    prevButton.disabled = page <= 1;
    prevButton.addEventListener('click', () => {
        if (page > 1) loadEventHistory(page - 1);
    });
    paginationControls.appendChild(prevButton);

    const nextButton = document.createElement('button');
    nextButton.innerHTML = '<i class="fas fa-chevron-right"></i>';
    nextButton.className = "px-3 py-1 border rounded-md text-sm hover:bg-gray-100 disabled:opacity-50";
    nextButton.disabled = page >= total_pages;
    nextButton.addEventListener('click', () => {
        if (page < total_pages) loadEventHistory(page + 1);
    });
    paginationControls.appendChild(nextButton);
    console.log("[Analytics] Controles de paginação renderizados. Conteúdo:", paginationControls.innerHTML);
}

/**
 * Carrega e exibe o histórico de eventos para uma página específica.
 */
async function loadEventHistory(pageNum = 1) {
    eventHistoryCurrentPage = pageNum;
    console.log(`[Analytics] loadEventHistory chamado para página: ${pageNum} com filtros:`, currentAlertFilters);
    const historyData = await fetchAlertsHistory(currentAlertFilters, eventHistoryCurrentPage, ALERTS_PER_PAGE);
    if (historyData && historyData.alerts) {
        populateEventHistoryTable(historyData.alerts);
        if (historyData.pagination) {
            renderPaginationControls(historyData.pagination);
        } else {
            console.warn("[Analytics] Dados de paginação ausentes na resposta de fetchAlertsHistory.");
            renderPaginationControls({ page: 1, total_pages: 1, total_items: historyData.alerts.length });
        }
    } else {
        console.error("[Analytics] Falha ao carregar histórico de eventos ou dados de alertas ausentes.");
        populateEventHistoryTable([]); 
        renderPaginationControls({ page: 1, total_pages: 1, total_items: 0 });
    }
}

/**
 * Inicializa os listeners e funcionalidades do modal de filtro.
 */
function initializeFilterModal() {
    const openBtn = document.getElementById('openFilterModalBtn');
    const closeBtn = document.getElementById('closeFilterModalBtn');
    const modal = document.getElementById('filterModal');
    const filterForm = document.getElementById('filterForm');
    const clearFiltersBtn = document.getElementById('clearFiltersBtn');

    if (!openBtn || !closeBtn || !modal || !filterForm || !clearFiltersBtn) {
        console.error("[Analytics] Elementos do modal de filtro não encontrados (openFilterModalBtn, closeFilterModalBtn, filterModal, filterForm, ou clearFiltersBtn).");
        return;
    }
    console.log("[Analytics] Elementos do modal de filtro encontrados e listeners sendo adicionados.");

    openBtn.addEventListener('click', () => modal.classList.remove('hidden'));
    closeBtn.addEventListener('click', () => modal.classList.add('hidden'));
    modal.addEventListener('click', (e) => { 
        if (e.target === modal) modal.classList.add('hidden');
    });

    filterForm.addEventListener('submit', (e) => {
        e.preventDefault();
        console.log("[Analytics] Formulário de filtro submetido.");
        currentAlertFilters.start_date = document.getElementById('filterStartDate').value;
        currentAlertFilters.end_date = document.getElementById('filterEndDate').value;
        currentAlertFilters.type = document.getElementById('filterEventType').value;
        currentAlertFilters.lata_id = document.getElementById('filterLataId').value;
        modal.classList.add('hidden');
        loadEventHistory(1); 
    });

    clearFiltersBtn.addEventListener('click', () => {
        console.log("[Analytics] Botão Limpar Filtros clicado.");
        filterForm.reset();
        currentAlertFilters = { start_date: '', end_date: '', type: '', lata_id: '' };
        // Opcional: recarregar imediatamente após limpar
        // loadEventHistory(1); 
    });
}

/**
 * Exporta o histórico de eventos.
 */
async function exportEventHistory() {
    console.log("[Analytics] Solicitando exportação do histórico de eventos com filtros:", currentAlertFilters);
    const params = new URLSearchParams({
        start_date: currentAlertFilters.start_date || '',
        end_date: currentAlertFilters.end_date || '',
        type: currentAlertFilters.type || '',
        lata_id: currentAlertFilters.lata_id || ''
    });

    try {
        const response = await fetch(`/api/export_event_history?${params.toString()}`);
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ message: 'Erro desconhecido na exportação.' }));
            console.error(`[Analytics] Erro ao exportar histórico (${response.status}):`, errorData.message);
            alert(`Falha na exportação: ${errorData.message}`);
            return;
        }

        const blob = await response.blob();
        const disposition = response.headers.get('content-disposition');
        let filename = 'historico_eventos.xlsx';
        if (disposition && disposition.indexOf('attachment') !== -1) {
            const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
            const matches = filenameRegex.exec(disposition);
            if (matches != null && matches[1]) {
                filename = matches[1].replace(/['"]/g, '');
            }
        }

        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
        console.log("[Analytics] Exportação do histórico de eventos iniciada.");

    } catch (error) {
        console.error('[Analytics] Erro na função exportEventHistory:', error);
        alert('Erro de conexão ao tentar exportar o histórico.');
    }
}


/**
 * Função principal de inicialização para a página de Analytics.
 */
async function initializeAnalyticsPage() {
    console.log("[Analytics] Iniciando initializeAnalyticsPage (analytics.js)...");

    if (typeof Chart === 'undefined') {
        console.error("[Analytics] ERRO CRÍTICO: Chart.js não está carregado! Verifique a inclusão da biblioteca.");
        // Adicionar uma mensagem visível para o usuário na página
        const body = document.querySelector('body');
        if (body) {
            const errorDiv = document.createElement('div');
            errorDiv.innerHTML = '<p style="color: red; background: white; padding: 10px; text-align: center; font-weight: bold;">Erro: A biblioteca de gráficos (Chart.js) não pôde ser carregada. Os gráficos não funcionarão.</p>';
            body.prepend(errorDiv);
        }
        return; // Interrompe a inicialização se Chart.js não estiver disponível
    }
    console.log("[Analytics] Chart.js está carregado.");

    const classificationPeriodSelect = document.getElementById('classificationPeriodSelect');
    const trendPeriodSelect = document.getElementById('trendPeriodSelect');
    const exportAlertsBtn = document.getElementById('exportAlertsBtn');

    console.log("[Analytics] Configurando listeners para classificationPeriodSelect...");
    if (classificationPeriodSelect) {
        classificationPeriodSelect.addEventListener('change', async () => {
            console.log("[Analytics] classificationPeriodSelect mudou.");
            const selectedPeriod = classificationPeriodSelect.value;
            const apiData = await fetchAnalyticsChartData(selectedPeriod);
            if (apiData) {
                renderClassificationChart(apiData);
                updateKpis(apiData.kpis); // Passa a sub-chave kpis
                updateModelInfo(apiData.model_info); // Passa a sub-chave model_info
            }
        });
        console.log("[Analytics] Carregando dados iniciais para gráfico de classificação...");
        const initialClassificationData = await fetchAnalyticsChartData(classificationPeriodSelect.value);
        if (initialClassificationData) {
            renderClassificationChart(initialClassificationData);
            updateKpis(initialClassificationData.kpis);
            updateModelInfo(initialClassificationData.model_info);
        }
    } else {
        console.error("[Analytics] Elemento 'classificationPeriodSelect' não encontrado.");
    }

    console.log("[Analytics] Configurando listeners para trendPeriodSelect...");
    if (trendPeriodSelect) {
        trendPeriodSelect.addEventListener('change', async () => {
            console.log("[Analytics] trendPeriodSelect mudou.");
            const selectedPeriod = trendPeriodSelect.value;
            const apiData = await fetchAnalyticsChartData(selectedPeriod);
            if (apiData) renderTrendChart(apiData);
        });
        console.log("[Analytics] Carregando dados iniciais para gráfico de tendência...");
        const initialTrendData = await fetchAnalyticsChartData(trendPeriodSelect.value);
        if (initialTrendData) renderTrendChart(initialTrendData);
    } else {
        console.error("[Analytics] Elemento 'trendPeriodSelect' não encontrado.");
    }

    console.log("[Analytics] Carregando histórico de eventos inicial...");
    loadEventHistory(1);

    console.log("[Analytics] Inicializando modal de filtro...");
    initializeFilterModal();

    console.log("[Analytics] Configurando botão de exportar...");
    if (exportAlertsBtn) {
        exportAlertsBtn.addEventListener('click', exportEventHistory);
        console.log("[Analytics] Listener do botão de exportar configurado.");
    } else {
        console.error("[Analytics] Elemento 'exportAlertsBtn' não encontrado.");
    }

    console.log("[Analytics] Página de Analytics completamente inicializada.");
}