// ── pages/history.js ────────────────────────────────────────────────
(function() {
    document.getElementById('page-history-content').innerHTML = `
        <div class="flex justify-between items-start mb-2">
            <div>
                <h2 class="text-2xl font-bold text-white tracking-tight">History</h2>
                <p class="text-slate-400 text-sm mt-1">Your past backup sessions</p>
            </div>
            <button onclick="loadHistory()"
                class="flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-sm font-medium text-slate-300 hover:text-white transition-all">
                ↻ Refresh
            </button>
        </div>

        <div class="bg-slate-900 rounded-2xl border border-slate-800 shadow-xl overflow-hidden">
            <table class="w-full text-left">
                <thead class="bg-slate-800/50 border-b border-slate-800">
                    <tr>
                        <th class="px-6 py-4 text-[10px] font-bold text-slate-500 tracking-widest uppercase">Date</th>
                        <th class="px-6 py-4 text-[10px] font-bold text-slate-500 tracking-widest uppercase">Device</th>
                        <th class="px-6 py-4 text-[10px] font-bold text-slate-500 tracking-widest uppercase">Files</th>
                        <th class="px-6 py-4 text-[10px] font-bold text-slate-500 tracking-widest uppercase">Status</th>
                    </tr>
                </thead>
                <tbody id="historyTableBody" class="divide-y divide-slate-800">
                    <tr>
                        <td colspan="4" class="px-6 py-12 text-center text-slate-500 text-sm">Loading history…</td>
                    </tr>
                </tbody>
            </table>
        </div>
    `;
})();
