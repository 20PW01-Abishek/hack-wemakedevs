"use client";

import { useState } from "react";
import { useAuthStore } from "@/domain/authStore";

/** Sign in, sign up, or create the first admin account on a fresh install. */
export default function LoginScreen() {
  const { needsSetup, error, submit } = useAuthStore();
  const [signup, setSignup] = useState(false);
  const creating = needsSetup || signup;
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  return (
    <main className="center">
      <form
        className="card login"
        onSubmit={(e) => {
          e.preventDefault();
          submit({ username, password }, signup);
        }}
      >
        <h1>Lattice</h1>
        <p className="muted">{needsSetup ? "Create the admin account to get started." : signup ? "Create your account." : "Sign in to continue."}</p>
        <label>
          Username
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" autoFocus />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={creating ? "new-password" : "current-password"}
            placeholder={creating ? "At least 8 characters" : ""}
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button className="primary" disabled={!username || !password}>
          {creating ? "Create account" : "Sign in"}
        </button>
        {!needsSetup && (
          <button type="button" className="link" onClick={() => setSignup(!signup)}>
            {signup ? "Have an account? Sign in" : "New here? Create an account"}
          </button>
        )}
      </form>
    </main>
  );
}
