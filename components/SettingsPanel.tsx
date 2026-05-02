'use client';

import { useState } from 'react';
import type { AppState } from '@/app/page';

type Props = {
  state: AppState;
  onUpdate: (partial: Partial<AppState>) => void;
};

export default function SettingsPanel({ state, onUpdate }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <div className="border border-[#1e2530] rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full bg-[#0d1117] px-4 py-3 border-b border-[#1e2530] flex items-center justify-between hover:bg-[#111620] transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-[#c8f060] text-xs">⚙</span>
          <span className="text-xs font-bold tracking-widest uppercase text-[#8892a4]">Launcher Settings</span>
        </div>
        <span className="text-[#4a5568] text-xs">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="p-4 bg-[#0a0c0f] flex flex-col gap-4">

          {/* Pressure */}
          <div>
            <div className="flex justify-between mb-1">
              <label className="text-[10px] text-[#4a5568] tracking-widest uppercase">Pressure (PSI)</label>
              <span className="text-[10px] text-[#c8f060] font-mono">{state.pressure}</span>
            </div>
            <input
              type="range" min={35} max={70} value={state.pressure}
              onChange={e => onUpdate({ pressure: parseInt(e.target.value) })}
              className="w-full accent-[#c8f060] bg-[#1e2530] rounded h-1"
            />
            <div className="flex justify-between mt-0.5">
              <span className="text-[9px] text-[#4a5568]">35</span>
              <span className="text-[9px] text-[#4a5568]">70</span>
            </div>
          </div>

          {/* Barrel */}
          <div>
            <label className="text-[10px] text-[#4a5568] tracking-widest uppercase block mb-2">Barrel Type</label>
            <div className="grid grid-cols-2 gap-2">
              {(['optimised', 'standard'] as const).map(b => (
                <button
                  key={b}
                  onClick={() => onUpdate({ barrel: b })}
                  className={`py-2 px-3 rounded border text-[10px] tracking-widest uppercase transition-all ${
                    state.barrel === b
                      ? 'border-[#c8f060] text-[#c8f060] bg-[#c8f060]/10'
                      : 'border-[#1e2530] text-[#4a5568] hover:border-[#8892a4]'
                  }`}
                >
                  {b === 'optimised' ? 'Helical Kv=0.24' : 'Standard Kv=0.20'}
                </button>
              ))}
            </div>
          </div>

          {/* Angle */}
          <div>
            <div className="flex justify-between mb-1">
              <label className="text-[10px] text-[#4a5568] tracking-widest uppercase">Launch Angle (°)</label>
              <span className="text-[10px] text-[#c8f060] font-mono">{state.angleDeg}°</span>
            </div>
            <input
              type="range" min={55} max={75} value={state.angleDeg}
              onChange={e => onUpdate({ angleDeg: parseInt(e.target.value) })}
              className="w-full accent-[#c8f060]"
            />
            <div className="flex justify-between mt-0.5">
              <span className="text-[9px] text-[#4a5568]">55°</span>
              <span className="text-[9px] text-[#4a5568]">75°</span>
            </div>
          </div>

          {/* Load Height */}
          <div>
            <label className="text-[10px] text-[#4a5568] tracking-widest uppercase block mb-1">Load Height (m)</label>
            <input
              type="number" min={3} max={6} step={0.1} value={state.loadHeight}
              onChange={e => onUpdate({ loadHeight: parseFloat(e.target.value) || 4.3 })}
              className="w-full bg-[#0d1117] border border-[#1e2530] rounded px-3 py-2 text-sm text-[#e8eaf0] font-mono focus:outline-none focus:border-[#c8f060]"
            />
          </div>

          {/* Rain */}
          <label className="flex items-center gap-3 cursor-pointer">
            <div
              onClick={() => onUpdate({ rain: !state.rain })}
              className={`w-10 h-5 rounded-full transition-colors relative ${state.rain ? 'bg-[#c8f060]' : 'bg-[#1e2530]'}`}
            >
              <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${state.rain ? 'translate-x-5' : 'translate-x-0.5'}`} />
            </div>
            <span className="text-xs text-[#8892a4] tracking-wide">Rain (2% velocity penalty)</span>
          </label>
        </div>
      )}
    </div>
  );
}
