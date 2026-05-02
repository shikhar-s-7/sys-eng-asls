'use client';

import { useState, useEffect, useCallback } from 'react';
import MissionPanel from '@/components/MissionPanel';
import LocationPanel from '@/components/LocationPanel';
import ResultsPanel from '@/components/ResultsPanel';
import SettingsPanel from '@/components/SettingsPanel';
import { calculateBallistics, getWeather, type BallisticsResult } from '@/lib/physics';

export type AppState = {
  windSpeed: number;
  windDir: number;
  userHeading: number;
  userLat: number | null;
  userLon: number | null;
  locationFetched: boolean;
  pressure: number;
  barrel: 'optimised' | 'standard';
  angleDeg: number;
  rain: boolean;
  loadHeight: number;
  weatherError: string | null;
  locationError: string | null;
  fetchingWeather: boolean;
};

const DEFAULT_STATE: AppState = {
  windSpeed: 25,
  windDir: 90,
  userHeading: 0,
  userLat: null,
  userLon: null,
  locationFetched: false,
  pressure: 50,
  barrel: 'optimised',
  angleDeg: 65,
  rain: false,
  loadHeight: 4.3,
  weatherError: null,
  locationError: null,
  fetchingWeather: false,
};

export default function Home() {
  const [state, setState] = useState<AppState>(DEFAULT_STATE);
  const [ballistics, setBallistics] = useState<BallisticsResult | null>(null);

  const updateState = useCallback((partial: Partial<AppState>) => {
    setState(prev => ({ ...prev, ...partial }));
  }, []);

  useEffect(() => {
    setBallistics(calculateBallistics(state));
  }, [state]);

  const fetchWeatherForCoords = useCallback(async (lat: number, lon: number) => {
    updateState({ fetchingWeather: true, weatherError: null });
    try {
      const weather = await getWeather(lat, lon);
      updateState({
        windSpeed: weather.windspeed,
        windDir: weather.winddirection,
        locationFetched: true,
        fetchingWeather: false,
      });
    } catch {
      updateState({
        weatherError: 'Could not fetch weather. Using manual values.',
        locationFetched: true,
        fetchingWeather: false,
      });
    }
  }, [updateState]);

  const handleLocationObtained = useCallback(async (lat: number, lon: number) => {
    updateState({ userLat: lat, userLon: lon, locationError: null });
    await fetchWeatherForCoords(lat, lon);
  }, [updateState, fetchWeatherForCoords]);

  return (
    <main className="min-h-screen bg-[#0a0c0f] text-[#e8eaf0] font-mono">
      <header className="border-b border-[#1e2530] px-6 py-4 flex items-center justify-between sticky top-0 bg-[#0a0c0f] z-10">
        <div className="flex items-center gap-4">
          <div className="w-8 h-8 rounded-full bg-[#c8f060] flex items-center justify-center">
            <span className="text-[#0a0c0f] text-sm font-bold">⊕</span>
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-widest text-[#c8f060] uppercase">ASLS</h1>
            <p className="text-[10px] text-[#4a5568] tracking-[0.3em] uppercase">Azimuth Offset Planner</p>
          </div>
        </div>
        <div className="flex items-center gap-4 text-[10px] tracking-widest uppercase">
          {state.locationFetched && (
            <span className="text-[#8892a4] font-mono">{state.windSpeed} km/h · {state.windDir}°</span>
          )}
          <span className={state.locationFetched ? 'text-[#c8f060]' : 'text-[#4a5568]'}>
            {state.locationFetched ? '● LIVE' : '○ STANDBY'}
          </span>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 py-6 grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-6">
        <div className="flex flex-col gap-4">
          <LocationPanel
            state={state}
            onLocationObtained={handleLocationObtained}
            onManualWeather={(speed, dir) => updateState({ windSpeed: speed, windDir: dir })}
            onHeadingChange={(h) => updateState({ userHeading: h })}
            onLocationError={(e) => updateState({ locationError: e })}
          />
          <SettingsPanel state={state} onUpdate={updateState} />
        </div>

        <div className="flex flex-col gap-4">
          {ballistics && (
            <>
              <ResultsPanel state={state} ballistics={ballistics} />
              <MissionPanel state={state} ballistics={ballistics} />
            </>
          )}
        </div>
      </div>
    </main>
  );
}
