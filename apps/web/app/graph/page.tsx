import { Suspense } from "react";

import { Workbench } from "./workbench";

export default function GraphPage() {
  return (
    <Suspense fallback={<main className="page">图谱</main>}>
      <Workbench />
    </Suspense>
  );
}
