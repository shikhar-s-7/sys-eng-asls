'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import type { AppState } from '@/app/page';

type Props = {
  state: AppState;
  onLocationObtained: (lat: number, lon: number) => Promise<void>;
  onManualWeather: (speed: number, dir: number) => void;
  onHeadingChange: (h: number) => void;
  onLocationError: (e: string) => void;
};

type CompassState = 'unsupported' | 'desktop' | 'idle' | 'requesting' | 'active' | 'error';

// Extend window type for iOS permission API
declare global {
  interface DeviceOrientationEvent {
    webkitCompassHeading?: number;
  }
}

export default function LocationPanel({ state, onLocationObtained, onManualWeather, onHeadingChange, onLocationError }: Props) {
  const [gpsStatus, setGpsStatus] = useState<'idle' | 'requesting' | 'done' | 'error'>('idle');
  const [manualLat, setManualLat] = useState(-27.4679);
  const [manualLon, setManualLon] = useState(153.0281);
  const [manualSpeed, setManualSpeed] = useState(state.windSpeed);
  const [manualDir, setManualDir] = useState(state.windDir);
  const [manualHeading, setManualHeading] = useState(state.userHeading);
  const [showManual, setShowManual] = useState(false);
  const [compassState, setCompassState] = useState<CompassState>('idle');
  const [liveHeading, setLiveHeading] = useState<number | null>(null);
  const [compassError, setCompassError] = useState<string | null>(null);
  const listenerRef = useRef<((e: DeviceOrientationEvent) => void) | null>(null);

  // Detect if mobile on mount
  useEffect(() => {
    const isMobile = /Mobi|Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
    if (!isMobile) {
      setCompassState('desktop');
    } else if (!window.DeviceOrientationEvent) {
      setCompassState('unsupported');
    } else {
      setCompassState('idle');
    }
  }, []);

  const stopCompass = useCallback(() => {
    if (listenerRef.current) {
      window.removeEventListener('deviceorientationabsolute', listenerRef.current as EventListener);
      window.removeEventListener('deviceorientation', listenerRef.current);
      listenerRef.current = null;
    }
    setCompassState('idle');
    setLiveHeading(null);
  }, []);

  const startCompass = useCallback(async () => {
    setCompassError(null);
    let gotReading = false;

    const handler = (e: DeviceOrientationEvent) => {
      let heading: number | null = null;

      if (typeof e.webkitCompassHeading === 'number' && e.webkitCompassHeading >= 0) {
        // iOS Safari — already true magnetic north, clockwise
        heading = e.webkitCompassHeading;
      } else if (typeof e.alpha === 'number' && e.alpha !== null) {
        // Android deviceorientationabsolute — alpha is CCW from true north, convert to CW
        heading = (360 - e.alpha) % 360;
      }

      if (heading !== null && !isNaN(heading)) {
        gotReading = true;
        const rounded = Math.round(heading);
        setLiveHeading(rounded);
        onHeadingChange(rounded);
        setCompassState('active');
      }
    };

    // iOS 13+ requires explicit permission
    const DevOrient = DeviceOrientationEvent as unknown as {
      requestPermission?: () => Promise<string>;
    };

    if (typeof DevOrient.requestPermission === 'function') {
      setCompassState('requesting');
      try {
        const result = await DevOrient.requestPermission();
        if (result !== 'granted') {
          setCompassState('error');
          setCompassError('Permission denied — allow motion access in iOS Settings → Safari.');
          return;
        }
      } catch {
        setCompassState('error');
        setCompassError('Could not request motion permission.');
        return;
      }
    }

    listenerRef.current = handler;

    // deviceorientationabsolute gives alpha relative to true geographic north on Android.
    // Regular deviceorientation alpha is relative to wherever the phone was pointing
    // when the page loaded — useless as a compass. Always prefer the absolute version.
    const supportsAbsolute = 'ondeviceorientationabsolute' in window;
    if (supportsAbsolute) {
      window.addEventListener('deviceorientationabsolute', handler as EventListener, true);
    } else {
      // iOS falls back here — webkitCompassHeading handles the north correction above
      window.addEventListener('deviceorientation', handler, true);
    }

    setCompassState('requesting');

    setTimeout(() => {
      if (!gotReading) {
        if (supportsAbsolute) {
          window.removeEventListener('deviceorientationabsolute', handler as EventListener, true);
        } else {
          window.removeEventListener('deviceorientation', handler, true);
        }
        listenerRef.current = null;
        setCompassState('error');
        setCompassError('Brave blocks the compass sensor by default. Open in Chrome or Samsung Internet, or enter heading manually.');
      }
    }, 3000);
  }, [onHeadingChange]);

  // Clean up listener on unmount
  useEffect(() => () => { stopCompass(); }, [stopCompass]);

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

        {/* ── COMPASS / HEADING SECTION ── */}
        <div className="border border-[#1e2530] rounded-lg p-3 bg-[#0d1117]">
          <div className="text-[10px] text-[#4a5568] tracking-widest uppercase mb-2">Your Heading</div>

          {/* Desktop: show prompt to use phone */}
          {compassState === 'desktop' && (
            <div className="text-[11px] text-[#8892a4] bg-[#0a0c0f] border border-[#1e2530] rounded p-2 mb-2 leading-relaxed">
              📱 Open this page on your <span className="text-[#c8f060]">phone</span> to auto-detect heading using the compass.
              <br />Or enter it manually below.
            </div>
          )}

          {/* Mobile idle: show activate button */}
          {(compassState === 'idle' || compassState === 'error') && (
            <button
              onClick={startCompass}
              className="w-full py-2 px-3 rounded border border-[#8892a4] text-[#8892a4] text-[10px] tracking-widest uppercase hover:border-[#c8f060] hover:text-[#c8f060] transition-all mb-2"
            >
              🧭 USE PHONE COMPASS
            </button>
          )}

          {/* Requesting permission */}
          {compassState === 'requesting' && (
            <div className="text-[11px] text-[#fbbf24] mb-2">⏳ Requesting compass permission…</div>
          )}

          {/* Active compass */}
          {compassState === 'active' && (
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-3">
                {/* Compass rose */}
                <div
                  className="w-10 h-10 rounded-full border-2 border-[#c8f060] flex items-center justify-center relative"
                  style={{ transform: `rotate(${liveHeading ?? 0}deg)`, transition: 'transform 0.3s ease' }}
                >
                  <div className="w-0 h-0 border-l-[4px] border-r-[4px] border-b-[10px] border-l-transparent border-r-transparent border-b-[#c8f060]" />
                </div>
                <div>
                  <div className="text-xl font-bold font-mono text-[#c8f060]">{liveHeading ?? '--'}°</div>
                  <div className="text-[9px] text-[#4a5568] tracking-widest uppercase">Live compass</div>
                </div>
              </div>
              <button
                onClick={stopCompass}
                className="text-[9px] text-[#4a5568] hover:text-[#f87171] tracking-widest uppercase transition-colors"
              >
                STOP
              </button>
            </div>
          )}

          {compassError && (
            <p className="text-[#f87171] text-[10px] mb-2">{compassError}</p>
          )}

          {/* Manual heading input — always shown, grayed out when compass is active */}
          <div>
            <label className="text-[9px] text-[#4a5568] tracking-widest uppercase block mb-1">
              {compassState === 'active' ? 'MANUAL OVERRIDE (compass active)' : 'MANUAL HEADING (°, 0=N)'}
            </label>
            <input
              type="number"
              min={0} max={360}
              value={compassState === 'active' ? (liveHeading ?? manualHeading) : manualHeading}
              disabled={compassState === 'active'}
              onChange={(e) => {
                const v = parseInt(e.target.value) || 0;
                setManualHeading(v);
                onHeadingChange(v);
              }}
              className="w-full bg-[#0a0c0f] border border-[#1e2530] rounded px-3 py-2 text-sm text-[#e8eaf0] font-mono focus:outline-none focus:border-[#c8f060] disabled:opacity-40 disabled:cursor-not-allowed"
            />
          </div>
        </div>

        {/* Manual override toggle */}
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