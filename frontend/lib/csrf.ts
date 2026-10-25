export function csrfToken(): string {
  if (typeof document === 'undefined') return '';
  const prefix = 'artha_csrf=';
  const item = document.cookie.split('; ').find((value) => value.startsWith(prefix));
  return item ? decodeURIComponent(item.slice(prefix.length)) : '';
}

export function csrfHeaders(): Record<string, string> {
  const token = csrfToken();
  return token ? { 'X-CSRF-Token': token } : {};
}
