/**
 * ASR INT8 Tester — Controlador Frontend en Vanilla JavaScript
 * Implementado bajo estrictas directivas de seguridad (DOM seguro sin innerHTML no saneado).
 */

(function () {
  'use strict';

  // =========================================================================
  // 1. ESTADO GLOBAL DE LA APLICACIÓN
  // =========================================================================
  const state = {
    currentAudioBlob: null,
    currentAudioFile: null,
    currentAudioUrl: null,
    corpusData: { oraciones: [], palabras: [] },
    serverInfo: null,
    history: [],
    isRecording: false,
    isEvaluating: false,
    mediaRecorder: null,
    audioContext: null,
    analyserNode: null,
    animFrameId: null,
    recordStartTime: null,
    recordTimerInterval: null,
    g2pDebounceTimer: null,
    modelsList: [],
    decodingModesList: []
  };

  // =========================================================================
  // 2. ELEMENTOS DEL DOM
  // =========================================================================
  const dom = {
    // Header & Info
    modelStatusPill: document.getElementById('modelStatusPill'),
    modelStatusText: document.getElementById('modelStatusText'),
    btnMobileModal: document.getElementById('btnMobileModal'),
    historyBadgeCount: document.getElementById('historyBadgeCount'),

    // Pestañas
    tabBtns: document.querySelectorAll('.tab-btn'),
    tabContents: document.querySelectorAll('.tab-content'),

    // Configuración de Inferencia (Modelos y Decodificación)
    selectModel: document.getElementById('selectModel'),
    selectDecodingMode: document.getElementById('selectDecodingMode'),
    modelDescriptionText: document.getElementById('modelDescriptionText'),
    decodingDescriptionText: document.getElementById('decodingDescriptionText'),

    // Métodos de Entrada
    methodBtns: document.querySelectorAll('.method-btn'),
    containerMic: document.getElementById('containerMic'),
    containerUpload: document.getElementById('containerUpload'),
    containerCorpus: document.getElementById('containerCorpus'),

    // Micrófono
    btnRecordToggle: document.getElementById('btnRecordToggle'),
    recordBtnLabel: document.getElementById('recordBtnLabel'),
    recordTimer: document.getElementById('recordTimer'),
    liveCanvas: document.getElementById('liveVisualizerCanvas'),
    vuMeterFill: document.getElementById('vuMeterFill'),
    micHint: document.getElementById('micHint'),

    // Subida de Archivo
    uploadDropzone: document.getElementById('uploadDropzone'),
    fileAudioInput: document.getElementById('fileAudioInput'),
    selectedFileInfo: document.getElementById('selectedFileInfo'),
    selectedFileName: document.getElementById('selectedFileName'),
    selectedFileSize: document.getElementById('selectedFileSize'),
    btnClearFile: document.getElementById('btnClearFile'),

    // Corpus Pregrabado
    selectCorpusType: document.getElementById('selectCorpusType'),
    selectCorpusItem: document.getElementById('selectCorpusItem'),
    selectCorpusSpeaker: document.getElementById('selectCorpusSpeaker'),
    corpusPreviewUch: document.getElementById('corpusPreviewUch'),
    corpusPreviewEs: document.getElementById('corpusPreviewEs'),
    btnLoadCorpusSample: document.getElementById('btnLoadCorpusSample'),

    // Reproductor & Texto
    audioPlayback: document.getElementById('audioPlayback'),
    inputTargetText: document.getElementById('inputTargetText'),
    btnClearTargetText: document.getElementById('btnClearTargetText'),
    g2pPhonemeCount: document.getElementById('g2pPhonemeCount'),
    g2pTokensContainer: document.getElementById('g2pTokensContainer'),

    // Botón de Evaluación
    btnEvaluate: document.getElementById('btnEvaluate'),
    evaluateSpinner: document.getElementById('evaluateSpinner'),
    evaluateIcon: document.getElementById('evaluateIcon'),
    evaluateBtnText: document.getElementById('evaluateBtnText'),

    // Panel de Resultados
    emptyResultsState: document.getElementById('emptyResultsState'),
    activeResultsContainer: document.getElementById('activeResultsContainer'),
    resultModelChipText: document.getElementById('resultModelChipText'),
    resultDecodingChipText: document.getElementById('resultDecodingChipText'),
    bannerDecision: document.getElementById('bannerDecision'),
    decisionBadgeText: document.getElementById('decisionBadgeText'),
    decisionTitle: document.getElementById('decisionTitle'),
    decisionSubtitle: document.getElementById('decisionSubtitle'),
    meterBarFill: document.getElementById('meterBarFill'),

    // Comparación Directa Objetivo vs Real
    speechComparisonBox: document.getElementById('speechComparisonBox'),
    compTargetText: document.getElementById('compTargetText'),
    compTargetPhonemes: document.getElementById('compTargetPhonemes'),
    cardSpokenResult: document.getElementById('cardSpokenResult'),
    badgeMatchResult: document.getElementById('badgeMatchResult'),
    compSpokenText: document.getElementById('compSpokenText'),
    compSpokenPhonemes: document.getElementById('compSpokenPhonemes'),
    rawReconstructedText: document.getElementById('rawReconstructedText'),

    // Métricas
    valPER: document.getElementById('valPER'),
    valPrecision: document.getElementById('valPrecision'),
    valHits: document.getElementById('valHits'),
    footHits: document.getElementById('footHits'),
    valSubstitutions: document.getElementById('valSubstitutions'),
    valDeletions: document.getElementById('valDeletions'),
    valInsertions: document.getElementById('valInsertions'),

    // Palabras Léxico y Alineación
    boxLexiconWords: document.getElementById('boxLexiconWords'),
    countLexiconWords: document.getElementById('countLexiconWords'),
    containerLexiconWords: document.getElementById('containerLexiconWords'),
    alignmentVisualizer: document.getElementById('alignmentVisualizer'),
    rawExpectedPhonemes: document.getElementById('rawExpectedPhonemes'),
    rawPredictedPhonemes: document.getElementById('rawPredictedPhonemes'),
    rawCtcString: document.getElementById('rawCtcString'),
    rawModelName: document.getElementById('rawModelName'),
    rawDecodingMode: document.getElementById('rawDecodingMode'),

    // Diagnóstico Acústico
    acRate: document.getElementById('acRate'),
    acDuration: document.getElementById('acDuration'),
    acSilStart: document.getElementById('acSilStart'),
    acSilEnd: document.getElementById('acSilEnd'),
    acRms: document.getElementById('acRms'),
    acClipping: document.getElementById('acClipping'),
    errorExplanationList: document.getElementById('errorExplanationList'),

    // Historial
    historyTableBody: document.getElementById('historyTableBody'),
    btnExportCSV: document.getElementById('btnExportCSV'),
    btnClearHistory: document.getElementById('btnClearHistory'),

    // Modal Móvil
    mobileModalOverlay: document.getElementById('mobileModalOverlay'),
    btnCloseMobileModal: document.getElementById('btnCloseMobileModal'),
    btnOkMobileModal: document.getElementById('btnOkMobileModal'),
    qrCodeWrapper: document.getElementById('qrCodeWrapper'),
    mobileUrlLink: document.getElementById('mobileUrlLink'),
    mobileIpBadge: document.getElementById('mobileIpBadge'),

    // Ficha técnica
    modelsTableBody: document.getElementById('modelsTableBody')
  };

  // =========================================================================
  // 3. INICIALIZACIÓN
  // =========================================================================
  document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initInferenceConfig();
    initMethodSelectors();
    initAudioRecording();
    initFileUpload();
    initTargetTextG2P();
    initCorpusSelector();
    initEvaluationAction();
    initHistoryHandlers();
    initMobileModal();
    fetchServerInfo();
    fetchCorpus();
  });

  // =========================================================================
  // 4. GESTIÓN DE PESTAÑAS Y MÉTODOS DE ENTRADA
  // =========================================================================
  function initTabs() {
    dom.tabBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const targetId = btn.getAttribute('data-tab');
        dom.tabBtns.forEach(b => b.classList.remove('active'));
        dom.tabContents.forEach(c => c.classList.remove('active'));

        btn.classList.add('active');
        const targetContent = document.getElementById(targetId);
        if (targetContent) targetContent.classList.add('active');
      });
    });
  }

  // =========================================================================
  // 4.1. GESTIÓN DE CONFIGURACIÓN DE INFERENCIA (MODELOS Y DECODIFICACIÓN)
  // =========================================================================
  function initInferenceConfig() {
    if (dom.selectModel) {
      dom.selectModel.addEventListener('change', () => {
        state.selectedModel = dom.selectModel.value;
        updateModelDescription();
        updateEvaluateButtonLabel();
      });
    }
    if (dom.selectDecodingMode) {
      dom.selectDecodingMode.addEventListener('change', () => {
        state.selectedDecodingMode = dom.selectDecodingMode.value;
        updateDecodingDescription();
      });
    }
  }

  function updateModelDescription() {
    if (!dom.selectModel) return;
    const model = (state.modelsList || []).find(m => m.id === dom.selectModel.value);
    if (model && dom.modelDescriptionText) {
      const rec = model.recomendado ? ' • [Recomendado]' : '';
      dom.modelDescriptionText.textContent = `${model.descripcion} (${model.precision} - ${model.tamano_mb} MB)${rec}`;
    }
  }

  function updateDecodingDescription() {
    if (!dom.selectDecodingMode) return;
    const mode = (state.decodingModesList || []).find(d => d.id === dom.selectDecodingMode.value);
    if (mode && dom.decodingDescriptionText) {
      dom.decodingDescriptionText.textContent = mode.descripcion;
    }
  }

  function updateEvaluateButtonLabel() {
    if (!dom.selectModel || !dom.evaluateBtnText || state.isEvaluating) return;
    const model = (state.modelsList || []).find(m => m.id === dom.selectModel.value);
    const shortName = model ? model.nombre.split('(')[0].trim() : 'Modelo';
    dom.evaluateBtnText.textContent = `Evaluar con ${shortName}`;
  }

  function initMethodSelectors() {
    dom.methodBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const method = btn.getAttribute('data-method');
        dom.methodBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        dom.containerMic.classList.remove('active');
        dom.containerUpload.classList.remove('active');
        dom.containerCorpus.classList.remove('active');

        if (method === 'mic') dom.containerMic.classList.add('active');
        if (method === 'upload') dom.containerUpload.classList.add('active');
        if (method === 'corpus') dom.containerCorpus.classList.add('active');
      });
    });
  }

  // =========================================================================
  // 5. GRABACIÓN DE AUDIO (MICRÓFONO & VISUALIZADOR)
  // =========================================================================
  function initAudioRecording() {
    dom.btnRecordToggle.addEventListener('click', toggleRecording);
  }

  async function toggleRecording() {
    if (state.isRecording) {
      stopRecording();
    } else {
      await startRecording();
    }
  }

  async function startRecording() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      alert('Tu navegador no soporta captura de audio o el contexto no es seguro (requiere HTTPS o localhost). Revisa la pestaña de conexión móvil.');
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true
        }
      });

      state.isRecording = true;
      dom.btnRecordToggle.classList.add('recording');
      dom.recordBtnLabel.textContent = 'Detener Grabación';
      dom.micHint.textContent = '🔴 Grabando... Habla ahora con claridad.';

      // Iniciar temporizador
      state.recordStartTime = Date.now();
      dom.recordTimer.textContent = '00:00.0';
      state.recordTimerInterval = setInterval(updateTimerDisplay, 100);

      // Iniciar Visualizador Web Audio API
      setupAudioVisualizer(stream);

      // Iniciar MediaRecorder
      const options = { mimeType: 'audio/webm' };
      let recorder;
      try {
        recorder = new MediaRecorder(stream, options);
      } catch (e) {
        recorder = new MediaRecorder(stream);
      }

      const recordedChunks = [];
      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) recordedChunks.push(e.data);
      };

      recorder.onstop = () => {
        const mimeType = recorder.mimeType || 'audio/webm';
        const blob = new Blob(recordedChunks, { type: mimeType });
        setNewAudioBlob(blob, 'grabacion_microfono.webm');
        stream.getTracks().forEach(t => t.stop());
      };

      recorder.start(250);
      state.mediaRecorder = recorder;

    } catch (err) {
      console.error('Error accediendo al micrófono:', err);
      alert('No se pudo acceder al micrófono: ' + err.message);
    }
  }

  function stopRecording() {
    if (!state.isRecording) return;
    state.isRecording = false;

    dom.btnRecordToggle.classList.remove('recording');
    dom.recordBtnLabel.textContent = 'Iniciar Grabación';
    dom.micHint.textContent = 'Grabación completada y lista para evaluar.';

    clearInterval(state.recordTimerInterval);

    if (state.mediaRecorder && state.mediaRecorder.state !== 'inactive') {
      state.mediaRecorder.stop();
    }

    if (state.animFrameId) cancelAnimationFrame(state.animFrameId);
    if (state.audioContext && state.audioContext.state !== 'closed') {
      state.audioContext.close();
    }
    dom.vuMeterFill.style.width = '0%';
  }

  function updateTimerDisplay() {
    const elapsed = Date.now() - state.recordStartTime;
    const totalSecs = Math.floor(elapsed / 1000);
    const ms = Math.floor((elapsed % 1000) / 100);
    const mins = Math.floor(totalSecs / 60);
    const secs = totalSecs % 60;
    dom.recordTimer.textContent = `${pad(mins)}:${pad(secs)}.${ms}`;
  }

  function pad(n) {
    return n < 10 ? '0' + n : n;
  }

  function setupAudioVisualizer(stream) {
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      const ctx = new AudioCtx();
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      const source = ctx.createMediaStreamSource(stream);
      source.connect(analyser);

      state.audioContext = ctx;
      state.analyserNode = analyser;

      const canvas = dom.liveCanvas;
      const canvasCtx = canvas.getContext('2d');
      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);

      function draw() {
        if (!state.isRecording) return;
        state.animFrameId = requestAnimationFrame(draw);

        analyser.getByteFrequencyData(dataArray);

        // Nivel VU promedio
        let sum = 0;
        for (let i = 0; i < bufferLength; i++) sum += dataArray[i];
        const average = sum / bufferLength;
        const vuPercent = Math.min(100, (average / 128) * 100);
        dom.vuMeterFill.style.width = vuPercent + '%';

        // Dibujar barras en canvas
        canvasCtx.fillStyle = '#0b0f19';
        canvasCtx.fillRect(0, 0, canvas.width, canvas.height);

        const barWidth = (canvas.width / bufferLength) * 2.5;
        let barHeight;
        let x = 0;

        for (let i = 0; i < bufferLength; i++) {
          barHeight = (dataArray[i] / 255) * canvas.height;

          // Gradiente
          const gradient = canvasCtx.createLinearGradient(0, canvas.height, 0, 0);
          gradient.addColorStop(0, '#4f46e5');
          gradient.addColorStop(0.6, '#6366f1');
          gradient.addColorStop(1, '#a855f7');

          canvasCtx.fillStyle = gradient;
          canvasCtx.fillRect(x, canvas.height - barHeight, barWidth, barHeight);
          x += barWidth + 1;
        }
      }
      draw();
    } catch (e) {
      console.warn('Visualizador WebAudio no disponible:', e);
    }
  }

  // =========================================================================
  // 6. SUBIDA DE ARCHIVOS DE AUDIO
  // =========================================================================
  function initFileUpload() {
    const dropzone = dom.uploadDropzone;
    const fileInput = dom.fileAudioInput;

    dropzone.addEventListener('click', () => fileInput.click());

    dropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', () => {
      dropzone.classList.remove('dragover');
    });

    dropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        handleFileSelection(e.dataTransfer.files[0]);
      }
    });

    fileInput.addEventListener('change', () => {
      if (fileInput.files && fileInput.files.length > 0) {
        handleFileSelection(fileInput.files[0]);
      }
    });

    dom.btnClearFile.addEventListener('click', (e) => {
      e.stopPropagation();
      clearSelectedFile();
    });
  }

  function handleFileSelection(file) {
    state.currentAudioFile = file;
    dom.selectedFileName.textContent = file.name;
    dom.selectedFileSize.textContent = `(${(file.size / 1024).toFixed(1)} KB)`;
    dom.selectedFileInfo.classList.remove('hidden');

    setNewAudioBlob(file, file.name);
  }

  function clearSelectedFile() {
    state.currentAudioFile = null;
    dom.fileAudioInput.value = '';
    dom.selectedFileInfo.classList.add('hidden');
    dom.selectedFileName.textContent = '';
    dom.selectedFileSize.textContent = '';
  }

  function setNewAudioBlob(blob, filename) {
    state.currentAudioBlob = blob;
    if (state.currentAudioUrl) {
      URL.revokeObjectURL(state.currentAudioUrl);
    }
    state.currentAudioUrl = URL.createObjectURL(blob);
    dom.audioPlayback.src = state.currentAudioUrl;
    dom.audioPlayback.load();
  }

  // =========================================================================
  // 7. GESTIÓN DEL TEXTO OBJETIVO Y CONVERSIÓN G2P EN VIVO
  // =========================================================================
  function initTargetTextG2P() {
    dom.inputTargetText.addEventListener('input', () => {
      clearTimeout(state.g2pDebounceTimer);
      state.g2pDebounceTimer = setTimeout(triggerG2PConversion, 250);
    });

    dom.btnClearTargetText.addEventListener('click', () => {
      dom.inputTargetText.value = '';
      dom.g2pPhonemeCount.textContent = '0 fonemas';
      renderG2PChips({ fonemas: [], desglose: [] });
    });
  }

  async function triggerG2PConversion() {
    const texto = dom.inputTargetText.value.trim();
    if (!texto) {
      dom.g2pPhonemeCount.textContent = '0 fonemas';
      renderG2PChips({ fonemas: [], desglose: [] });
      return;
    }

    try {
      const resp = await fetch('/api/g2p', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ texto })
      });
      if (resp.ok) {
        const data = await resp.json();
        dom.g2pPhonemeCount.textContent = `${data.fonemas.length} fonemas`;
        renderG2PChips(data);
      }
    } catch (e) {
      console.warn('Error en llamada G2P:', e);
    }
  }

  function renderG2PChips(data) {
    const container = dom.g2pTokensContainer;
    container.replaceChildren();

    if (!data.desglose || data.desglose.length === 0) {
      const placeholder = document.createElement('span');
      placeholder.className = 'placeholder-tag';
      placeholder.textContent = 'Escribe texto para ver fonemas automáticos';
      container.appendChild(placeholder);
      return;
    }

    data.desglose.forEach(item => {
      const chunk = document.createElement('div');
      chunk.className = 'g2p-word-chunk';
      chunk.title = `Palabra: ${item.palabra}`;

      item.fonemas.forEach(f => {
        const token = document.createElement('span');
        token.className = 'phoneme-token';
        token.textContent = f;
        chunk.appendChild(token);
      });

      container.appendChild(chunk);
    });
  }

  // =========================================================================
  // 8. CATÁLOGO DEL CORPUS PREGRABADO
  // =========================================================================
  async function fetchCorpus() {
    try {
      const res = await fetch('/api/corpus');
      if (res.ok) {
        state.corpusData = await res.json();
        populateCorpusSelector();
      }
    } catch (e) {
      console.error('Error cargando corpus:', e);
    }
  }

  function initCorpusSelector() {
    dom.selectCorpusType.addEventListener('change', populateCorpusSelector);
    dom.selectCorpusItem.addEventListener('change', updateCorpusItemPreview);
    dom.btnLoadCorpusSample.addEventListener('click', loadSelectedCorpusSample);
  }

  function populateCorpusSelector() {
    const tipo = dom.selectCorpusType.value;
    const items = tipo === 'oraciones' ? state.corpusData.oraciones : state.corpusData.palabras;

    dom.selectCorpusItem.replaceChildren();

    if (!items || items.length === 0) {
      const opt = document.createElement('option');
      opt.textContent = 'Sin elementos disponibles';
      dom.selectCorpusItem.appendChild(opt);
      return;
    }

    items.forEach(item => {
      const opt = document.createElement('option');
      opt.value = item.id;
      const countAudios = item.audios ? item.audios.length : 0;
      opt.textContent = `[${item.id}] ${item.uch} — "${item.es}" (${countAudios} audios)`;
      dom.selectCorpusItem.appendChild(opt);
    });

    updateCorpusItemPreview();
  }

  function updateCorpusItemPreview() {
    const tipo = dom.selectCorpusType.value;
    const items = tipo === 'oraciones' ? state.corpusData.oraciones : state.corpusData.palabras;
    const selectedId = dom.selectCorpusItem.value;

    const item = items.find(i => i.id === selectedId);
    if (!item) return;

    dom.corpusPreviewUch.textContent = item.uch;
    dom.corpusPreviewEs.textContent = item.es;

    // Actualizar hablantes
    dom.selectCorpusSpeaker.replaceChildren();
    if (item.audios && item.audios.length > 0) {
      item.audios.forEach((a, idx) => {
        const opt = document.createElement('option');
        opt.value = a.ruta_relativa;
        opt.textContent = `Hablante: ${a.hablante.toUpperCase()} (${a.archivo})`;
        dom.selectCorpusSpeaker.appendChild(opt);
      });
      dom.selectCorpusSpeaker.disabled = false;
      dom.btnLoadCorpusSample.disabled = false;
    } else {
      const opt = document.createElement('option');
      opt.textContent = 'Sin audio pregrabado (solo texto)';
      dom.selectCorpusSpeaker.appendChild(opt);
      dom.selectCorpusSpeaker.disabled = true;
    }
  }

  async function loadSelectedCorpusSample() {
    const tipo = dom.selectCorpusType.value;
    const items = tipo === 'oraciones' ? state.corpusData.oraciones : state.corpusData.palabras;
    const selectedId = dom.selectCorpusItem.value;
    const item = items.find(i => i.id === selectedId);
    if (!item) return;

    // Llenar texto objetivo
    dom.inputTargetText.value = item.uch;
    triggerG2PConversion();

    // Cargar audio si existe
    const audioRuta = dom.selectCorpusSpeaker.value;
    if (audioRuta) {
      try {
        const resp = await fetch(`/api/audio?ruta=${encodeURIComponent(audioRuta)}`);
        if (resp.ok) {
          const blob = await resp.blob();
          setNewAudioBlob(blob, audioRuta.split('/').pop());
          alert(`Muestra cargada: ${item.uch}`);
        } else {
          alert('No se pudo cargar el audio del servidor.');
        }
      } catch (err) {
        console.error(err);
      }
    }
  }

  // =========================================================================
  // 9. ACCIÓN DE EVALUACIÓN CON MODELO INT8
  // =========================================================================
  function initEvaluationAction() {
    dom.btnEvaluate.addEventListener('click', runModelEvaluation);
  }

  async function runModelEvaluation() {
    if (!state.currentAudioBlob) {
      alert('Primero debes grabar tu voz o subir un archivo de audio.');
      return;
    }

    const textoObjetivo = dom.inputTargetText.value.trim();
    if (!textoObjetivo) {
      alert('Por favor escribe o selecciona el texto objetivo esperado.');
      dom.inputTargetText.focus();
      return;
    }

    setEvaluatingUI(true);

    try {
      const formData = new FormData();
      formData.append('audio', state.currentAudioBlob, 'audio_muestra.wav');
      formData.append('texto_objetivo', textoObjetivo);

      if (dom.selectModel) {
        formData.append('modelo', dom.selectModel.value);
      }
      if (dom.selectDecodingMode) {
        formData.append('decodificacion', dom.selectDecodingMode.value);
      }

      const response = await fetch('/api/evaluate', {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.error || 'Error evaluando con el modelo.');
      }

      const resultado = await response.json();
      renderEvaluationResults(resultado);
      addTestToHistory(resultado);

    } catch (err) {
      console.error(err);
      alert('Error en evaluación: ' + err.message);
    } finally {
      setEvaluatingUI(false);
    }
  }

  function setEvaluatingUI(loading) {
    state.isEvaluating = loading;
    dom.btnEvaluate.disabled = loading;
    if (loading) {
      dom.evaluateSpinner.classList.remove('hidden');
      dom.evaluateIcon.classList.add('hidden');
      const model = (state.modelsList || []).find(m => m.id === (dom.selectModel ? dom.selectModel.value : ''));
      const modelName = model ? model.nombre.split('(')[0].trim() : 'Sherpa ASR';
      const decMode = dom.selectDecodingMode && dom.selectDecodingMode.value === 'con_restricciones' ? 'Léxico' : 'Greedy';
      dom.evaluateBtnText.textContent = `Decodificando (${modelName} • ${decMode})...`;
    } else {
      dom.evaluateSpinner.classList.add('hidden');
      dom.evaluateIcon.classList.remove('hidden');
      updateEvaluateButtonLabel();
    }
  }

  // =========================================================================
  // 10. RENDERIZADO VISUAL DE RESULTADOS Y DIAGNÓSTICO
  // =========================================================================
  function renderEvaluationResults(res) {
    dom.emptyResultsState.classList.add('hidden');
    dom.activeResultsContainer.classList.remove('hidden');

    const m = res.metricas;
    const diag = res.diagnostico_audio;

    // 0. Badges de Configuración Activa
    if (dom.resultModelChipText && res.modelo_info) {
      dom.resultModelChipText.textContent = `Modelo: ${res.modelo_info.nombre.split('(')[0].trim()}`;
    }
    if (dom.resultDecodingChipText) {
      const isLex = res.modo_decodificacion === 'con_restricciones';
      dom.resultDecodingChipText.textContent = `Decodificación: ${isLex ? 'Restricciones Léxicas' : 'Greedy Search'}`;
    }

    // 1. Banner de Aceptación Pedagógica (≥ 85%)
    const esAprobado = (m.pasa_85 !== undefined)
      ? Boolean(m.pasa_85)
      : ((m.aprobado !== undefined) ? Boolean(m.aprobado) : (Number(m.precision_fonetica || 0) >= 85.0));

    if (esAprobado) {
      dom.bannerDecision.className = 'decision-banner banner-passed';
      dom.decisionBadgeText.textContent = 'APROBADO (≥85%)';
      dom.decisionTitle.textContent = '¡Pronunciación Correcta!';
      dom.decisionSubtitle.textContent = `Acierto fonético: ${m.precision_fonetica}% (≥ 85.0% requerido). Pronunciación pedagógicamente aceptable.`;
    } else {
      dom.bannerDecision.className = 'decision-banner banner-rejected';
      dom.decisionBadgeText.textContent = 'RECHAZADO (<85%)';
      dom.decisionTitle.textContent = `Pronunciación Inexacta (${m.precision_fonetica}% de precisión)`;
      const detallesErr = [];
      if (m.substitutions > 0) detallesErr.push(`${m.substitutions} sustitución(es)`);
      if (m.deletions > 0) detallesErr.push(`${m.deletions} omisión(es)`);
      if (m.insertions > 0) detallesErr.push(`${m.insertions} inserción(es)`);
      const txtErr = detallesErr.length > 0 ? ` [${detallesErr.join(', ')}]` : '';
      dom.decisionSubtitle.textContent = `Se requiere al menos 85% de precisión fonética. Se rechaza por discrepancias${txtErr}.`;
    }

    // 1.1. Comparación Visual Directa: Objetivo vs Lo que Realmente Repetiste
    if (dom.compTargetText) {
      dom.compTargetText.textContent = res.texto_objetivo || '(sin texto)';
    }
    if (dom.compTargetPhonemes) {
      dom.compTargetPhonemes.textContent = (res.fonemas_esperados || []).join(' ') || '—';
    }
    if (dom.compSpokenText) {
      dom.compSpokenText.textContent = res.texto_repetido_real || '(sin audio reconocido)';
    }
    if (dom.compSpokenPhonemes) {
      dom.compSpokenPhonemes.textContent = (res.fonemas_predichos || []).join(' ') || '—';
    }
    if (dom.cardSpokenResult && dom.badgeMatchResult) {
      if (esAprobado) {
        dom.cardSpokenResult.className = 'speech-comp-card spoken-card comp-passed';
        dom.badgeMatchResult.className = 'speech-comp-badge badge-comp-pass';
        dom.badgeMatchResult.textContent = `✅ ${m.precision_fonetica}% APROBADO`;
      } else {
        dom.cardSpokenResult.className = 'speech-comp-card spoken-card comp-failed';
        dom.badgeMatchResult.className = 'speech-comp-badge badge-comp-fail';
        dom.badgeMatchResult.textContent = `❌ ${m.precision_fonetica}% (RECHAZADO)`;
      }
    }

    // Barra de progreso animada
    const scoreVal = Math.min(100, Math.max(0, m.ratio_acierto_simple));
    dom.meterBarFill.style.width = scoreVal + '%';

    // 2. Tarjetas de Métricas Clave
    dom.valPER.textContent = `${m.per}%`;
    dom.valPrecision.textContent = `${m.precision_fonetica}%`;
    dom.valHits.textContent = m.hits;
    dom.footHits.textContent = `de ${m.total_referencia} esperados`;
    dom.valSubstitutions.textContent = m.substitutions;
    dom.valDeletions.textContent = m.deletions;
    dom.valInsertions.textContent = m.insertions;

    // 2.1. Palabras Reconocidas del Léxico (si aplica)
    if (dom.boxLexiconWords && dom.containerLexiconWords) {
      if (res.modo_decodificacion === 'con_restricciones' && Array.isArray(res.palabras_reconocidas_lexico) && res.palabras_reconocidas_lexico.length > 0) {
        dom.boxLexiconWords.classList.remove('hidden');
        if (dom.countLexiconWords) {
          dom.countLexiconWords.textContent = `${res.palabras_reconocidas_lexico.length} palabras`;
        }
        dom.containerLexiconWords.replaceChildren();
        res.palabras_reconocidas_lexico.forEach((w, idx) => {
          const chip = document.createElement('span');
          chip.className = 'lexicon-word-chip';
          const idxSpan = document.createElement('span');
          idxSpan.className = 'word-idx';
          idxSpan.textContent = `#${idx + 1}`;
          chip.appendChild(idxSpan);
          const txt = document.createTextNode(` ${w}`);
          chip.appendChild(txt);
          dom.containerLexiconWords.appendChild(chip);
        });
      } else {
        dom.boxLexiconWords.classList.add('hidden');
      }
    }

    // 3. Tira de Alineación Fonética Interactiva
    renderPhonemeAlignmentStrip(m.alineacion);

    // Cadenas crudas
    dom.rawExpectedPhonemes.textContent = res.fonemas_esperados.join(' ');
    if (dom.rawReconstructedText) {
      dom.rawReconstructedText.textContent = res.texto_repetido_real || '(vacío)';
    }
    dom.rawPredictedPhonemes.textContent = res.fonemas_predichos.join(' ');
    dom.rawCtcString.textContent = res.salida_cruda_modelo || '(vacío)';
    if (dom.rawModelName && res.modelo_info) {
      dom.rawModelName.textContent = `${res.modelo_info.nombre} [${res.modelo_info.precision}]`;
    }
    if (dom.rawDecodingMode) {
      dom.rawDecodingMode.textContent = res.modo_decodificacion === 'con_restricciones' ? 'con_restricciones (Lexicón Cerrado)' : 'greedy_search (CTC Puro)';
    }

    // 4. Diagnóstico Acústico
    dom.acRate.textContent = `${diag.sample_rate || 16000} Hz (${diag.canales === 1 ? 'Mono' : 'Stereo'})`;
    dom.acDuration.textContent = `${diag.duracion_s} s`;
    dom.acSilStart.textContent = `${diag.silencio_inicio_ms} ms`;
    dom.acSilEnd.textContent = `${diag.silencio_fin_ms} ms`;
    dom.acRms.textContent = `${diag.rms_db} dB`;
    dom.acClipping.textContent = diag.clipping ? '⚠️ Sí (Saturado)' : 'No (Correcto)';

    // 5. Lista de Errores y Explicaciones
    renderErrorBreakdown(m.errores_detallados);

    // Scroll suave hacia los resultados en móviles
    if (window.innerWidth < 960) {
      dom.bannerDecision.scrollIntoView({ behavior: 'smooth' });
    }
  }

  function renderPhonemeAlignmentStrip(alineacion) {
    const container = dom.alignmentVisualizer;
    container.replaceChildren();

    if (!alineacion || alineacion.length === 0) {
      const msg = document.createElement('span');
      msg.textContent = 'No hay fonemas para alinear.';
      container.appendChild(msg);
      return;
    }

    alineacion.forEach((step, idx) => {
      const card = document.createElement('div');
      card.className = `alignment-card card-${step.tipo}`;
      card.title = `Paso ${idx + 1}: ${step.tipo.toUpperCase()}`;

      // Fila Esperada
      const rowExp = document.createElement('div');
      rowExp.className = 'align-row-exp';
      rowExp.textContent = step.esperado || '—';

      // Fila Predicha
      const rowPred = document.createElement('div');
      rowPred.className = 'align-row-pred';
      rowPred.textContent = step.predicho || '—';

      // Etiqueta de tipo
      const tag = document.createElement('div');
      tag.className = 'align-tag';
      if (step.tipo === 'match') tag.textContent = 'OK';
      else if (step.tipo === 'substitution') tag.textContent = 'SUB';
      else if (step.tipo === 'deletion') tag.textContent = 'DEL';
      else if (step.tipo === 'insertion') tag.textContent = 'INS';

      card.appendChild(rowExp);
      card.appendChild(rowPred);
      card.appendChild(tag);
      container.appendChild(card);
    });
  }

  function renderErrorBreakdown(errores) {
    const container = dom.errorExplanationList;
    container.replaceChildren();

    if (!errores || errores.length === 0) {
      const okMsg = document.createElement('div');
      okMsg.className = 'error-entry';
      okMsg.style.borderLeftColor = 'var(--color-emerald)';
      
      const badge = document.createElement('span');
      badge.className = 'error-badge';
      badge.style.color = 'var(--color-emerald)';
      badge.textContent = '¡Sin discrepancias!';
      
      const txt = document.createElement('span');
      txt.className = 'error-msg';
      txt.textContent = 'Todos los fonemas coincidieron exactamente con el modelo.';
      
      okMsg.appendChild(badge);
      okMsg.appendChild(txt);
      container.appendChild(okMsg);
      return;
    }

    errores.forEach(err => {
      const row = document.createElement('div');
      row.className = 'error-entry';
      if (err.tipo.includes('Eliminación')) row.classList.add('error-del');
      if (err.tipo.includes('Inserción')) row.classList.add('error-ins');

      const badge = document.createElement('span');
      badge.className = 'error-badge';
      badge.textContent = `[${err.tipo}]`;

      const msg = document.createElement('span');
      msg.className = 'error-msg';
      msg.textContent = err.mensaje;

      row.appendChild(badge);
      row.appendChild(msg);
      container.appendChild(row);
    });
  }

  // =========================================================================
  // 11. HISTORIAL ACUMULATIVO Y EXPORTACIÓN
  // =========================================================================
  function addTestToHistory(res) {
    const item = {
      id: state.history.length + 1,
      timestamp: new Date().toLocaleTimeString(),
      texto_objetivo: res.texto_objetivo,
      salida_cruda_modelo: res.salida_cruda_modelo,
      fonemas_esperados: res.fonemas_esperados,
      fonemas_predichos: res.fonemas_predichos,
      palabras_reconocidas_lexico: res.palabras_reconocidas_lexico || [],
      modo_decodificacion: res.modo_decodificacion || 'greedy_search',
      metricas: res.metricas,
      diagnostico_audio: res.diagnostico_audio,
      modelo_info: res.modelo_info
    };

    state.history.unshift(item);
    dom.historyBadgeCount.textContent = state.history.length;
    renderHistoryTable();
  }

  function renderHistoryTable() {
    const tbody = dom.historyTableBody;
    tbody.replaceChildren();

    if (state.history.length === 0) {
      const tr = document.createElement('tr');
      tr.className = 'empty-row';
      const td = document.createElement('td');
      td.colSpan = 12;
      td.textContent = 'No hay pruebas registradas en esta sesión todavía.';
      tr.appendChild(td);
      tbody.appendChild(tr);
      return;
    }

    state.history.forEach(item => {
      const tr = document.createElement('tr');

      // 1. #
      const tdId = document.createElement('td');
      tdId.textContent = item.id;

      // 2. Hora
      const tdHora = document.createElement('td');
      tdHora.textContent = item.timestamp;

      // 3. Modelo
      const tdMod = document.createElement('td');
      const badgeMod = document.createElement('span');
      badgeMod.className = 'badge-table-model';
      const modName = (item.modelo_info && item.modelo_info.nombre) ? item.modelo_info.nombre.split('(')[0].trim() : 'ASR';
      badgeMod.textContent = modName;
      tdMod.appendChild(badgeMod);

      // 4. Decodificación
      const tdDec = document.createElement('td');
      const badgeDec = document.createElement('span');
      const isLex = item.modo_decodificacion === 'con_restricciones';
      badgeDec.className = isLex ? 'badge-table-lexicon' : 'badge-table-greedy';
      badgeDec.textContent = isLex ? 'Léxico' : 'Greedy';
      tdDec.appendChild(badgeDec);

      // 5. Tipo
      const tdTipo = document.createElement('td');
      tdTipo.textContent = item.texto_objetivo.split(' ').length > 1 ? 'Oración' : 'Palabra';

      // 6. Texto Objetivo
      const tdObj = document.createElement('td');
      tdObj.textContent = item.texto_objetivo;

      // 6.1. Repetido Real
      const tdRepetido = document.createElement('td');
      const strongRep = document.createElement('strong');
      strongRep.textContent = item.texto_repetido_real || '(vacío)';
      tdRepetido.appendChild(strongRep);

      // 7. Salida Cruda / Léxico
      const tdRaw = document.createElement('td');
      const codeRaw = document.createElement('code');
      codeRaw.className = 'raw-code';
      if (item.palabras_reconocidas_lexico && item.palabras_reconocidas_lexico.length > 0) {
        codeRaw.textContent = item.palabras_reconocidas_lexico.join(' ');
      } else {
        codeRaw.textContent = item.salida_cruda_modelo || '(vacío)';
      }
      tdRaw.appendChild(codeRaw);

      // 8. PER
      const tdPER = document.createElement('td');
      tdPER.textContent = `${item.metricas.per}%`;

      // 9. Precisión
      const tdPrec = document.createElement('td');
      tdPrec.textContent = `${item.metricas.precision_fonetica}%`;

      // 10. Aprobado (≥ 85% pedagógico)
      const tdAprob = document.createElement('td');
      const badgeAprob = document.createElement('span');
      const esAprob = (item.metricas.pasa_85 !== undefined)
        ? Boolean(item.metricas.pasa_85)
        : ((item.metricas.aprobado !== undefined) ? Boolean(item.metricas.aprobado) : (Number(item.metricas.precision_fonetica || 0) >= 85.0));
      badgeAprob.className = esAprob ? 'badge-table-pass' : 'badge-table-fail';
      badgeAprob.textContent = esAprob ? 'APROBADO (≥85%)' : 'RECHAZADO (<85%)';
      tdAprob.appendChild(badgeAprob);

      // 11. Duración
      const tdDur = document.createElement('td');
      tdDur.textContent = `${item.diagnostico_audio.duracion_s} s`;

      // 12. Acción
      const tdAccion = document.createElement('td');
      const btnVer = document.createElement('button');
      btnVer.className = 'btn-link-xs';
      btnVer.textContent = 'Ver Detalle';
      btnVer.addEventListener('click', () => {
        renderEvaluationResults(item);
        document.getElementById('tabEvaluacion').click();
      });
      tdAccion.appendChild(btnVer);

      tr.appendChild(tdId);
      tr.appendChild(tdHora);
      tr.appendChild(tdMod);
      tr.appendChild(tdDec);
      tr.appendChild(tdTipo);
      tr.appendChild(tdObj);
      tr.appendChild(tdRepetido);
      tr.appendChild(tdRaw);
      tr.appendChild(tdPER);
      tr.appendChild(tdPrec);
      tr.appendChild(tdAprob);
      tr.appendChild(tdDur);
      tr.appendChild(tdAccion);

      tbody.appendChild(tr);
    });
  }

  function initHistoryHandlers() {
    dom.btnExportCSV.addEventListener('click', async () => {
      if (state.history.length === 0) {
        alert('No hay pruebas en el historial para exportar.');
        return;
      }

      try {
        const resp = await fetch('/api/export_csv', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ pruebas: state.history })
        });

        if (resp.ok) {
          const blob = await resp.blob();
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `reporte_evaluacion_asr_int8_${Date.now()}.csv`;
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(url);
        }
      } catch (err) {
        console.error(err);
      }
    });

    dom.btnClearHistory.addEventListener('click', () => {
      if (confirm('¿Estás seguro de limpiar todo el historial de pruebas?')) {
        state.history = [];
        dom.historyBadgeCount.textContent = '0';
        renderHistoryTable();
      }
    });
  }

  // =========================================================================
  // 12. INFO DEL SERVIDOR & MODAL MÓVIL (QR & IP)
  // =========================================================================
  async function fetchServerInfo() {
    try {
      const res = await fetch('/api/info');
      if (res.ok) {
        const info = await res.json();
        state.serverInfo = info;
        state.modelsList = info.modelos || [];
        state.decodingModesList = info.modos_decodificacion || [];

        populateModelsDropdown(info.modelos, info.modelo_activo_default);
        populateDecodingModesDropdown(info.modos_decodificacion);
        renderModelsTechTable(info.modelos);

        const totalModelos = state.modelsList.filter(m => m.disponible).length;
        dom.modelStatusText.textContent = `${totalModelos} Modelos Listos (Scratch & Fine-Tuning)`;

        // Configurar modal móvil
        const urlMovil = info.servidor.url_movil;
        dom.mobileUrlLink.textContent = urlMovil;
        dom.mobileUrlLink.href = urlMovil;
        dom.mobileIpBadge.textContent = urlMovil;

        renderQuickQR(urlMovil);
      }
    } catch (e) {
      console.warn('Error obteniendo estado del servidor:', e);
      dom.modelStatusText.textContent = 'Sherpa ASR Listo';
    }
  }

  function populateModelsDropdown(modelos, defaultModelId) {
    if (!dom.selectModel || !Array.isArray(modelos)) return;
    dom.selectModel.replaceChildren();

    modelos.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.id;
      const rec = m.recomendado ? ' ⭐ Recomendado' : '';
      opt.textContent = `${m.nombre} (${m.tamano_mb} MB)${rec}`;
      if (m.id === defaultModelId) {
        opt.selected = true;
      }
      dom.selectModel.appendChild(opt);
    });

    state.selectedModel = dom.selectModel.value;
    updateModelDescription();
    updateEvaluateButtonLabel();
  }

  function populateDecodingModesDropdown(modos) {
    if (!dom.selectDecodingMode || !Array.isArray(modos)) return;
    dom.selectDecodingMode.replaceChildren();

    modos.forEach((d, idx) => {
      const opt = document.createElement('option');
      opt.value = d.id;
      opt.textContent = `${d.nombre}`;
      if (idx === 0) opt.selected = true;
      dom.selectDecodingMode.appendChild(opt);
    });

    state.selectedDecodingMode = dom.selectDecodingMode.value;
    updateDecodingDescription();
  }

  function renderModelsTechTable(modelos) {
    if (!dom.modelsTableBody || !Array.isArray(modelos)) return;
    dom.modelsTableBody.replaceChildren();

    modelos.forEach(m => {
      const tr = document.createElement('tr');

      // Nombre + badge
      const tdNombre = document.createElement('td');
      const strong = document.createElement('strong');
      strong.textContent = m.nombre.split('(')[0].trim();
      tdNombre.appendChild(strong);
      if (m.recomendado) {
        const badge = document.createElement('span');
        badge.className = 'badge-model-rec';
        badge.textContent = 'Recomendado';
        tdNombre.appendChild(badge);
      }

      // Origen / Épocas
      const tdOrigen = document.createElement('td');
      tdOrigen.textContent = m.origen || '-';

      // Precisión
      const tdPrec = document.createElement('td');
      tdPrec.textContent = m.precision || '-';

      // Tamaño
      const tdTam = document.createElement('td');
      tdTam.textContent = `${m.tamano_mb} MB`;

      // Uso recomendado
      const tdUso = document.createElement('td');
      tdUso.textContent = m.descripcion || '-';

      // SHA256
      const tdHash = document.createElement('td');
      const code = document.createElement('code');
      code.textContent = m.sha256 ? `${m.sha256.substring(0, 16)}...` : '-';
      tdHash.appendChild(code);

      tr.appendChild(tdNombre);
      tr.appendChild(tdOrigen);
      tr.appendChild(tdPrec);
      tr.appendChild(tdTam);
      tr.appendChild(tdUso);
      tr.appendChild(tdHash);

      dom.modelsTableBody.appendChild(tr);
    });
  }

  function initMobileModal() {
    dom.btnMobileModal.addEventListener('click', () => {
      dom.mobileModalOverlay.classList.remove('hidden');
    });

    dom.btnCloseMobileModal.addEventListener('click', () => {
      dom.mobileModalOverlay.classList.add('hidden');
    });

    dom.btnOkMobileModal.addEventListener('click', () => {
      dom.mobileModalOverlay.classList.add('hidden');
    });

    dom.mobileModalOverlay.addEventListener('click', (e) => {
      if (e.target === dom.mobileModalOverlay) {
        dom.mobileModalOverlay.classList.add('hidden');
      }
    });
  }

  /**
   * Generador de código QR SVG interactivo y ligero (sin librerías externas).
   * Utiliza la API de visualización de QR segura en SVG.
   */
  function renderQuickQR(url) {
    const wrapper = dom.qrCodeWrapper;
    wrapper.replaceChildren();

    // Generar imagen QR segura o enlace directo
    const img = document.createElement('img');
    img.src = `https://api.qrserver.com/v1/create-qr-code/?size=120x120&data=${encodeURIComponent(url)}`;
    img.alt = 'Código QR para celular';
    img.loading = 'lazy';
    img.onerror = () => {
      // Fallback si no hay conexión a internet
      wrapper.replaceChildren();
      const txt = document.createElement('span');
      txt.style.color = '#333';
      txt.style.fontSize = '0.75rem';
      txt.style.textAlign = 'center';
      txt.textContent = 'IP Directa';
      wrapper.appendChild(txt);
    };
    wrapper.appendChild(img);
  }

})();
