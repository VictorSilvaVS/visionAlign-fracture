


async function fetchBasicApiStats() {
    try {
        const response = await fetch('/api/basic_stats');
        if (!response.ok) {
            console.error(`Erro ao buscar /api/basic_stats: ${response.status}`);
            return null;
        }

        return await response.json();
    } catch (error) {
        console.error('Erro em fetchBasicApiStats:', error);
        return null;
    }
}


async function fetchApiAlertsHistory(limit = 5) {
    try {

        const response = await fetch(`/api/alerts_history?per_page=${limit}&page=1`);
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ message: `Erro HTTP ${response.status}` }));
            throw new Error(errorData.message || `Falha ao buscar histórico de alertas: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error("Erro em fetchApiAlertsHistory:", error);
        throw error;
    }
}


function updateCanCounts(statsData) {
    const statNormal = document.getElementById('stat-normal');
    const statFallen = document.getElementById('stat-fallen');
    const statInverted = document.getElementById('stat-inverted');
    const statFracture = document.getElementById('stat-fracture');

    if (statsData) {
        if (statNormal) statNormal.textContent = (statsData.lata_normal !== undefined ? statsData.lata_normal : '--');
        if (statFallen) statFallen.textContent = (statsData.lata_tombada !== undefined ? statsData.lata_tombada : '--');
        if (statInverted) statInverted.textContent = (statsData.lata_invertida !== undefined ? statsData.lata_invertida : '--');
        if (statFracture) statFracture.textContent = (statsData.fracture !== undefined ? statsData.fracture : '--');

        // Atualiza resolução visual se disponível
        const resDisplay = document.getElementById('current-resolution-display');
        if (resDisplay && statsData.resolution) {
            resDisplay.textContent = `Resolução: ${statsData.resolution} @ ${statsData.fps ? statsData.fps.toFixed(1) : '--'} FPS`;
        }
    }
}


function updateRates(statsData) {
    const rateAcceptanceValue = document.getElementById('rate-acceptance-value');
    const rateAcceptanceBar = document.getElementById('rate-acceptance-bar');
    const rateErrorValue = document.getElementById('rate-error-value');
    const rateErrorBar = document.getElementById('rate-error-bar');

    if (statsData) {
        const normal = statsData.lata_normal || 0;
        const fallen = statsData.lata_tombada || 0;
        const inverted = statsData.lata_invertida || 0;
        const fracture = statsData.fracture || 0;
        const total = normal + fallen + inverted + fracture;

        if (total === 0) {
            // Se não tem dados ainda, não mostra 0.0% para não "piscar"
            if (rateAcceptanceValue) rateAcceptanceValue.textContent = '--%';
            if (rateAcceptanceBar) rateAcceptanceBar.style.width = '0%';
            if (rateErrorValue) rateErrorValue.textContent = '--%';
            if (rateErrorBar) rateErrorBar.style.width = '0%';
            return;
        }

        const acceptanceRate = (normal / total) * 100;
        const errorRate = ((fallen + inverted + fracture) / total) * 100;

        if (rateAcceptanceValue) rateAcceptanceValue.textContent = `${acceptanceRate.toFixed(1)}%`;
        if (rateAcceptanceBar) rateAcceptanceBar.style.width = `${acceptanceRate}%`;

        if (rateErrorValue) rateErrorValue.textContent = `${errorRate.toFixed(1)}%`;
        if (rateErrorBar) rateErrorBar.style.width = `${errorRate}%`;
    }
}


function populateRecentAlertsList(alertsApiResponse) {
    const listElement = document.getElementById('alerts-list');
    if (!listElement) {
        console.warn("Elemento 'alerts-list' não encontrado.");
        return;
    }

    listElement.innerHTML = '';

    const alerts = alertsApiResponse?.alerts;

    if (!alerts || alerts.length === 0) {
        listElement.innerHTML = '<p class="text-xs text-gray-400 text-center">Nenhum alerta recente.</p>';
        return;
    }

    alerts.forEach(alert => {
        const itemDiv = document.createElement('div');
        itemDiv.className = 'border-b border-gray-200 pb-2 last:border-b-0 last:pb-0';

        let typeText = alert.type || "Alerta Desconhecido";
        let statusIndicatorClass = "status-warning";
        let typeColorClass = "text-yellow-600";


        if (typeText.toLowerCase().includes("invertida")) {
            statusIndicatorClass = "status-offline";
            typeColorClass = "text-red-600";
        } else if (typeText.toLowerCase().includes("tombada")) {
            statusIndicatorClass = "status-warning";
            typeColorClass = "text-yellow-600";
        } else if (typeText.toLowerCase().includes("normal")) {

            statusIndicatorClass = "status-online";
            typeColorClass = "text-green-600";
        } else {

            statusIndicatorClass = "status-info";
            typeColorClass = "text-blue-600";
        }
        let formattedTimestamp = alert.timestamp;
        try {

            const dateObj = new Date(alert.timestamp);
            if (!isNaN(dateObj)) {
                formattedTimestamp = `${String(dateObj.getHours()).padStart(2, '0')}:${String(dateObj.getMinutes()).padStart(2, '0')}:${String(dateObj.getSeconds()).padStart(2, '0')}`;
            }
        } catch (e) {
            console.warn("Erro ao formatar timestamp do alerta para HH:MM:SS:", alert.timestamp, e);
        }
        itemDiv.innerHTML = `
            <div class="flex items-center text-xs text-gray-700">
                <span class="status-indicator ${statusIndicatorClass} mr-1"></span>
                <span class="font-semibold ${typeColorClass}">${typeText}:</span>
                <span class="ml-1 text-gray-600">${alert.details || 'Sem detalhes.'}</span>
                <span class="ml-auto text-gray-500">${formattedTimestamp}</span>
            </div>
        `;
        listElement.appendChild(itemDiv);
    });
}


function updateCameraStatuses(statsData) {

    const cameraStatuses = statsData?.camera_status || {};
    const cameraMap = {
        'cam-sec1': 'secondary1',
        'cam-sec2': 'secondary2',
        'cam-sec3': 'secondary3',
        'cam-sec4': 'secondary4',
        'cam-rej': 'rejection'
    };

    for (const uiId in cameraMap) {
        const apiId = cameraMap[uiId];
        const status = cameraStatuses[apiId] || 'unknown';
        const indicator = document.getElementById(`status-${uiId}-indicator`);
        const text = document.getElementById(`status-${uiId}-text`);
        if (indicator && text) {
            let statusText = 'Desconhecido';
            let statusClass = 'status-offline';

            if (status === 'online') {
                statusText = 'ONLINE';
                statusClass = 'status-online';
            } else if (status === 'offline') {
                statusText = 'SEM SINAL';
                statusClass = 'status-offline';
            } else if (status === 'processing') {
                statusText = 'REJEIÇÃO';
                statusClass = 'status-warning';
            }
            indicator.className = `status-indicator ${statusClass}`;
            text.innerHTML = `<span class="status-indicator ${statusClass} pulse"></span> ${statusText}`;
        }
    }
}

async function updateFractureRoi() {
    const statusText = document.getElementById('status-cam-rej-text');
    const timestamp = new Date().getTime();

    // --- SLOT 1: Feed ao vivo do ROI que o VisionFracture esta analisando ---
    const liveImg = document.getElementById('roi-img-1');
    const livePh = document.getElementById('roi-placeholder-1');
    const liveBadge = document.getElementById('roi-badge-1');

    if (liveImg && livePh) {
        const liveUrl = `/api/last_fracture_roi?v=${timestamp}&slot=1`;
        try {
            const response = await fetch(liveUrl);
            if (response.ok) {
                const blob = await response.blob();
                const blobUrl = URL.createObjectURL(blob);
                liveImg.src = blobUrl;
                liveImg.classList.remove('hidden');
                livePh.classList.add('hidden');
                
                // Captura informações de fratura dos headers
                const detected = response.headers.get('X-Fracture-Detected') === 'true';
                const count = response.headers.get('X-Fracture-Count') || '0';
                const area = response.headers.get('X-Fracture-Area-Px') || '0';
                
                if (liveBadge) {
                    if (detected) {
                        liveBadge.textContent = '🔴 FRATURA';
                        liveBadge.style.backgroundColor = '#EF4444'; // vermelho
                        liveBadge.title = `${count} máscaras, ${area}px`;
                    } else {
                        liveBadge.textContent = '✓ LIVE';
                        liveBadge.style.backgroundColor = '#3B82F6'; // azul
                        liveBadge.title = 'Analisando...';
                    }
                    liveBadge.style.opacity = '1';
                }
            } else {
                liveImg.classList.add('hidden');
                livePh.classList.remove('hidden');
                if (liveBadge) liveBadge.style.opacity = '0';
            }
        } catch (e) {
            console.error('Erro ao atualizar ROI ao vivo:', e);
            liveImg.classList.add('hidden');
            livePh.classList.remove('hidden');
            if (liveBadge) liveBadge.style.opacity = '0';
        }
    }

    // --- SLOTS 2-4: Ultimas fraturas salvas em disco ---
    let anyFracture = false;
    for (let i = 2; i <= 4; i++) {
        const roiImg = document.getElementById(`roi-img-${i}`);
        const placeholder = document.getElementById(`roi-placeholder-${i}`);
        const badge = document.getElementById(`roi-badge-${i}`);

        if (!roiImg || !placeholder) continue;

        try {
            const url = `/api/last_fracture_roi?v=${timestamp}&slot=${i}`;
            const testImg = new Image();
            testImg.onload = function () {
                if (roiImg.src && roiImg.src !== testImg.src && !roiImg.classList.contains('hidden')) {
                    if (badge) {
                        badge.textContent = 'FR';
                        badge.style.backgroundColor = '#EF4444'; // vermelho
                        badge.style.opacity = '1';
                        setTimeout(() => { badge.style.opacity = '0'; }, 5000);
                    }
                }
                roiImg.src = url;
                roiImg.classList.remove('hidden');
                placeholder.classList.add('hidden');
                anyFracture = true;
            };
            testImg.onerror = function () {
                roiImg.classList.add('hidden');
                placeholder.classList.remove('hidden');
                if (badge) badge.style.opacity = '0';
            };
            testImg.src = url;
        } catch (e) {
            console.error(`Erro ROI ${i}:`, e);
        }
    }

    if (statusText) {
        // Mostra LIVE se o modelo esta ativo, ALERTA se ha fratura recente
        if (anyFracture) {
            statusText.textContent = 'FRATURA';
            statusText.className = 'text-[9px] font-bold text-red-500 uppercase animate-pulse';
        } else {
            statusText.textContent = 'ANALISANDO';
            statusText.className = 'text-[9px] font-bold text-blue-400 uppercase';
        }
    }
}

function selectCamera(id) {
    const mainStream = document.getElementById('mainMonitorStream');
    const mainTitle = document.querySelector('h4.font-bold.text-gray-800');
    const container = document.getElementById('mainMonitorVideoContainer');

    if (!mainStream || !mainTitle) return;

    // Reset indicator classes on all mini-containers
    document.querySelectorAll('[id^="cam-sec"]').forEach(el => {
        el.classList.remove('ring-4', 'ring-blue-500', 'ring-opacity-50');
    });

    // Add selection highlight to the clicked container
    const selectedContainer = document.getElementById(`${id}-container`) || document.getElementById(`cam-sec${id.replace('cam', '')}-container`);
    if (selectedContainer) {
        selectedContainer.classList.add('ring-4', 'ring-blue-500', 'ring-opacity-50');
    }

    // Logic: In a real multi-feed system, we would change the src to /video_feed?cam=id
    // For now, we update the placeholder/title to show we are "selecting"
    let camName = "";
    switch (id) {
        case 'cam1': camName = "WASHER 22 - CÂMERA 01"; break;
        case 'cam2': camName = "WASHER 22 - CÂMERA 02"; break;
        case 'cam3': camName = "WASHER 23 - CÂMERA 03"; break;
        case 'cam4': camName = "WASHER 23 - CÂMERA 04"; break;
    }

    mainTitle.textContent = camName || "Câmera Principal";

    // Simula troca de fonte (no futuro o backend lidará com isso)
    // Se for a cam1 (ativa), mostra o feed real
    if (id === 'cam1') {
        const timestamp = new Date().getTime();
        mainStream.src = `/video_feed?v=${timestamp}`;
        mainStream.parentElement.classList.remove('opacity-50');
    } else {
        // Para as outras que estão "offline" no momento, mostramos um placeholder
        // ou avisamos que está sem sinal no main view
        mainStream.src = "";
        mainStream.classList.add('hidden');

        let placeholder = document.getElementById('mainMonitorPlaceholder');
        if (!placeholder) {
            placeholder = document.createElement('div');
            placeholder.id = 'mainMonitorPlaceholder';
            placeholder.className = 'absolute inset-0 flex flex-col items-center justify-center bg-gray-900 text-gray-500';
            placeholder.innerHTML = `<i class="fas fa-video-slash fa-3x mb-4"></i><span class="text-xl font-bold uppercase">Sem Sinal em ${camName}</span>`;
            mainStream.parentElement.appendChild(placeholder);
        } else {
            placeholder.classList.remove('hidden');
            placeholder.querySelector('span').textContent = `Sem Sinal em ${camName}`;
        }
    }
}

function expandRoi(id) {
    const modal = document.getElementById('roiModal');
    const modalImg = document.getElementById('expandedRoiImg');
    const modalTitle = document.getElementById('modalTitle');
    const sourceImg = document.getElementById(`roi-img-${id}`);

    if (modal && modalImg && sourceImg && !sourceImg.classList.contains('hidden')) {
        modalImg.src = sourceImg.src;
        modalTitle.textContent = `Visualização Detalhada - ROI 0${id}`;
        modal.style.display = 'flex';  // Usa display flex para melhor performance
        // Não bloqueia scroll - deixa a página responsiva e dinâmica
    }
}

function closeRoiModal() {
    const modal = document.getElementById('roiModal');
    if (modal) {
        modal.style.display = 'none';  // Usa display none para melhor performance
    }
}

function setupFullscreenVideo() {
    const videoElement = document.getElementById('mainMonitorStream');
    const videoContainer = document.getElementById('mainMonitorVideoContainer');
    const toggleFullscreenBtn = document.getElementById('toggleFullscreenButton');
    const fullscreenControls = document.getElementById('fullscreenControls');
    const saveTrainingFrameBtn = document.getElementById('saveTrainingFrameButton');
    const exitFullscreenBtnAlt = document.getElementById('exitFullscreenButtonAlt');

    if (!videoContainer || !videoElement || !toggleFullscreenBtn || !fullscreenControls || !exitFullscreenBtnAlt) {
        console.warn("Elementos básicos para tela cheia não encontrados.");
        return;
    }

    const icon = toggleFullscreenBtn.querySelector('i');
    let hideControlsTimeoutId = null;
    function showControlsAndSetHideTimeout() {
        const currentFullscreenEl = document.fullscreenElement || document.mozFullScreenElement || document.webkitFullscreenElement || document.msFullscreenElement;
        if (currentFullscreenEl !== videoContainer) {
            fullscreenControls.classList.add('hidden');
            fullscreenControls.classList.remove('flex');
            if (hideControlsTimeoutId) {
                clearTimeout(hideControlsTimeoutId);
                hideControlsTimeoutId = null;
            }
            return;
        }
        fullscreenControls.classList.remove('hidden');
        fullscreenControls.classList.add('flex');

        if (hideControlsTimeoutId) {
            clearTimeout(hideControlsTimeoutId);
        }

        hideControlsTimeoutId = setTimeout(() => {
            const stillCurrentFullscreenEl = document.fullscreenElement || document.mozFullScreenElement || document.webkitFullscreenElement || document.msFullscreenElement;
            if (stillCurrentFullscreenEl === videoContainer) {
                fullscreenControls.classList.add('hidden');
                fullscreenControls.classList.remove('flex');
            }
            hideControlsTimeoutId = null;
        }, 3000);
    }

    function enterFullscreenInternal() {

        if (!document.fullscreenElement &&
            !document.mozFullScreenElement &&
            !document.webkitFullscreenElement &&
            !document.msFullscreenElement) {

            if (videoContainer.requestFullscreen) {
                videoContainer.requestFullscreen();
            } else if (videoContainer.mozRequestFullScreen) {
                videoContainer.mozRequestFullScreen();
            } else if (videoContainer.webkitRequestFullscreen) {
                videoContainer.webkitRequestFullscreen();
            } else if (videoContainer.msRequestFullscreen) {
                videoContainer.msRequestFullscreen();
            }
        }
    }

    function exitFullscreenInternal() {
        if (document.exitFullscreen) {
            document.exitFullscreen();
        } else if (document.mozCancelFullScreen) {
            document.mozCancelFullScreen();
        } else if (document.webkitExitFullscreen) {
            document.webkitExitFullscreen();
        } else if (document.msExitFullscreen) {
            document.msExitFullscreen();
        }
    }

    toggleFullscreenBtn.addEventListener('click', () => {
        const currentFullscreenElement = document.fullscreenElement || document.mozFullScreenElement || document.webkitFullscreenElement || document.msFullscreenElement;
        if (!currentFullscreenElement) {
            enterFullscreenInternal();
        } else {
            exitFullscreenInternal();
        }
    });

    exitFullscreenBtnAlt.addEventListener('click', exitFullscreenInternal);
    videoContainer.addEventListener('mousemove', () => {
        const currentFullscreenEl = document.fullscreenElement || document.mozFullScreenElement || document.webkitFullscreenElement || document.msFullscreenElement;
        if (currentFullscreenEl === videoContainer) {
            showControlsAndSetHideTimeout();
        }
    });

    // Captura de frame removida daqui, agora tratada no index.html (unificado via API)

    if (saveTrainingFrameBtn) {
        saveTrainingFrameBtn.addEventListener('click', async () => {
            try {
                const response = await fetch('/api/save_training_frame', { method: 'POST' });
                const result = await response.json();
                if (result.success) {
                    alert(result.message);
                } else {
                    alert('Erro: ' + result.message);
                }
            } catch (error) {
                console.error("Erro ao salvar frame para treinamento:", error);
                alert("Erro de conexão ao tentar salvar frame.");
            }
        });
    }
    function updateUIForFullscreenState() {
        const currentFullscreenElement = document.fullscreenElement ||
            document.mozFullScreenElement ||
            document.webkitFullscreenElement ||
            document.msFullscreenElement;

        if (currentFullscreenElement === videoContainer) {
            icon.classList.remove('fa-expand');
            icon.classList.add('fa-compress');
            toggleFullscreenBtn.setAttribute('title', 'Sair da Tela Cheia');
            showControlsAndSetHideTimeout();
        } else {
            icon.classList.remove('fa-compress');
            icon.classList.add('fa-expand');
            toggleFullscreenBtn.setAttribute('title', 'Tela Cheia');
            fullscreenControls.classList.add('hidden');
            fullscreenControls.classList.remove('flex');
            if (hideControlsTimeoutId) {
                clearTimeout(hideControlsTimeoutId);
                hideControlsTimeoutId = null;
            }
        }
    }
    document.addEventListener('fullscreenchange', updateUIForFullscreenState);
    document.addEventListener('webkitfullscreenchange', updateUIForFullscreenState);
    document.addEventListener('mozfullscreenchange', updateUIForFullscreenState);
    document.addEventListener('MSFullscreenChange', updateUIForFullscreenState);
    updateUIForFullscreenState();
}
function updateTrend(statId, trendPercentage) {
    const statElement = document.getElementById(statId);
    if (!statElement) return;

    // O texto da tendência está em um span com classe 'stat-trend-text'
    // dentro do próximo parágrafo irmão do elemento de contagem.
    const trendTextElement = statElement.nextElementSibling?.querySelector('.stat-trend-text');

    if (trendTextElement) {
        if (trendPercentage === null || trendPercentage === undefined) {
            trendTextElement.textContent = "--%";
            trendTextElement.className = "stat-trend-text text-gray-400"; // Cor neutra
        } else {
            const roundedPercentage = parseFloat(trendPercentage).toFixed(1);
            let textToShow = "";
            let colorClass = "text-gray-400"; // Padrão neutro

            if (trendPercentage > 0) {
                textToShow = `+${roundedPercentage}%`;
                colorClass = "text-green-500"; // Tendência positiva
            } else if (trendPercentage < 0) {
                textToShow = `${roundedPercentage}%`; // O sinal negativo já vem no valor
                colorClass = "text-red-500";   // Tendência negativa
            } else {
                textToShow = `0.0%`;
            }
            trendTextElement.textContent = textToShow;
            trendTextElement.className = `stat-trend-text ${colorClass} font-bold`;
        }
    }
}

async function updateMonitorDashboard() {
    let newStatsData = null;
    let newAlertsApiResponse = null;
    let fetchSuccess = true;
    try {
        // Tenta pegar stats completas se for possível (apenas se for admin para evitar 405 no log)
        if (window.USER_ROLE === 'admin') {
            const response = await fetch('/api/stats');
            if (response.ok) {
                const contentType = response.headers.get("content-type");
                if (contentType && contentType.includes("application/octet-stream")) {
                    // Dados criptografados - precisamos descriptografar via API
                    const encryptedBlob = await response.blob();
                    const decryptResponse = await fetch('/api/decrypt', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/octet-stream' },
                        body: encryptedBlob
                    });

                    if (decryptResponse.ok) {
                        newStatsData = await decryptResponse.json();
                    } else {
                        console.error("Falha ao descriptografar stats, tentando basic_stats...");
                        newStatsData = await fetchBasicApiStats();
                    }
                } else {
                    newStatsData = await response.json();
                }
            } else {
                // Fallback para basic stats (usuários comuns)
                newStatsData = await fetchBasicApiStats();
            }
        } else {
            // Se for operador comum, vai direto no basic_stats
            newStatsData = await fetchBasicApiStats();
        }

        newAlertsApiResponse = await fetchApiAlertsHistory(5);
    } catch (error) {
        console.error("Erro durante o fetch de dados:", error);
        // Tenta pelo menos as basic stats se falhou
        if (!newStatsData) {
            try {
                newStatsData = await fetchBasicApiStats();
                newAlertsApiResponse = await fetchApiAlertsHistory(5);
                fetchSuccess = !!newStatsData;
            } catch (e) {
                fetchSuccess = false;
            }
        } else {
            fetchSuccess = false;
        }
    }

    if (fetchSuccess) {
        if (newStatsData) {
            updateCanCounts(newStatsData);
            updateRates(newStatsData);
            updateCameraStatuses(newStatsData);

            // Atualiza tendências se disponíveis
            updateTrend('stat-fracture', newStatsData.fracture_change_pct);
            updateTrend('stat-normal', newStatsData.lata_normal_change_pct);
            updateTrend('stat-fallen', newStatsData.lata_tombada_change_pct);
            updateTrend('stat-inverted', newStatsData.lata_invertida_change_pct);
        }
        if (newAlertsApiResponse && newAlertsApiResponse.alerts) {
            populateRecentAlertsList(newAlertsApiResponse);
        }
    }
}
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('monitor-content')) {
        console.log("Initializing Monitor Dashboard Page...");
        updateMonitorDashboard();
        setInterval(updateMonitorDashboard, 2000); // 2s para stats - CONTINUA MESMO COM MODAL ABERTO
        setInterval(updateFractureRoi, 800);       // ~1s para o ROI ao vivo - CONTINUA MESMO COM MODAL ABERTO
        setupFullscreenVideo();
        
        // <<<< NOVO: Listener para fechar modal com ESC e garantir updates contínuas >>>>
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                const modal = document.getElementById('roiModal');
                if (modal && modal.style.display === 'flex') {
                    closeRoiModal();
                    e.preventDefault();
                }
            }
        });
    }
});
console.log("monitor.js loaded for dynamic values");
