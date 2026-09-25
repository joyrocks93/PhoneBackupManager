// ── app.js – Core app logic ─────────────────────────────────────────

let currentDevice = null;
let currentFreeBytes = -1;
let currentScanBytes = -1;
let initialSettingsStr = '';

function getCurrentSettingsObj() {
    return {
        backup_dir: el('settingBackupDir')?.value || '',
        duplicate_detection: el('settingDupDetection')?.checked || false,
        hash_verification: el('settingHashVerif')?.checked || false,
        chunk_size_photos_mb: parseInt(el('settingChunkPhotos')?.value) || 4,
        chunk_size_videos_mb: parseInt(el('settingChunkVideos')?.value) || 32,
        chunk_size_others_mb: parseInt(el('settingChunkOthers')?.value) || 1
    };
}

function checkSettingsChanged() {
    const btn = el('saveSettingsBtn');
    if (!btn) return;
    const currentStr = JSON.stringify(getCurrentSettingsObj());
    
    if (currentStr !== initialSettingsStr) {
        btn.disabled = false;
        btn.classList.remove('opacity-50', 'saturate-0', 'cursor-not-allowed');
        btn.classList.add('hover:bg-blue-500', 'shadow-lg', 'shadow-blue-500/20', 'hover:-translate-y-0.5');
    } else {
        btn.disabled = true;
        btn.classList.add('opacity-50', 'saturate-0', 'cursor-not-allowed');
        btn.classList.remove('hover:bg-blue-500', 'shadow-lg', 'shadow-blue-500/20', 'hover:-translate-y-0.5');
    }
}

function checkSpaceWarning() {
    if (currentFreeBytes !== -1 && currentScanBytes !== -1) {
        const startBackupBtn = el('startBackupBtn');
        const startBackupNowBtn = el('startBackupNowBtn');
        const warnLabel = el('spaceWarningLabel');
        
        if (currentScanBytes > currentFreeBytes) {
            if (startBackupBtn) startBackupBtn.disabled = true;
            if (startBackupNowBtn) startBackupNowBtn.disabled = true;
            if (warnLabel) {
                warnLabel.innerText = 'Not enough free space!';
                warnLabel.classList.remove('hidden');
            }
        } else {
            if (currentScanBytes > 0) {
                if (startBackupBtn) startBackupBtn.disabled = false;
                if (startBackupNowBtn) startBackupNowBtn.disabled = false;
            }
            if (warnLabel) warnLabel.classList.add('hidden');
        }
    }
}

// ── Init ───────────────────────────────────────────────────────────
window.addEventListener('pywebviewready', function() {
    console.log('PyWebView ready');
    refreshDevices();
    loadSettings();
    loadHistory();
});

// ── Device helpers ─────────────────────────────────────────────────
function el(id) { return document.getElementById(id); }

function setDevice(device) {
    currentDevice = device;
    const dot = el('statusDot');
    const statusText = el('statusText');
    const deviceNameBadge = el('deviceNameBadge');
    const scanBtn = el('scanBtn');
    const startBackupBtn = el('startBackupBtn');

    if (device) {
        el('deviceName').innerText = device.name;
        el('deviceMeta').innerText = `Connected — ${device.manufacturer || 'Android Device'}`;
        el('deviceMeta').className = 'text-green-400 text-sm mt-0.5 font-medium';

        dot.className = 'w-2 h-2 rounded-full bg-green-400 shadow-[0_0_6px_2px_rgba(74,222,128,0.5)]';
        statusText.innerText = 'CONNECTED';
        statusText.className = 'text-[10px] font-bold tracking-widest text-green-400 uppercase';
        deviceNameBadge.innerText = device.name;

        if (scanBtn) scanBtn.disabled = false;
        if (startBackupBtn) startBackupBtn.disabled = true;
    } else {
        el('deviceName').innerText = 'No device connected';
        el('deviceMeta').innerText = 'Connect your Android phone via USB and select File Transfer';
        el('deviceMeta').className = 'text-slate-400 text-sm mt-0.5';

        dot.className = 'w-2 h-2 rounded-full bg-slate-500';
        statusText.innerText = 'NO DEVICE';
        statusText.className = 'text-[10px] font-bold tracking-widest text-slate-400 uppercase';
        deviceNameBadge.innerText = '—';

        if (scanBtn) scanBtn.disabled = true;
        if (startBackupBtn) startBackupBtn.disabled = true;

        resetStats();
    }
}

function resetStats() {
    ['statPhotos', 'statVideos', 'statSize'].forEach(id => {
        const e = el(id);
        if (e) e.innerText = '—';
    });
}

// ── Refresh Devices ─────────────────────────────────────────────────
async function refreshDevices() {
    const btn = el('refreshBtn');
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="animate-spin inline-block">↻</span> Refreshing…'; }
    try {
        const devices = await window.pywebview.api.get_devices();
        setDevice(devices && devices.length > 0 ? devices[0] : null);
    } catch (e) {
        console.error('Error refreshing devices:', e);
        setDevice(null);
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = '↻ Refresh'; }
    }
}

// ── Scan Device ─────────────────────────────────────────────────────
async function scanDevice(excludedFolders = []) {
    if (!currentDevice) return;
    const scanBtn = el('scanBtn');
    const startBackupBtn = el('startBackupBtn');
    const container = el('scanProgressContainer');

    if (scanBtn) { scanBtn.disabled = true; scanBtn.innerText = '🔍 Scanning…'; }
    if (container) {
        container.classList.remove('hidden');
        el('scanCountText').innerText = '0 files';
        el('scanPathText').innerText = 'Initializing scan…';
    }

    try {
        const stats = await window.pywebview.api.scan_device(currentDevice.pnp_id, excludedFolders);
        el('statPhotos').innerText = stats.photos.toLocaleString();
        el('statVideos').innerText = stats.videos.toLocaleString();
        el('statSize').innerText = stats.size_str;

        // Sync to Backup page summary
        if (el('backupSumPhotos')) el('backupSumPhotos').innerText = stats.photos.toLocaleString();
        if (el('backupSumVideos')) el('backupSumVideos').innerText = stats.videos.toLocaleString();
        if (el('backupSumSize')) el('backupSumSize').innerText = stats.size_str;

        currentScanBytes = stats.size_bytes;
        checkSpaceWarning();

        // If space is okay, we enable buttons. (checkSpaceWarning handles disabled state)
        if (currentFreeBytes === -1 || currentScanBytes <= currentFreeBytes) {
            if ((stats.photos > 0 || stats.videos > 0) && startBackupBtn) {
                startBackupBtn.disabled = false;
                const startBackupNowBtn = el('startBackupNowBtn');
                if (startBackupNowBtn) startBackupNowBtn.disabled = false;
            }
        }

        if (container) el('scanPathText').innerText = `Scan complete — ${stats.photos + stats.videos} media files found.`;
    } catch (e) {
        console.error('Scan error', e);
        if (container) el('scanPathText').innerText = 'Scan failed. Check terminal for details.';
    } finally {
        if (scanBtn) { scanBtn.disabled = false; scanBtn.innerText = '🔍 Scan Device'; }
        if (container) setTimeout(() => container.classList.add('hidden'), 5000);
    }
}

// Called directly by Python via evaluate_js
function updateScanProgress(count, path) {
    const elCount = el('scanCountText');
    const elPath = el('scanPathText');
    if (elCount) elCount.innerText = `${count} files`;
    if (elPath) elPath.innerText = path;
}

async function cancelScan() {
    try {
        await window.pywebview.api.cancel_scan();
        const elPath = el('scanPathText');
        if (elPath) elPath.innerText = 'Cancelling...';
    } catch (e) {
        console.error('Cancel failed', e);
    }
}

async function browseFolder() {
    if (!currentDevice) {
        alert("Please connect and scan a device first.");
        return;
    }
    try {
        const result = await window.pywebview.api.select_backup_folder(currentDevice.name || currentDevice.pnp_id);
        if (result && result.success) {
            const input = el('backupDestination');
            const settingInput = el('settingBackupDir');
            const spaceLabel = el('backupFreeSpace');
            const dashboardStatFree = el('statFree');
            const dashboardStatFreeLabel = el('statFreeLabel');
            if (input) input.value = result.path;
            if (settingInput) settingInput.value = result.path;
            if (spaceLabel) {
                currentFreeBytes = result.free_bytes;
                spaceLabel.innerText = `Free: ${result.free_gb} GB`;
                spaceLabel.classList.remove('hidden');
            }
            if (dashboardStatFree) {
                dashboardStatFree.innerText = `${result.free_gb} GB`;
            }
            if (dashboardStatFreeLabel) {
                dashboardStatFreeLabel.innerText = 'Free on PC';
            }
            checkSpaceWarning();
            checkSettingsChanged(); // Trigger settings changed since path updated
        } else if (result && result.error !== 'No folder selected') {
            alert("Error: " + result.error);
        }
    } catch (e) {
        console.error("Browse folder failed", e);
    }
}

// ── Backup ──────────────────────────────────────────────────────────
async function startBackup() {
    if (!currentDevice) return;
    
    const dest = el('backupDestination')?.value;
    if (!dest) {
        alert('Please select a backup destination folder first!');
        return;
    }
    
    const btn = el('startBackupNowBtn');
    const card = el('backupProgressCard');
    
    if (btn) btn.disabled = true;
    if (card) card.classList.remove('hidden');
    
    try {
        const result = await window.pywebview.api.start_backup(currentDevice.pnp_id, dest);
        if (result && result.success) {
            updateBackupProgress(100, `Complete! ${result.copied_files} files backed up successfully.`, 'Done');
        } else if (result && result.error === 'Cancelled') {
            if (card) card.classList.add('hidden');
        } else {
            updateBackupProgress(0, `Error: ${result.error || 'Unknown error'}`, '');
        }
    } catch (e) {
        console.error('Backup failed', e);
        updateBackupProgress(0, 'Failed to start backup.', '');
    } finally {
        if (btn) btn.disabled = false;
        isBackupPaused = false;
        el('pauseResumeBtn').innerText = 'PAUSE';
    }
}

let isBackupPaused = false;

async function pauseResumeBackup() {
    isBackupPaused = !isBackupPaused;
    const btn = el('pauseResumeBtn');
    if (isBackupPaused) {
        btn.innerText = 'RESUME';
        btn.className = 'px-3 py-1 text-[11px] font-bold text-green-400 border border-green-500/30 rounded hover:bg-green-500/20 transition-all';
        await window.pywebview.api.pause_backup();
        updateBackupProgress(parseFloat(el('backupPct').innerText) || 0, 'Paused', '0.0 MB/s');
    } else {
        btn.innerText = 'PAUSE';
        btn.className = 'px-3 py-1 text-[11px] font-bold text-amber-400 border border-amber-500/30 rounded hover:bg-amber-500/20 transition-all';
        await window.pywebview.api.resume_backup();
    }
}

async function cancelBackupAction() {
    if(confirm('Are you sure you want to cancel the backup?')) {
        await window.pywebview.api.cancel_backup();
    }
}

// Called directly by Python via evaluate_js
function updateBackupProgress(pct, statusText, speedText = '', etaText = '') {
    const bar = el('backupProgressBar');
    const pctText = el('backupPct');
    const status = el('backupStatusText');
    const speed = el('backupSpeed');
    const eta = el('backupEta');
    
    if (bar) bar.style.width = `${pct}%`;
    if (pctText) pctText.innerText = `${Math.round(pct)}%`;
    if (status) status.innerText = statusText;
    if (speed && speedText) speed.innerText = speedText;
    if (eta && etaText) eta.innerText = etaText;
}

// ── Tab Navigation ──────────────────────────────────────────────────
function switchTab(tabId) {
    document.querySelectorAll('.page-section').forEach(p => p.classList.add('hidden'));

    document.querySelectorAll('.nav-btn').forEach(b => {
        b.classList.remove('active', 'text-blue-400', 'bg-blue-500/10');
        b.classList.add('text-slate-400', 'hover:text-slate-200', 'hover:bg-slate-800');
    });

    const page = el('page-' + tabId);
    if (page) page.classList.remove('hidden');

    const btn = el('tab' + tabId.charAt(0).toUpperCase() + tabId.slice(1));
    if (btn) {
        btn.classList.add('active', 'text-blue-400', 'bg-blue-500/10');
        btn.classList.remove('text-slate-400', 'hover:text-slate-200', 'hover:bg-slate-800');
    }

    if (tabId === 'history') loadHistory();
    if (tabId === 'settings') loadSettings();
}

// ── History ─────────────────────────────────────────────────────────
async function loadHistory() {
    const tbody = el('historyTableBody');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="4" class="px-6 py-8 text-center text-slate-500 text-sm">Loading…</td></tr>';
    try {
        const history = await window.pywebview.api.get_history();
        if (!history || history.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="px-6 py-12 text-center text-slate-500 text-sm">No backup history yet.</td></tr>';
            return;
        }
        tbody.innerHTML = history.map(item => {
            const sc = item.status === 'Success' ? 'text-green-400 bg-green-500/10' : 'text-red-400 bg-red-500/10';
            return `
                <tr class="hover:bg-slate-800/40 transition-colors">
                    <td class="px-6 py-4 text-sm font-medium text-white">${item.date}</td>
                    <td class="px-6 py-4 text-sm text-slate-400">${item.device}</td>
                    <td class="px-6 py-4 text-sm text-slate-400">${item.files} files</td>
                    <td class="px-6 py-4">
                        <span class="px-2.5 py-1 rounded-full text-xs font-bold ${sc}">${item.status}</span>
                    </td>
                </tr>`;
        }).join('');
    } catch (e) {
        console.error('Failed to load history', e);
        tbody.innerHTML = '<tr><td colspan="4" class="px-6 py-8 text-center text-red-400 text-sm">Failed to load history.</td></tr>';
    }
}

// ── Settings ─────────────────────────────────────────────────────────
async function loadSettings() {
    try {
        const settings = await window.pywebview.api.get_settings();
        if (el('settingBackupDir')) el('settingBackupDir').value = settings.backup_dir || '';
        if (el('backupDestination')) el('backupDestination').value = settings.backup_dir || '';
        if (el('settingDupDetection')) el('settingDupDetection').checked = settings.duplicate_detection;
        if (el('settingHashVerif')) el('settingHashVerif').checked = settings.hash_verification;
        
        if (el('settingChunkPhotos')) el('settingChunkPhotos').value = settings.chunk_size_photos_mb || 4;
        if (el('settingChunkVideos')) el('settingChunkVideos').value = settings.chunk_size_videos_mb || 32;
        if (el('settingChunkOthers')) el('settingChunkOthers').value = settings.chunk_size_others_mb || 1;
        
        applyTheme(settings.theme || 'dark');
        
        // Load free space
        if (settings.backup_dir) {
            const freeSpace = await window.pywebview.api.get_free_space(settings.backup_dir);
            if (freeSpace) {
                currentFreeBytes = freeSpace.free_bytes;
                const spaceLabel = el('backupFreeSpace');
                if (spaceLabel) {
                    spaceLabel.innerText = `Free: ${freeSpace.free_gb_str}`;
                    spaceLabel.classList.remove('hidden');
                }
                const dashboardStatFree = el('statFree');
                if (dashboardStatFree) dashboardStatFree.innerText = freeSpace.free_gb_str;
                const dashboardStatFreeLabel = el('statFreeLabel');
                if (dashboardStatFreeLabel) dashboardStatFreeLabel.innerText = 'Free on PC';
                checkSpaceWarning();
            }
        } else {
            const dashboardStatFree = el('statFree');
            if (dashboardStatFree) dashboardStatFree.innerText = 'Browse';
            const dashboardStatFreeLabel = el('statFreeLabel');
            if (dashboardStatFreeLabel) dashboardStatFreeLabel.innerText = 'Select Folder';
        }

        // Setup change listeners
        ['settingBackupDir', 'settingDupDetection', 'settingHashVerif', 'settingChunkPhotos', 'settingChunkVideos', 'settingChunkOthers'].forEach(id => {
            const element = el(id);
            if (element) {
                element.addEventListener('input', checkSettingsChanged);
                element.addEventListener('change', checkSettingsChanged);
            }
        });
        
        initialSettingsStr = JSON.stringify(getCurrentSettingsObj());
        checkSettingsChanged();
        
    } catch (e) {
        console.error('Failed to load settings', e);
    }
}

async function saveSettings() {
    const btn = el('saveSettingsBtn');
    if (!btn) return;
    btn.disabled = true;
    btn.innerText = 'Saving…';
    try {
        let pMB = parseInt(el('settingChunkPhotos')?.value) || 1;
        let vMB = parseInt(el('settingChunkVideos')?.value) || 8;
        let oMB = parseInt(el('settingChunkOthers')?.value) || 16;
        
        // Clamp UI limits between 1 and 100 MB
        pMB = Math.min(100, Math.max(1, pMB));
        vMB = Math.min(100, Math.max(1, vMB));
        oMB = Math.min(100, Math.max(1, oMB));

        // Visually update the UI if the user typed something out of bounds
        if (el('settingChunkPhotos')) el('settingChunkPhotos').value = pMB;
        if (el('settingChunkVideos')) el('settingChunkVideos').value = vMB;
        if (el('settingChunkOthers')) el('settingChunkOthers').value = oMB;

        const newSettings = {
            backup_dir: el('settingBackupDir')?.value || '',
            duplicate_detection: el('settingDupDetection')?.checked || false,
            hash_verification: el('settingHashVerif')?.checked || false,
            chunk_size_photos_mb: pMB,
            chunk_size_videos_mb: vMB,
            chunk_size_others_mb: oMB
        };
        const success = await window.pywebview.api.save_settings(newSettings);
        
        if (success) {
            btn.innerText = '✓ Saved!';
            initialSettingsStr = JSON.stringify(newSettings);
            
            // Dynamically check storage space for the newly saved folder
            const freeSpace = await window.pywebview.api.get_free_space(newSettings.backup_dir);
            if (freeSpace) {
                currentFreeBytes = freeSpace.free_bytes;
                if (el('backupFreeSpace')) {
                    el('backupFreeSpace').innerText = `Free: ${freeSpace.free_gb_str}`;
                    el('backupFreeSpace').classList.remove('hidden');
                }
                if (el('statFree')) el('statFree').innerText = freeSpace.free_gb_str;
                if (el('statFreeLabel')) el('statFreeLabel').innerText = 'Free on PC';
                if (el('backupDestination')) el('backupDestination').value = newSettings.backup_dir;
                checkSpaceWarning();
            }
            
            setTimeout(() => {
                btn.innerText = '💾 Save Changes';
                checkSettingsChanged();
            }, 1500);
        } else {
            btn.innerText = '✗ Error';
            setTimeout(() => {
                btn.innerText = '💾 Save Changes';
                checkSettingsChanged();
            }, 1500);
        }
    } catch (e) {
        console.error('Failed to save settings', e);
        btn.innerText = '✗ Error';
        setTimeout(() => { btn.innerText = '💾 Save Changes'; btn.disabled = false; }, 2000);
    }
}

function applyTheme(theme) {
    const toggleText = el('themeToggleText');
    if (theme === 'light') {
        document.documentElement.classList.remove('dark');
        if (toggleText) toggleText.innerText = '🌙 Dark Mode';
    } else {
        document.documentElement.classList.add('dark');
        if (toggleText) toggleText.innerText = '☀️ Light Mode';
    }
}

function toggleTheme() {
    const isDark = document.documentElement.classList.contains('dark');
    applyTheme(isDark ? 'light' : 'dark');
    window.pywebview.api.save_settings({ theme: isDark ? 'light' : 'dark' }).catch(e => console.error(e));
}

// (duplicate browseFolder removed)
