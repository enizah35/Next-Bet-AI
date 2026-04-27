"use client";
import { redirect } from "next/navigation";
import { useEffect } from "react";

export default function RegisterPage() {
  useEffect(() => { redirect("/login?tab=register"); }, []);
  return null;
}
