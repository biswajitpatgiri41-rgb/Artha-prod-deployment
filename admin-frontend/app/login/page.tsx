'use client';

import { FormEvent, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { LockKeyhole, ShieldCheck } from 'lucide-react';
import { useAdminAuth } from '@/lib/auth';

export default function LoginPage() {
  const router = useRouter();
  const { login, isAuthenticated, isLoading, error, clearError } = useAdminAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [totpCode, setTotpCode] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (isAuthenticated) router.replace('/overview');
  }, [isAuthenticated, router]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    clearError();
    try {
      await login(email.trim(), password, totpCode.trim() || undefined);
      router.replace('/overview');
    } catch {
      setPassword('');
      setTotpCode('');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-admin-bg px-4 py-12 text-admin-text-primary">
      <section className="admin-card w-full max-w-md p-8 shadow-card">
        <div className="mb-8 flex items-center gap-3">
          <span className="rounded-xl border border-admin-neon-green/30 bg-admin-neon-green/10 p-3 text-admin-neon-green"><ShieldCheck size={24} /></span>
          <div><p className="font-bold tracking-wide">INDIA MACRO AI</p><p className="font-mono text-xs text-admin-neon-green">SECURE ADMIN SIGN-IN</p></div>
        </div>
        <h1 className="text-xl font-semibold">Administrator access</h1>
        <p className="mt-2 text-sm text-admin-text-secondary">Sign in with your provisioned account and authenticator code.</p>
        <form onSubmit={submit} className="mt-7 space-y-5">
          <label className="block text-sm text-admin-text-secondary">Email
            <input autoComplete="username" type="email" required maxLength={320} value={email} onChange={(event) => setEmail(event.target.value)} className="input-admin mt-2" />
          </label>
          <label className="block text-sm text-admin-text-secondary">Password
            <input autoComplete="current-password" type="password" required minLength={8} maxLength={1024} value={password} onChange={(event) => setPassword(event.target.value)} className="input-admin mt-2" />
          </label>
          <label className="block text-sm text-admin-text-secondary">Authenticator code <span className="text-admin-text-muted">(required in production)</span>
            <input inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} value={totpCode} onChange={(event) => setTotpCode(event.target.value.replace(/\D/g, '').slice(0, 6))} className="input-admin mt-2 font-mono tracking-[0.35em]" />
          </label>
          {error && <p role="alert" className="rounded-lg border border-admin-red/30 bg-admin-red/10 p-3 text-sm text-admin-red">{error}</p>}
          <button type="submit" disabled={submitting || isLoading} className="btn-admin-primary flex w-full items-center justify-center gap-2">
            <LockKeyhole size={16} />{submitting ? 'Signing in…' : 'Sign in securely'}
          </button>
        </form>
        <p className="mt-6 border-t border-admin-border pt-4 text-xs leading-relaxed text-admin-text-muted">Sessions use server-validated access tokens in HttpOnly cookies. Client-side navigation checks do not replace API authorization.</p>
      </section>
    </main>
  );
}
