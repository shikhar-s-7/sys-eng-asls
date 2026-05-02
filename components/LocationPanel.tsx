'use client';

import { useState } from 'react';
import type { AppState } from '@/app/page';

type Props = {
  state: AppState;
  onLocationObtained: (lat: number, lon: number) => Promise<void>;
  onManualWeather: (speed: number, dir: number) => void;
  onHeadingChange: (h: number) => void;
  onLocationError: (e: string) => void;
};

export default function LocationPanel({ state, onLocationObtained, onManualWeather, onHeadingChange, onLocationError }: Props) {
  const [gpsStatus, setGpsStatus] = useState<'idle' | 'requesting' | 'done' | 'error'>('idle');
  const [manualLat, setManualLat] = useState(-27.4679);
  const [manualLon, setManualLon] = useState(153.0281);
  const [manualSpeed, setManualSpeed] = useState(state.windSpeed);
  const [manualDir, setManualDir] = useState(state.windDir);
  const [manualHeading, setManualHeading] = useState(state.userHeading);
  const [showManual, setShowManual] = useState(false);

  const handleGPS = () => {
    if (!navigator.geolocation) {
      setGpsStatus('error');
      onLocationError('Geolocation not supported by this browser.');
      return;
    }
    setGpsStatus('requesting');
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        setGpsStatus('done');
        await onLocationObtained(pos.coords.latitude, pos.coords.longitude);
      },
      (err) => {
        setGpsStatus('error');
        const msgs: Record<number, string> = {
          1: 'Permission denied — allow location in browser settings.',
          2: 'Position unavailable — try outdoors or enable GPS.',
          3: 'Request timed out — try again.',
        };
        onLocationError(msgs[err.code] || err.message);
      },
      { timeout: 12000, enableHighAccuracy: true }
    );
  };

  return (
    <div className="border border-[#1e2530] rounded-lg overflow-hidden">
      {/* Section header */}
      <div className="bg-[#0d1117] px-4 py-3 border-b border-[#1e2530] flex items-center gap-2">
        <span className="text-[#c8f060] text-xs">◎</span>
        <span className="text-xs font-bold tracking-widest uppercase text-[#8892a4]">Location & Wind</span>
      </div>

      <div className="p-4 bg-[#0a0c0f] flex flex-col gap-3">
        {/* GPS Button */}
        <button
          onClick={handleGPS}
          disabled={gpsStatus === 'requesting' || state.fetchingWeather}
          className="w-full py-3 px-4 rounded border font-bold text-xs tracking-widest uppercase transition-all duration-200
            disabled:opacity-40 disabled:cursor-not-allowed
            border-[#c8f060] text-[#c8f060] hover:bg-[#c8f060] hover:text-[#0a0c0f]"
        >
          {gpsStatus === 'requesting'
            ? '⏳ REQUESTING GPS…'
            : state.fetchingWeather
            ? '⏳ FETCHING WEATHER…'
            : gpsStatus === 'done' && state.locationFetched
            ? '✓ LOCATION ACTIVE — REFRESH'
            : '📍 USE MY LOCATION (GPS)'}
        </button>

        {/* Status messages */}
        {state.locationError && (
          <p className="text-[#f87171] text-[11px] tracking-wide">❌ {state.locationError}</p>
        )}
        {state.weatherError && (
          <p className="text-[#fbbf24] text-[11px] tracking-wide">⚠ {state.weatherError}</p>
        )}
        {state.userLat && state.locationFetched && (
          <div className="bg-[#0d1117] border border-[#1e2530] rounded p-2 text-[11px] text-[#8892a4] font-mono">
            <div>LAT {state.userLat.toFixed(5)} / LON {state.userLon?.toFixed(5)}</div>
            <div className="text-[#c8f060] mt-1">
              WIND {state.windSpeed} km/h FROM {state.windDir}°
            </div>
          </div>
        )}

        {/* Heading input */}
        <div>
          <label className="text-[10px] text-[#4a5568] tracking-widest uppercase block mb-1">Your Heading (°, 0=N)</label>
          <input
            type="number"
            min={0} max={360}
            value={manualHeading}
            onChange={(e) => {
              const v = parseInt(e.target.value) || 0;
              setManualHeading(v);
              onHeadingChange(v);
            }}
            className="w-full bg-[#0d1117] border border-[#1e2530] rounded px-3 py-2 text-sm text-[#e8eaf0] font-mono focus:outline-none focus:border-[#c8f060]"
          />
        </div>

        {/* Manual toggle */}
        <button
          onClick={() => setShowManual(!showManual)}
          className="text-[10px] text-[#4a5568] hover:text-[#8892a4] tracking-widest uppercase text-left transition-colors"
        >
          {showManual ? '▲' : '▼'} MANUAL OVERRIDE
        </button>

        {showManual && (
          <div className="flex flex-col gap-2 border border-[#1e2530] rounded p-3 bg-[#0d1117]">
            <p className="text-[10px] text-[#4a5568] tracking-widest uppercase mb-1">Manual Coordinates</p>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-[10px] text-[#4a5568] block mb-1">Latitude</label>
                <input type="number" value={manualLat} step={0.01}
                  onChange={e => setManualLat(parseFloat(e.target.value))}
                  className="w-full bg-[#0a0c0f] border border-[#1e2530] rounded px-2 py-1.5 text-xs text-[#e8eaf0] font-mono focus:outline-none focus:border-[#c8f060]"
                />
              </div>
              <div>
                <label className="text-[10px] text-[#4a5568] block mb-1">Longitude</label>
                <input type="number" value={manualLon} step={0.01}
                  onChange={e => setManualLon(parseFloat(e.target.value))}
                  className="w-full bg-[#0a0c0f] border border-[#1e2530] rounded px-2 py-1.5 text-xs text-[#e8eaf0] font-mono focus:outline-none focus:border-[#c8f060]"
                />
              </div>
            </div>
            <button
              onClick={async () => { await onLocationObtained(manualLat, manualLon); }}
              disabled={state.fetchingWeather}
              className="py-2 px-3 rounded border border-[#1e2530] text-[10px] tracking-widest uppercase text-[#8892a4] hover:text-[#c8f060] hover:border-[#c8f060] transition-all disabled:opacity-40"
            >
              {state.fetchingWeather ? 'FETCHING…' : 'FETCH WEATHER FOR COORDS'}
            </button>

            <div className="border-t border-[#1e2530] pt-2 mt-1">
              <p className="text-[10px] text-[#4a5568] tracking-widest uppercase mb-2">Manual Wind Values</p>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[10px] text-[#4a5568] block mb-1">Speed (km/h)</label>
                  <input type="number" min={0} max={150} value={manualSpeed}
                    onChange={e => setManualSpeed(parseInt(e.target.value) || 0)}
                    className="w-full bg-[#0a0c0f] border border-[#1e2530] rounded px-2 py-1.5 text-xs text-[#e8eaf0] font-mono focus:outline-none focus:border-[#c8f060]"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-[#4a5568] block mb-1">Direction (°)</label>
                  <input type="number" min={0} max={360} value={manualDir}
                    onChange={e => setManualDir(parseInt(e.target.value) || 0)}
                    className="w-full bg-[#0a0c0f] border border-[#1e2530] rounded px-2 py-1.5 text-xs text-[#e8eaf0] font-mono focus:outline-none focus:border-[#c8f060]"
                  />
                </div>
              </div>
              <button
                onClick={() => onManualWeather(manualSpeed, manualDir)}
                className="mt-2 w-full py-2 px-3 rounded border border-[#1e2530] text-[10px] tracking-widest uppercase text-[#8892a4] hover:text-[#c8f060] hover:border-[#c8f060] transition-all"
              >
                APPLY MANUAL WIND
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
