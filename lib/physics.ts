const G = 9.81;
const Kd = 0.045;
const GYRO_REDUCTION = 0.65;
const AZIMUTH_OFFSET_COEFF = 0.02425;
const DISTANCE_TO_FAR_SIDE = 7.0;

export type WeatherData = {
  windspeed: number;
  winddirection: number;
};

export type AppState = {
  windSpeed: number;
  windDir: number;
  userHeading: number;
  pressure: number;
  barrel: 'optimised' | 'standard';
  angleDeg: number;
  rain: boolean;
  loadHeight: number;
};

export type BallisticsResult = {
  v0: number;
  tFlight: number;
  apex: number;
  rangeM: number;
  crosswindKmh: number;
  rawDrift: number;
  gyroDrift: number;
  offsetM: number;
  azimuthAngle: number;
  netDrift: number;
  apexPass: boolean;
  rangePass: boolean;
};

export type StrapResult = {
  strap: number;
  regPsi: number;
  v0: number;
  apex: number;
  rangeM: number;
  drift: number;
  success: boolean;
};

function muzzleVelocity(psi: number, kv: number): number {
  return kv * psi;
}

function flightTime(v0: number, thetaDeg: number): number {
  const rad = (thetaDeg * Math.PI) / 180;
  return (2 * v0 * Math.sin(rad)) / G;
}

function apexHeight(v0: number, thetaDeg: number): number {
  const rad = (thetaDeg * Math.PI) / 180;
  return (v0 * Math.sin(rad)) ** 2 / (2 * G);
}

function horizontalRange(v0: number, thetaDeg: number): number {
  return (v0 ** 2 * Math.sin(2 * (thetaDeg * Math.PI) / 180)) / G;
}

function rawLateralDrift(windMs: number, tFlight: number): number {
  return Kd * windMs * tFlight;
}

function netDrift(crosswindKmh: number, tFlight: number): number {
  if (crosswindKmh <= 0) return 0;
  const windMs = crosswindKmh / 3.6;
  const raw = rawLateralDrift(windMs, tFlight);
  const afterGyro = raw * GYRO_REDUCTION;
  const offset = AZIMUTH_OFFSET_COEFF * Math.min(crosswindKmh, 40);
  return Math.max(0, afterGyro - offset);
}

export function calculateBallistics(state: AppState): BallisticsResult {
  const kv = state.barrel === 'optimised' ? 0.24 : 0.20;
  let v0 = muzzleVelocity(state.pressure, kv);
  if (state.rain) v0 *= 0.98;

  const tFlight = flightTime(v0, state.angleDeg);
  const apex = apexHeight(v0, state.angleDeg);
  const rangeM = horizontalRange(v0, state.angleDeg);

  const relRad = ((state.windDir - state.userHeading) * Math.PI) / 180;
  const crosswindKmh = Math.abs(state.windSpeed * Math.sin(relRad));

  let rawDrift = 0, gyroDrift = 0, offsetM = 0, azimuthAngle = 0, netD = 0;

  if (crosswindKmh > 0) {
    rawDrift = rawLateralDrift(crosswindKmh / 3.6, tFlight);
    gyroDrift = rawDrift * GYRO_REDUCTION;
    offsetM = AZIMUTH_OFFSET_COEFF * Math.min(crosswindKmh, 40);
    azimuthAngle = (Math.atan(offsetM / DISTANCE_TO_FAR_SIDE) * 180) / Math.PI;
    netD = Math.max(0, gyroDrift - offsetM);
  }

  const requiredApex = state.loadHeight + 0.4;

  return {
    v0,
    tFlight,
    apex,
    rangeM,
    crosswindKmh,
    rawDrift,
    gyroDrift,
    offsetM,
    azimuthAngle,
    netDrift: netD,
    apexPass: apex >= requiredApex,
    rangePass: rangeM >= 2.4,
  };
}

export function simulateMission(
  numStraps: number,
  state: AppState,
  crosswindKmh: number
): { rows: StrapResult[]; swaps: number } {
  const kv = state.barrel === 'optimised' ? 0.24 : 0.20;
  const DROP_PER_SHOT = (60 - 35) / 12;
  let cylinder = 60.0;
  let swaps = 0;
  const rows: StrapResult[] = [];

  for (let i = 1; i <= numStraps; i++) {
    let reg = cylinder >= state.pressure ? state.pressure : cylinder;
    if (reg < 46) {
      cylinder = 60.0;
      reg = state.pressure;
      swaps++;
    }
    let v = muzzleVelocity(reg, kv);
    if (state.rain) v *= 0.98;
    const a = apexHeight(v, state.angleDeg);
    const r = horizontalRange(v, state.angleDeg);
    const t = flightTime(v, state.angleDeg);
    const d = netDrift(crosswindKmh, t);
    const apexOk = a >= state.loadHeight + 0.4;
    const success = apexOk && (d < 0.3 || crosswindKmh === 0);
    rows.push({ strap: i, regPsi: reg, v0: v, apex: a, rangeM: r, drift: d, success });
    if (i < numStraps) cylinder = Math.max(35, cylinder - DROP_PER_SHOT);
  }
  return { rows, swaps };
}

export async function getWeather(lat: number, lon: number): Promise<WeatherData> {
  const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current_weather=true`;
  const res = await fetch(url, { signal: AbortSignal.timeout(10000) });
  if (!res.ok) throw new Error('Weather fetch failed');
  const data = await res.json();
  const cw = data.current_weather;
  if (!cw || cw.windspeed == null || cw.winddirection == null) throw new Error('No weather data');
  return { windspeed: parseFloat(cw.windspeed), winddirection: parseFloat(cw.winddirection) };
}
