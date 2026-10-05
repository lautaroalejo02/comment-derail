export type CurrencyCode = "USD" | "EUR" | "JPY";

export interface LineItemInput {
  sku: string;
  description: string;
  quantity: number;
  unitPrice: number;
}

export interface Order {
  id: string;
  currency: CurrencyCode;
  items: LineItemInput[];
  discountRate: number;
  taxRate: number;
}

export type LineKind = "item" | "adjustment";

export interface InvoiceLine {
  kind: LineKind;
  sku: string;
  description: string;
  quantity: number;
  unitPrice: number;
  gross: number;
  discount: number;
  tax: number;
  total: number;
}

export interface Invoice {
  orderId: string;
  currency: CurrencyCode;
  lines: InvoiceLine[];
  subtotal: number;
  discountTotal: number;
  taxTotal: number;
  total: number;
}
