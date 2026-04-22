const { invoke } = window.__TAURI__.core;

const cookieInput = document.getElementById('cookie-input');
const surveyIdInput = document.getElementById('survey-id');
const downloadBtn = document.getElementById('download-btn');
const progressContainer = document.getElementById('progress-container');
const progressText = document.getElementById('progress-text');
const logOutput = document.getElementById('log-output');
const clearLogBtn = document.getElementById('clear-log');

let isDownloading = false;

function getTimestamp() {
    const now = new Date();
    const hours = String(now.getHours()).padStart(2, '0');
    const mins = String(now.getMinutes()).padStart(2, '0');
    const secs = String(now.getSeconds()).padStart(2, '0');
    return `${hours}:${mins}:${secs}`;
}

function addLog(message, type = '') {
    const line = document.createElement('div');
    line.className = 'log-line';
    
    let msgClass = 'log-msg';
    if (message.includes('✅') || message.includes('成功')) msgClass += ' success';
    else if (message.includes('❌') || message.includes('错误')) msgClass += ' error';
    else if (message.includes('📥') || message.includes('🚀')) msgClass += ' info';
    
    line.innerHTML = `<span class="log-time">[${getTimestamp()}]</span><span class="${msgClass}">${escapeHtml(message)}</span>`;
    logOutput.appendChild(line);
    logOutput.scrollTop = logOutput.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showAlert(message, type = 'success') {
    const existing = document.querySelector('.alert');
    if (existing) existing.remove();
    
    const alert = document.createElement('div');
    alert.className = `alert ${type}`;
    alert.textContent = message;
    document.body.appendChild(alert);
    
    setTimeout(() => alert.remove(), 4000);
}

function setDownloading(state) {
    isDownloading = state;
    downloadBtn.disabled = state;
    downloadBtn.querySelector('.btn-text').textContent = state ? '下载中...' : '开始下载';
    progressContainer.style.display = state ? 'block' : 'none';
    
    if (!state) {
        surveyIdInput.removeAttribute('readonly');
        cookieInput.removeAttribute('readonly');
    } else {
        surveyIdInput.setAttribute('readonly', 'readonly');
        cookieInput.setAttribute('readonly', 'readonly');
    }
}

clearLogBtn.addEventListener('click', () => {
    logOutput.innerHTML = '';
});

downloadBtn.addEventListener('click', async () => {
    const cookieText = cookieInput.value.trim();
    const surveyId = surveyIdInput.value.trim();
    
    if (!cookieText) {
        showAlert('请先粘贴 Cookie 内容', 'warning');
        cookieInput.focus();
        return;
    }
    
    if (!surveyId || !/^\d+$/.test(surveyId)) {
        showAlert('请输入有效的问卷ID（纯数字）', 'warning');
        surveyIdInput.focus();
        return;
    }
    
    setDownloading(true);
    addLog('🔍 开始解析Cookie...');
    
    try {
        const result = await invoke('download_data', {
            cookieText,
            surveyId,
        });
        
        if (result.success) {
            addLog(`✅ 成功！共下载 ${result.total} 条数据`);
            showAlert(`下载完成！共 ${result.total} 条数据\n📁 ${result.filename}`, 'success');
        } else {
            addLog(`❌ ${result.message}`);
            showAlert(result.message, 'error');
        }
    } catch (error) {
        addLog(`❌ 程序异常: ${error}`);
        showAlert(`发生错误: ${error}`, 'error');
    } finally {
        setDownloading(false);
    }
});

window.__TAURI__.event.listen('log', (event) => {
    addLog(event.payload);
});

window.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && e.ctrlKey && !isDownloading) {
        downloadBtn.click();
    }
});

addLog('🚀 程序已就绪，请输入 Cookie 和问卷ID');