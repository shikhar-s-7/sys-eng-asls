'use client';

import { useState } from 'react';
import type { AppState } from '@/app/page';
import type { BallisticsResult } from '@/lib/physics';
import { simulateMission, type StrapResult } from '@/lib/physics';

type Props = {
  state: AppState;
  ballistics: BallisticsResult;
};

export default function MissionPanel({ state, ballistics }: Props) {
  const [numStraps, setNumStraps] = useState(10);
  const [rows, setRows] = useState<StrapResult[]>([]);
  const [swaps, setSwaps] = useState(0);
  const [ran, setRan] = useState(false);

  const run = () => {
    const result = simulateMission(numStraps, state, ballistics.crosswindKmh);
    setRows(result.rows);
    setSwaps(result.swaps);
    setRan(true);
  };

  const successCount = rows.filter(r => r.success).length;

  return (
    <div className="border border-[#1e2530] rounded-lg overflow-hidden">
      <div className="bg-[#0d1117] px-4 py-3 border-b border-[#1e2530] flex items-center gap-2">
        <span className="text-[#c8f060] text-xs">▶</span>
        <span className="text-xs font-bold tracking-widest uppercase text-[#8892a4]">Full Load Mission Check</span>
      </div>

      <div className="p-4 bg-[#0a0c0f]">
        <div className="flex items-end gap-4 mb-4">
          <div className="flex-1">
            <div className="flex justify-between mb-1">
              <label className="text-[10px] text-[#4a5568] tracking-widest uppercase">Number of Straps</label>
              <span className="text-[10px] text-[#c8f060] font-mono">{numStraps}</span>
            </div>
            <input
              type="range" min={6} max={13} value={numStraps}
              onChange={e => { setNumStraps(parseInt(e.target.value)); setRan(false); }}
              className="w-full accent-[#c8f060]"
            />
          </div>
          <button
            onClick={run}
            className="px-6 py-2.5 rounded border border-[#c8f060] text-[#c8f060] text-xs tracking-widest uppercase font-bold hover:bg-[#c8f060] hover:text-[#0a0c0f] transition-all"
          >
            RUN
          </button>
        </div>

        {ran && (
          <>
            <div className="flex gap-4 mb-3">
              <div className="bg-[#0d1117] border border-[#1e2530] rounded px-4 py-2 text-center">
                <div className="text-[9px] text-[#4a5568] tracking-widest uppercase">Completed</div>
                <div className="text-lg font-bold font-mono text-[#c8f060]">{successCount}/{numStraps}</div>
              </div>
              <div className="bg-[#0d1117] border border-[#1e2530] rounded px-4 py-2 text-center">
                <div className="text-[9px] text-[#4a5568] tracking-widest uppercase">Cylinder Swaps</div>
                <div className="text-lg font-bold font-mono text-[#e8eaf0]">{swaps}</div>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-xs font-mono">
                <thead>
                  <tr className="border-b border-[#1e2530]">
                    {['Strap', 'PSI', 'v₀', 'Apex (m)', 'Range (m)', 'Drift (m)', 'OK'].map(h => (
                      <th key={h} className="text-left text-[9px] text-[#4a5568] tracking-widest uppercase py-2 pr-4">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map(r => (
                    <tr key={r.strap} className={`border-b border-[#0d1117] ${!r.success ? 'bg-[#f87171]/5' : ''}`}>
                      <td className="py-1.5 pr-4 text-[#8892a4]">{r.strap}</td>
                      <td className="py-1.5 pr-4">{r.regPsi.toFixed(0)}</td>
                      <td className="py-1.5 pr-4">{r.v0.toFixed(1)}</td>
                      <td className="py-1.5 pr-4">{r.apex.toFixed(2)}</td>
                      <td className="py-1.5 pr-4">{r.rangeM.toFixed(1)}</td>
                      <td className="py-1.5 pr-4">{r.drift.toFixed(2)}</td>
                      <td className="py-1.5">{r.success ? <span className="text-[#c8f060]">✓</span> : <span className="text-[#f87171]">✗</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
