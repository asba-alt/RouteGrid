import { useState } from "react";
import { ErrorState } from "../components/ui";
import { api } from "../lib/api";

export default function LoginPage({ onSignedIn }: { onSignedIn: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const data = new FormData(event.currentTarget);
    const username = String(data.get("username") ?? "").trim();
    const password = String(data.get("password") ?? "");

    setBusy(true);
    setError(null);
    try {
      await api.login(username, password);
      onSignedIn();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-screen place-items-center bg-slate-950 p-6">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center justify-center gap-2.5">
          <span className="grid h-9 w-9 place-items-center rounded-lg bg-indigo-600 text-xs font-bold text-white">
            RG
          </span>
          <span className="text-lg font-semibold tracking-tight text-slate-100">
            RouteGrid
          </span>
        </div>

        <form
          onSubmit={submit}
          className="rounded-xl border border-panel-line bg-panel-soft/70 p-6 shadow-xl"
        >
          <h1 className="text-sm font-semibold text-slate-200">Operator sign in</h1>
          <p className="mt-1 text-xs text-slate-500">
            Dispatch operations console. Your session is kept in an HttpOnly cookie.
          </p>

          <label className="mt-5 block">
            <span className="label">Username</span>
            <input
              name="username"
              className="input mt-1"
              autoComplete="username"
              defaultValue="operator"
              required
            />
          </label>

          <label className="mt-3 block">
            <span className="label">Password</span>
            <input
              name="password"
              className="input mt-1"
              type="password"
              autoComplete="current-password"
              required
            />
          </label>

          <button className="btn btn-primary mt-5 w-full" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>

          {error !== null && (
            <div className="mt-4">
              <ErrorState error={error} />
            </div>
          )}
        </form>
      </div>
    </div>
  );
}
