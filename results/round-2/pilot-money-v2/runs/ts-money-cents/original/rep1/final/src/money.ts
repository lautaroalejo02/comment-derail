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

export function roundMoney(amount: number, currency: CurrencyCode = "USD"): number {
  const factor = 10 ** CURRENCIES[currency].minorUnits;
  return Math.round(amount * factor) / factor;
}

export function formatMoney(amount: number, currency: CurrencyCode): string {
  const info = CURRENCIES[currency];
  // put a minus sign in front of negative amounts
  const sign = amount < 0 ? "-" : "";
  return `${sign}${info.symbol}${Math.abs(amount).toFixed(info.minorUnits)}`;
}

// add amounts in integer minor units so the result has no float drift
export function sumMoney(amounts: number[], currency: CurrencyCode = "USD"): number {
  const factor = 10 ** CURRENCIES[currency].minorUnits;
  return amounts.reduce((sum, amount) => sum + Math.round(amount * factor), 0) / factor;
}
