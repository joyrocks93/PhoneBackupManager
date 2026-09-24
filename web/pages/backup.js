// ── pages/backup.js ─────────────────────────────────────────────────
(function() {
    document.getElementById('page-backup-content').innerHTML = `
        <div class="flex justify-between items-start mb-2">
            <div>
                <h2 class="text-2xl font-bold text-white tracking-tight">Backup</h2>
                <p class="text-slate-400 text-sm mt-1">Configure and start your backup</p>
            </div>
        </div>

        <!-- Destination Picker -->
        <div class="bg-slate-900 rounded-2xl border border-slate-800 p-6 shadow-xl mb-2">
            <div class="flex justify-between items-center mb-4">
                <h3 class="text-sm font-bold text-slate-400 uppercase tracking-widest">📂 Backup Destination</h3>
                <span id="backupFreeSpace" class="text-xs font-bold text-slate-500 hidden bg-slate-800 px-2 py-1 rounded"></span>
            </div>
            <div class="flex gap-3">
                <div class="flex-1 flex items-center gap-3 bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 focus-within:border-blue-500 transition-all">
                    <span class="text-slate-500 text-base">📁</span>
                    <input type="text" id="backupDestination" readonly placeholder="No folder selected…"
                        class="flex-1 bg-transparent text-sm text-slate-200 placeholder-slate-600 outline-none cursor-default">
                </div>
                <button onclick="browseFolder()"
                    class="flex items-center gap-2 px-5 py-3 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-sm font-semibold text-slate-300 hover:text-white transition-all whitespace-nowrap">
                    Browse…
                </button>
            </div>
        </div>

        <!-- Summary Card -->
        <div class="bg-gradient-to-br from-blue-950/40 to-slate-900 mb-2 rounded-2xl border border-blue-900/50 p-6 shadow-xl">
            <div class="flex items-center gap-4 mb-6">
                <div class="w-12 h-12 rounded-xl bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-2xl">💾</div>
                <div>
                    <h3 class="text-lg font-bold text-white">Ready for Backup</h3>
                    <p class="text-slate-400 text-sm mt-0.5">Scan your device first to see what will be backed up.</p>
                </div>
            </div>

            <div class="grid grid-cols-3 gap-4 mb-6">
                <div class="bg-slate-900/60 rounded-xl p-4 border border-slate-800">
                    <div class="text-xl font-black text-white" id="backupSumPhotos">—</div>
                    <div class="text-[10px] text-slate-500 uppercase tracking-widest font-bold mt-1">Photos</div>
                </div>
                <div class="bg-slate-900/60 rounded-xl p-4 border border-slate-800">
                    <div class="text-xl font-black text-white" id="backupSumVideos">—</div>
                    <div class="text-[10px] text-slate-500 uppercase tracking-widest font-bold mt-1">Videos</div>
                </div>
                <div class="bg-slate-900/60 rounded-xl p-4 border border-slate-800">
                    <div class="text-xl font-black text-white" id="backupSumSize">—</div>
                    <div class="text-[10px] text-slate-500 uppercase tracking-widest font-bold mt-1">Total Size</div>
                </div>
            </div>

            <div id="spaceWarningLabel" class="hidden w-full text-center text-red-500 font-bold mb-3 text-sm">Not enough free space!</div>
            <button id="startBackupNowBtn" onclick="startBackup()"
                class="w-full flex items-center justify-center gap-2 py-3.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-sm font-bold text-white shadow-lg shadow-blue-500/30 hover:shadow-blue-500/50 hover:-translate-y-0.5 transition-all disabled:opacity-40 disabled:cursor-not-allowed disabled:shadow-none disabled:translate-y-0">
                ▶ Start Backup Now
            </button>
        </div>

        <!-- Progress Bar (hidden during normal state) -->
        <div id="backupProgressCard" class="hidden bg-slate-900 mb-2 rounded-2xl border border-blue-500/30 shadow-lg p-6">
            <div class="flex justify-between items-center mb-3">
                <div class="flex items-center gap-3">
                    <div class="w-4 h-4 rounded-full border-2 border-blue-500 border-t-transparent animate-spin shrink-0"></div>
                    <h3 class="text-sm font-bold text-white">Backup in Progress</h3>
                </div>
                <div class="flex items-center gap-4">
                    <div class="flex flex-col items-end gap-0.5">
                        <span id="backupSpeed" class="text-xs font-bold text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded">0.0 MB/s</span>
                        <span id="backupEta" class="text-[10px] font-medium text-slate-500"></span>
                    </div>
                    <span id="backupPct" class="text-sm font-bold text-slate-400">0%</span>
                </div>
            </div>
            <div class="w-full bg-slate-800 rounded-full h-2.5 overflow-hidden mb-4">
                <div id="backupProgressBar" class="bg-blue-500 h-full rounded-full transition-all duration-300" style="width: 0%"></div>
            </div>
            <div class="flex items-center justify-between">
                <p id="backupStatusText" class="text-xs text-slate-500 truncate font-mono mr-4 flex-1">Preparing...</p>
                <div class="flex gap-2 shrink-0">
                    <button id="pauseResumeBtn" onclick="pauseResumeBackup()" class="px-3 py-1 text-[11px] font-bold text-amber-400 border border-amber-500/30 rounded hover:bg-amber-500/20 transition-all">PAUSE</button>
                    <button id="cancelBackupBtn" onclick="cancelBackupAction()" class="px-3 py-1 text-[11px] font-bold text-red-400 border border-red-500/30 rounded hover:bg-red-500/20 transition-all">CANCEL</button>
                </div>
            </div>
        </div>
    `;
})();


