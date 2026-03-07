// ========================================================================
// Variáveis Globais e Constantes
// ========================================================================
let inactivityTimer;
let statsInterval;
// Variáveis globais para guardar o estado anterior das estatísticas (para cálculo de tendência)
let previousStats = { lata_normal: 0, lata_invertida: 0, lata_tombada: 0 };
// Variável para guardar o tempo de início do script (para timestamp do vídeo se necessário)
let scriptLoadTime = Date.now();
const inactivityTime = 5 * 60 * 1000; // 5 minutos em milissegundos
let analyticsIntervalRef = null; // <<< NOVO: Referência para o intervalo do analytics.js
let isModalStreamPaused = false; // State for modal video pause
let originalModalStreamSrc = ''; // To store the original stream URL

// ========================================================================
// Funções Auxiliares
// ========================================================================

function showMessage(elementId, message, isError = false) {
    const element = document.getElementById(elementId);
    if (!element) return;
    element.textContent = message;
    element.className = isError ? 'error-message' : 'status-message'; // Reusa as classes CSS
    element.style.display = message ? 'block' : 'none';
}

function formatUptime(totalSeconds) {
    if (totalSeconds < 0 || isNaN(totalSeconds)) {
        return "00:00:00";
    }
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

function resetInactivityTimer() {
    clearTimeout(inactivityTimer);
    // Só reinicia o timer se estivermos em uma página que requer logout por inatividade
    if (document.getElementById('settings-display') || document.getElementById('login-form')) {
        // console.log("Resetting inactivity timer.");
        inactivityTimer = setTimeout(() => {
            console.log("Inatividade detectada. Deslogando...");
            window.location.href = '/logout';
        }, inactivityTime);
    }
}

// ========================================================================
// Lógica da Página de Login
// ========================================================================

function initializeLoginPage() {
    console.log("Initializing Login Page...");
    // Garante que o timer de inatividade comece assim que a página de login é carregada
    resetInactivityTimer();

    const loginForm = document.getElementById('login-form');
    if (!loginForm) {
        console.error("Elemento 'login-form' não encontrado.");
        return;
    }

    loginForm.addEventListener('submit', async (event) => {
        event.preventDefault(); // Impede o envio padrão do formulário

        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;

        showMessage('error-message', ''); // Limpa mensagens anteriores

        try {
            const response = await fetch('/api/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ username, password }),
            });

            const data = await response.json();

            if (response.ok && data.success) {
                // Login bem-sucedido, redireciona para a página principal
                window.location.href = '/';
            } else {
                // Exibe mensagem de erro
                showMessage('error-message', data.message || 'Erro desconhecido no login.', true);
            }
        } catch (error) {
            console.error('Erro ao tentar fazer login:', error);
            showMessage('error-message', 'Erro de conexão ao tentar fazer login.', true);
        }
    });
    console.log("Login form listener added.");
}

// ========================================================================
// Lógica da Página Principal (Index)
// ========================================================================

// let settingsDisplay; // <<< REMOVIDO: Textarea não existe mais
// let getSettingsButton; // <<< REMOVIDO: Botão não existe mais
// let editSettingsButton; // <<< REMOVIDO: Botão não existe mais
// let updateSettingsButton; // <<< REMOVIDO: Botão não existe mais
let videoStreamElement;
let videoModal;
let modalVideoStreamElement;
let closeModalBtn;
let statNormal;
let statInverted;
let statFallen;
let statFracture;
let statFps;
let videoTimestamp; // Para o overlay do vídeo
let videoResolution; // Para o overlay do vídeo
let systemTime; // Para o rodapé
let systemLoad; // Para o rodapé (será placeholder)
let extractFrameBtn; // Botão de extrair frame
let exportDataBtn; // Botão de exportar dados
let streamSnapshotBtn; // Botão de snapshot do stream
let streamFullscreenBtn; // Botão de fullscreen do stream
let modalSnapshotBtn; // Snapshot button inside the modal

// <<< NOVOS: Elementos da página de Monitoramento (index.html) >>>
let statFallenValue; // Elemento para valor de latas tombadas
let statInvertedValue; // Elemento para valor de latas invertidas
let rateAcceptanceValue, rateAcceptanceBar;
let rateFallenValue, rateFallenBar;
let rateInvertedValue, rateInvertedBar;
let alertsList; // Container para a lista de alertas
let statusCamSec1Text, statusCamSec1Indicator;
let statusCamSec2Text, statusCamSec2Indicator;
let statusCamRejText, statusCamRejIndicator;
let modalPauseResumeBtn; // Pause/Resume button inside the modal

// <<< NOVOS: Referências para os botões da página de settings >>>
let saveSettingsBtn;
let cancelSettingsBtn;

async function fetchAndUpdateStats() {
    // Só executa se estivermos na página principal (onde os elementos existem)
    if (!statNormal) {
        // console.log("Not on index page, skipping stats fetch.");
        return;
    }
    // console.log("Fetching stats...");
    try {
        // Chamar /api/basic_stats que retorna JSON não criptografado
        const response = await fetch('/api/basic_stats');
        if (!response.ok) {
            console.error(`Erro ao buscar /api/basic_stats: ${response.status}`);
            // Limpar os campos ou mostrar N/A em caso de erro
            if (statNormal) statNormal.textContent = '--';
            if (statFallenValue) statFallenValue.textContent = '--';
            if (statInvertedValue) statInvertedValue.textContent = '--';
            // ... limpar outros campos relevantes ...
            return;
        }

        const stats = await response.json(); // Dados já são JSON

        // --- Atualiza Stats Grid ---
        if (statFracture) statFracture.textContent = stats.fracture ?? '--';
        if (statNormal) statNormal.textContent = stats.lata_normal ?? '--';
        if (statFallen) statFallen.textContent = stats.lata_tombada ?? '--'; // Usando statFallen ao invés de statFallenValue para consistência com init
        if (statInverted) statInverted.textContent = stats.lata_invertida ?? '--';

        if (statFps) statFps.textContent = stats.fps ? stats.fps.toFixed(1) : '--';

        // --- Atualiza Tendências ---
        // Assumindo que a API retornará pct de mudança eventualmente
        updateTrend('stat-fracture', stats.fracture_change_pct);
        updateTrend('stat-normal', stats.lata_normal_change_pct);
        updateTrend('stat-fallen', stats.lata_tombada_change_pct);
        updateTrend('stat-inverted', stats.lata_invertida_change_pct);

        // Atualiza FPS (sem cálculo de tendência complexo por enquanto)
        // Se você tiver um elemento para a tendência do FPS, você pode chamá-lo aqui:
        // Exemplo: updateFPSTrend(stats.fps_trend_value); // Uma nova função específica para FPS se necessário
        // A função updateTrend original (com isFps flag) era para uma estrutura HTML diferente.
        // For now, we assume FPS trend is not displayed in the same way as can counts.
        // If you need to update FPS trend similar to the old way:
        /*
        const fpsTrendElement = document.getElementById('stat-fps-trend'); // Assuming an ID for FPS trend text
        if (fpsTrendElement && stats.fps_trend_text) { // Assuming API provides 'fps_trend_text'
            fpsTrendElement.textContent = stats.fps_trend_text;
            // Add color classes based on trend if needed
        }
        */

        // --- Calcula e Atualiza Taxas de Aceitação/Erro ---
        // Não é possível calcular taxas detalhadas com basic_stats
        const acceptanceRate = 0; // Placeholder
        const fallenRate = 0; // Placeholder
        const invertedRate = 0; // Placeholder

        if (rateAcceptanceValue) rateAcceptanceValue.textContent = `${acceptanceRate.toFixed(1)}%`;
        if (rateAcceptanceBar) rateAcceptanceBar.style.width = `${acceptanceRate}%`;
        if (rateFallenValue) rateFallenValue.textContent = `${fallenRate.toFixed(1)}%`;
        if (rateFallenBar) rateFallenBar.style.width = `${fallenRate}%`;
        if (rateInvertedValue) rateInvertedValue.textContent = `${invertedRate.toFixed(1)}%`;
        if (rateInvertedBar) rateInvertedBar.style.width = `${invertedRate}%`;

        // --- Atualiza Status das Câmeras ---
        // updateCameraStatus(null); // Status de câmera não vêm de basic_stats

        // Guarda os stats atuais para a próxima comparação
        previousStats = {
            fracture: stats.fracture || 0,
            lata_normal: stats.lata_normal || 0,
            lata_invertida: stats.lata_invertida || 0,
            lata_tombada: stats.lata_tombada || 0,
            fps: stats.fps || 0
        };

        // --- Atualiza Video Overlay ---
        if (videoResolution) {
            videoResolution.textContent = 'N/A'; // Resolução não vem de basic_stats
        }
        // Usar o tempo de atividade do sistema como timestamp do vídeo por simplicidade
        if (videoTimestamp) {
            // Poderia usar stats.system_uptime_seconds se preferir o tempo do backend
            const elapsedSeconds = Math.floor((Date.now() - scriptLoadTime) / 1000);
            videoTimestamp.textContent = formatUptime(elapsedSeconds);
        }

        // --- Atualiza Footer System Info ---
        if (systemTime) { // Uptime não vem de basic_stats
            systemTime.textContent = formatUptime(0); // Ou algum placeholder
        }
        if (systemLoad) {
            // CPU/RAM é complexo de obter remotamente de forma confiável, usamos placeholder
            systemLoad.textContent = "CPU/RAM: N/A";
        }
    } catch (error) {
        console.error('Erro na requisição de stats:', error);
    }
}

async function fetchSettings() {
    console.log("[fetchSettings] Start");
    showMessage('status-message', 'Carregando configurações...');
    try {
        console.log("[fetchSettings] Calling fetch('/api/settings')...");
        // 1. Buscar dados criptografados
        const response = await fetch('/api/settings');
        if (!response.ok) {
            // Se for erro 401 (Não autorizado), redireciona para login
            if (response.status === 401) {
                window.location.href = '/login';
                return;
            }
            console.error(`[fetchSettings] Fetch failed with status: ${response.status}`);
            throw new Error(`Erro HTTP: ${response.status}`);
        }
        console.log("[fetchSettings] Encrypted data received, attempting to decrypt via /api/decrypt...");

        // 2. Enviar dados criptografados para /api/decrypt
        const encryptedData = await response.blob(); // Ou response.text() se for base64, mas octet-stream é melhor com blob/arrayBuffer
        const decryptResponse = await fetch('/api/decrypt', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/octet-stream' // Enviar como bytes crus
            },
            body: encryptedData
        });

        if (!decryptResponse.ok) {
            const errorData = await decryptResponse.json().catch(() => ({ message: 'Erro desconhecido na descriptografia' }));
            console.error(`[fetchSettings] Decryption failed: ${decryptResponse.status}`, errorData);
            throw new Error(errorData.message || `Erro ao descriptografar: ${decryptResponse.status}`);
        }

        // 3. Usar os dados JSON descriptografados
        const settings = await decryptResponse.json();
        console.log("[fetchSettings] Decryption successful, JSON parsed:", settings);

        // Atualiza a UI (agora o formulário estruturado)
        // settingsDisplay.value = JSON.stringify(settings, null, 4); // <<< REMOVIDO
        // settingsDisplay.readOnly = true; // <<< REMOVIDO
        populateStructuredSettingsForm(settings); // <<< NOVO: Popula o form estruturado
        if (saveSettingsBtn) saveSettingsBtn.disabled = false; // Habilita salvar após carregar
        showMessage('status-message', 'Configurações carregadas.');
        console.log("[fetchSettings] UI updated.");
        resetInactivityTimer(); // Reseta timer ao carregar
    } catch (error) {
        console.error('Erro ao buscar configurações:', error);
        showMessage('status-message', `Erro ao carregar configurações: ${error.message}`, true);
    }
}

// <<<< Funções auxiliares de conversão de cores >>>>
function rgbToHex(rgbArray) {
    if (!Array.isArray(rgbArray) || rgbArray.length !== 3) {
        return '#000000';
    }
    const r = Math.round(rgbArray[0]) & 0xFF;
    const g = Math.round(rgbArray[1]) & 0xFF;
    const b = Math.round(rgbArray[2]) & 0xFF;
    return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, '0').toUpperCase()}`;
}

function hexToRgb(hexStr) {
    const hex = hexStr.replace('#', '');
    if (hex.length !== 6) {
        return [0, 0, 0];
    }
    return [
        parseInt(hex.substring(0, 2), 16),
        parseInt(hex.substring(2, 4), 16),
        parseInt(hex.substring(4, 6), 16)
    ];
}

// <<< NOVO: Função para popular o formulário estruturado >>>
// <<< MODIFICADO: Para usar os novos IDs e estrutura, INCLUINDO colors e styles >>>
function populateStructuredSettingsForm(settings) {
    console.log("[populateStructuredSettingsForm] Populating form with:", settings);

    // IA Thresholds
    const thresholdNormalInput = document.getElementById('setting-threshold-normal');
    const thresholdFallenInput = document.getElementById('setting-threshold-fallen');
    const thresholdInvertedInput = document.getElementById('setting-threshold-inverted');
    const thresholdFractureInput = document.getElementById('setting-threshold-fracture');
    const iouInput = document.getElementById('setting-iou');

    if (thresholdNormalInput) thresholdNormalInput.value = settings?.AI_PARAMS?.thresholds?.lata_normal ?? 0.90;
    if (thresholdFallenInput) thresholdFallenInput.value = settings?.AI_PARAMS?.thresholds?.lata_tombada ?? 0.85;
    if (thresholdInvertedInput) thresholdInvertedInput.value = settings?.AI_PARAMS?.thresholds?.lata_invertida ?? 0.95;
    if (thresholdFractureInput) thresholdFractureInput.value = settings?.AI_PARAMS?.thresholds?.fracture ?? 0.80;
    if (iouInput) iouInput.value = settings?.AI_PARAMS?.iou_default ?? 0.5;

    // Video Source
    const sourceTypeSelect = document.getElementById('setting-source-type');
    const sourceParamInput = document.getElementById('setting-source-param');
    if (sourceTypeSelect) {
        sourceTypeSelect.value = settings?.VIDEO_PARAMS?.source_type ?? 'video'; // Default to video if missing
    }
    if (sourceParamInput) {
        sourceParamInput.value = settings?.VIDEO_PARAMS?.source_param ?? '';
    }

    // Camera Settings (if applicable)
    const resolutionSelect = document.getElementById('setting-camera-resolution');
    const fpsSelect = document.getElementById('setting-camera-fps');
    if (resolutionSelect) resolutionSelect.value = settings?.VIDEO_PARAMS?.resolution ?? '';
    if (fpsSelect) fpsSelect.value = settings?.VIDEO_PARAMS?.fps ?? '';

    // Pre-processing
    const gammaInput = document.getElementById('setting-gamma');
    const claheCheckbox = document.getElementById('setting-clahe');
    if (gammaInput) gammaInput.value = settings?.AI_PARAMS?.advanced?.gamma ?? 0.8;
    if (claheCheckbox) claheCheckbox.checked = settings?.AI_PARAMS?.advanced?.clahe_enabled ?? true;

    // Drawing Customization
    const drawThicknessInput = document.getElementById('setting-draw-thickness');
    const drawFontScaleInput = document.getElementById('setting-draw-font-scale');
    const drawFontThicknessInput = document.getElementById('setting-draw-font-thickness');
    const drawShowLabelCheckbox = document.getElementById('setting-draw-show-label');
    const drawShowConfCheckbox = document.getElementById('setting-draw-show-conf');
    const drawShowBgCheckbox = document.getElementById('setting-draw-show-bg');

    if (drawThicknessInput) drawThicknessInput.value = settings?.AI_PARAMS?.advanced?.drawing?.box_thickness ?? 2;
    if (drawFontScaleInput) drawFontScaleInput.value = settings?.AI_PARAMS?.advanced?.drawing?.font_scale ?? 0.5;
    if (drawFontThicknessInput) drawFontThicknessInput.value = settings?.AI_PARAMS?.advanced?.drawing?.font_thickness ?? 1;
    if (drawShowLabelCheckbox) drawShowLabelCheckbox.checked = settings?.AI_PARAMS?.advanced?.drawing?.show_label ?? true;
    if (drawShowConfCheckbox) drawShowConfCheckbox.checked = settings?.AI_PARAMS?.advanced?.drawing?.show_conf ?? true;
    if (drawShowBgCheckbox) drawShowBgCheckbox.checked = settings?.AI_PARAMS?.advanced?.drawing?.show_bg ?? true;

    // <<<< NOVO: Cores de Detecção >>>>
    const colorLataNormalPicker = document.getElementById('color-lata-normal');
    const colorLataNormalText = document.getElementById('color-lata-normal-text');
    const colorLataInvertidaPicker = document.getElementById('color-lata-invertida');
    const colorLataInvertidaText = document.getElementById('color-lata-invertida-text');
    const colorLataTombadaPicker = document.getElementById('color-lata-tombada');
    const colorLataTombadaText = document.getElementById('color-lata-tombada-text');
    const colorFracturePicker = document.getElementById('color-fracture');
    const colorFractureText = document.getElementById('color-fracture-text');

    // Carregar cores: converter RGB [R,G,B] para HEX
    const defalto_lata_normal = rgbToHex(settings?.COLORS?.detection?.lata_normal ?? [0, 255, 0]);
    const defalto_lata_invertida = rgbToHex(settings?.COLORS?.detection?.lata_invertida ?? [0, 0, 255]);
    const defalto_lata_tombada = rgbToHex(settings?.COLORS?.detection?.lata_tombada ?? [255, 165, 0]);
    const defalto_fracture = rgbToHex(settings?.COLORS?.detection?.fracture ?? [0, 0, 255]);

    if (colorLataNormalPicker) {
        colorLataNormalPicker.value = defalto_lata_normal.toLowerCase();
        if (colorLataNormalText) colorLataNormalText.value = defalto_lata_normal;
    }
    if (colorLataInvertidaPicker) {
        colorLataInvertidaPicker.value = defalto_lata_invertida.toLowerCase();
        if (colorLataInvertidaText) colorLataInvertidaText.value = defalto_lata_invertida;
    }
    if (colorLataTombadaPicker) {
        colorLataTombadaPicker.value = defalto_lata_tombada.toLowerCase();
        if (colorLataTombadaText) colorLataTombadaText.value = defalto_lata_tombada;
    }
    if (colorFracturePicker) {
        colorFracturePicker.value = defalto_fracture.toLowerCase();
        if (colorFractureText) colorFractureText.value = defalto_fracture;
    }

    // Update range slider value displays
    document.querySelectorAll('.range-slider').forEach(updateRangeValueDisplay);
    console.log("[populateStructuredSettingsForm] Form populated.");

    // Zonas de Exclusão
    const exclusionZones = settings?.AI_PARAMS?.advanced?.exclusion_zones || [];
    renderExclusionZones(exclusionZones);

    // Dataset Collection
    const collectEnabledCheckbox = document.getElementById('setting-collect-enabled');
    const collectOnEventCheckbox = document.getElementById('setting-collect-on-event');
    const collectIntervalInput = document.getElementById('setting-collect-interval');
    const collectRetentionInput = document.getElementById('setting-collect-retention');
    const collectDistrustMinInput = document.getElementById('setting-collect-distrust-min');
    const collectDistrustMaxInput = document.getElementById('setting-collect-distrust-max');

    if (collectEnabledCheckbox) collectEnabledCheckbox.checked = settings?.AI_PARAMS?.dataset_collection?.enabled ?? true;
    if (collectOnEventCheckbox) collectOnEventCheckbox.checked = settings?.AI_PARAMS?.dataset_collection?.save_on_event ?? false;
    if (collectIntervalInput) collectIntervalInput.value = settings?.AI_PARAMS?.dataset_collection?.save_interval ?? 10;
    if (collectRetentionInput) collectRetentionInput.value = settings?.AI_PARAMS?.dataset_collection?.retention_days ?? 30;
    if (collectDistrustMinInput) collectDistrustMinInput.value = settings?.AI_PARAMS?.dataset_collection?.distrust_range?.[0] ?? 0.3;
    if (collectDistrustMaxInput) collectDistrustMaxInput.value = settings?.AI_PARAMS?.dataset_collection?.distrust_range?.[1] ?? 0.6;

    // O listener do botão "Adicionar Zona" agora é tratado em initializeAppForSettingsPage
    // para evitar duplicidade ou conflitos com populateStructuredSettingsForm.
}


/**
 * Updates the trend text for main statistics (Normal, Fallen, Inverted cans).
 * @param {string} statId - The ID of the HTML element displaying the main count (e.g., 'stat-normal').
 * @param {number|null} trendPercentage - The percentage change value from the API (e.g., 10.5, -5.2, null).
 */
function updateTrend(statId, trendPercentage) {
    const statElement = document.getElementById(statId);
    if (!statElement) {
        // console.warn(`[updateTrend] Element with ID '${statId}' not found.`);
        return;
    }

    // The trend text is in a <span> with class 'stat-trend-text'
    // inside the next sibling <p> element of the stat count element.
    const trendTextElement = statElement.nextElementSibling?.querySelector('.stat-trend-text');

    if (trendTextElement) {
        if (trendPercentage === null || trendPercentage === undefined) {
            trendTextElement.textContent = "--%";
            trendTextElement.className = "stat-trend-text text-gray-500"; // Neutral color
        } else {
            const roundedPercentage = parseFloat(trendPercentage).toFixed(1);
            let textToShow = "";
            let colorClass = "text-gray-500"; // Default neutral color

            if (trendPercentage > 0) {
                textToShow = `+${roundedPercentage}%`;
                colorClass = "text-green-500"; // Positive trend
            } else if (trendPercentage < 0) {
                textToShow = `${roundedPercentage}%`; // Negative sign is inherent
                colorClass = "text-red-500";   // Negative trend (context defines if good/bad)
            } else { // trendPercentage == 0
                textToShow = `0.0%`;
            }
            trendTextElement.textContent = textToShow;
            trendTextElement.className = `stat-trend-text ${colorClass}`;
        }
    }
}

// <<< NOVA: Função para atualizar a lista de alertas >>>
function updateAlertsList(alerts) {
    if (!alertsList) return;

    alertsList.innerHTML = ''; // Limpa alertas antigos

    if (!alerts || alerts.length === 0) {
        alertsList.innerHTML = '<p class="text-xs text-gray-400 text-center">Nenhum alerta recente.</p>';
        return;
    }

    alerts.forEach(alert => {
        let iconClass = 'fa-info-circle';
        let bgColor = 'bg-blue-100';
        let textColor = 'text-blue-600';

        if (alert.level === 'warning') {
            iconClass = 'fa-exclamation-triangle';
            bgColor = 'bg-yellow-100';
            textColor = 'text-yellow-600';
        } else if (alert.level === 'error') {
            iconClass = 'fa-times-circle';
            bgColor = 'bg-red-100';
            textColor = 'text-red-600';
        }

        const alertHTML = `
            <div class="flex items-start">
                <div class="flex-shrink-0 pt-0.5">
                    <div class="${bgColor} rounded-full p-1">
                        <i class="fas ${iconClass} ${textColor} text-xs"></i>
                    </div>
                </div>
                <div class="ml-3">
                    <p class="text-sm font-medium">${alert.message || 'Mensagem não disponível'}</p>
                    <p class="text-xs text-gray-500">${alert.timestamp || '--:--:--'}</p>
                </div>
            </div>
        `;
        alertsList.insertAdjacentHTML('beforeend', alertHTML);
    });
}

// <<< NOVA: Função para atualizar o status das câmeras >>>
function updateCameraStatus(statuses) {
    const cameras = {
        'sec1': { text: statusCamSec1Text, indicator: statusCamSec1Indicator },
        'sec2': { text: statusCamSec2Text, indicator: statusCamSec2Indicator },
        'rej': { text: statusCamRejText, indicator: statusCamRejIndicator }
    };

    for (const camKey in cameras) {
        const status = statuses ? statuses[camKey] : 'offline'; // Default to offline if status missing
        const elements = cameras[camKey];

        if (elements.text && elements.indicator) {
            const isOnline = status === 'online';
            elements.text.textContent = isOnline ? 'Ativa' : 'Inativa';
            elements.text.className = `inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${isOnline ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`;
            elements.indicator.className = `status-indicator ${isOnline ? 'status-online' : 'status-offline'}`;
        }
    }
}

// <<< REMOVIDO: Função toggleEditMode não é mais necessária com o novo design >>>
/*
function toggleEditMode() {
    const isReadOnly = settingsDisplay.readOnly;
    settingsDisplay.readOnly = !isReadOnly; // Toggle para o JSON cru
    editSettingsButton.textContent = isReadOnly ? 'Desabilitar Edição' : 'Habilitar Edição';
    updateSettingsButton.disabled = !isReadOnly;
    showMessage('settings-status-message', isReadOnly ? 'Modo de edição habilitado.' : 'Modo de edição desabilitado.');
    resetInactivityTimer(); // Reseta timer ao interagir
}
*/

async function updateSettings() {
    let formSettings; // Renomeado para clareza

    try {
        // Lê apenas os dados modificados no formulário
        formSettings = readStructuredSettingsForm();
    } catch (error) {
        showMessage('settings-status-message', `Erro ao ler dados do formulário: ${error.message}`, true);
        return;
    }

    showMessage('settings-status-message', 'Atualizando configurações...');
    if (saveSettingsBtn) saveSettingsBtn.disabled = true; // Desabilita enquanto envia
    if (cancelSettingsBtn) cancelSettingsBtn.disabled = true;

    try {
        // --- ETAPA 1: Buscar as configurações atuais completas (descriptografadas) ---
        console.log("[updateSettings] Fetching current full settings...");
        const currentSettingsResponse = await fetch('/api/settings');
        if (!currentSettingsResponse.ok) throw new Error(`Erro ao buscar config. atuais: ${currentSettingsResponse.status}`);
        const encryptedCurrentSettings = await currentSettingsResponse.blob();

        const decryptResponse = await fetch('/api/decrypt', {
            method: 'POST',
            headers: { 'Content-Type': 'application/octet-stream' },
            body: encryptedCurrentSettings
        });
        if (!decryptResponse.ok) throw new Error(`Erro ao descriptografar config. atuais: ${decryptResponse.status}`);
        const currentFullSettings = await decryptResponse.json();
        console.log("[updateSettings] Current full settings fetched and decrypted.");

        // --- ETAPA 2: Mesclar as alterações do formulário nas configurações completas ---
        // Deep merge manual simples para AI_PARAMS e VIDEO_PARAMS
        const updatedFullSettings = JSON.parse(JSON.stringify(currentFullSettings)); // Deep copy

        if (formSettings.AI_PARAMS) {
            updatedFullSettings.AI_PARAMS = { ...updatedFullSettings.AI_PARAMS, ...formSettings.AI_PARAMS };
            if (formSettings.AI_PARAMS.thresholds) { // Merge thresholds separadamente
                updatedFullSettings.AI_PARAMS.thresholds = { ...updatedFullSettings.AI_PARAMS.thresholds, ...formSettings.AI_PARAMS.thresholds };
            }
            if (formSettings.AI_PARAMS.advanced) {
                updatedFullSettings.AI_PARAMS.advanced = { ...updatedFullSettings.AI_PARAMS.advanced, ...formSettings.AI_PARAMS.advanced };
            }
        }
        if (formSettings.VIDEO_PARAMS) {
            updatedFullSettings.VIDEO_PARAMS = { ...updatedFullSettings.VIDEO_PARAMS, ...formSettings.VIDEO_PARAMS };
        }
        console.log("[updateSettings] Merged settings:", updatedFullSettings);

        // --- ETAPA 3: Enviar as configurações completas e atualizadas para o servidor ---
        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updatedFullSettings), // Envia a estrutura completa atualizada
        });
        const data = await response.json();
        if (!response.ok) {
            // Se for erro 401 (Não autorizado), redireciona para login
            if (response.status === 401) {
                console.log("Não autorizado para atualizar. Redirecionando para login...");
                window.location.href = '/login';
                return; // Interrompe a execução
            }
            console.error(`Fetch settings failed with status: ${response.status}`);
            throw new Error(data.message || `Erro HTTP: ${response.status}`);
        }
        console.log("Fetch settings successful, parsing JSON...");
        // Não precisa mais ler a resposta aqui, apenas confirmação
        // Repopula o form com os dados que foram efetivamente salvos (se a API retornasse)
        // Por enquanto, apenas mostra a mensagem de sucesso.
        // populateStructuredSettingsForm(newSettings); // Opcional: repopular se a API não retornar o estado salvo
        showMessage('settings-status-message', data.message || 'Configurações atualizadas com sucesso no servidor.');
        console.log("[updateSettings] Settings updated successfully.");
    } catch (error) {
        console.error('Erro ao atualizar configurações:', error);
        showMessage('settings-status-message', `Erro ao atualizar: ${error.message}`, true);
    } finally {
        if (saveSettingsBtn) saveSettingsBtn.disabled = false; // Reabilita
        if (cancelSettingsBtn) cancelSettingsBtn.disabled = false;
    }
}

// <<< NOVO: Função para ler dados do formulário estruturado >>>
// <<< MODIFICADO: Para ler os novos IDs e estrutura, INCLUINDO colors e styles >>>
function readStructuredSettingsForm() {
    console.log("[readStructuredSettingsForm] Reading form data...");

    // IA Thresholds
    const thresholdNormalInput = document.getElementById('setting-threshold-normal');
    const thresholdFallenInput = document.getElementById('setting-threshold-fallen');
    const thresholdInvertedInput = document.getElementById('setting-threshold-inverted');
    const thresholdFractureInput = document.getElementById('setting-threshold-fracture');
    const iouInput = document.getElementById('setting-iou');

    // Video Source
    const sourceTypeSelect = document.getElementById('setting-source-type');
    const sourceParamInput = document.getElementById('setting-source-param');

    // Camera Settings
    const resolutionSelect = document.getElementById('setting-camera-resolution');
    const fpsSelect = document.getElementById('setting-camera-fps');

    // Zonas de Exclusão
    const exclusionZonesContainer = document.getElementById('exclusion-zones-container');
    let exclusionZones = [];
    if (exclusionZonesContainer) {
        const zoneItems = exclusionZonesContainer.querySelectorAll('.exclusion-zone-item');
        zoneItems.forEach(item => {
            exclusionZones.push({
                x: parseInt(item.querySelector('.zone-x').value) || 0,
                y: parseInt(item.querySelector('.zone-y').value) || 0,
                w: parseInt(item.querySelector('.zone-w').value) || 0,
                h: parseInt(item.querySelector('.zone-h').value) || 0
            });
        });
    }

    // <<<< NOVO: Ler cores de detecção (converter HEX para RGB) >>>>
    const colorLataNormalHex = document.getElementById('color-lata-normal')?.value || '#00ff00';
    const colorLataInvertidaHex = document.getElementById('color-lata-invertida')?.value || '#0000ff';
    const colorLataTombadaHex = document.getElementById('color-lata-tombada')?.value || '#ffa500';
    const colorFractureHex = document.getElementById('color-fracture')?.value || '#ff0000';

    const settingsData = {
        AI_PARAMS: {
            thresholds: {
                lata_normal: thresholdNormalInput ? parseFloat(thresholdNormalInput.value) : 0.90,
                lata_tombada: thresholdFallenInput ? parseFloat(thresholdFallenInput.value) : 0.85,
                lata_invertida: thresholdInvertedInput ? parseFloat(thresholdInvertedInput.value) : 0.95,
                fracture: thresholdFractureInput ? parseFloat(thresholdFractureInput.value) : 0.80, // <<< NEW
            },
            iou_default: iouInput ? parseFloat(iouInput.value) : 0.5,
            advanced: {
                exclusion_zones: exclusionZones,
                gamma: document.getElementById('setting-gamma') ? parseFloat(document.getElementById('setting-gamma').value) : 0.8,
                clahe_enabled: document.getElementById('setting-clahe') ? document.getElementById('setting-clahe').checked : true,
                drawing: {
                    box_thickness: document.getElementById('setting-draw-thickness') ? parseInt(document.getElementById('setting-draw-thickness').value) : 2,
                    font_scale: document.getElementById('setting-draw-font-scale') ? parseFloat(document.getElementById('setting-draw-font-scale').value) : 0.5,
                    font_thickness: document.getElementById('setting-draw-font-thickness') ? parseInt(document.getElementById('setting-draw-font-thickness').value) : 1,
                    show_label: document.getElementById('setting-draw-show-label') ? document.getElementById('setting-draw-show-label').checked : true,
                    show_conf: document.getElementById('setting-draw-show-conf') ? document.getElementById('setting-draw-show-conf').checked : true,
                    show_bg: document.getElementById('setting-draw-show-bg') ? document.getElementById('setting-draw-show-bg').checked : true
                }
            },
            dataset_collection: {
                enabled: document.getElementById('setting-collect-enabled') ? document.getElementById('setting-collect-enabled').checked : true,
                save_on_event: document.getElementById('setting-collect-on-event') ? document.getElementById('setting-collect-on-event').checked : true,
                save_interval: document.getElementById('setting-collect-interval') ? parseFloat(document.getElementById('setting-collect-interval').value) : 10.0,
                retention_days: document.getElementById('setting-collect-retention') ? parseInt(document.getElementById('setting-collect-retention').value) : 30,
                distrust_range: [
                    document.getElementById('setting-collect-distrust-min') ? parseFloat(document.getElementById('setting-collect-distrust-min').value) : 0.3,
                    document.getElementById('setting-collect-distrust-max') ? parseFloat(document.getElementById('setting-collect-distrust-max').value) : 0.6
                ]
            }
            // Manter outros AI_PARAMS que não estão no form, se necessário (requer merge)
        },
        VIDEO_PARAMS: {
            source_type: sourceTypeSelect ? sourceTypeSelect.value : 'video',
            source_param: sourceParamInput ? sourceParamInput.value : '',
            resolution: resolutionSelect ? resolutionSelect.value : '',
            fps: fpsSelect ? fpsSelect.value : '',
            // Manter outros VIDEO_PARAMS que não estão no form, se necessário (requer merge)
        },
        // <<<< NOVO: Salvar cores de detecção (converter HEX para RGB) >>>>
        COLORS: {
            detection: {
                lata_normal: hexToRgb(colorLataNormalHex),
                lata_invertida: hexToRgb(colorLataInvertidaHex),
                lata_tombada: hexToRgb(colorLataTombadaHex),
                fracture: hexToRgb(colorFractureHex)
            }
        }
    };
    console.log("[readStructuredSettingsForm] Data read:", settingsData);
    return settingsData;
}

// --- Funções para os Novos Botões de Ação ---

async function requestFrameExtraction() {
    showMessage('status-message', 'Enviando solicitação para extrair frame...');
    try {
        // A resposta agora será a própria imagem ou um JSON de erro
        const extractResponse = await fetch('/api/extract_frame', { method: 'POST' });

        if (extractResponse.ok) {
            const contentType = extractResponse.headers.get("content-type");

            // <<< MODIFICADO: Verificar se é octet-stream (dados criptografados) >>>
            if (contentType && contentType.includes("application/octet-stream")) {
                const encryptedBlob = await extractResponse.blob();

                // <<< NOVO: Enviar para /api/decrypt >>>
                const decryptResponse = await fetch('/api/decrypt', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/octet-stream' },
                    body: encryptedBlob
                });

                if (!decryptResponse.ok) {
                    const errorData = await decryptResponse.json().catch(() => ({ message: 'Erro desconhecido na descriptografia do frame' }));
                    throw new Error(errorData.message || `Erro ao descriptografar frame: ${decryptResponse.status}`);
                }

                // <<< NOVO: A resposta de /api/decrypt agora contém os bytes JPEG crus >>>
                const decryptedJpegBlob = await decryptResponse.blob();

                // <<< NOVO: Criar link de download para o blob JPEG descriptografado >>>
                const url = window.URL.createObjectURL(decryptedJpegBlob); // Usa o blob descriptografado
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                // Pega o nome do arquivo do header, ou usa um padrão
                const disposition = extractResponse.headers.get('content-disposition');
                let filenameEnc = 'frame_capturado.jpg.enc'; // Nome padrão se header falhar
                if (disposition && disposition.indexOf('attachment') !== -1) {
                    const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
                    const matches = filenameRegex.exec(disposition);
                    if (matches != null && matches[1]) {
                        filenameEnc = matches[1].replace(/['"]/g, '');
                    }
                }
                const filename = filenameEnc.replace(/\.enc$/, '');
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                a.remove();
                showMessage('status-message', 'Download do frame iniciado.');
            } else {
                // Se não for imagem, pode ser uma mensagem de erro inesperada
                const data = await extractResponse.json();
                throw new Error(data.message || 'Resposta inesperada do servidor.');
            }
        } else {
            // Se a resposta não for OK, tenta ler a mensagem de erro JSON
            const data = await response.json();
            throw new Error(data.message || `Erro HTTP: ${response.status}`);
        }

    } catch (error) {
        console.error('Erro ao solicitar extração de frame:', error);
        showMessage('status-message', `Erro: ${error.message}`, true);
    }
}

async function requestDataExport() {
    showMessage('status-message', 'Solicitando exportação de dados...');
    try {
        const response = await fetch('/api/export_data', { method: 'GET' });

        if (response.ok) {
            // Verifica se é um arquivo CSV para download
            const contentType = response.headers.get("content-type");
            if (contentType && contentType.includes("text/csv")) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                // Pega o nome do arquivo do header, ou usa um padrão
                const disposition = response.headers.get('content-disposition');
                let filename = 'exported_data.csv';
                if (disposition && disposition.indexOf('attachment') !== -1) {
                    const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
                    const matches = filenameRegex.exec(disposition);
                    if (matches != null && matches[1]) {
                        filename = matches[1].replace(/['"]/g, '');
                    }
                }
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                a.remove();
                showMessage('status-message', 'Download do relatório iniciado.');
            } else {
                // Se não for CSV, trata como JSON (mensagem de status/erro)
                const data = await extractResponse.json();
                if (data.success) {
                    showMessage('status-message', data.message || 'Exportação concluída (sem arquivo).');
                } else {
                    throw new Error(data.message || 'Erro na exportação.');
                }
            }
        } else {
            const data = await response.json(); // Tenta pegar mensagem de erro
            throw new Error(data.message || `Erro HTTP: ${response.status}`);
        }
    } catch (error) {
        console.error('Erro ao exportar dados:', error);
        showMessage('status-message', `Erro na exportação: ${error.message}`, true);
    }
}

// --- Function to handle Pause/Resume in Modal ---
async function toggleModalStreamPause() { // Tornar a função async
    if (!modalVideoStreamElement || !modalPauseResumeBtn) return;

    const action = isModalStreamPaused ? 'resume' : 'pause'; // Determina a ação
    const apiUrl = `/api/web_stream/${action}`;
    const buttonText = isModalStreamPaused ? '<i class="fas fa-pause"></i> Pausar' : '<i class="fas fa-play"></i> Retomar';
    const nextState = !isModalStreamPaused; // Estado esperado após sucesso

    console.log(`Requesting ${action} for web stream...`);
    modalPauseResumeBtn.disabled = true; // Desabilita botão durante a requisição

    try {
        const response = await fetch(apiUrl, { method: 'POST' });
        const data = await response.json();

        if (response.ok && data.success) {
            console.log(`Web stream ${action} successful.`);
            isModalStreamPaused = nextState; // Atualiza o estado do cliente
            modalPauseResumeBtn.innerHTML = buttonText; // Atualiza o botão
        } else {
            // Se falhou, reverte o estado visual do botão se necessário
            console.error(`Failed to ${action} web stream:`, data.message || response.status);
            showMessage('status-message-bottom', `Erro ao ${action} stream: ${data.message || 'Erro desconhecido'}`, true);
            // Não muda isModalStreamPaused nem o botão
        }
    } catch (error) {
        console.error(`Error during web stream ${action}:`, error);
        showMessage('status-message-bottom', `Erro de conexão ao tentar ${action} o stream.`, true);
        // Não muda isModalStreamPaused nem o botão
    } finally {
        modalPauseResumeBtn.disabled = false; // Reabilita o botão
        // Limpa a mensagem de status após alguns segundos
        setTimeout(() => {
            showMessage('status-message-bottom', '');
        }, 3000);
    }

    resetInactivityTimer(); // Reset inactivity on interaction
}

function initializeIndexPage() {
    console.log("Initializing Index Page...");
    let elementCheckFailed = false; // Flag to track if any element is missing
    // <<< REMOVIDO: Referências aos elementos antigos de settings >>>
    // settingsDisplay = document.getElementById('settings-display');
    // getSettingsButton = document.getElementById('get-settings-button');
    // editSettingsButton = document.getElementById('edit-settings-button');
    // updateSettingsButton = document.getElementById('update-settings-button');
    statFracture = document.getElementById('stat-fracture'); // <<< NEW
    statNormal = document.getElementById('stat-normal');
    statInverted = document.getElementById('stat-inverted');
    statFallen = document.getElementById('stat-fallen');
    statFps = document.getElementById('stat-fps');
    videoStreamElement = document.getElementById('video-stream');
    videoModal = document.getElementById('video-modal');
    modalVideoStreamElement = document.getElementById('modal-video-stream');
    closeModalBtn = document.querySelector('.close-modal-btn');
    videoTimestamp = document.getElementById('video-timestamp');
    videoResolution = document.getElementById('video-resolution');
    systemTime = document.getElementById('system-time');
    systemLoad = document.getElementById('system-load');
    // Adiciona IDs aos botões no HTML se ainda não tiverem
    extractFrameBtn = document.querySelector('.actions-grid .action-btn:nth-child(1)'); // Assume a ordem
    exportDataBtn = document.querySelector('.actions-grid .action-btn:nth-child(2)'); // Assume a ordem
    streamSnapshotBtn = document.getElementById('stream-snapshot'); // Pega pelo ID direto
    streamFullscreenBtn = document.getElementById('stream-fullscreen'); // Pega pelo ID direto
    modalSnapshotBtn = document.getElementById('snapshot-btn'); // Modal snapshot button
    modalPauseResumeBtn = document.getElementById('modal-pause-resume-btn'); // Modal pause/resume button
    if (extractFrameBtn) extractFrameBtn.id = 'extract-frame-btn'; // Atribui ID se necessário
    else console.warn("Element '.actions-grid .action-btn:nth-child(1)' (extractFrameBtn) not found.");
    if (exportDataBtn) exportDataBtn.id = 'export-data-btn'; // Atribui ID se necessário
    else console.warn("Element '.actions-grid .action-btn:nth-child(2)' (exportDataBtn) not found.");

    // Check if essential elements were found
    // <<< REMOVIDO: Verificação dos elementos antigos de settings >>>
    // settingsFormStructured = document.getElementById('settings-form-structured');
    const essentialElementsIndex = { videoStreamElement, videoModal, modalVideoStreamElement }; // Apenas elementos essenciais do Index
    for (const [name, element] of Object.entries(essentialElementsIndex)) {
        if (!element) {
            console.error(`Essential element '${name}' not found in the DOM!`);
            elementCheckFailed = true;
        }
    }
    if (elementCheckFailed) {
        return;
        // Stop initialization if essential elements are missing
    }

    // <<< REMOVIDO: Listeners dos botões antigos de settings >>>
    // getSettingsButton.addEventListener('click', fetchSettings);
    // editSettingsButton.addEventListener('click', toggleEditMode);
    // updateSettingsButton.addEventListener('click', updateSettings);

    // Action buttons
    if (extractFrameBtn) extractFrameBtn.addEventListener('click', requestFrameExtraction);
    if (exportDataBtn) exportDataBtn.addEventListener('click', requestDataExport);

    // Stream control buttons (main view)
    if (streamSnapshotBtn) streamSnapshotBtn.addEventListener('click', requestFrameExtraction);
    if (streamFullscreenBtn) streamFullscreenBtn.addEventListener('click', openVideoStreamModal);

    // Video stream double-click for modal
    if (videoStreamElement) {
        videoStreamElement.addEventListener('dblclick', () => {
            if (videoModal && modalVideoStreamElement) {
                modalVideoStreamElement.src = videoStreamElement.src;
                videoModal.classList.add('active');
                resetInactivityTimer();
            }
            openVideoStreamModal(); // Use the function directly
        });
    }

    // Função para abrir o modal (reutilizada pelo botão e duplo clique)
    function openVideoStreamModal() {
        console.log("Opening video stream modal.");
        if (videoModal && modalVideoStreamElement && videoStreamElement) {
            originalModalStreamSrc = videoStreamElement.src; // Store the source
            modalVideoStreamElement.src = originalModalStreamSrc; // Set the modal stream source
            videoModal.classList.add('active');
            // Reset pause state when opening
            isModalStreamPaused = false;
            if (modalPauseResumeBtn) {
                modalPauseResumeBtn.innerHTML = '<i class="fas fa-pause"></i> Pausar';
            }
            resetInactivityTimer();

        }
    }

    // Listeners para fechar o modal
    if (videoModal) {
        videoModal.addEventListener('click', (event) => {
            // Fecha se clicar fora da imagem do modal
            if (event.target === videoModal) {
                videoModal.classList.remove('active');
                modalVideoStreamElement.src = ""; // Clear src to stop loading
                originalModalStreamSrc = ''; // Clear stored src
            }
        });
    }
    if (closeModalBtn) {
        closeModalBtn.addEventListener('click', () => {
            videoModal.classList.remove('active');
            modalVideoStreamElement.src = ""; // Clear src
            originalModalStreamSrc = ''; // Clear stored src
        });
    }

    // Modal control buttons
    if (modalSnapshotBtn) {
        modalSnapshotBtn.addEventListener('click', requestFrameExtraction); // Use the same snapshot function
    }
    if (modalPauseResumeBtn) {
        modalPauseResumeBtn.addEventListener('click', toggleModalStreamPause);
    }
    console.log("Index page event listeners added.");

    // <<< REMOVIDO: Chamada inicial a fetchSettings() movida para initializeAppForSettingsPage >>>
    // fetchSettings().catch(error => {
    //     console.error('Erro inicial ao buscar configurações:', error);
    //     showMessage('status-message', `Erro inicial ao carregar configurações: ${error.message}`, true);
    // });

    // Inicia busca de estatísticas
    fetchAndUpdateStats(); // Busca inicial
    statsInterval = setInterval(fetchAndUpdateStats, 2000); // Atualiza a cada 2 segundos
    console.log("Stats fetching interval started.");

    // Configura listeners de atividade para o timer
    ['mousemove', 'keypress', 'click', 'scroll'].forEach(event => {
        // Não reseta o timer se o clique foi dentro do modal (exceto no botão fechar)
        document.addEventListener(event, (e) => {
            if (videoModal && videoModal.classList.contains('active') && e.target !== closeModalBtn && e.target !== videoModal) {
                // Se modal está ativo e o evento não é no botão fechar ou no fundo, não reseta
                return;
            }
            resetInactivityTimer();
        });
    });
    resetInactivityTimer(); // Inicia o timer
}

// ========================================================================
// Inicialização Geral (Roda quando o DOM está pronto)
// ========================================================================
// Listener para fechar modal com a tecla Esc
document.addEventListener('keydown', (event) => {
    if (event.key === "Escape" && videoModal && videoModal.classList.contains('active')) {
        videoModal.classList.remove('active');
        modalVideoStreamElement.src = ""; // Limpa src
        originalModalStreamSrc = ''; // Clear stored src
    }
});
document.addEventListener('DOMContentLoaded', () => {
    console.log("DOMContentLoaded fired.");

    // Inicialização comum
    resetInactivityTimer();
    // Adiciona listeners de atividade comuns
    ['mousemove', 'keypress', 'click', 'scroll'].forEach(event => {
        document.addEventListener(event, resetInactivityTimer);
    });

    // Inicialização específica da página
    if (document.getElementById('login-form')) {
        initializeLoginPage();
    } else if (document.getElementById('monitor-content')) { // <<< CORRIGIDO AQUI
        // Estamos na página do Stream (index.html)
        initializeAppForStreamPage();
    } else if (document.getElementById('dashboard-section')) {
        // Estamos na página do Dashboard
        initializeAppForDashboardPage();
    } else if (document.getElementById('settings-section')) {
        // Estamos na página de Configurações
        initializeAppForSettingsPage();
    } else if (document.getElementById('analytics-section')) { // ID da div principal em analytics.html
        console.log("[script.js] Página de Analytics detectada. analitycs.js deve se auto-inicializar.");
    }

    // Limpa intervalos ao sair da página
    window.addEventListener('beforeunload', () => {
        console.log("beforeunload: Clearing intervals and timers.");
        clearInterval(statsInterval);
        if (typeof analyticsIntervalRef !== 'undefined' && analyticsIntervalRef) clearInterval(analyticsIntervalRef); // <<< NOVO: Limpa intervalo do analytics
        clearTimeout(inactivityTimer);
    });
});

// <<< NOVO: Funções de inicialização específicas por página >>>
function initializeAppForStreamPage() {
    console.log("Initializing Stream Page specific elements...");
    // Obter referências aos elementos específicos desta página
    statFracture = document.getElementById('stat-fracture'); // <<< NEW
    statNormal = document.getElementById('stat-normal');
    statInverted = document.getElementById('stat-inverted');
    statFallen = document.getElementById('stat-fallen');
    statFps = document.getElementById('stat-fps');
    videoStreamElement = document.getElementById('video-stream');
    videoTimestamp = document.getElementById('video-timestamp');
    videoResolution = document.getElementById('video-resolution');
    systemTime = document.getElementById('system-time'); // Footer
    systemLoad = document.getElementById('system-load'); // Footer
    extractFrameBtn = document.getElementById('extract-frame-btn');
    exportDataBtn = document.getElementById('export-data-btn');
    streamSnapshotBtn = document.getElementById('stream-snapshot');
    streamFullscreenBtn = document.getElementById('stream-fullscreen');

    // <<< NOVOS: Elementos de stats/rates/alerts/cams da página de Monitoramento >>>
    statFallenValue = document.getElementById('stat-fallen');
    statInvertedValue = document.getElementById('stat-inverted');
    rateAcceptanceValue = document.getElementById('rate-acceptance-value');
    rateAcceptanceBar = document.getElementById('rate-acceptance-bar');
    rateFallenValue = document.getElementById('rate-fallen-value');
    rateFallenBar = document.getElementById('rate-fallen-bar');
    rateInvertedValue = document.getElementById('rate-inverted-value');
    rateInvertedBar = document.getElementById('rate-inverted-bar');
    alertsList = document.getElementById('alerts-list');
    // Modal (se estiver no base.html)
    videoModal = document.getElementById('video-modal');
    modalVideoStreamElement = document.getElementById('modal-video-stream');
    closeModalBtn = document.querySelector('.close-modal-btn');
    modalSnapshotBtn = document.getElementById('snapshot-btn');
    modalPauseResumeBtn = document.getElementById('modal-pause-resume-btn');

    // Status das Câmeras Secundárias/Rejeição
    statusCamSec1Text = document.getElementById('status-cam-sec1-text');
    statusCamSec1Indicator = document.getElementById('status-cam-sec1-indicator');
    statusCamSec2Text = document.getElementById('status-cam-sec2-text');
    statusCamSec2Indicator = document.getElementById('status-cam-sec2-indicator');
    statusCamRejText = document.getElementById('status-cam-rej-text');
    statusCamRejIndicator = document.getElementById('status-cam-rej-indicator');
    // Adicionar listeners específicos
    if (extractFrameBtn) extractFrameBtn.addEventListener('click', requestFrameExtraction);
    if (exportDataBtn) exportDataBtn.addEventListener('click', requestDataExport);
    if (streamSnapshotBtn) streamSnapshotBtn.addEventListener('click', requestFrameExtraction);
    if (streamFullscreenBtn) streamFullscreenBtn.addEventListener('click', openVideoStreamModal);
    if (videoStreamElement) videoStreamElement.addEventListener('dblclick', openVideoStreamModal);
    if (videoModal) videoModal.addEventListener('click', (event) => {
        if (event.target === videoModal) closeModal();
    });
    if (closeModalBtn) closeModalBtn.addEventListener('click', closeModal);
    if (modalSnapshotBtn) modalSnapshotBtn.addEventListener('click', requestFrameExtraction);
    if (modalPauseResumeBtn) modalPauseResumeBtn.addEventListener('click', toggleModalStreamPause);
    document.addEventListener('keydown', (event) => { // Listener Esc para modal
        if (event.key === "Escape" && videoModal && videoModal.classList.contains('active')) {
            closeModal();
        }
    });

    // <<< REMOVIDO: Chamada para initVideoStreams (simulação) >>>
    // initVideoStreams();

    // Iniciar busca de estatísticas
    fetchAndUpdateStats(); // Busca inicial
    statsInterval = setInterval(fetchAndUpdateStats, 2000); // Atualiza a cada 2 segundos
    console.log("Stream Page Initialized. Stats fetching started.");
}

function initializeAppForDashboardPage() {
    console.log("Initializing Dashboard Page specific elements...");
    // A lógica principal agora está em dashboard.js
    // Podemos manter esta função vazia ou adicionar inicializações
    // que *não* dependam dos elementos específicos do dashboard.
    console.log("Dashboard Page - Main initialization handled by dashboard.js.");
}
function initializeAppForAnalyticsPage() {
    console.log("Initializing Analytics Page specific elements...");
    // A lógica principal está em analytics.js
    if (typeof initializeAnalyticsPage === 'function') {
        initializeAnalyticsPage();
        // Guarda a referência do intervalo criado em analytics.js para poder limpar depois
        if (typeof analyticsInterval !== 'undefined') {
            analyticsIntervalRef = analyticsInterval;
        }
    } else {
        console.error("Função initializeAnalyticsPage() não encontrada. analytics.js foi carregado?");
    }
}
function initializeAppForSettingsPage() {
    console.log("Initializing Settings Page specific elements...");
    // Obter referências aos novos botões
    saveSettingsBtn = document.getElementById('save-settings-btn');
    cancelSettingsBtn = document.getElementById('cancel-settings-btn');

    // Adicionar listeners
    if (saveSettingsBtn) {
        saveSettingsBtn.addEventListener('click', () => {
            // Removido o confirm para uma experiência mais fluida ou manter se desejar
            // if (confirm('Tem certeza que deseja salvar e aplicar estas configurações? Algumas podem requerer reinício manual.')) {
            updateSettings();
            // }
        });
    }
    if (cancelSettingsBtn) {
        cancelSettingsBtn.addEventListener('click', () => {
            if (confirm('Descartar alterações e recarregar configurações atuais?')) {
                fetchSettings(); // Recarrega as configurações originais
            }
        });
    }

    // Listener para atualizar valor dos sliders
    document.querySelectorAll('.range-slider').forEach(slider => {
        // Inicializa o valor
        updateRangeValueDisplay(slider);
        // Atualiza ao mover
        slider.addEventListener('input', () => updateRangeValueDisplay(slider));
    });

    // <<<< NOVO: Listeners para sincronizar color pickers com text inputs >>>>>
    const colorPickers = [
        { picker: 'color-lata-normal', text: 'color-lata-normal-text' },
        { picker: 'color-lata-invertida', text: 'color-lata-invertida-text' },
        { picker: 'color-lata-tombada', text: 'color-lata-tombada-text' },
        { picker: 'color-fracture', text: 'color-fracture-text' }
    ];

    colorPickers.forEach(({ picker, text }) => {
        const pickerEl = document.getElementById(picker);
        const textEl = document.getElementById(text);
        
        if (pickerEl && textEl) {
            // Color picker muda o text input
            pickerEl.addEventListener('change', (e) => {
                textEl.value = e.target.value.toUpperCase();
            });
            pickerEl.addEventListener('input', (e) => {
                textEl.value = e.target.value.toUpperCase();
            });
            
            // Text input muda o color picker (se for hex válido)
            textEl.addEventListener('change', (e) => {
                const hex = e.target.value;
                if (/^#[0-9A-F]{6}$/i.test(hex)) {
                    pickerEl.value = hex.toLowerCase();
                }
            });
        }
    });

    // <<<< NOVO: Listeners para acordeão >>>>>
    const accordionHeaders = document.querySelectorAll('.accordion-header');
    accordionHeaders.forEach(header => {
        header.addEventListener('click', function() {
            const content = this.nextElementSibling;
            const icon = this.querySelector('i:last-child');
            
            // Toggle da classe hidden
            content.classList.toggle('hidden');
            
            // Animar o ícone
            if (content.classList.contains('hidden')) {
                icon.style.transform = 'rotate(0deg)';
            } else {
                icon.style.transform = 'rotate(180deg)';
            }
        });
    });

    // <<<< NOVO: Listeners para navegação de abas >>>>>
    const tabButtons = document.querySelectorAll('.settings-tab');
    tabButtons.forEach(tab => {
        tab.addEventListener('click', function() {
            const tabName = this.getAttribute('data-tab');
            
            // Remover class 'active' de todas as abas
            document.querySelectorAll('.settings-tab').forEach(t => {
                t.classList.remove('active', 'border-b-2', 'border-blue-600');
            });
            
            // Ocultar todos os conteúdos
            document.querySelectorAll('.settings-tab-content').forEach(content => {
                content.classList.add('hidden');
            });
            
            // Adicionar class 'active' na aba clicada
            this.classList.add('active', 'border-b-2', 'border-blue-600');
            
            // Mostrar o conteúdo correspondente
            const tabContent = document.getElementById('tab-' + tabName);
            if (tabContent) {
                tabContent.classList.remove('hidden');
            }
        });
    });

    // Carregar configurações iniciais
    showMessage('settings-status-message', 'Carregando configurações...');
    fetchSettings().catch(error => {
        console.error('Erro inicial ao buscar configurações:', error);
        showMessage('settings-status-message', `Erro inicial ao carregar configurações: ${error.message}`, true);
    });

    // Listener para o botão Adicionar Zona de Exclusão
    const addZoneBtn = document.getElementById('add-exclusion-zone-btn');
    if (addZoneBtn) {
        console.log("Setting up add-exclusion-zone-btn listener.");
        addZoneBtn.addEventListener('click', (e) => {
            e.preventDefault();
            console.log("Add Zone button clicked.");
            addExclusionZoneToDOM(0, 0, 100, 100);
        });
    }

    console.log("Settings Page Initialized.");
}

// <<< NOVO: Funções auxiliares para o modal >>>
function openVideoStreamModal() {
    console.log("Opening video stream modal.");
    if (videoModal && modalVideoStreamElement && videoStreamElement) {
        originalModalStreamSrc = videoStreamElement.src; // Store the source
        modalVideoStreamElement.src = originalModalStreamSrc; // Set the modal stream source
        videoModal.classList.add('active');
        // Reset pause state when opening
        isModalStreamPaused = false;
        if (modalPauseResumeBtn) {
            modalPauseResumeBtn.innerHTML = '<i class="fas fa-pause"></i> Pausar';
        }
        resetInactivityTimer();
    }
}

function closeModal() {
    if (videoModal && modalVideoStreamElement) {
        videoModal.classList.remove('active');
        modalVideoStreamElement.src = ""; // Clear src to stop loading
        originalModalStreamSrc = ''; // Clear stored src
    }
}

// <<< NOVA: Função para atualizar o span de valor do range slider >>>
function updateRangeValueDisplay(sliderElement) {
    if (!sliderElement) return;
    const valueSpan = sliderElement.parentElement.querySelector('.range-value');
    if (valueSpan) {
        const value = parseFloat(sliderElement.value);
        if (sliderElement.id === 'setting-gamma') {
            valueSpan.textContent = value.toFixed(2);
        } else {
            valueSpan.textContent = `${(value * 100).toFixed(0)}%`; // Formata como porcentagem
        }
    }
}


/*
// Código antigo de inicialização que agora está dividido
// ... removido comentário extenso ...
*/

console.log("script.js loaded.");

// <<< NOVAS FUNÇÕES ZONA DE EXCLUSÃO >>>
function renderExclusionZones(zones) {
    const container = document.getElementById('exclusion-zones-container');
    if (!container) return;
    container.innerHTML = '';

    if (!zones || zones.length === 0) {
        container.innerHTML = '<p class="text-sm text-gray-400 italic" id="empty-zones-msg">Nenhuma zona de exclusão. Todo o quadro será analisado.</p>';
        return;
    }

    zones.forEach((zone) => {
        addExclusionZoneToDOM(zone.x || 0, zone.y || 0, zone.w || 0, zone.h || 0);
    });
}

function addExclusionZoneToDOM(x = 0, y = 0, w = 0, h = 0) {
    console.log(`Adding exclusion zone to DOM: x=${x}, y=${y}, w=${w}, h=${h}`);
    const container = document.getElementById('exclusion-zones-container');
    if (!container) {
        console.error("Container 'exclusion-zones-container' not found!");
        return;
    }

    const emptyMsg = document.getElementById('empty-zones-msg');
    if (emptyMsg) emptyMsg.remove();

    const zoneDiv = document.createElement('div');
    zoneDiv.className = 'flex items-end space-x-4 bg-gray-50 p-3 rounded-md border border-gray-200 exclusion-zone-item mt-2';

    zoneDiv.innerHTML = `
        <div class="flex-1 space-y-2 lg:space-y-0 lg:flex lg:space-x-4">
            <div class="w-full lg:w-1/4">
                <label class="block text-xs font-medium text-gray-700 mb-1">X</label>
                <input type="number" class="zone-x mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-1 px-2 text-sm focus:ring-blue-500 focus:border-blue-500" value="${x}">
            </div>
            <div class="w-full lg:w-1/4">
                <label class="block text-xs font-medium text-gray-700 mb-1">Y</label>
                <input type="number" class="zone-y mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-1 px-2 text-sm focus:ring-blue-500 focus:border-blue-500" value="${y}">
            </div>
            <div class="w-full lg:w-1/4">
                <label class="block text-xs font-medium text-gray-700 mb-1">Largura</label>
                <input type="number" class="zone-w mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-1 px-2 text-sm focus:ring-blue-500 focus:border-blue-500" value="${w}">
            </div>
            <div class="w-full lg:w-1/4">
                <label class="block text-xs font-medium text-gray-700 mb-1">Altura</label>
                <input type="number" class="zone-h mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-1 px-2 text-sm focus:ring-blue-500 focus:border-blue-500" value="${h}">
            </div>
        </div>
        <button type="button" class="remove-zone-btn mb-1 text-red-500 hover:text-red-700 focus:outline-none p-2" title="Remover Zona">
            <i class="fas fa-trash"></i>
        </button>
    `;

    zoneDiv.querySelector('.remove-zone-btn').addEventListener('click', function () {
        zoneDiv.remove();
        const remaining = container.querySelectorAll('.exclusion-zone-item');
        if (remaining.length === 0) {
            container.innerHTML = '<p class="text-sm text-gray-400 italic" id="empty-zones-msg">Nenhuma zona de exclusão. Todo o quadro será analisado.</p>';
        }
    });

    container.appendChild(zoneDiv);
}

// <<< LÓGICA DO MODAL VISUAL DE ZONAS >>>
document.addEventListener('DOMContentLoaded', () => {
    const btnOpenDraw = document.getElementById('btn-open-draw-modal');
    if (!btnOpenDraw) return; // Só existe na página de settings

    const drawModal = document.getElementById('draw-zones-modal');
    const drawImg = document.getElementById('draw-zones-img');
    const drawCanvas = document.getElementById('draw-zones-canvas');
    const ctx = drawCanvas.getContext('2d');
    const loadingDiv = document.getElementById('draw-zones-loading');
    const btnCancel = document.getElementById('draw-zones-cancel-btn');
    const btnSave = document.getElementById('draw-zones-save-btn');
    const btnClear = document.getElementById('draw-zones-clear-btn');

    let drawingZones = [];
    let isDrawing = false;
    let startX = 0, startY = 0;
    let tempZone = null;
    let imgScaleX = 1;
    let imgScaleY = 1;

    // --- NOVAS VARIÁVEIS DO PINCEL ---
    let currentTool = 'rect'; // 'rect' ou 'brush'
    let brushSize = 40;

    // Listeners dos botões de ferramenta
    const rectToolBtn = document.getElementById('draw-rect-tool');
    const brushToolBtn = document.getElementById('draw-brush-tool');
    const brushSizeContainer = document.getElementById('brush-size-container');
    const brushSizeInput = document.getElementById('draw-brush-size');
    const brushSizeValLabel = document.getElementById('brush-size-val');

    if (rectToolBtn && brushToolBtn) {
        rectToolBtn.onclick = () => {
            currentTool = 'rect';
            rectToolBtn.className = 'tool-btn px-3 py-1.5 bg-blue-600 text-white rounded shadow-sm hover:bg-blue-700 transition flex items-center text-sm';
            brushToolBtn.className = 'tool-btn px-3 py-1.5 bg-white text-gray-700 border border-gray-300 rounded shadow-sm hover:bg-gray-50 transition flex items-center text-sm';
            if (brushSizeContainer) brushSizeContainer.classList.add('hidden');
        };

        brushToolBtn.onclick = () => {
            currentTool = 'brush';
            brushToolBtn.className = 'tool-btn px-3 py-1.5 bg-blue-600 text-white rounded shadow-sm hover:bg-blue-700 transition flex items-center text-sm';
            rectToolBtn.className = 'tool-btn px-3 py-1.5 bg-white text-gray-700 border border-gray-300 rounded shadow-sm hover:bg-gray-50 transition flex items-center text-sm';
            if (brushSizeContainer) brushSizeContainer.classList.remove('hidden');
        };
    }

    if (brushSizeInput) {
        brushSizeInput.oninput = () => {
            brushSize = parseInt(brushSizeInput.value);
            if (brushSizeValLabel) brushSizeValLabel.textContent = brushSize + 'px';
        };
    }

    // Resgata o frame atual da API
    async function fetchFrameForCanvas() {
        try {
            const extractResponse = await fetch('/api/extract_frame', { method: 'POST' });
            if (!extractResponse.ok) throw new Error("Erro na extração");

            const contentType = extractResponse.headers.get("content-type");
            if (contentType && contentType.includes("application/octet-stream")) {
                const encryptedBlob = await extractResponse.blob();
                const decryptResponse = await fetch('/api/decrypt', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/octet-stream' },
                    body: encryptedBlob
                });
                if (!decryptResponse.ok) throw new Error("Erro de decriptação");
                const decryptedJpegBlob = await decryptResponse.blob();
                const url = window.URL.createObjectURL(decryptedJpegBlob);

                drawImg.onload = () => {
                    // Configura canvas em cima da imagem
                    drawCanvas.width = drawImg.clientWidth;
                    drawCanvas.height = drawImg.clientHeight;

                    // Escala real
                    imgScaleX = drawImg.naturalWidth / drawImg.clientWidth;
                    imgScaleY = drawImg.naturalHeight / drawImg.clientHeight;

                    loadingDiv.classList.add('hidden');
                    drawImg.classList.remove('opacity-0');
                    drawCanvas.classList.remove('hidden');

                    // Importar as zonas já existentes no form
                    drawingZones = [];
                    const currentZones = [];
                    const items = document.querySelectorAll('.exclusion-zone-item');
                    items.forEach(item => {
                        const x = parseInt(item.querySelector('.zone-x').value) || 0;
                        const y = parseInt(item.querySelector('.zone-y').value) || 0;
                        const w = parseInt(item.querySelector('.zone-w').value) || 0;
                        const h = parseInt(item.querySelector('.zone-h').value) || 0;
                        if (w > 0 && h > 0) currentZones.push({ x, y, w, h });
                    });

                    // Transforma p/ viewport
                    drawingZones = currentZones.map(z => ({
                        x: z.x / imgScaleX,
                        y: z.y / imgScaleY,
                        w: z.w / imgScaleX,
                        h: z.h / imgScaleY
                    }));

                    redrawCanvas();
                };
                drawImg.src = url;
            } else {
                loadingDiv.innerHTML = '<span class="text-red-500">Erro: Stream sem imagem.</span>';
            }
        } catch (err) {
            console.error('Erro ao buscar frame para desenho:', err);
            loadingDiv.innerHTML = '<span class="text-red-500">Falha ao obter imagem da câmera.</span>';
        }
    }

    btnOpenDraw.onclick = () => {
        drawModal.classList.remove('hidden');
        drawModal.classList.add('flex');
        loadingDiv.classList.remove('hidden');
        drawImg.src = '';
        drawImg.classList.add('opacity-0');
        fetchFrameForCanvas();
    };

    btnCancel.onclick = () => {
        drawModal.classList.add('hidden');
        drawModal.classList.remove('flex');
    };

    btnClear.onclick = () => {
        drawingZones = [];
        redrawCanvas();
    };

    btnSave.onclick = () => {
        // Converte as zonas de volta para as dimensões originais da câmera usando a escala e joga no form
        const container = document.getElementById('exclusion-zones-container');
        if (container) container.innerHTML = '';

        drawingZones.forEach(z => {
            const rx = Math.round(z.x * imgScaleX);
            const ry = Math.round(z.y * imgScaleY);
            const rw = Math.round(z.w * imgScaleX);
            const rh = Math.round(z.h * imgScaleY);
            if (rw > 0 && rh > 0) {
                addExclusionZoneToDOM(rx, ry, rw, rh);
            }
        });

        drawModal.classList.add('hidden');
        drawModal.classList.remove('flex');

        // Ativa o botão Salvar Configurações
        const saveSettingsBtn = document.getElementById('save-settings-btn');
        if (saveSettingsBtn) saveSettingsBtn.classList.add('animate-pulse');
        setTimeout(() => { if (saveSettingsBtn) saveSettingsBtn.classList.remove('animate-pulse'); }, 2000);
    };

    function redrawCanvas() {
        ctx.clearRect(0, 0, drawCanvas.width, drawCanvas.height);

        // Fundo semitransparente escuro p/ destacar as zonas cortadas
        ctx.fillStyle = 'rgba(0, 0, 0, 0.4)';
        ctx.fillRect(0, 0, drawCanvas.width, drawCanvas.height);

        // Zonas de exclusão
        drawingZones.forEach(z => {
            ctx.fillStyle = 'rgba(0,0,0,1)';
            ctx.fillRect(z.x, z.y, z.w, z.h);
            ctx.strokeStyle = '#ef4444'; // contorno vermelho
            ctx.lineWidth = 2;
            ctx.strokeRect(z.x, z.y, z.w, z.h);
        });

        if (isDrawing && tempZone && currentTool === 'rect') {
            ctx.fillStyle = 'rgba(0,0,0,0.8)';
            ctx.fillRect(tempZone.x, tempZone.y, tempZone.w, tempZone.h);
            ctx.strokeStyle = '#3b82f6'; // Azul visualização
            ctx.lineWidth = 2;
            ctx.strokeRect(tempZone.x, tempZone.y, tempZone.w, tempZone.h);
        }
    }

    // Eventos do Mouse
    drawCanvas.onmousedown = (e) => {
        const rect = drawCanvas.getBoundingClientRect();
        startX = e.clientX - rect.left;
        startY = e.clientY - rect.top;
        isDrawing = true;

        if (currentTool === 'rect') {
            tempZone = { x: startX, y: startY, w: 0, h: 0 };
        } else {
            // Brush: Adiciona ponto inicial
            drawingZones.push({
                x: startX - brushSize / 2,
                y: startY - brushSize / 2,
                w: brushSize,
                h: brushSize
            });
            redrawCanvas();
        }
    };

    drawCanvas.onmousemove = (e) => {
        if (!isDrawing) return;
        const rect = drawCanvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        if (currentTool === 'rect') {
            tempZone.x = Math.min(startX, mouseX);
            tempZone.y = Math.min(startY, mouseY);
            tempZone.w = Math.abs(mouseX - startX);
            tempZone.h = Math.abs(mouseY - startY);
        } else {
            // Pincel: Adiciona quadrados ao longo do caminho se moveu o suficiente
            // Verifica o último desenho para não saturar de retângulos
            const last = drawingZones[drawingZones.length - 1];
            const dist = Math.sqrt(Math.pow(mouseX - (last.x + last.w / 2), 2) + Math.pow(mouseY - (last.y + last.h / 2), 2));

            if (dist > brushSize / 4) {
                drawingZones.push({
                    x: mouseX - brushSize / 2,
                    y: mouseY - brushSize / 2,
                    w: brushSize,
                    h: brushSize
                });
            }
        }
        redrawCanvas();
    };

    drawCanvas.onmouseup = () => {
        if (isDrawing) {
            isDrawing = false;
            // Só salva se tiver tamanho mínimo
            if (tempZone && tempZone.w > 10 && tempZone.h > 10) {
                drawingZones.push(tempZone);
            }
            tempZone = null;
            redrawCanvas();
        }
    };
});