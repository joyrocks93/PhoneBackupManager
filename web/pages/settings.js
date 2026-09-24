// ── pages/settings.js ───────────────────────────────────────────────
(function() {
    document.getElementById('page-settings-content').innerHTML = `
        <div class="flex justify-between items-start mb-2">
            <div>
                <h2 class="text-2xl font-bold text-white tracking-tight">Settings</h2>
                <p class="text-slate-400 text-sm mt-1">Configure your backup preferences</p>
            </div>
            <button onclick="saveSettings()" id="saveSettingsBtn"
                class="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-sm font-bold text-white shadow-lg shadow-blue-500/20 hover:-translate-y-0.5 transition-all">
                💾 Save Changes
            </button>
        </div>

        <div class="grid grid-cols-2 gap-5">
            <!-- Backup Config -->
            <div class="bg-slate-900 rounded-2xl border border-slate-800 p-6 shadow-xl flex flex-col gap-5">
                <h3 class="text-sm font-bold text-slate-400 uppercase tracking-widest">📂 Backup Configuration</h3>

                <div class="flex flex-col gap-2">
                    <label class="text-xs font-semibold text-slate-400 uppercase tracking-wide">Backup Directory</label>
                    <input type="text" id="settingBackupDir" placeholder="C:\\Backups"
                        class="bg-slate-950 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/50 transition-all">
                </div>

                <div class="flex items-center justify-between pt-3 border-t border-slate-800">
                    <div>
                        <p class="text-sm font-semibold text-white">Duplicate Detection</p>
                        <p class="text-xs text-slate-500 mt-0.5">Skip files that already exist</p>
                    </div>
                    <label class="relative inline-flex items-center cursor-pointer">
                        <input type="checkbox" id="settingDupDetection" class="sr-only peer">
                        <div class="w-10 h-5 bg-slate-700 rounded-full peer peer-checked:bg-blue-600
                                    peer-checked:after:translate-x-5 after:content-[''] after:absolute
                                    after:top-0.5 after:left-0.5 after:bg-white after:rounded-full
                                    after:h-4 after:w-4 after:transition-all"></div>
                    </label>
                </div>

                <div class="flex items-center justify-between pt-3 border-t border-slate-800">
                    <div>
                        <p class="text-sm font-semibold text-white">Hash Verification</p>
                        <p class="text-xs text-slate-500 mt-0.5">Verify files using SHA-256 after copy</p>
                    </div>
                    <label class="relative inline-flex items-center cursor-pointer">
                        <input type="checkbox" id="settingHashVerif" class="sr-only peer">
                        <div class="w-10 h-5 bg-slate-700 rounded-full peer peer-checked:bg-blue-600
                                    peer-checked:after:translate-x-5 after:content-[''] after:absolute
                                    after:top-0.5 after:left-0.5 after:bg-white after:rounded-full
                                    after:h-4 after:w-4 after:transition-all"></div>
                    </label>
                </div>
            </div>

            <!-- About -->
            <div class="bg-slate-900 rounded-2xl border border-slate-800 p-6 shadow-xl flex flex-col gap-4">
                <h3 class="text-sm font-bold text-slate-400 uppercase tracking-widest">ℹ️ About</h3>
                <div class="flex flex-col gap-3">
                    <div class="flex justify-between items-center py-2.5 border-b border-slate-800">
                        <span class="text-sm text-slate-400">Version</span>
                        <span class="text-sm font-mono font-semibold text-white bg-slate-800 px-2.5 py-0.5 rounded">1.0.0</span>
                    </div>
                    <div class="flex justify-between items-center py-2.5 border-b border-slate-800">
                        <span class="text-sm text-slate-400">Platform</span>
                        <span class="text-sm font-semibold text-white">Windows / WPD</span>
                    </div>
                    <div class="flex justify-between items-center py-2.5 border-b border-slate-800">
                        <span class="text-sm text-slate-400">Interface</span>
                        <span class="text-sm font-semibold text-white">PyWebView + Tailwind</span>
                    </div>
                    <div class="flex justify-between items-center py-2.5">
                        <span class="text-sm text-slate-400">Created by</span>
                        <a href="#" onclick="window.pywebview.api.open_url('https://github.com/joyrocks93')" class="flex items-center gap-1.5 text-sm font-semibold text-blue-400 hover:text-blue-300 transition-colors">
                            <svg class="w-4 h-4 fill-current" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/></svg>
                            joyrocks
                        </a>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Advanced Settings -->
        <div class="bg-slate-900 rounded-2xl border border-slate-800 p-6 shadow-xl flex flex-col gap-5 mt-5">
            <div class="flex justify-between items-center cursor-pointer" onclick="document.getElementById('advSettingsContent').classList.toggle('hidden')">
                <h3 class="text-sm font-bold text-slate-400 uppercase tracking-widest">⚙️ Advanced Settings (USB Chunk Sizes)</h3>
                <span class="text-slate-500 text-xs font-bold px-2 py-1 bg-slate-800 rounded">Toggle</span>
            </div>
            
            <div id="advSettingsContent" class="hidden flex flex-col gap-4 pt-3 border-t border-slate-800">
                <div class="grid grid-cols-3 gap-6">
                    <div class="flex flex-col gap-2">
                        <label class="text-xs font-semibold text-white">Photos Chunk Size (MB)</label>
                        <input type="number" id="settingChunkPhotos" class="bg-slate-950 border border-slate-700 rounded-xl px-3 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500" min="1" max="100">
                        <span class="text-[10px] text-slate-500">Applies to: .jpg, .jpeg, .png, .heic, .gif, .webp, .bmp, .dng, .raw</span>
                    </div>
                    <div class="flex flex-col gap-2">
                        <label class="text-xs font-semibold text-white">Videos Chunk Size (MB)</label>
                        <input type="number" id="settingChunkVideos" class="bg-slate-950 border border-slate-700 rounded-xl px-3 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500" min="1" max="100">
                        <span class="text-[10px] text-slate-500">Applies to: .mp4, .mov, .mkv, .avi, .wmv, .flv, .webm</span>
                    </div>
                    <div class="flex flex-col gap-2">
                        <label class="text-xs font-semibold text-white">Other Files (MB)</label>
                        <input type="number" id="settingChunkOthers" class="bg-slate-950 border border-slate-700 rounded-xl px-3 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500" min="1" max="100">
                        <span class="text-[10px] text-slate-500">Fallback size for unknown files</span>
                    </div>
                </div>
            </div>
        </div>
    `;
})();
