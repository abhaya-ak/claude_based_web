/**
 * Formatting utilities for currency, dates, indicators, and reference numbers.
 */

export function formatCurrency(amount: string | number, currency = 'MYR'): string {
  const numeric = typeof amount === 'string' ? parseFloat(amount) : amount;
  if (isNaN(numeric)) return `${currency} 0.00`;

  return new Intl.NumberFormat('en-MY', {
    style: 'currency',
    currency: currency || 'MYR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(numeric);
}

export function formatDate(dateString: string): string {
  if (!dateString) return '—';
  try {
    const d = new Date(dateString);
    return new Intl.DateTimeFormat('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    }).format(d);
  } catch {
    return dateString;
  }
}

export function formatDateTime(dateString: string): string {
  if (!dateString) return '—';
  try {
    const d = new Date(dateString);
    return new Intl.DateTimeFormat('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(d);
  } catch {
    return dateString;
  }
}

export function maskBankAccount(account: string): string {
  if (!account || account.length <= 4) return '****';
  const lastFour = account.slice(-4);
  return `****${lastFour}`;
}

export function formatReferenceCode(code: string): string {
  if (!code) return '';
  return code.toUpperCase().trim();
}
