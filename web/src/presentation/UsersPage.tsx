"use client";

import { useEffect } from "react";
import { useAuthStore } from "@/domain/authStore";
import { useUserStore } from "@/domain/userStore";
import UserForm from "./UserForm";
import UserTable from "./UserTable";

/** Admins manage accounts and roles here. */
export default function UsersPage() {
  const admin = useAuthStore((s) => s.account?.admin);
  const { notice, load } = useUserStore();

  useEffect(() => {
    if (admin) load();
  }, [admin, load]);

  if (!admin) {
    return (
      <div className="page">
        <header className="page-header">
          <h1>Users</h1>
        </header>
        <div className="page-body">
          <p className="muted">Only admins can manage users.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <header className="page-header">
        <h1>Users</h1>
      </header>
      <div className="page-body">
        <UserForm />
        {notice && <p className={notice.error ? "error" : "success"}>{notice.text}</p>}
        <UserTable />
      </div>
    </div>
  );
}
