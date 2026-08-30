import { Suspense } from "react";

import { DiagnoseForm } from "./diagnose-form";

export default function DiagnosePage() {
  return (
    <Suspense fallback={<main className="page">诊断</main>}>
      <DiagnoseForm />
    </Suspense>
  );
}
