/**
 * YouTubeダウンローダー - フロントエンドアプリケーション
 */

// グローバル変数
let currentVideoInfo = null;
let websocket = null;
let currentDownloadId = null;

// DOM要素
const elements = {
    videoUrl: document.getElementById('videoUrl'),
    fetchInfoBtn: document.getElementById('fetchInfoBtn'),
    downloadBtn: document.getElementById('downloadBtn'),
    newDownloadBtn: document.getElementById('newDownloadBtn'),
    retryBtn: document.getElementById('retryBtn'),
    downloadFileBtn: document.getElementById('downloadFileBtn'),

    previewSection: document.getElementById('preview-section'),
    progressSection: document.getElementById('progress-section'),
    completeSection: document.getElementById('complete-section'),
    errorSection: document.getElementById('error-section'),

    videoThumbnail: document.getElementById('videoThumbnail'),
    videoTitle: document.getElementById('videoTitle'),
    videoDuration: document.getElementById('videoDuration'),
    videoUploader: document.getElementById('videoUploader'),
    videoViews: document.getElementById('videoViews'),
    videoDescription: document.getElementById('videoDescription'),

    progressBar: document.getElementById('progressBar'),
    progressPercent: document.getElementById('progressPercent'),
    progressSpeed: document.getElementById('progressSpeed'),
    progressEta: document.getElementById('progressEta'),
    progressMessage: document.getElementById('progressMessage'),

    completeFilename: document.getElementById('completeFilename'),
    errorMessage: document.getElementById('errorMessage'),

    historyList: document.getElementById('historyList'),

    // 品質選択要素
    formatTypeRadios: document.getElementsByName('formatType'),
    videoQualitySelect: document.getElementById('videoQuality'),
    audioQualitySelect: document.getElementById('audioQuality'),
    videoQualitySelector: document.getElementById('videoQualitySelector'),
    audioQualitySelector: document.getElementById('audioQualitySelector'),
};

// 初期化
document.addEventListener('DOMContentLoaded', () => {
    initEventListeners();
    initWebSocket();
    loadHistory();
});

/**
 * イベントリスナーの初期化
 */
function initEventListeners() {
    elements.fetchInfoBtn.addEventListener('click', handleFetchInfo);
    elements.downloadBtn.addEventListener('click', handleDownload);
    elements.newDownloadBtn.addEventListener('click', resetForm);
    elements.retryBtn.addEventListener('click', resetForm);

    // Enterキーで動画情報を取得
    elements.videoUrl.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            handleFetchInfo();
        }
    });

    // 品質選択のトグル
    elements.formatTypeRadios.forEach(radio => {
        radio.addEventListener('change', handleFormatTypeChange);
    });
}

/**
 * WebSocket接続の初期化
 */
function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    websocket = new WebSocket(wsUrl);

    websocket.onopen = () => {
        console.log('WebSocket接続が確立されました');
    };

    websocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };

    websocket.onerror = (error) => {
        console.error('WebSocketエラー:', error);
    };

    websocket.onclose = () => {
        console.log('WebSocket接続が閉じられました。再接続します...');
        setTimeout(initWebSocket, 3000);
    };
}

/**
 * WebSocketメッセージの処理
 */
function handleWebSocketMessage(data) {
    if (data.status === 'downloading') {
        updateProgress(data);
    } else if (data.status === 'finished') {
        elements.progressMessage.textContent = data.message || 'ファイルを処理中...';
    } else if (data.status === 'completed') {
        handleDownloadComplete(data.result);
    } else if (data.status === 'error') {
        showError(data.error);
    }
}

/**
 * 動画情報の取得
 */
async function handleFetchInfo() {
    const url = elements.videoUrl.value.trim();

    if (!url) {
        showError('URLを入力してください');
        return;
    }

    // ボタンをローディング状態に
    setButtonLoading(elements.fetchInfoBtn, true);
    hideAllSections();

    try {
        const response = await fetch('/api/video-info', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '動画情報の取得に失敗しました');
        }

        const result = await response.json();
        currentVideoInfo = result.data;
        showVideoPreview(currentVideoInfo);

    } catch (error) {
        showError(error.message);
    } finally {
        setButtonLoading(elements.fetchInfoBtn, false);
    }
}

/**
 * 動画プレビューの表示
 */
function showVideoPreview(info) {
    elements.videoThumbnail.src = info.thumbnail || 'https://via.placeholder.com/640x360?text=No+Thumbnail';
    elements.videoTitle.textContent = info.title;
    elements.videoDuration.textContent = formatDuration(info.duration);
    elements.videoUploader.textContent = info.uploader;
    elements.videoViews.textContent = formatNumber(info.view_count) + ' 回視聴';
    elements.videoDescription.textContent = info.description || '説明なし';

    hideAllSections();
    elements.previewSection.classList.remove('hidden');
}

/**
 * ダウンロードの開始
 */
async function handleDownload() {
    const url = elements.videoUrl.value.trim();

    if (!url) {
        showError('URLを入力してください');
        return;
    }

    setButtonLoading(elements.downloadBtn, true);
    hideAllSections();
    elements.progressSection.classList.remove('hidden');

    // 進捗をリセット
    updateProgress({ progress: 0, speed: 0, eta: 0 });

    // 品質設定を取得
    const formatType = getSelectedFormatType();
    const quality = formatType === 'video'
        ? elements.videoQualitySelect.value
        : 'best';
    const audioOnly = formatType === 'audio';
    const audioQuality = formatType === 'audio'
        ? elements.audioQualitySelect.value
        : '192';

    try {
        const response = await fetch('/api/download', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                url,
                quality,
                audio_only: audioOnly,
                audio_quality: audioQuality,
            }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'ダウンロードの開始に失敗しました');
        }

        const result = await response.json();
        console.log('ダウンロード開始:', result);

    } catch (error) {
        showError(error.message);
    } finally {
        setButtonLoading(elements.downloadBtn, false);
    }
}

/**
 * 進捗の更新
 */
function updateProgress(data) {
    const progress = Math.round(data.progress || 0);
    const speed = formatSpeed(data.speed || 0);
    const eta = formatEta(data.eta || 0);

    elements.progressBar.style.width = `${progress}%`;
    elements.progressPercent.textContent = `${progress}%`;
    elements.progressSpeed.textContent = speed;
    elements.progressEta.textContent = eta;
}

/**
 * ダウンロード完了の処理
 */
function handleDownloadComplete(result) {
    hideAllSections();
    elements.completeSection.classList.remove('hidden');

    elements.completeFilename.textContent = result.filename;
    elements.downloadFileBtn.href = `/api/downloads/${result.id}/file`;
    elements.downloadFileBtn.download = result.filename;

    currentDownloadId = result.id;

    // 履歴を再読み込み
    loadHistory();
}

/**
 * 履歴の読み込み
 */
async function loadHistory() {
    try {
        const response = await fetch('/api/history');
        const result = await response.json();

        if (result.success && result.data.length > 0) {
            displayHistory(result.data);
        } else {
            displayEmptyHistory();
        }
    } catch (error) {
        console.error('履歴の読み込みに失敗:', error);
        displayEmptyHistory();
    }
}

/**
 * 履歴の表示
 */
function displayHistory(history) {
    elements.historyList.innerHTML = '';

    history.forEach(item => {
        const historyItem = createHistoryItem(item);
        elements.historyList.appendChild(historyItem);
    });
}

/**
 * 履歴アイテムの作成
 */
function createHistoryItem(item) {
    const div = document.createElement('div');
    div.className = 'history-item';

    const thumbnail = item.thumbnail || 'https://via.placeholder.com/640x360?text=No+Thumbnail';
    const date = new Date(item.completed_at).toLocaleString('ja-JP');

    div.innerHTML = `
        <div class="history-thumbnail">
            <img src="${thumbnail}" alt="${item.title}">
        </div>
        <div class="history-info">
            <div class="history-title">${item.title}</div>
            <div class="history-date">${date}</div>
        </div>
    `;

    // クリックでダウンロード
    div.addEventListener('click', () => {
        window.location.href = `/api/downloads/${item.id}/file`;
    });

    return div;
}

/**
 * 空の履歴表示
 */
function displayEmptyHistory() {
    elements.historyList.innerHTML = `
        <div class="history-empty">まだダウンロード履歴がありません</div>
    `;
}

/**
 * エラーの表示
 */
function showError(message) {
    hideAllSections();
    elements.errorSection.classList.remove('hidden');
    elements.errorMessage.textContent = message;
}

/**
 * 全セクションを非表示
 */
function hideAllSections() {
    elements.previewSection.classList.add('hidden');
    elements.progressSection.classList.add('hidden');
    elements.completeSection.classList.add('hidden');
    elements.errorSection.classList.add('hidden');
}

/**
 * フォームのリセット
 */
function resetForm() {
    elements.videoUrl.value = '';
    currentVideoInfo = null;
    currentDownloadId = null;
    hideAllSections();
    elements.videoUrl.focus();
}

/**
 * ボタンのローディング状態を設定
 */
function setButtonLoading(button, isLoading) {
    if (isLoading) {
        button.disabled = true;
        button.style.opacity = '0.6';
        button.style.cursor = 'not-allowed';
    } else {
        button.disabled = false;
        button.style.opacity = '1';
        button.style.cursor = 'pointer';
    }
}

/**
 * 時間のフォーマット（秒 → MM:SS）
 */
function formatDuration(seconds) {
    if (!seconds) return '00:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

/**
 * 数値のフォーマット（3桁区切り）
 */
function formatNumber(num) {
    if (!num) return '0';
    return num.toLocaleString('ja-JP');
}

/**
 * 速度のフォーマット（バイト/秒 → MB/s）
 */
function formatSpeed(bytesPerSecond) {
    if (!bytesPerSecond) return '0 MB/s';
    const mbps = bytesPerSecond / (1024 * 1024);
    return `${mbps.toFixed(2)} MB/s`;
}

/**
 * 残り時間のフォーマット（秒 → 分秒）
 */
function formatEta(seconds) {
    if (!seconds) return '-- 残り';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);

    if (mins > 0) {
        return `${mins}分${secs}秒 残り`;
    } else {
        return `${secs}秒 残り`;
    }
}

/**
 * フォーマットタイプの変更処理
 */
function handleFormatTypeChange(event) {
    const formatType = event.target.value;

    if (formatType === 'video') {
        elements.videoQualitySelector.classList.remove('hidden');
        elements.audioQualitySelector.classList.add('hidden');
    } else {
        elements.videoQualitySelector.classList.add('hidden');
        elements.audioQualitySelector.classList.remove('hidden');
    }
}

/**
 * 選択されたフォーマットタイプを取得
 */
function getSelectedFormatType() {
    for (const radio of elements.formatTypeRadios) {
        if (radio.checked) {
            return radio.value;
        }
    }
    return 'video'; // デフォルト
}
