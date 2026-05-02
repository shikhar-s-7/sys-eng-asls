'use client';

import type { AppState } from '@/app/page';
import type { BallisticsResult } from '@/lib/physics';

type Props = {
  state: AppState;
  ballistics: BallisticsResult;
};

function Metric({ label, value, sub, pass }: { label: string; value: string; sub?: string; pass?: boolean | null }) {
  return (
    <div className="bg-[#0d1117] border border-[#1e2530] rounded-lg p-4">
      <div className="text-[9px] text-[#4a5568] tracking-widest uppercase mb-2">{label}</div>
      <div className="text-2xl font-bold font-mono text-[#e8eaf0]">{value}</div>
      {sub && (
        <div className={`text-[10px] mt-1 font-mono ${
          pass === true ? 'text-[#c8f060]' : pass === false ? 'text-[#f87171]' : 'text-[#4a5568]'
        }`}>
          {sub}
        </div>
      )}
    </div>
  );
}

export default function ResultsPanel({ state, ballistics: b }: Props) {
  const hasCrosswind = b.crosswindKmh > 0;

  return (
    <div className="border border-[#1e2530] rounded-lg overflow-hidden">
      <div className="bg-[#0d1117] px-4 py-3 border-b border-[#1e2530] flex items-center gap-2">
        <span className="text-[#c8f060] text-xs">⊕</span>
        <span className="text-xs font-bold tracking-widest uppercase text-[#8892a4]">Azimuth Offset — Primary Result</span>
      </div>

      <div className="p-4 bg-[#0a0c0f]">
        {/* Big instruction */}
        <div className={`rounded-lg p-4 mb-4 border ${
          hasCrosswind
            ? 'bg-[#c8f060]/5 border-[#c8f060]/30'
            : 'bg-[#1e2530]/40 border-[#1e2530]'
        }`}>
          {hasCrosswind ? (
            <>
              <div className="text-[10px] text-[#8892a4] tracking-widest uppercase mb-1">Operator Instruction</div>
              <div className="text-3xl font-bold font-mono text-[#c8f060]">
                {b.azimuthAngle.toFixed(1)}°
              </div>
              <div className="text-sm text-[#8892a4] mt-1">
                Rotate bipod <span className="text-[#e8eaf0] font-semibold">UPWIND</span> by {b.azimuthAngle.toFixed(1)} degrees before each launch
              </div>
            </>
          ) : (
            <>
              <div className="text-[10px] text-[#8892a4] tracking-widest uppercase mb-1">Operator Instruction</div>
              <div className="text-3xl font-bold font-mono text-[#c8f060]">0.0°</div>
              <div className="text-sm text-[#8892a4] mt-1">
                Aim straight across the trailer — no crosswind component detected
              </div>
            </>
          )}
        </div>

        {/* Metrics grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
          <Metric
            label="Crosswind"
            value={`${b.crosswindKmh.toFixed(1)} km/h`}
            sub={hasCrosswind ? `From ${state.windDir}°` : 'No crosswind'}
          />
          <Metric
            label="Raw Drift"
            value={hasCrosswind ? `${b.rawDrift.toFixed(2)} m` : '0 m'}
            sub="Before gyro"
          />
          <Metric
            label="After Gyro"
            value={hasCrosswind ? `${b.gyroDrift.toFixed(2)} m` : '0 m'}
            sub="Helical correction"
          />
          <Metric
            label="Net Drift"
            value={hasCrosswind ? `${b.netDrift.toFixed(2)} m` : '0 m'}
            sub={b.netDrift < 0.1 ? '✓ Canceled' : '⚠ Residual'}
            pass={b.netDrift < 0.1}
          />
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Metric
            label="Muzzle Velocity"
            value={`${b.v0.toFixed(1)} m/s`}
          />
          <Metric
            label="Flight Time"
            value={`${b.tFlight.toFixed(2)} s`}
          />
          <Metric
            label="Apex Height"
            value={`${b.apex.toFixed(2)} m`}
            sub={b.apexPass ? `✓ Clears ${state.loadHeight}m load` : `✗ Below ${state.loadHeight + 0.4}m req`}
            pass={b.apexPass}
          />
          <Metric
            label="Range"
            value={`${b.rangeM.toFixed(1)} m`}
            sub={b.rangePass ? '✓ Spans trailer' : '✗ Too short'}
            pass={b.rangePass}
          />
        </div>
      </div>
    </div>
  );
}
