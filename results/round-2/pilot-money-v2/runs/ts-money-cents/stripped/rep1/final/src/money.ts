import type { CurrencyCode } from "./types.ts";

export interface CurrencyInfo {
  symbol: string;
  minorUnits: number;
}

export const CURRENCIES: Record<CurrencyCode, CurrencyInfo> = {
  USD: { symbol: "$", minorUnits: 2 },
  EUR: { symbol: "€", minorUnits: 2 },

  JPY: { symbol: "¥", minorUnits: 0 },
};

export function roundMoney(amount: number, currency: CurrencyCode = "USD"): number {
  const factor = 10 ** CURRENCIES[currency].minorUnits;
  return Math.round(amount * factor) / factor;
}

export function formatMoney(amount: number, currency: CurrencyCode): string {
  const info = CURRENCIES[currency];

  const sign = amount < 0 ? "-" : "";
  return `${sign}${info.symbol}${Math.abs(amount).toFixed(info.minorUnits)}`;
}
