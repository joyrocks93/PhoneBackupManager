// ── pages/dashboard.js ──────────────────────────────────────────────
(function() {
    document.getElementById('page-dashboard-content').innerHTML = `
        <div class="flex justify-between items-start mb-2">
            <div>
                <h2 class="text-2xl font-bold text-white tracking-tight">Dashboard</h2>
                <p class="text-slate-400 text-sm mt-1">Overview of your connected device</p>
            </div>
            <button id="refreshBtn" onclick="refreshDevices()"
                class="flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-sm font-medium text-slate-300 hover:text-white transition-all">
                <span id="refreshIcon">↻</span> Refresh
            </button>
        </div>

        <!-- Device Card -->
        <div class="bg-gradient-to-br from-slate-800 to-slate-900 rounded-2xl border border-slate-700 p-6 mb-2 flex items-center gap-5 shadow-xl">
            <div class="w-14 h-14 rounded-2xl bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-3xl shrink-0">📱</div>
            <div class="flex-1 min-w-0">
                <h3 id="deviceName" class="text-lg font-bold text-white truncate">No device connected</h3>
                <p id="deviceMeta" class="text-slate-400 text-sm mt-0.5">Connect your Android phone via USB and select File Transfer</p>
            </div>
        </div>

        <!-- Stats Grid -->
        <div class="grid grid-cols-4 gap-4 mb-2">
            <div class="bg-slate-900 rounded-xl border border-slate-800 p-5 hover:border-blue-800/50 transition-all hover:shadow-lg">
                <div class="text-2xl mb-3">📷</div>
                <div id="statPhotos" class="text-3xl font-black text-white tracking-tight">—</div>
                <div class="text-[10px] font-bold text-slate-500 tracking-widest uppercase mt-1">Photos</div>
            </div>
            <div class="bg-slate-900 rounded-xl border border-slate-800 p-5 hover:border-purple-800/50 transition-all hover:shadow-lg">
                <div class="text-2xl mb-3">🎬</div>
                <div id="statVideos" class="text-3xl font-black text-white tracking-tight">—</div>
                <div class="text-[10px] font-bold text-slate-500 tracking-widest uppercase mt-1">Videos</div>
            </div>
            <div class="bg-slate-900 rounded-xl border border-slate-800 p-5 hover:border-green-800/50 transition-all hover:shadow-lg">
                <div class="text-2xl mb-3">💾</div>
                <div id="statSize" class="text-3xl font-black text-white tracking-tight">—</div>
                <div class="text-[10px] font-bold text-slate-500 tracking-widest uppercase mt-1">Total Size</div>
            </div>
            <div class="bg-slate-900 rounded-xl border border-slate-800 p-5 hover:border-amber-800/50 transition-all hover:shadow-lg cursor-pointer" onclick="browseFolder()">
                <div class="text-2xl mb-3">🗂️</div>
                <div id="statFree" class="text-2xl font-black text-white tracking-tight">—</div>
                <div id="statFreeLabel" class="text-[10px] font-bold text-slate-500 tracking-widest uppercase mt-1">Free on PC</div>
            </div>
        </div>

        <!-- Folder Picker (step 1 – hidden until Scan clicked) -->
        <div id="folderPickerCard" class="hidden bg-slate-900 rounded-2xl border border-blue-900/40 shadow-xl overflow-hidden mb-2">
            <!-- Header -->
            <div class="flex items-center justify-between px-5 py-4 border-b border-slate-800 bg-slate-800/40">
                <div class="flex items-center gap-3">
                    <div class="w-8 h-8 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-base">📂</div>
                    <div>
                        <h3 class="text-sm font-bold text-white">Select Folders to Scan</h3>
                        <p class="text-[11px] text-slate-500 mt-0.5">Uncheck folders you want to skip (e.g. Android, .trash)</p>
                    </div>
                </div>
                <div class="flex items-center gap-2">
                    <button onclick="toggleAllFolders(true)" class="px-2.5 py-1 rounded-md text-[11px] font-semibold text-blue-400 hover:bg-blue-500/10 transition-all">All</button>
                    <button onclick="toggleAllFolders(false)" class="px-2.5 py-1 rounded-md text-[11px] font-semibold text-slate-400 hover:bg-slate-700 transition-all">None</button>
                    <button onclick="closeFolderPicker()" class="px-2.5 py-1 rounded-md text-[11px] font-semibold text-slate-500 hover:bg-slate-700 transition-all">✕</button>
                </div>
            </div>

            <!-- Loading state -->
            <div id="folderPickerLoading" class="flex items-center justify-center gap-3 py-10 text-slate-500 text-sm">
                <div class="w-4 h-4 rounded-full border-2 border-blue-500 border-t-transparent animate-spin"></div>
                Fetching folders from device…
            </div>

            <!-- Folder grid (populated by JS) -->
            <div id="folderGrid" class="hidden grid grid-cols-3 gap-2 p-4 max-h-56 overflow-y-auto"></div>

            <!-- Footer -->
            <div class="flex items-center justify-between px-5 py-3 border-t border-slate-800 bg-slate-800/20">
                <p id="folderSelectionCount" class="text-xs text-slate-500"></p>
                <div class="flex gap-2">
                    <button onclick="closeFolderPicker()"
                        class="px-4 py-2 rounded-lg text-xs font-semibold text-slate-400 hover:text-white hover:bg-slate-700 transition-all border border-slate-700">
                        Cancel
                    </button>
                    <button id="startScanBtn" onclick="confirmAndScan()"
                        class="flex items-center gap-2 px-5 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-xs font-bold text-white shadow-lg shadow-blue-500/20 hover:-translate-y-0.5 transition-all">
                        🔍 Scan Selected
                    </button>
                </div>
            </div>
        </div>

        <!-- Scan Progress (shown during active scan) -->
        <div id="scanProgressContainer" class="hidden bg-slate-900 rounded-xl border border-blue-500/30 p-4 shadow-lg mb-2 mt-2">
            <div class="flex items-center gap-3 mb-3">
                <div class="w-4 h-4 rounded-full border-2 border-blue-500 border-t-transparent animate-spin shrink-0"></div>
                <span class="text-xs font-bold text-blue-400 tracking-widest uppercase">Scanning Device</span>
                <div class="ml-auto flex items-center gap-2">
                    <span id="scanCountText" class="text-xs font-bold text-slate-400 bg-slate-800 px-2.5 py-0.5 rounded-full">0 files</span>
                    <button onclick="cancelScan()" class="px-2 py-0.5 rounded text-[10px] font-bold text-red-400 hover:bg-red-500/20 transition-all border border-red-500/30">CANCEL</button>
                </div>
            </div>
            <div class="bg-slate-950 rounded-lg p-3 border border-slate-800">
                <p id="scanPathText" class="text-xs text-slate-500 truncate font-mono">Initializing…</p>
            </div>
        </div>

        <!-- Action Row -->
        <div class="flex justify-end gap-3 mt-2 mb-2">
            <button id="scanBtn" onclick="openFolderPicker()" disabled
                class="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-sm font-semibold text-slate-300 hover:text-white transition-all disabled:opacity-40 disabled:cursor-not-allowed">
                🔍 Scan Device
            </button>
            <button id="startBackupBtn" onclick="switchTab('backup')" disabled
                class="flex items-center gap-2 px-6 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-sm font-bold text-white shadow-lg shadow-blue-500/30 hover:shadow-blue-500/50 hover:-translate-y-0.5 transition-all disabled:opacity-40 disabled:cursor-not-allowed disabled:shadow-none disabled:translate-y-0">
                ▶ Start Backup
            </button>
        </div>
    `;
})();

// ── Folder Picker State ─────────────────────────────────────────────
let _allFolderNames = [];
let _selectedFolders = new Set();

// Known "junk" folders to auto-uncheck
const AUTO_EXCLUDE = new Set([
    'Android', '.android_secure', 'LOST.DIR', '.trash', 'Trash',
    'obb', 'data', 'cache', '.thumbnails', 'Thumbnails',
    'Podcasts', 'Ringtones', 'Notifications', 'Alarms', 'Music', 'Audiobooks'
]);

async function openFolderPicker() {
    if (!currentDevice) return;

    const card = document.getElementById('folderPickerCard');
    const loading = document.getElementById('folderPickerLoading');
    const grid = document.getElementById('folderGrid');

    card.classList.remove('hidden');
    loading.classList.remove('hidden');
    grid.classList.add('hidden');
    document.getElementById('folderGrid').innerHTML = '';

    try {
        const folders = await window.pywebview.api.get_device_folders(currentDevice.pnp_id);
        _allFolderNames = folders;

        // Default: select everything EXCEPT known junk
        _selectedFolders = new Set(folders.filter(f => !AUTO_EXCLUDE.has(f)));

        renderFolderGrid();
    } catch (e) {
        console.error('Failed to get folders', e);
        loading.innerHTML = '<span class="text-red-400 text-sm">Failed to load folders.</span>';
    }
}

function renderFolderGrid() {
    const loading = document.getElementById('folderPickerLoading');
    const grid = document.getElementById('folderGrid');

    loading.classList.add('hidden');
    grid.classList.remove('hidden');

    const FOLDER_ICONS = {
        'DCIM': '📷', 'Pictures': '🖼️', 'Videos': '🎬', 'Movies': '🎥',
        'Music': '🎵', 'Downloads': '⬇️', 'Documents': '📄',
        'WhatsApp': '💬', 'Telegram': '✈️', 'Snapchat': '👻',
        'Instagram': '📸', 'Android': '🤖', 'data': '🗄️',
        'Ringtones': '🔔', 'Notifications': '🔔', 'Alarms': '⏰',
    };

    grid.innerHTML = _allFolderNames.map(name => {
        const checked = _selectedFolders.has(name);
        const icon = FOLDER_ICONS[name] || '📁';
        const isJunk = AUTO_EXCLUDE.has(name);
        const dimClass = isJunk ? 'opacity-60' : '';
        return `
            <label class="flex items-center gap-2.5 p-3 rounded-xl cursor-pointer
                          border transition-all select-none group
                          ${checked
                            ? 'border-blue-500/40 bg-blue-500/5 hover:bg-blue-500/10'
                            : 'border-slate-700 bg-slate-800/40 hover:bg-slate-800'}
                          ${dimClass}">
                <input type="checkbox" value="${name}"
                    ${checked ? 'checked' : ''}
                    onchange="toggleFolder('${name}', this.checked)"
                    class="w-3.5 h-3.5 rounded accent-blue-500 cursor-pointer shrink-0">
                <span class="text-base leading-none">${icon}</span>
                <span class="text-xs font-medium truncate ${checked ? 'text-white' : 'text-slate-400'} group-hover:text-white transition-colors">${name}</span>
            </label>`;
    }).join('');

    updateFolderCount();
}

function toggleFolder(name, checked) {
    if (checked) _selectedFolders.add(name);
    else _selectedFolders.delete(name);
    updateFolderCount();

    // Re-style the label
    const input = document.querySelector(`input[value="${name}"]`);
    if (input) {
        const label = input.closest('label');
        if (checked) {
            label.classList.remove('border-slate-700', 'bg-slate-800/40');
            label.classList.add('border-blue-500/40', 'bg-blue-500/5');
            label.querySelector('span:last-child').className = 'text-xs font-medium truncate text-white transition-colors';
        } else {
            label.classList.add('border-slate-700', 'bg-slate-800/40');
            label.classList.remove('border-blue-500/40', 'bg-blue-500/5');
            label.querySelector('span:last-child').className = 'text-xs font-medium truncate text-slate-400 group-hover:text-white transition-colors';
        }
    }
}

function toggleAllFolders(select) {
    _allFolderNames.forEach(name => {
        const input = document.querySelector(`input[value="${name}"]`);
        if (input) {
            input.checked = select;
            toggleFolder(name, select);
        }
    });
}

function updateFolderCount() {
    const el = document.getElementById('folderSelectionCount');
    const excl = _allFolderNames.length - _selectedFolders.size;
    el.innerText = `${_selectedFolders.size} of ${_allFolderNames.length} folders selected${excl > 0 ? ` · ${excl} excluded` : ''}`;
}

function closeFolderPicker() {
    document.getElementById('folderPickerCard').classList.add('hidden');
}

async function confirmAndScan() {
    closeFolderPicker();
    // Build exclusion list: folders NOT in selected
    const excluded = _allFolderNames.filter(f => !_selectedFolders.has(f));
    await scanDevice(excluded);
}
