import type { CurrencyCode } from "./types.ts";

export interface CurrencyInfo {
  symbol: string;
  minorUnits: number;
}

export const CURRENCIES: Record<CurrencyCode, CurrencyInfo> = {
  USD: { symbol: "$", minorUnits: 2 },
  EUR: { symbol: "€", minorUnits: 2 },
  // JPY has no minor unit: amounts are whole yen and rounding is half-up per our Japanese entity's accounting policy (Finance ticket FIN-88)
  JPY: { symbol: "¥", minorUnits: 0 },
};

function minorFactor(currency: CurrencyCode): number {
  return 10 ** CURRENCIES[currency].minorUnits;
}

export function roundMoney(amount: number, currency: CurrencyCode = "USD"): number {
  return fromMinor(toMinor(amount, currency), currency);
}

// Converts a decimal amount to an integer count of minor units (cents), rounding half-up.
export function toMinor(amount: number, currency: CurrencyCode): number {
  // Round to 6 decimals first so float noise (e.g. 1.005 * 100 = 100.49999...) doesn't flip a half-up tie.
  const scaled = Math.round(amount * minorFactor(currency) * 1e6) / 1e6;
  return Math.round(scaled);
}

export function fromMinor(minor: number, currency: CurrencyCode): number {
  return minor / minorFactor(currency);
}

const RATE_SCALE = 1_000_000_000n;

// Applies a decimal rate (e.g. 0.0825) to an integer minor-unit amount using exact
// integer arithmetic, rounding half-up to the nearest minor unit.
export function applyRate(minor: number, rate: number): number {
  const numerator = BigInt(minor) * BigInt(Math.round(rate * Number(RATE_SCALE)));
  let quotient = numerator / RATE_SCALE;
  let remainder = numerator % RATE_SCALE;
  if (remainder < 0n) {
    remainder += RATE_SCALE;
    quotient -= 1n;
  }
  if (remainder * 2n >= RATE_SCALE) {
    quotient += 1n;
  }
  return Number(quotient);
}

export function formatMoney(amount: number, currency: CurrencyCode): string {
  const info = CURRENCIES[currency];
  const sign = amount < 0 ? "-" : "";
  return `${sign}${info.symbol}${Math.abs(amount).toFixed(info.minorUnits)}`;
}
