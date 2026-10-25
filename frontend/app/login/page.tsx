'use client';

import { type FormEvent, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { LockKeyhole, ShieldCheck } from 'lucide-react';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [totpCode, setTotpCode] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError('');
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ email: email.trim(), password, ...(totpCode ? { totp_code: totpCode } : {}) }),
      });
      if (!response.ok) {
        const result = await response.json().catch(() => null) as { error?: string } | null;
        throw new Error(result?.error ?? 'Sign-in failed');
      }
      router.replace('/');
    } catch (reason) {
      setPassword(''); setTotpCode('');
      setError(reason instanceof Error ? reason.message : 'Sign-in failed');
    } finally { setBusy(false); }
  }

  return <main className="mx-auto flex min-h-[75vh] max-w-5xl items-center justify-center px-4 py-12">
    <section className="w-full max-w-md rounded-2xl border border-white/10 bg-slate-900/80 p-8 shadow-2xl backdrop-blur-xl">
      <div className="mb-7 flex items-center gap-3"><span className="rounded-xl border border-cyan-300/20 bg-cyan-400/10 p-3 text-cyan-200"><ShieldCheck size={24} /></span><div><p className="font-semibold text-slate-50">Research workspace</p><p className="font-mono text-[10px] uppercase tracking-[0.14em] text-cyan-200">Secure sign-in</p></div></div>
      <h1 className="text-xl font-semibold text-white">Sign in to research tools</h1>
      <p className="mt-2 text-sm leading-6 text-slate-400">Saved research runs, evidence uploads and assistant actions require an authorized account.</p>
      <form onSubmit={submit} className="mt-6 space-y-4">
        <label className="block text-sm text-slate-300">Email<input required type="email" autoComplete="username" maxLength={320} value={email} onChange={(event) => setEmail(event.target.value)} className="mt-2 w-full rounded-lg border border-white/15 bg-slate-950/70 px-3 py-2.5 text-white outline-none focus:border-cyan-300/60" /></label>
        <label className="block text-sm text-slate-300">Password<input required type="password" autoComplete="current-password" minLength={8} maxLength={1024} value={password} onChange={(event) => setPassword(event.target.value)} className="mt-2 w-full rounded-lg border border-white/15 bg-slate-950/70 px-3 py-2.5 text-white outline-none focus:border-cyan-300/60" /></label>
        <label className="block text-sm text-slate-300">Authenticator code <span className="text-slate-500">(required in production)</span><input inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} value={totpCode} onChange={(event) => setTotpCode(event.target.value.replace(/\D/g, '').slice(0, 6))} className="mt-2 w-full rounded-lg border border-white/15 bg-slate-950/70 px-3 py-2.5 font-mono tracking-[0.35em] text-white outline-none focus:border-cyan-300/60" /></label>
        {error && <p role="alert" className="rounded-lg border border-rose-400/30 bg-rose-400/10 p-3 text-sm text-rose-200">{error}</p>}
        <button disabled={busy} type="submit" className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-cyan-300 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200 disabled:opacity-60"><LockKeyhole size={16} />{busy ? 'Signing in…' : 'Sign in securely'}</button>
      </form>
      <p className="mt-6 border-t border-white/10 pt-4 text-xs leading-relaxed text-slate-500">Session tokens are stored in HttpOnly cookies and are never returned to browser JavaScript. <Link href="/" className="ml-1 text-cyan-200 hover:underline">Return to the public dashboard</Link></p>
    </section>
  </main>;
}
